import json
import re
from datetime import timedelta

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.decorators.cache import cache_control

from .models import Case, Client, Event, Lead, OdooStage, Reel, Screen, SiteSettings, Visit
from . import notify
from .notify import sync_later


def url(f):
    return f.url if f else ''


@cache_control(public=True, max_age=60)
def content(request):
    cases = Case.objects.filter(active=True)
    return JsonResponse({
        'pixel_id': SiteSettings.get().pixel_id,
        'clients': [{'name': c.name, 'logo': url(c.logo)} for c in Client.objects.filter(active=True)],
        'results': [{'num': c.num, 'who': c.who, 'what': c.short, 'logo': url(c.logo)} for c in cases if c.in_hero],
        'cases': [{
            'who': c.who, 'what': c.industry, 'num': c.num, 'line': c.line,
            'bLabel': c.before_label, 'bW': c.before_pct, 'aLabel': c.after_label, 'aW': c.after_pct,
        } for c in cases],
        'screens': [{
            'tag': s.tag, 'title': s.title, 'src': url(s.image), 'max': s.max_width,
            'points': [p.strip() for p in s.points.splitlines() if p.strip()],
        } for s in Screen.objects.filter(active=True)],
        'reels': [{
            'src': url(r.video) or r.video_url, 'poster': url(r.poster) or r.poster_url,
            'url': r.instagram_url, 'cap': r.caption,
        } for r in Reel.objects.filter(active=True)],
    }, json_dumps_params={'ensure_ascii': False})


@csrf_exempt
@require_POST
def lead(request):
    try:
        d = json.loads(request.body or b'{}')
    except ValueError:
        return JsonResponse({'ok': False}, status=400)
    name = str(d.get('name', '')).strip()[:150]
    phone = str(d.get('phone', '')).strip()[:40]
    if not name or len(re.sub(r'\D', '', phone)) < 9:
        return JsonResponse({'ok': False}, status=400)
    ip = (request.META.get('HTTP_X_FORWARDED_FOR') or request.META.get('REMOTE_ADDR') or '').split(',')[0].strip() or None
    # Спамдан ҳимоя: битта IP'дан соатига 10 тадан ортиқ ариза қабул қилинмайди
    if ip and Lead.objects.filter(ip=ip, created__gte=timezone.now() - timedelta(hours=1)).count() >= 10:
        return JsonResponse({'ok': False}, status=429)
    sid = str(d.get('sid', ''))[:40]
    obj = Lead.objects.create(
        name=name, phone=phone, ip=ip,
        business=str(d.get('business', ''))[:200], problem=str(d.get('problem', ''))[:5000],
        page=str(d.get('page', ''))[:500], sid=sid if re.fullmatch(r'[\w-]{8,40}', sid) else '',
        stage=OdooStage.objects.filter(active=True).first(),
    )
    sync_later(obj)  # Telegram бот ва Odoo CRM'га — фонда
    return JsonResponse({'ok': True})


SECTIONS = ['top', 'how', 'camera', 'screens', 'cases', 'reels', 'audit', 'contact']
EVENTS = {'video_start', 'video_50', 'video_complete', 'video_unmute', 'video_swipe', 'form_view', 'form_start',
          'lead_sent', 'click_phone', 'click_telegram', 'click_instagram', 'click_cta'}
BOT = re.compile(r'bot|crawl|spider|slurp|preview|headless|lighthouse|facebookexternalhit', re.I)


def _source(d):
    src = str(d.get('utm_source') or '').strip().lower()
    if src:
        return src[:100]
    ref = str(d.get('referrer') or '')
    m = re.match(r'https?://([^/]+)', ref)
    if not m or 'novacode.uz' in m.group(1):
        return 'тўғридан-тўғри'
    host = m.group(1).lower().removeprefix('www.').removeprefix('m.').removeprefix('l.').removeprefix('lm.')
    for k in ('instagram', 'facebook', 'google', 'yandex', 't.me', 'telegram', 'youtube'):
        if k in host:
            return 'telegram' if k == 't.me' else k
    return host[:100]


@csrf_exempt
@require_POST
def track(request):
    """sendBeacon орқали келади: {sid, vid, t: 'start'|'ping'|'event', ...}"""
    try:
        d = json.loads(request.body or b'{}')
    except ValueError:
        return JsonResponse({'ok': False}, status=400)
    ua = request.META.get('HTTP_USER_AGENT', '')
    sid, vid = str(d.get('sid', ''))[:40], str(d.get('vid', ''))[:40]
    if not re.fullmatch(r'[\w-]{8,40}', sid) or not re.fullmatch(r'[\w-]{8,40}', vid) or BOT.search(ua):
        return JsonResponse({'ok': False}, status=400)
    t = d.get('t')
    if t == 'start':
        ip = (request.META.get('HTTP_X_FORWARDED_FOR') or request.META.get('REMOTE_ADDR') or '').split(',')[0].strip() or None
        if ip and Visit.objects.filter(ip=ip, started__gte=timezone.now() - timedelta(hours=1)).count() >= 60:
            return JsonResponse({'ok': False}, status=429)
        Visit.objects.get_or_create(sid=sid, defaults=dict(
            vid=vid, ip=ip, ua=ua[:300], referrer=str(d.get('referrer', ''))[:300], source=_source(d),
            campaign=str(d.get('utm_campaign') or '')[:150],
            device='mobile' if re.search(r'Mobi|Android|iPhone', ua) else 'desktop',
            last_section='top', max_section='top',
        ))
        return JsonResponse({'ok': True})
    v = Visit.objects.filter(sid=sid).first()
    if not v or v.started < timezone.now() - timedelta(hours=6):
        return JsonResponse({'ok': False}, status=404)
    if t == 'ping':
        v.duration = max(v.duration, min(int(d.get('dur') or 0), 6 * 3600))
        v.max_scroll = max(v.max_scroll, min(int(d.get('scroll') or 0), 100))
        sec = d.get('sec')
        if sec in SECTIONS:
            v.last_section = sec
        mx = d.get('maxsec')
        if mx in SECTIONS and SECTIONS.index(mx) > SECTIONS.index(v.max_section or 'top'):
            v.max_section = mx
        v.save()
    elif t == 'event' and d.get('name') in EVENTS:
        if v.events.count() < 200:
            Event.objects.create(visit=v, name=d['name'], label=str(d.get('label') or '')[:200])
        v.save(update_fields=['last_seen'])
    return JsonResponse({'ok': True})


@csrf_exempt
@require_POST
def tg_webhook(request):
    """Telegram бот webhook'и: /start — обуна, /stop — обунадан чиқиш."""
    s = SiteSettings.get()
    if not s.tg_token or request.headers.get('X-Telegram-Bot-Api-Secret-Token') != notify.webhook_secret(s):
        return JsonResponse({'ok': False}, status=403)
    try:
        notify.handle_update(s, json.loads(request.body or b'{}'))
    except Exception:  # noqa: BLE001 — Telegram 200 олмаса, бир хил update'ни қайта-қайта юбораверади
        notify.log.exception('Telegram webhook')
    return JsonResponse({'ok': True})
