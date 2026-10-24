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
# Бот webhook орқали ишлайди: /start босган одам (ёки бот қўшилган гуруҳ) TgSubscriber'га
# ёзилади ва янги аризалар ҳаммасига юборилади. Webhook admin'да токен сақланганда уланади.

WELCOME = ('Ассалому алайкум, {name}! 👋\n\n'
           'Сиз <b>novacode.uz</b> сайтидан келадиган аризалар рўйхатига қўшилдингиз. '
           'Янги ариза тушиши билан шу ерга хабар келади.\n\nТўхтатиш учун: /stop')
GROUP_WELCOME = 'Ассалому алайкум! 👋 Энди <b>novacode.uz</b> сайтидан келадиган аризалар шу гуруҳга юборилади.'
BYE = 'Аризалар юбориш тўхтатилди. Қайта улаш учун: /start'


def tg(s, method, **data):
    return _post(f'https://api.telegram.org/bot{s.tg_token}/{method}', data)


def webhook_secret(s):
    return hashlib.sha256(f'{settings.SECRET_KEY}:{s.tg_token}'.encode()).hexdigest()[:48]


def set_webhook(s, url):
    return tg(s, 'setWebhook', url=url, secret_token=webhook_secret(s),
              allowed_updates=['message', 'my_chat_member'], drop_pending_updates=True)


def _chat_name(c):
    return (c.get('title') or ' '.join(filter(None, [c.get('first_name'), c.get('last_name')]))
            or c.get('username') or str(c['id']))[:200]


def _subscribe(s, chat, greet):
    sub, _ = TgSubscriber.objects.update_or_create(chat_id=chat['id'], defaults=dict(
        name=_chat_name(chat), username=(chat.get('username') or '')[:100],
        is_group=chat.get('type') != 'private', active=True))
    tg(s, 'sendMessage', chat_id=chat['id'], parse_mode='HTML', text=greet)
    return sub


def handle_update(s, u):
    """Telegram'дан келган битта update."""
    m = u.get('message')
    if m and m.get('chat'):
        chat, text = m['chat'], (m.get('text') or '').strip().lower()
        cmd = text.split()[0].split('@')[0] if text else ''
        if cmd == '/start':
            if chat.get('type') == 'private':
                _subscribe(s, chat, WELCOME.format(name=escape(m.get('from', {}).get('first_name') or '')))
            else:
                _subscribe(s, chat, GROUP_WELCOME)
        elif cmd == '/stop':
            TgSubscriber.objects.filter(chat_id=chat['id']).update(active=False)
            tg(s, 'sendMessage', chat_id=chat['id'], text=BYE)
        return
    cm = u.get('my_chat_member')
    if cm and cm.get('chat'):
        chat, status = cm['chat'], (cm.get('new_chat_member') or {}).get('status')
        if status in ('left', 'kicked'):  # ботни блоклади ёки гуруҳдан чиқарди
            TgSubscriber.objects.filter(chat_id=chat['id']).update(active=False)
        elif status in ('member', 'administrator') and chat.get('type') != 'private':
            _subscribe(s, chat, GROUP_WELCOME)


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
    for sub in TgSubscriber.objects.filter(active=True):
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
    if s.tg_token and TgSubscriber.objects.filter(active=True).exists() and not lead.tg_sent:
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
