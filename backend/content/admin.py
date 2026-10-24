from django.contrib import admin
from django.utils.html import format_html

from .models import Case, Client, Event, Lead, Reel, Screen, SiteSettings, Visit

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
    list_display = ['created', 'name', 'phone', 'business', 'status']
    list_editable = ['status']
    list_filter = ['status', 'created']
    search_fields = ['name', 'phone', 'business', 'problem']
    readonly_fields = ['created', 'name', 'phone', 'business', 'problem', 'page', 'ip']
    fields = readonly_fields + ['status', 'note']

    def has_add_permission(self, request):
        return False


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


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
