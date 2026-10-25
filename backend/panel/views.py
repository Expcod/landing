import csv
import json
from datetime import timedelta
from functools import wraps

from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from content import notify, odoo_sync
from content.models import Case, Client, Lead, OdooStage, Reel, Screen, SiteSettings, TgSubscriber, Visit
from content.reports import SECTION_NAMES, report_data

from .forms import CONTENT_FORMS, SettingsForm, UserForm

# ---------- Рухсатлар ----------
# Супер админ (is_superuser) — ҳамма бўлимлар. Менежер (is_staff) — бош саҳифа, аризалар, ҳисоботлар.


def staff_required(view):
    @wraps(view)
    def wrap(request, *a, **kw):
        if not request.user.is_authenticated:
            return redirect(f'/panel/login/?next={request.path}')
        if not request.user.is_staff or not request.user.is_active:
            return render(request, 'panel/denied.html', status=403)
        return view(request, *a, **kw)
    return wrap


def super_required(view):
    @wraps(view)
    @staff_required
    def wrap(request, *a, **kw):
        if not request.user.is_superuser:
            return render(request, 'panel/denied.html', status=403)
        return view(request, *a, **kw)
    return wrap


def _waiting(qs=None):
    """Биринчи босқичдаги (масалан «Yangi») аризалар — қўнғироқ кутаётганлар."""
    qs = Lead.objects.all() if qs is None else qs
    first = odoo_sync.first_stage()
    return qs.filter(Q(stage=first) | Q(stage__isnull=True)) if first else qs.filter(status='new')


def _sync(request, force=False):
    ok, err = odoo_sync.refresh(force=force)
    if not ok and request.user.is_superuser:
        return err
    return ''


# ---------- Бош саҳифа ----------

def _day_start(days_ago=0):
    now = timezone.localtime()
    return now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days_ago)


@staff_required
def dashboard(request):
    sync_error = _sync(request)
    today, week = _day_start(), _day_start(6)
    leads = Lead.objects.all()
    days = []
    for i in range(13, -1, -1):
        a = _day_start(i)
        days.append({'day': a, 'leads': leads.filter(created__gte=a, created__lt=a + timedelta(days=1)).count(),
                     'visits': Visit.objects.filter(started__gte=a, started__lt=a + timedelta(days=1)).count()})
    top = max([d['leads'] for d in days] or [0]) or 1
    for d in days:
        d['h'] = round(d['leads'] * 100 / top)
    week_visits = Visit.objects.filter(started__gte=week).count()
    week_leads = leads.filter(created__gte=week).count()
    ctx = {
        'waiting': _waiting().select_related('stage').order_by('created')[:6],
        'waiting_count': _waiting().count(),
        'first_stage': odoo_sync.first_stage(),
        'sync_error': sync_error,
        'stats': [
            ('Бугунги аризалар', leads.filter(created__gte=today).count()),
            ('7 кунда аризалар', week_leads),
            ('7 кунда ташрифлар', week_visits),
            ('Конверсия, 7 кун', f'{round(week_leads * 100 / week_visits, 1) if week_visits else 0}%'),
        ],
        'days': days,
        'pending_subs': TgSubscriber.objects.filter(status=TgSubscriber.PENDING).count() if request.user.is_superuser else 0,
        'failed': leads.exclude(sync_error='').count() if request.user.is_superuser else 0,
    }
    return render(request, 'panel/dashboard.html', ctx)


# ---------- Аризалар ----------

PERIODS = {'all': 'Ҳаммаси', '1': 'Бугун', '7': '7 кун', '30': '30 кун'}


def _filtered_leads(request):
    qs = Lead.objects.all()
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(phone__icontains=q) | Q(business__icontains=q) | Q(problem__icontains=q))
    period = request.GET.get('d', 'all')
    if period in PERIODS and period != 'all':
        qs = qs.filter(created__gte=_day_start(int(period) - 1))
    return qs, q, period if period in PERIODS else 'all'


