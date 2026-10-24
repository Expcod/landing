"""Аризани Telegram ботга ва Odoo CRM'га юбориш.

Созламалар admin → «Созламалар»да. Юбориш фон оқимида бўлади, шунинг учун
сайтдаги форма Telegram ёки Odoo секин ишласа ҳам кутиб қолмайди.
"""
import json
import logging
import threading
import urllib.error
import urllib.request
from html import escape

from django.db import close_old_connections, transaction
from django.utils import timezone

from .models import Lead, SiteSettings, Visit

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

def chat_ids(s):
    return [c.strip() for c in s.tg_chat_ids.replace(';', ',').split(',') if c.strip()]


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
    for chat in chat_ids(s):
        _post(f'https://api.telegram.org/bot{s.tg_token}/sendMessage',
              {'chat_id': chat, 'text': text, 'parse_mode': 'HTML', 'disable_web_page_preview': True})


def bot_chats(token):
    """Ботга ёзган / уни қўшган чатлар — admin'да чат ID топиш учун."""
    req = urllib.request.Request(f'https://api.telegram.org/bot{token}/getUpdates', headers=UA)
    with urllib.request.urlopen(req, timeout=10) as r:
        data = json.load(r)
    chats = {}
    for u in data.get('result', []):
        for k in ('message', 'channel_post', 'my_chat_member', 'edited_message'):
            c = (u.get(k) or {}).get('chat')
            if c:
                chats[c['id']] = c.get('title') or ' '.join(filter(None, [c.get('first_name'), c.get('last_name')])) or c.get('username', '')
    return chats


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
    if s.tg_token and chat_ids(s) and not lead.tg_sent:
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
