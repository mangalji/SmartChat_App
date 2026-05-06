import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

User = get_user_model()

# Maximum characters per chat message (prevents DB flooding)
MAX_MSG_LENGTH = 5000


# ══════════════════════════════════════════════
#  1-on-1 Direct Message Consumer
# ══════════════════════════════════════════════
class DirectMessageConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        if not self.scope['user'].is_authenticated:
            await self.close()
            return

        self.me       = self.scope['user']
        self.other_id = self.scope['url_route']['kwargs']['user_id']
        self.room     = self._room_name(self.me.pk, self.other_id)

        await self.channel_layer.group_add(self.room, self.channel_name)
        await self.accept()

        # Notify presence
        await self.channel_layer.group_send(self.room, {
            'type':    'user_status',
            'user_id': self.me.pk,
            'status':  'online',
        })

    async def disconnect(self, code):
        await self.channel_layer.group_send(self.room, {
            'type':    'user_status',
            'user_id': self.me.pk,
            'status':  'offline',
        })
        await self.channel_layer.group_discard(self.room, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        try:
            data = json.loads(text_data)
        except (json.JSONDecodeError, TypeError):
            return
        msg_type = data.get('type', 'message')

        if msg_type == 'message':
            body = data.get('body', '').strip()[:MAX_MSG_LENGTH]
            if not body:
                return
            msg = await self.save_message(body)
            await self.channel_layer.group_send(self.room, {
                'type':        'chat_message',
                'id':          msg.id,
                'body':        body,
                'sender_id':   self.me.pk,
                'sender_name': f'@{self.me.username}',
                'timestamp':   msg.timestamp.isoformat(),
                'media_url':   '',
                'media_type':  '',
            })

        elif msg_type == 'media_notify':
            # Sent after a successful AJAX media upload
            await self.channel_layer.group_send(self.room, {
                'type':        'chat_message',
                'id':          data.get('id'),
                'body':        '',
                'sender_id':   self.me.pk,
                'sender_name': f'@{self.me.username}',
                'timestamp':   data.get('timestamp', timezone.now().isoformat()),
                'media_url':   data.get('media_url', ''),
                'media_type':  data.get('media_type', 'file'),
            })

        elif msg_type == 'typing':
            await self.channel_layer.group_send(self.room, {
                'type':      'typing_indicator',
                'user_id':   self.me.pk,
                'is_typing': data.get('is_typing', False),
            })

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'type':        'message',
            'id':          event['id'],
            'body':        event['body'],
            'sender_id':   event['sender_id'],
            'sender_name': event['sender_name'],
            'timestamp':   event['timestamp'],
            'media_url':   event.get('media_url', ''),
            'media_type':  event.get('media_type', ''),
        }))

    async def user_status(self, event):
        await self.send(text_data=json.dumps({
            'type':    'status',
            'user_id': event['user_id'],
            'status':  event['status'],
        }))

    async def typing_indicator(self, event):
        if event['user_id'] != self.me.pk:
            await self.send(text_data=json.dumps({
                'type':      'typing',
                'user_id':   event['user_id'],
                'is_typing': event['is_typing'],
            }))

    @database_sync_to_async
    def save_message(self, body):
        from .models import Message
        receiver = User.objects.get(pk=self.other_id)
        return Message.objects.create(
            sender=self.me,
            receiver=receiver,
            body=body,
            timestamp=timezone.now(),
        )

    @staticmethod
    def _room_name(id1, id2):
        ids = sorted([int(id1), int(id2)])
        return f'dm_{ids[0]}_{ids[1]}'


# ══════════════════════════════════════════════
#  Group Chat Consumer
# ══════════════════════════════════════════════
class GroupChatConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        if not self.scope['user'].is_authenticated:
            await self.close()
            return

        self.me       = self.scope['user']
        self.group_id = self.scope['url_route']['kwargs']['group_id']
        self.room     = f'group_{self.group_id}'

        if not await self.check_membership():
            await self.close()
            return

        await self.channel_layer.group_add(self.room, self.channel_name)
        await self.accept()

        # Announce join
        await self.channel_layer.group_send(self.room, {
            'type':    'member_event',
            'user_id': self.me.pk,
            'name':    f'@{self.me.username}',
            'action':  'joined',
        })

    async def disconnect(self, code):
        await self.channel_layer.group_discard(self.room, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        try:
            data = json.loads(text_data)
        except (json.JSONDecodeError, TypeError):
            return
        msg_type = data.get('type', 'message')

        if msg_type == 'message':
            body = data.get('body', '').strip()[:MAX_MSG_LENGTH]
            if not body:
                return
            msg = await self.save_group_message(body)
            await self.channel_layer.group_send(self.room, {
                'type':        'chat_message',
                'id':          msg.id,
                'body':        body,
                'sender_id':   self.me.pk,
                'sender_name': f'@{self.me.username}',
                'timestamp':   msg.timestamp.isoformat(),
                'media_url':   '',
                'media_type':  '',
            })

        elif msg_type == 'media_notify':
            await self.channel_layer.group_send(self.room, {
                'type':        'chat_message',
                'id':          data.get('id'),
                'body':        '',
                'sender_id':   self.me.pk,
                'sender_name': f'@{self.me.username}',
                'timestamp':   data.get('timestamp', timezone.now().isoformat()),
                'media_url':   data.get('media_url', ''),
                'media_type':  data.get('media_type', 'file'),
            })

        elif msg_type == 'typing':
            await self.channel_layer.group_send(self.room, {
                'type':      'typing_indicator',
                'user_id':   self.me.pk,
                'name':      f'@{self.me.username}',
                'is_typing': data.get('is_typing', False),
            })

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'type':        'message',
            'id':          event['id'],
            'body':        event['body'],
            'sender_id':   event['sender_id'],
            'sender_name': event['sender_name'],
            'timestamp':   event['timestamp'],
            'media_url':   event.get('media_url', ''),
            'media_type':  event.get('media_type', ''),
        }))

    async def member_event(self, event):
        await self.send(text_data=json.dumps({
            'type':   'member_event',
            'name':   event['name'],
            'action': event['action'],
        }))

    async def typing_indicator(self, event):
        if event['user_id'] != self.me.pk:
            await self.send(text_data=json.dumps({
                'type':      'typing',
                'name':      event['name'],
                'is_typing': event['is_typing'],
            }))

    @database_sync_to_async
    def check_membership(self):
        from .models import GroupMember
        return GroupMember.objects.filter(
            group_id=self.group_id, user=self.me
        ).exists()

    @database_sync_to_async
    def save_group_message(self, body):
        from .models import GroupMessage
        return GroupMessage.objects.create(
            group_id=self.group_id,
            sender=self.me,
            body=body,
            timestamp=timezone.now(),
        )