@staff_required
def leads(request):
    if request.method == 'POST':  # «Odoo'дан янгилаш»
        ok, err = odoo_sync.refresh(force=True)
        (messages.success if ok else messages.error)(request, 'Босқичлар Odoo билан солиштирилди.' if ok else err)
        return redirect(request.get_full_path())
    sync_error = _sync(request)
    qs, q, period = _filtered_leads(request)
    qs = qs.select_related('stage')
    view = 'list' if request.GET.get('view') == 'list' else 'board'
    stages = list(OdooStage.objects.filter(active=True))
    ctx = {'q': q, 'period': period, 'periods': PERIODS, 'view': view, 'stages': stages,
           'total': qs.count(), 'sync_error': sync_error}
    if view == 'list':
        ctx['page'] = Paginator(qs, 30).get_page(request.GET.get('p'))
    else:
        counts = dict(qs.values_list('stage').annotate(c=Count('id')))
        first = stages[0] if stages else None
        cols = []
        for st in stages:
            items = qs.filter(Q(stage=st) | Q(stage__isnull=True)) if st == first else qs.filter(stage=st)
            n = counts.get(st.pk, 0) + (counts.get(None, 0) if st == first else 0)
            cols.append({'stage': st, 'count': n, 'items': items[:60]})
        ctx['columns'] = cols
    return render(request, 'panel/leads.html', ctx)


@staff_required
def lead_detail(request, pk):
    lead = get_object_or_404(Lead, pk=pk)
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'note':
            lead.note = request.POST.get('note', '')[:5000]
            lead.save(update_fields=['note'])
            messages.success(request, 'Изоҳ сақланди.')
        elif action == 'resend':
            ok = notify.sync(lead)
            (messages.success if ok else messages.error)(
                request, 'Telegram ва CRM\'га юборилди.' if ok else f'Юбориб бўлмади: {lead.sync_error}')
        elif action == 'delete' and request.user.is_superuser:
            lead.delete()
            messages.success(request, f'«{lead.name}» аризаси ўчирилди.')
            return redirect('panel:leads')
        return redirect('panel:lead', pk=pk)
    sync_error = _sync(request)
    lead.refresh_from_db()
    visit = Visit.objects.filter(sid=lead.sid).first() if lead.sid else None
    s = SiteSettings.get()
    ctx = {'lead': lead, 'visit': visit, 'stages': OdooStage.objects.filter(active=True), 'sync_error': sync_error,
           'current_stage': lead.stage or odoo_sync.first_stage(), 'section_names': SECTION_NAMES,
           'crm_url': notify.odoo_link(lead, s) if lead.odoo_id and s.odoo_url else '',
           'events': visit.events.all()[:40] if visit else []}
    return render(request, 'panel/lead_detail.html', ctx)


@staff_required
@require_POST
def lead_status(request, pk):
    lead = get_object_or_404(Lead, pk=pk)
    stage = OdooStage.objects.filter(pk=request.POST.get('stage'), active=True).first()
    fetch = request.headers.get('X-Requested-With') == 'fetch'
    if not stage:
        return JsonResponse({'ok': False, 'error': 'Бундай босқич йўқ. Саҳифани янгиланг.'}, status=400)
    try:
        odoo_sync.set_stage(lead, stage)
    except odoo_sync.OdooError as e:
        msg = f'Odoo босқични қабул қилмади, ҳеч нарса ўзгармади: {e}'
        if fetch:
            return JsonResponse({'ok': False, 'error': msg}, status=502)
        messages.error(request, msg)
        return redirect('panel:lead', pk=pk)
    if fetch:
        return JsonResponse({'ok': True, 'label': stage.name})
    messages.success(request, f'Босқич: {stage.name}.')
    nxt = request.POST.get('next', '')
    return redirect(nxt) if nxt.startswith('/panel/') else redirect('panel:lead', pk=pk)


@super_required
def leads_csv(request):
    qs, _, _ = _filtered_leads(request)
    resp = HttpResponse(content_type='text/csv; charset=utf-8')
    resp['Content-Disposition'] = f'attachment; filename="arizalar-{timezone.localdate():%Y-%m-%d}.csv"'
    resp.write('﻿')  # Excel кириллни тўғри очиши учун
    w = csv.writer(resp, delimiter=';')
    w.writerow(['Вақти', 'Исм', 'Телефон', 'Фаолият тури', 'Муаммо', 'Босқич', 'Изоҳ', 'Odoo ID'])
    for l in qs.select_related('stage'):
        w.writerow([timezone.localtime(l.created).strftime('%d.%m.%Y %H:%M'), l.name, l.phone, l.business,
                    l.problem, l.stage.name if l.stage else '', l.note, l.odoo_id or ''])
    return resp


