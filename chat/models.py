from django.db import models
from django.conf import settings
from django.utils import timezone


class Message(models.Model):
    sender    = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_messages'
    )
    receiver  = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='received_messages'
    )
    body      = models.TextField(blank=True)
    media     = models.FileField(upload_to='chat_media/', blank=True, null=True)
    media_type = models.CharField(
        max_length=10,
        choices=[('image', 'Image'), ('file', 'File')],
        blank=True
    )
    timestamp = models.DateTimeField(default=timezone.now)
    is_read   = models.BooleanField(default=False)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f'{self.sender} → {self.receiver}: {self.body[:40]}'

    @staticmethod
    def get_room_name(user1_id, user2_id):
        """Deterministic room name regardless of who initiates."""
        ids = sorted([int(user1_id), int(user2_id)])
        return f'dm_{ids[0]}_{ids[1]}'


class ChatGroup(models.Model):
    name        = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    created_by  = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_groups'
    )
    created_at  = models.DateTimeField(auto_now_add=True)
    avatar      = models.ImageField(upload_to='group_avatars/', blank=True, null=True)

    def __str__(self):
        return self.name


class GroupMember(models.Model):
    ROLE_CHOICES = [('admin', 'Admin'), ('member', 'Member')]
    group  = models.ForeignKey(ChatGroup, on_delete=models.CASCADE, related_name='members')
    user   = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='group_memberships')
    role   = models.CharField(max_length=10, choices=ROLE_CHOICES, default='member')
    joined = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('group', 'user')

    def __str__(self):
        return f'{self.user.email} in {self.group.name}'


class GroupMessage(models.Model):
    group     = models.ForeignKey(ChatGroup, on_delete=models.CASCADE, related_name='messages')
    sender    = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='group_messages')
    body      = models.TextField(blank=True)
    media     = models.FileField(upload_to='group_media/', blank=True, null=True)
    media_type = models.CharField(max_length=10, choices=[('image', 'Image'), ('file', 'File')], blank=True)
    timestamp = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f'[{self.group.name}] {self.sender}: {self.body[:40]}'
