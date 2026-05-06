import logging
from django.utils import timezone
from .models import ScheduledMessage
from chat.models import Message, GroupMessage
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

logger = logging.getLogger(__name__)

def send_scheduled_messages():
    """
    Check for messages that are due and send them via WebSocket and save to DB.
    """
    now = timezone.now()
    due_messages = ScheduledMessage.objects.filter(
        scheduled_time__lte=now,
        is_sent=False
    ).select_related('sender', 'receiver', 'group')

    if not due_messages.exists():
        return

    channel_layer = get_channel_layer()

    for sm in due_messages:
        try:
            if sm.receiver:
                # 1-on-1 DM
                msg = Message.objects.create(
                    sender=sm.sender,
                    receiver=sm.receiver,
                    body=sm.body,
                    timestamp=now
                )
                
                # Notify via WebSocket if possible
                room = f'dm_{min(sm.sender.pk, sm.receiver.pk)}_{max(sm.sender.pk, sm.receiver.pk)}'
                async_to_sync(channel_layer.group_send)(room, {
                    'type': 'chat_message',
                    'id': msg.id,
                    'body': msg.body,
                    'sender_id': sm.sender.pk,
                    'sender_name': f'@{sm.sender.username}',
                    'timestamp': msg.timestamp.isoformat(),
                })
            
            elif sm.group:
                # Group Message
                msg = GroupMessage.objects.create(
                    group=sm.group,
                    sender=sm.sender,
                    body=sm.body,
                    timestamp=now
                )
                
                room = f'group_{sm.group.pk}'
                async_to_sync(channel_layer.group_send)(room, {
                    'type': 'chat_message',
                    'id': msg.id,
                    'body': msg.body,
                    'sender_id': sm.sender.pk,
                    'sender_name': f'@{sm.sender.username}',
                    'timestamp': msg.timestamp.isoformat(),
                })

            sm.is_sent = True
            sm.save(update_fields=['is_sent'])
            logger.info(f"Sent scheduled message ID {sm.id}")

        except Exception as e:
            logger.error(f"Error sending scheduled message {sm.id}: {e}")