# ---------- Ҳисоботлар ----------

@staff_required
def reports(request):
    return render(request, 'panel/reports.html', report_data(request.GET.get('d', '7')))


# ---------- Сайт контенти ----------

CONTENT = {
    'cases': {'model': Case, 'title': 'Кейслар', 'one': 'кейс', 'image': 'logo', 'main': 'who', 'sub': ['industry', 'num'],
              'hint': 'Лойиҳа натижалари: биринчи экрандаги рақамлар ва «Кейслар» бўлими.'},
    'clients': {'model': Client, 'title': 'Мижозлар', 'one': 'мижоз', 'image': 'logo', 'main': 'name', 'sub': [],
                'hint': 'Логотиплар қатори.'},
    'screens': {'model': Screen, 'title': 'Экранлар', 'one': 'экран', 'image': 'image', 'main': 'title', 'sub': ['tag'],
                'hint': 'Дастур скриншотлари ва уларнинг пунктлари.'},
    'reels': {'model': Reel, 'title': 'Видеолар', 'one': 'видео', 'image': 'poster', 'main': 'caption', 'sub': ['instagram_url'],
              'hint': 'Reels карусели. Видео файлини юкланг ёки манзилини киритинг.'},
}


def _kind(kind):
    if kind not in CONTENT:
        raise Http404
    return CONTENT[kind]


def _thumb(obj, field):
    f = getattr(obj, field, None)
    if f:
        return f.url
    return getattr(obj, field + '_url', '') or ''


@super_required
def content_list(request, kind):
    meta = _kind(kind)
    items = [{'obj': o, 'main': getattr(o, meta['main']), 'thumb': _thumb(o, meta['image']),
              'sub': [str(getattr(o, f)) for f in meta['sub'] if getattr(o, f)]}
             for o in meta['model'].objects.all()]
    return render(request, 'panel/content_list.html', {'kind': kind, 'meta': meta, 'items': items, 'kinds': CONTENT})


@super_required
def content_edit(request, kind, pk=None):
    meta = _kind(kind)
    obj = get_object_or_404(meta['model'], pk=pk) if pk else None
    Form = CONTENT_FORMS[meta['model']]
    form = Form(request.POST or None, request.FILES or None, instance=obj)
    if request.method == 'POST' and form.is_valid():
        new = form.save(commit=False)
        if not obj:
            last = meta['model'].objects.order_by('-order').first()
            new.order = (last.order + 1) if last else 0
        new.save()
        messages.success(request, f'{meta["one"].capitalize()} сақланди.')
        return redirect('panel:content', kind=kind)
    return render(request, 'panel/content_form.html', {'kind': kind, 'meta': meta, 'form': form, 'obj': obj, 'kinds': CONTENT})


@super_required
@require_POST
def content_delete(request, kind, pk):
    meta = _kind(kind)
    obj = get_object_or_404(meta['model'], pk=pk)
    obj.delete()
    messages.success(request, f'{meta["one"].capitalize()} ўчирилди.')
    return redirect('panel:content', kind=kind)


@super_required
@require_POST
def content_toggle(request, kind, pk):
    obj = get_object_or_404(_kind(kind)['model'], pk=pk)
    obj.active = not obj.active
    obj.save(update_fields=['active'])
    return JsonResponse({'ok': True, 'active': obj.active})


@super_required
@require_POST
def content_reorder(request, kind):
    model = _kind(kind)['model']
    try:
        ids = [int(i) for i in json.loads(request.body)['ids']]
    except (ValueError, KeyError, TypeError):
        return JsonResponse({'ok': False}, status=400)
    for i, pk in enumerate(ids):
        model.objects.filter(pk=pk).update(order=i)
    return JsonResponse({'ok': True})


# ---------- Telegram обуначилар ----------

