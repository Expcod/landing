import json
import re
from datetime import timedelta

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.decorators.cache import cache_control

from .models import Case, Client, Lead, Reel, Screen, SiteSettings


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
    Lead.objects.create(
        name=name, phone=phone, ip=ip,
        business=str(d.get('business', ''))[:200], problem=str(d.get('problem', ''))[:5000],
        page=str(d.get('page', ''))[:500],
    )
    return JsonResponse({'ok': True})
