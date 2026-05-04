from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect

urlpatterns = [
    path('admin/',      admin.site.urls),
    path('',            lambda request: redirect('chat:index'), name='home'),
    path('accounts/',   include('accounts.urls',   namespace='accounts')),
    path('chat/',       include('chat.urls',        namespace='chat')),
    path('scheduler/',  include('scheduler.urls',   namespace='scheduler')),
    path('ai/',         include('ai_assist.urls',   namespace='ai_assist')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL,  document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