@super_required
def telegram(request):
    s = SiteSettings.get()
    if request.method == 'POST':
        sub = get_object_or_404(TgSubscriber, pk=request.POST.get('id'))
        action = request.POST.get('action')
        if action in ('approve', 'reject'):
            notify.set_subscriber_status(s, sub, sub.APPROVED if action == 'approve' else sub.REJECTED)
            messages.success(request, f'{sub}: {"рухсат берилди" if action == "approve" else "рад этилди"}.')
        elif action == 'admin':
            sub.is_admin = not sub.is_admin
            if sub.is_admin:
                sub.status = sub.APPROVED
            sub.save(update_fields=['is_admin', 'status'])
            messages.success(request, f'{sub} {"энди админ" if sub.is_admin else "админликдан олинди"}.')
        elif action == 'pause':
            sub.active = not sub.active
            sub.save(update_fields=['active'])
            messages.success(request, f'{sub}: аризалар {"яна юборилади" if sub.active else "юборилмайди"}.')
        elif action == 'delete':
            sub.delete()
            messages.success(request, f'{sub} рўйхатдан ўчирилди.')
        return redirect('panel:telegram')
    subs = TgSubscriber.objects.all()
    groups = [
        ('pending', 'Рухсат кутмоқда', subs.filter(status=TgSubscriber.PENDING)),
        ('approved', 'Аризалар боради', subs.filter(status=TgSubscriber.APPROVED)),
        ('rejected', 'Рад этилган', subs.filter(status=TgSubscriber.REJECTED)),
    ]
    bot = ''
    if s.tg_token:
        try:
            bot = notify.tg(s, 'getMe')['result']['username']
        except Exception:  # noqa: BLE001
            bot = ''
    return render(request, 'panel/telegram.html', {'groups': groups, 'bot': bot, 'has_token': bool(s.tg_token)})


# ---------- Созламалар ----------

@super_required
def settings_view(request):
    s = SiteSettings.get()
    old_token = s.tg_token
    form = SettingsForm(request.POST or None, instance=s)
    checks = {}
    if request.method == 'POST':
        action = request.POST.get('action', 'save')
        if action == 'save' and form.is_valid():
            s = form.save()
            messages.success(request, 'Созламалар сақланди.')
            if s.tg_token and (s.tg_token != old_token or request.POST.get('reconnect')):
                try:
                    notify.set_webhook(s, f'https://{request.get_host()}/api/tg/webhook/')
                    messages.success(request, 'Telegram бот сайтга уланди.')
                except Exception as e:  # noqa: BLE001
                    messages.error(request, f'Telegram ботни улаб бўлмади: {e}')
            return redirect('panel:settings')
        if action == 'check':
            form = SettingsForm(instance=s)
            ok, err = odoo_sync.refresh(force=True)
            checks = {'tg': notify.tg_check(s), 'odoo': notify.odoo_check(s),
                      'sync': (ok, f'{OdooStage.objects.filter(active=True).count()} та босқич олинди, аризалар солиштирилди.' if ok else err)}
    return render(request, 'panel/settings.html', {'form': form, 'checks': checks})


# ---------- Фойдаланувчилар ----------

@super_required
def users(request):
    return render(request, 'panel/users.html', {'users': User.objects.order_by('-is_superuser', 'username')})


@super_required
def user_edit(request, pk=None):
    obj = get_object_or_404(User, pk=pk) if pk else User()
    form = UserForm(request.POST or None, instance=obj, editor=request.user)
    if request.method == 'POST':
        if request.POST.get('action') == 'delete' and obj.pk:
            if obj == request.user:
                messages.error(request, 'Ўзингизни ўчира олмайсиз.')
                return redirect('panel:user', pk=obj.pk)
            obj.delete()
            messages.success(request, f'{obj.username} ўчирилди.')
            return redirect('panel:users')
        if form.is_valid():
            u = form.save()
            if u == request.user:
                update_session_auth_hash(request, u)
            messages.success(request, f'{u.username} сақланди.')
            return redirect('panel:users')
    return render(request, 'panel/user_form.html', {'form': form, 'obj': obj})


@staff_required
def password(request):
    form = PasswordChangeForm(request.user, request.POST or None)
    for f in form.fields.values():
        f.widget.attrs['class'] = 'input'
    if request.method == 'POST' and form.is_valid():
        update_session_auth_hash(request, form.save())
        messages.success(request, 'Парол ўзгартирилди.')
        return redirect('panel:dashboard')
    return render(request, 'panel/password.html', {'form': form})
