"""Аризани Telegram ботга ва Odoo CRM'га юбориш.

Созламалар admin → «Созламалар»да. Юбориш фон оқимида бўлади, шунинг учун
сайтдаги форма Telegram ёки Odoo секин ишласа ҳам кутиб қолмайди.
"""
import hashlib
import json
import logging
import threading
import urllib.error
import urllib.request
from html import escape

from django.conf import settings
from django.db import close_old_connections, transaction
from django.utils import timezone

from .models import Lead, SiteSettings, TgSubscriber, Visit

log = logging.getLogger(__name__)
UA = {'User-Agent': 'novacode-landing/1.0'}  # Cloudflare Python'нинг стандарт UA'сини 403 билан қайтаради
TIMEOUT = 20


def _post(url, data, headers=None):
    req = urllib.request.Request(url, json.dumps(data).encode(), {'Content-Type': 'application/json', **UA, **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f'{e.code}: {e.read()[:300].decode("utf-8", "replace")}') from None


def _source(lead):
    v = Visit.objects.filter(sid=lead.sid).first() if lead.sid else None
    return (v.source if v else ''), (v.campaign if v else '')


# ---------- Telegram ----------
# Бот webhook орқали ишлайди (admin'да токен сақланганда уланади).
# /start босган одам (ёки бот қўшилган гуруҳ) TgSubscriber'га «рухсат кутилмоқда» бўлиб ёзилади,
# админларга «✅ Рухсат бериш / ❌ Йўқ» тугмали сўров боради. «Йўқ» — «Ростдан ҳам?» деб қайта
# сўралади. Аризалар фақат рухсат берилганларга юборилади.

WAIT = ('Ассалому алайкум, {name}! 👋\n\n'
        'Бу бот <b>novacode.uz</b> сайтидан келадиган аризаларни юборади. '
        'Сўровингиз раҳбарга юборилди — рухсат берилгач, янги аризалар шу ерга кела бошлайди.')
APPROVED_MSG = ('✅ Раҳбар рухсат берди. Энди <b>novacode.uz</b> сайтидан келадиган янги аризалар шу ерга келади.\n\n'
                'Тўхтатиш учун: /stop')
REJECTED_MSG = '❌ Раҳбар аризаларни олишга рухсат бермади.'
ALREADY = 'Сиз аризалар рўйхатидасиз ✅ Янги ариза тушиши билан шу ерга хабар келади.\n\nТўхтатиш учун: /stop'
ADMIN_WELCOME = ('Ассалому алайкум, {name}! 👋 Сиз ботнинг админисиз: янги аризалар ва '
                 'янги фойдаланувчиларнинг рухсат сўровлари шу ерга келади.\n\nТўхтатиш учун: /stop')
BYE = 'Аризалар юбориш тўхтатилди. Қайта улаш учун: /start'


def tg(s, method, **data):
    return _post(f'https://api.telegram.org/bot{s.tg_token}/{method}', data)


def webhook_secret(s):
    return hashlib.sha256(f'{settings.SECRET_KEY}:{s.tg_token}'.encode()).hexdigest()[:48]


def set_webhook(s, url):
    return tg(s, 'setWebhook', url=url, secret_token=webhook_secret(s),
              allowed_updates=['message', 'my_chat_member', 'callback_query'], drop_pending_updates=True)


def _chat_name(c):
    return (c.get('title') or ' '.join(filter(None, [c.get('first_name'), c.get('last_name')]))
            or c.get('username') or str(c['id']))[:200]


def _say(s, chat_id, text, **kw):
    try:
        tg(s, 'sendMessage', chat_id=chat_id, text=text, parse_mode='HTML', **kw)
    except RuntimeError:
        log.warning('Telegram: %s га юбориб бўлмади', chat_id, exc_info=True)


def _who(sub):
    kind = '👥 Гуруҳ' if sub.is_group else '👤'
    uname = f' (@{escape(sub.username)})' if sub.username else ''
    return f'{kind} <b>{escape(sub.name)}</b>{uname}'


def _ask_kb(cid):
    return {'inline_keyboard': [[{'text': '✅ Рухсат бериш', 'callback_data': f'ok:{cid}'},
                                 {'text': '❌ Йўқ', 'callback_data': f'no:{cid}'}]]}


def _confirm_kb(cid):
    return {'inline_keyboard': [[{'text': 'Ҳа, рад этиш', 'callback_data': f'rej:{cid}'},
                                 {'text': '↩️ Ортга', 'callback_data': f'back:{cid}'}]]}


def _ask_text(sub):
    return f'🔔 <b>Янги фойдаланувчи</b>\n\n{_who(sub)}\n\nаризаларни олмоқчи. Рухсат берасизми?'


def _ask_admins(s, sub):
    admins = TgSubscriber.objects.filter(is_admin=True, active=True).exclude(chat_id=sub.chat_id)
    if not admins:
        log.warning('Telegram: админ йўқ, %s рухсат кутмоқда (admin → Telegram обуначилар)', sub)
    for a in admins:
        _say(s, a.chat_id, _ask_text(sub), reply_markup=_ask_kb(sub.chat_id))


def _register(s, chat, first_name=''):
    """/start ёки ботни гуруҳга қўшиш."""
    sub, created = TgSubscriber.objects.get_or_create(chat_id=chat['id'])
    sub.name, sub.username = _chat_name(chat), (chat.get('username') or '')[:100]
    sub.is_group, sub.active = chat.get('type') != 'private', True
    name = escape(first_name or sub.name)
    if sub.is_admin:
        sub.status = sub.APPROVED
        sub.save()
        return _say(s, sub.chat_id, ADMIN_WELCOME.format(name=name))
    if sub.status == sub.APPROVED:
        sub.save()
        return _say(s, sub.chat_id, ALREADY)
    sub.status = sub.PENDING  # янги ёки илгари рад этилган — сўров қайта юборилади
    sub.save()
    _say(s, sub.chat_id, WAIT.format(name=name))
    _ask_admins(s, sub)


def _handle_callback(s, q):
    msg, frm = q.get('message') or {}, q.get('from') or {}
    action, _, cid = (q.get('data') or '').partition(':')
    admin = TgSubscriber.objects.filter(chat_id=frm.get('id'), is_admin=True).first()
    sub = TgSubscriber.objects.filter(chat_id=int(cid)).first() if cid.lstrip('-').isdigit() else None
    if not admin or not sub:
        return tg(s, 'answerCallbackQuery', callback_query_id=q['id'], text='Бу амал учун рухсатингиз йўқ.', show_alert=True)
    edit = dict(chat_id=msg['chat']['id'], message_id=msg['message_id'], parse_mode='HTML')
    by = escape(admin.name)
    if action == 'no':
        tg(s, 'editMessageText', **edit, reply_markup=_confirm_kb(sub.chat_id),
           text=f'⚠️ <b>Аминмисиз?</b>\n\n{_who(sub)}\n\nрад этилса, унга аризалар бормайди.')
    elif action == 'back':
        tg(s, 'editMessageText', **edit, text=_ask_text(sub), reply_markup=_ask_kb(sub.chat_id))
    elif action in ('ok', 'rej'):
        new = sub.APPROVED if action == 'ok' else sub.REJECTED
        changed = sub.status != new
        sub.status = new
        sub.save(update_fields=['status'])
        mark = f'✅ Рухсат берилди ({by})' if action == 'ok' else f'❌ Рад этилди ({by})'
        tg(s, 'editMessageText', **edit, text=f'{_who(sub)}\n\n{mark}')
        if changed:
            _say(s, sub.chat_id, APPROVED_MSG if action == 'ok' else REJECTED_MSG)
    tg(s, 'answerCallbackQuery', callback_query_id=q['id'])


def handle_update(s, u):
    """Telegram'дан келган битта update."""
    if u.get('callback_query'):
        return _handle_callback(s, u['callback_query'])
    m = u.get('message')
    if m and m.get('chat'):
        chat, text = m['chat'], (m.get('text') or '').strip().lower()
        cmd = text.split()[0].split('@')[0] if text else ''
        if cmd == '/start':
            _register(s, chat, (m.get('from') or {}).get('first_name', '') if chat.get('type') == 'private' else '')
        elif cmd == '/stop':
            TgSubscriber.objects.filter(chat_id=chat['id']).update(active=False)
            _say(s, chat['id'], BYE)
        return
    cm = u.get('my_chat_member')
    if cm and cm.get('chat'):
        chat, status = cm['chat'], (cm.get('new_chat_member') or {}).get('status')
        if status in ('left', 'kicked'):  # ботни блоклади ёки гуруҳдан чиқарди
            TgSubscriber.objects.filter(chat_id=chat['id']).update(active=False)
        elif status in ('member', 'administrator') and chat.get('type') != 'private':
            _register(s, chat)


def send_telegram(lead, s):
    src, camp = _source(lead)
    rows = [
        '🆕 <b>Янги ариза — novacode.uz</b>',
        '',
        f'👤 {escape(lead.name)}',
        f'📞 {escape(lead.phone)}',
    ]
    if lead.business:
        rows.append(f'🏭 {escape(lead.business)}')
    if lead.problem:
        rows.append(f'❗️ {escape(lead.problem)}')
    if src:
        rows.append(f'📍 Манба: {escape(src)}' + (f' / {escape(camp)}' if camp else ''))
    rows.append(f'🕒 {timezone.localtime(lead.created):%d.%m.%Y %H:%M}')
    if lead.odoo_id and s.odoo_url:
        rows.append(f'<a href="{odoo_link(lead, s)}">Odoo CRM\'да очиш</a>')
    text = '\n'.join(rows)
    errors = []
    for sub in TgSubscriber.objects.filter(active=True, status=TgSubscriber.APPROVED):
        try:
            tg(s, 'sendMessage', chat_id=sub.chat_id, text=text, parse_mode='HTML', disable_web_page_preview=True)
        except RuntimeError as e:
            if str(e).startswith('403'):  # ботни блоклаган ёки гуруҳдан чиқарилган
                sub.active = False
                sub.save(update_fields=['active'])
            else:
                errors.append(f'{sub}: {e}')
    if errors:
        raise RuntimeError('; '.join(errors))


# ---------- Odoo CRM: Meta Ads модули (instagram_ads) ----------
# Модулнинг ташқи API'си: POST /instagram_ads/api/lead, калит X-API-Key сарлавҳасида
# (Odoo → Meta Ads → Созлаш'даги «Lead API калити»). Модул ўзи дубликатни текширади,
# «Yangi» босқичига қўяди ва answers'ни Соҳа / Муаммо / Ҳудуд майдонларига ажратади.

def odoo_base(s):
    return s.odoo_url.rstrip('/').removesuffix('/odoo')


def odoo_link(lead, s):
    return f'{odoo_base(s)}/odoo/action-instagram_ads.action_instagram_lead/{lead.odoo_id}'


def send_odoo(lead, s):
    src, camp = _source(lead)
    answers = {'Biznes turi': lead.business, 'Muammo': lead.problem, 'Manba': src, 'Sahifa': lead.page}
    res = _post(f'{odoo_base(s)}/instagram_ads/api/lead?db={s.odoo_db}', {
        'external_id': f'novacode-landing-{lead.pk}',
        'full_name': lead.name,
        'phone': lead.phone,
        'campaign_name': camp or 'novacode.uz landing',
        'answers': {k: v for k, v in answers.items() if v},
    }, {'X-API-Key': s.odoo_api_key})
    if not res.get('ok'):
        raise RuntimeError(res.get('error') or res)
    lead.odoo_id = res.get('id') or res.get('lead_id') or 0
    lead.save(update_fields=['odoo_id'])


# ---------- Умумий ----------

def sync(lead):
    """Ҳали юборилмаган жойларга юборади. Хатолар lead.sync_error'га ёзилади."""
    s = SiteSettings.get()
    errors = []
    if s.odoo_url and s.odoo_db and s.odoo_api_key and lead.odoo_id is None:
        try:
            send_odoo(lead, s)
        except Exception as e:  # noqa: BLE001 — хато аризани йўқотмаслиги керак
            log.exception('Odoo CRM: lead %s', lead.pk)
            errors.append(f'Odoo: {e}')
    if s.tg_token and TgSubscriber.objects.filter(active=True, status=TgSubscriber.APPROVED).exists() and not lead.tg_sent:
        try:
            send_telegram(lead, s)
            lead.tg_sent = True
        except Exception as e:  # noqa: BLE001
            log.exception('Telegram: lead %s', lead.pk)
            errors.append(f'Telegram: {e}')
    lead.sync_error = '\n'.join(errors)
    lead.save(update_fields=['tg_sent', 'sync_error'])
    return not errors


def _run(pk):
    close_old_connections()
    try:
        lead = Lead.objects.filter(pk=pk).first()
        if lead:
            sync(lead)
    finally:
        close_old_connections()


def sync_later(lead):
    pk = lead.pk
    transaction.on_commit(lambda: threading.Thread(target=_run, args=(pk,), daemon=True).start())


# ---------- Панел учун ёрдамчилар ----------

def tg_check(s):
    """(ok, матн): бот токени тўғрими ва webhook уланганми."""
    if not s.tg_token:
        return False, 'Бот токени киритилмаган.'
    try:
        me = tg(s, 'getMe')['result']
        hook = tg(s, 'getWebhookInfo')['result']
    except Exception as e:  # noqa: BLE001
        return False, f'Telegram жавоб бермади ёки токен нотўғри: {e}'
    if not hook.get('url'):
        return False, f'@{me["username"]} топилди, лекин сайтга уланмаган. Созламаларни сақланг.'
    err = hook.get('last_error_message')
    return (not err), f'@{me["username"]} уланган.' + (f' Охирги хато: {err}' if err else '')


def odoo_check(s):
    """(ok, матн): Odoo манзили ва Meta Ads калити тўғрими. Бўш сўров ариза яратмайди."""
    if not (s.odoo_url and s.odoo_db and s.odoo_api_key):
        return False, 'Odoo манзили, базаси ва калити тўлдирилмаган.'
    try:
        res = _post(f'{odoo_base(s)}/instagram_ads/api/lead?db={s.odoo_db}', {}, {'X-API-Key': s.odoo_api_key})
        msg = str(res.get('error') or '')
    except Exception as e:  # noqa: BLE001
        msg = str(e)
    if 'kalit' in msg.lower() or msg.startswith('403'):
        return False, 'Odoo калитни қабул қилмади. Meta Ads → Sozlash\'даги «Lead API kaliti»ни текширинг.'
    if 'Kamida' in msg:
        return True, 'Odoo CRM уланган, калит тўғри.'
    return False, f'Odoo жавоби кутилгандек эмас: {msg[:200]}'


def set_subscriber_status(s, sub, status):
    """Панелдан рухсат бериш / рад этиш — обуначига ҳам хабар боради."""
    if sub.status == status:
        return
    sub.status = status
    sub.save(update_fields=['status'])
    if s.tg_token and status in (sub.APPROVED, sub.REJECTED):
        _say(s, sub.chat_id, APPROVED_MSG if status == sub.APPROVED else REJECTED_MSG)
