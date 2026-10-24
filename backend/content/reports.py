from datetime import timedelta

from django.contrib import admin
from django.db.models import Avg, Count, Q
from django.db.models.functions import TruncDate
from django.shortcuts import render
from django.utils import timezone

from .models import Event, Lead, Visit
from .views import SECTIONS

SECTION_NAMES = {
    'top': 'Биринчи экран', 'how': 'Қандай ишлайди', 'camera': 'Камера', 'screens': 'Экранлар',
    'cases': 'Кейслар', 'reels': 'Видеолар', 'audit': 'Ариза формаси', 'contact': 'Алоқа',
}
PERIODS = {'1': 'Бугун', '7': '7 кун', '30': '30 кун', '90': '90 кун'}


def pct(a, b):
    return round(a * 100 / b) if b else 0


def with_bars(rows, key):
    top = max([r[key] for r in rows] or [0]) or 1
    for r in rows:
        r['bar'] = round(r[key] * 100 / top)
    return rows


def reports(request):
    period = request.GET.get('d', '7')
    if period not in PERIODS:
        period = '7'
    now = timezone.localtime()
    since = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=int(period) - 1)
    visits = Visit.objects.filter(started__gte=since)
    events = Event.objects.filter(visit__started__gte=since)
    total = visits.count()

    def reached(name):
        return events.filter(name=name).values('visit').distinct().count()

    leads_db = Lead.objects.filter(created__gte=since).count()
    lead_visits = reached('lead_sent')
    agg = visits.aggregate(dur=Avg('duration'), scroll=Avg('max_scroll'))

    funnel = with_bars([
        {'name': 'Сайтга кирди', 'n': total},
        {'name': 'Видео бўлимига етди', 'n': visits.filter(max_section__in=SECTIONS[SECTIONS.index('reels'):]).count()},
        {'name': 'Видео кўришни бошлади', 'n': reached('video_start')},
        {'name': 'Ариза формасига етди', 'n': reached('form_view')},
        {'name': 'Формани тўлдира бошлади', 'n': reached('form_start')},
        {'name': 'Ариза юборди', 'n': lead_visits},
    ], 'n')
    for i, r in enumerate(funnel):
        r['pct'] = pct(r['n'], total)
        r['lost'] = funnel[i - 1]['n'] - r['n'] if i else 0

    by_last = dict(visits.values_list('last_section').annotate(c=Count('id')))
    by_max = dict(visits.values_list('max_section').annotate(c=Count('id')))
    depth, cum = [], 0
    for s in reversed(SECTIONS):
        cum += by_max.get(s, 0)
        depth.append({'name': SECTION_NAMES[s], 'reach': cum, 'reach_pct': pct(cum, total),
                      'exit': by_last.get(s, 0), 'exit_pct': pct(by_last.get(s, 0), total)})
    depth = with_bars(list(reversed(depth)), 'reach')

    buckets = [('10 сониядан кам', 0, 10), ('10–30 сония', 10, 30), ('30–60 сония', 30, 60),
               ('1–3 дақиқа', 60, 180), ('3–10 дақиқа', 180, 600), ('10 дақиқадан кўп', 600, 10 ** 9)]
    times = with_bars([{'name': n, 'n': visits.filter(duration__gte=a, duration__lt=b).count()} for n, a, b in buckets], 'n')
    for r in times:
        r['pct'] = pct(r['n'], total)

    lead_q = Q(events__name='lead_sent')

    def grouped(field, limit=15):
        rows = visits.values(field).annotate(n=Count('id', distinct=True), leads=Count('id', filter=lead_q, distinct=True)).order_by('-n')[:limit]
        rows = [{'name': r[field] or '—', 'n': r['n'], 'leads': r['leads'], 'conv': pct(r['leads'], r['n'])} for r in rows]
        return with_bars(rows, 'n')

    videos = {}
    for label, name, c in events.filter(name__startswith='video_').exclude(name='video_swipe').values_list('label', 'name').annotate(c=Count('visit', distinct=True)):
        videos.setdefault(label or '—', {'name': label or '—'})[name] = c
    videos = sorted(videos.values(), key=lambda r: -r.get('video_start', 0))
    for r in videos:
        r['done_pct'] = pct(r.get('video_complete', 0), r.get('video_start', 0))

    clicks = [{'name': n, 'n': reached(k)} for k, n in [
        ('click_cta', '«Бепул аудит» тугмаси'), ('click_phone', 'Телефон'), ('click_telegram', 'Telegram'),
        ('click_instagram', 'Instagram'), ('video_unmute', 'Видео овозини ёқди'), ('video_swipe', 'Видеоларни варақлади')]]

    daily = list(visits.annotate(day=TruncDate('started')).values('day')
                 .annotate(n=Count('id', distinct=True), leads=Count('id', filter=lead_q, distinct=True)).order_by('day'))
    daily = with_bars(daily, 'n')

    ctx = {
        **admin.site.each_context(request), 'title': 'Ҳисоботлар', 'period': period, 'periods': PERIODS,
        'kpi': [
            ('Ташрифлар', total), ('Ноёб меҳмонлар', visits.values('vid').distinct().count()),
            ('Ўртача вақт', '%d:%02d' % divmod(int(agg['dur'] or 0), 60)), ('Ўртача тушиш', '%d%%' % (agg['scroll'] or 0)),
            ('Аризалар', leads_db), ('Конверсия', '%s%%' % pct(lead_visits, total)),
        ],
        'funnel': funnel, 'depth': depth, 'times': times, 'sources': grouped('source'),
        'campaigns': grouped('campaign'), 'devices': grouped('device', 3), 'videos': videos,
        'clicks': clicks, 'daily': daily,
    }
    return render(request, 'admin/content/reports.html', ctx)
