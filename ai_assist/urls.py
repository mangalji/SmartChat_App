from django.urls import path
from . import views

app_name = 'ai_assist'

urlpatterns = [
    path('',      views.assistant_page, name='assistant'),
    path('chat/', views.chat_with_ai,   name='chat'),
]
