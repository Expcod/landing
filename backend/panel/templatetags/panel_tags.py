from django import template
from django.utils import timezone

register = template.Library()


@register.filter
def ago(dt):
    """«5 дақиқа олдин», «кеча 14:20», «12.10 09:05»."""
    if not dt:
        return ''
    now = timezone.localtime()
    dt = timezone.localtime(dt)
    sec = (now - dt).total_seconds()
    if sec < 60:
        return 'ҳозиргина'
    if sec < 3600:
        return f'{int(sec // 60)} дақиқа олдин'
    if dt.date() == now.date():
        return f'бугун {dt:%H:%M}'
    if (now.date() - dt.date()).days == 1:
        return f'кеча {dt:%H:%M}'
    return f'{dt:%d.%m.%Y %H:%M}' if dt.year != now.year else f'{dt:%d.%m %H:%M}'


@register.filter
def tel(phone):
    """tel: ҳаволаси учун: фақат рақамлар, 9 хонали бўлса +998 қўшилади."""
    digits = ''.join(c for c in str(phone) if c.isdigit())
    if len(digits) == 9:
        digits = '998' + digits
    return '+' + digits if digits else ''


@register.filter
def initials(name):
    parts = [p for p in str(name).split() if p]
    return ''.join(p[0] for p in parts[:2]).upper() or '?'


@register.filter
def mmss(sec):
    return '%d:%02d' % divmod(int(sec or 0), 60)


@register.simple_tag(takes_context=True)
def active(context, *prefixes):
    path = context['request'].path
    return 'is-active' if any(path.startswith(p) for p in prefixes) else ''


@register.filter
def phone(value):
    """998991410990 → +998 99 141 09 90. Ўзбек рақами бўлмаса, ўзгаришсиз."""
    digits = ''.join(c for c in str(value) if c.isdigit())
    if len(digits) == 9:
        digits = '998' + digits
    if len(digits) == 12 and digits.startswith('998'):
        d = digits[3:]
        return f'+998 {d[:2]} {d[2:5]} {d[5:7]} {d[7:]}'
    return value
