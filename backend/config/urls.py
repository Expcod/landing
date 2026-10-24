from django.contrib import admin
from django.urls import path

from content.views import content, lead

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/content/', content),
    path('api/lead/', lead),
]
