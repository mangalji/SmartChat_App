from django.db import models
from django.conf import settings
from django.utils import timezone

class ScheduledMessage(models.Model):
    sender    = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='scheduled_messages')
    
    # Can be to a user (DM) or to a group
    receiver  = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name='received_scheduled_messages')
    group     = models.ForeignKey('chat.ChatGroup', on_delete=models.CASCADE, null=True, blank=True, related_name='scheduled_messages')
    
    body      = models.TextField()
    scheduled_time = models.DateTimeField()
    
    is_sent   = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['scheduled_time']

    def __str__(self):
        target = f'User:{self.receiver}' if self.receiver else f'Group:{self.group}'
        return f'From {self.sender} to {target} at {self.scheduled_time}'
