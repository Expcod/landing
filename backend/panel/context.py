from content.models import TgSubscriber


def counters(request):
    from .views import _waiting
    """Менюдаги рақамлар: жавоб кутаётган аризалар ва рухсат кутаётган Telegram обуначилар."""
    if not request.path.startswith('/panel/') or not getattr(request, 'user', None) or not request.user.is_staff:
        return {}
    return {
        'nav_new': _waiting().count(),
        'nav_pending': TgSubscriber.objects.filter(status=TgSubscriber.PENDING).count() if request.user.is_superuser else 0,
    }
