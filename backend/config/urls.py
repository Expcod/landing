from django.contrib import admin
from django.urls import path

from content.reports import reports
from content.views import content, lead, track

urlpatterns = [
    path('admin/reports/', admin.site.admin_view(reports), name='reports'),
    path('admin/', admin.site.urls),
    path('api/content/', content),
    path('api/lead/', lead),
    path('api/track/', track),
]
