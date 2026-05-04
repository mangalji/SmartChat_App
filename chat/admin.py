from django.contrib import admin
from .models import Message, ChatGroup, GroupMember, GroupMessage


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display  = ['sender', 'receiver', 'body_preview', 'media_type', 'timestamp', 'is_read']
    list_filter   = ['media_type', 'is_read', 'timestamp']
    search_fields = ['sender__email', 'receiver__email', 'body']
    readonly_fields = ['timestamp']

    def body_preview(self, obj):
        return obj.body[:50] if obj.body else '(media)'
    body_preview.short_description = 'Message'


@admin.register(ChatGroup)
class ChatGroupAdmin(admin.ModelAdmin):
    list_display  = ['name', 'created_by', 'created_at', 'member_count']
    search_fields = ['name']
    readonly_fields = ['created_at']

    def member_count(self, obj):
        return obj.members.count()
    member_count.short_description = 'Members'


@admin.register(GroupMember)
class GroupMemberAdmin(admin.ModelAdmin):
    list_display  = ['group', 'user', 'role', 'joined']
    list_filter   = ['role']
    search_fields = ['group__name', 'user__email']


@admin.register(GroupMessage)
class GroupMessageAdmin(admin.ModelAdmin):
    list_display  = ['group', 'sender', 'body_preview', 'timestamp']
    search_fields = ['group__name', 'sender__email', 'body']
    readonly_fields = ['timestamp']

    def body_preview(self, obj):
        return obj.body[:50] if obj.body else '(media)'
    body_preview.short_description = 'Message'
