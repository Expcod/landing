from django.contrib import admin, messages
from django.utils.html import format_html

from . import notify

from .models import Case, Client, Event, Lead, Reel, Screen, SiteSettings, TgSubscriber, Visit

admin.site.site_header = 'Nova Code — landing'
admin.site.site_title = 'Nova Code landing'
admin.site.index_title = 'Сайт маълумотлари'


def thumb(f, h=32):
    return format_html('<img src="{}" style="height:{}px">', f.url, h) if f else '—'


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ['name', 'preview', 'order', 'active']
    list_editable = ['order', 'active']

    @admin.display(description='Логотип')
    def preview(self, o):
        return thumb(o.logo, 24)


@admin.register(Case)
class CaseAdmin(admin.ModelAdmin):
    list_display = ['who', 'num', 'short', 'order', 'in_hero', 'active']
    list_editable = ['order', 'in_hero', 'active']


@admin.register(Screen)
class ScreenAdmin(admin.ModelAdmin):
    list_display = ['title', 'tag', 'preview', 'order', 'active']
    list_editable = ['order', 'active']

    @admin.display(description='Расм')
    def preview(self, o):
        return thumb(o.image, 48)


@admin.register(Reel)
class ReelAdmin(admin.ModelAdmin):
    list_display = ['caption', 'preview', 'order', 'active']
    list_editable = ['order', 'active']

    @admin.display(description='Муқова')
    def preview(self, o):
        if o.poster:
            return thumb(o.poster, 48)
        return format_html('<img src="{}" style="height:48px">', o.poster_url) if o.poster_url else '—'


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ['created', 'name', 'phone', 'business', 'status', 'crm', 'tg_sent']
    list_editable = ['status']
    list_filter = ['status', 'tg_sent', 'created']
    search_fields = ['name', 'phone', 'business', 'problem']
    readonly_fields = ['created', 'name', 'phone', 'business', 'problem', 'page', 'ip', 'crm', 'tg_sent', 'sync_error']
    fields = readonly_fields + ['status', 'note']
    actions = ['resend']

    @admin.display(description='Odoo CRM')
    def crm(self, o):
        if o.odoo_id:
            return format_html('<a href="{}" target="_blank">#{}</a>', notify.odoo_link(o, SiteSettings.get()), o.odoo_id)
        if o.odoo_id == 0:
            return 'юборилди'
        return format_html('<span style="color:#c00" title="{}">юборилмаган</span>', o.sync_error) if o.sync_error else '—'

    @admin.action(description="Telegram ва Odoo CRM'га қайта юбориш (юборилмаганларини)")
    def resend(self, request, qs):
        ok = sum(notify.sync(o) for o in qs)
        level = messages.SUCCESS if ok == len(qs) else messages.WARNING
        self.message_user(request, f'{ok} та ариза юборилди, {len(qs) - ok} тасида хато (аризани очиб кўринг).', level)

    def has_add_permission(self, request):
        return False


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    readonly_fields = ['webhook_status']
    fieldsets = [
        (None, {'fields': ['pixel_id']}),
        ('Аризалар → Telegram бот', {'fields': ['tg_token', 'webhook_status'],
                                     'description': 'Раҳбар ботга /start босади, кейин «Telegram обуначилар»да унга «Админ» '
                                                    'белгиси қўйилади. Бошқалар /start босганда админга «Рухсат бериш / Йўқ» '
                                                    'сўрови боради; аризалар фақат рухсат берилганларга юборилади.'}),
        ('Аризалар → Odoo CRM (Meta Ads модули)', {'fields': ['odoo_url', 'odoo_db', 'odoo_api_key'],
                                                    'description': 'API калит: Odoo → Meta Ads → Sozlash → «Lead API kaliti».'}),
    ]

    @admin.display(description='Бот ҳолати')
    def webhook_status(self, o):
        if not o.tg_token:
            return '—'
        try:
            info = notify.tg(o, 'getWebhookInfo')['result']
        except Exception as e:  # noqa: BLE001
            return f'Текшириб бўлмади: {e}'
        if not info.get('url'):
            return 'Уланмаган — «Сақлаш» босинг.'
        err = info.get('last_error_message')
        return f"Уланган: {info['url']}" + (f' (охирги хато: {err})' if err else '')

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if obj.tg_token:
            url = f'https://{request.get_host()}/api/tg/webhook/'
            try:
                notify.set_webhook(obj, url)
                self.message_user(request, f'Telegram бот уланди: {url}')
            except Exception as e:  # noqa: BLE001
                self.message_user(request, f'Telegram ботни улаб бўлмади: {e}', messages.ERROR)

    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(TgSubscriber)
class TgSubscriberAdmin(admin.ModelAdmin):
    list_display = ['name', 'username', 'is_group', 'is_admin', 'status', 'active', 'created']
    list_editable = ['is_admin', 'status', 'active']
    list_filter = ['status', 'is_admin', 'active', 'is_group']
    search_fields = ['name', 'username']
    readonly_fields = ['chat_id', 'name', 'username', 'is_group', 'created']

    def has_add_permission(self, request):
        return False

    def save_model(self, request, obj, form, change):
        if obj.is_admin:  # админга доим аризалар боради
            obj.status = TgSubscriber.APPROVED
        super().save_model(request, obj, form, change)


class EventInline(admin.TabularInline):
    model = Event
    extra = 0
    can_delete = False
    readonly_fields = ['created', 'name', 'label']
    fields = readonly_fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Visit)
class VisitAdmin(admin.ModelAdmin):
    list_display = ['started', 'source', 'campaign', 'device', 'duration_fmt', 'max_scroll', 'last_section', 'got_lead']
    list_filter = ['source', 'device', 'last_section', 'started']
    search_fields = ['source', 'campaign', 'referrer', 'ip']
    inlines = [EventInline]

    def get_readonly_fields(self, request, obj=None):
        return [f.name for f in Visit._meta.fields]

    def has_add_permission(self, request):
        return False

    @admin.display(description='Вақт')
    def duration_fmt(self, o):
        return '%d:%02d' % divmod(o.duration, 60)

    @admin.display(description='Ариза', boolean=True)
    def got_lead(self, o):
        return o.events.filter(name='lead_sent').exists()
