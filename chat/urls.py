from django.urls import path
from . import views

app_name = 'chat'

urlpatterns = [
    path('',                                        views.index,               name='index'),
    path('dm/<int:user_id>/',                       views.dm_room,             name='dm_room'),
    path('dm/<int:user_id>/media/',                 views.media_gallery,       name='media_gallery'),
    path('groups/',                                 views.group_list,          name='group_list'),
    path('groups/create/',                          views.create_group,        name='create_group'),
    path('groups/<int:group_id>/',                  views.group_room,          name='group_room'),
    path('groups/<int:group_id>/add/',              views.add_member,          name='add_member'),
    path('groups/<int:group_id>/remove/',           views.remove_member,       name='remove_member'),
    path('groups/<int:group_id>/leave/',            views.leave_group,         name='leave_group'),
    path('groups/<int:group_id>/media/',            views.group_media_gallery, name='group_media_gallery'),
    path('upload/',                                 views.upload_media,        name='upload_media'),
    path('ai-suggest/',                             views.ai_suggest,          name='ai_suggest'),
]
