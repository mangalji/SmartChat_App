"""
chat/tests.py — Security tests for chat, file upload & WebSocket consumers.

Covers:
  - MED-2:  File upload content-type spoofing prevention
  - MED-3:  WebSocket message size limits & JSON error handling
  - HIGH-4: Media URL XSS prevention (template-level, verified structurally)
  - Access control for group operations
"""

import json
import io
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from chat.models import Message, ChatGroup, GroupMember, GroupMessage
from chat.consumers import MAX_MSG_LENGTH

User = get_user_model()


class FileUploadSecurityTest(TestCase):
    """MED-2: File upload must validate both content-type AND extension."""

    def setUp(self):
        self.client = Client()
        self.sender = User.objects.create_user(
            email='sender@test.com', password='Pass123!',
            full_name='Sender', is_verified=True,
        )
        self.receiver = User.objects.create_user(
            email='receiver@test.com', password='Pass123!',
            full_name='Receiver', is_verified=True,
        )
        self.client.force_login(self.sender)

    def _create_test_image(self, fmt='PNG'):
        """Create a valid in-memory image file."""
        buf = io.BytesIO()
        img = Image.new('RGB', (100, 100), color='red')
        img.save(buf, format=fmt)
        buf.seek(0)
        return buf

    def test_valid_image_upload(self):
        """Valid image with correct content-type and extension should succeed."""
        img_data = self._create_test_image()
        uploaded = SimpleUploadedFile(
            'test.png', img_data.read(), content_type='image/png'
        )
        response = self.client.post(reverse('chat:upload_media'), {
            'file': uploaded,
            'user_id': self.receiver.pk,
        })
        data = response.json()
        self.assertNotIn('error', data, f"Valid image rejected: {data.get('error')}")
        self.assertEqual(data.get('media_type'), 'image')

    def test_content_type_spoofing_html_as_image(self):
        """HTML file with image content-type should be rejected."""
        html_content = b'<script>alert("XSS")</script>'
        uploaded = SimpleUploadedFile(
            'evil.png', html_content, content_type='image/png'
        )
        response = self.client.post(reverse('chat:upload_media'), {
            'file': uploaded,
            'user_id': self.receiver.pk,
        })
        data = response.json()
        self.assertIn('error', data,
                      "HTML disguised as PNG should be rejected by Pillow validation")

    def test_wrong_extension_correct_content_type(self):
        """Image with wrong extension (.html) but correct content-type should be rejected."""
        img_data = self._create_test_image()
        uploaded = SimpleUploadedFile(
            'evil.html', img_data.read(), content_type='image/png'
        )
        response = self.client.post(reverse('chat:upload_media'), {
            'file': uploaded,
            'user_id': self.receiver.pk,
        })
        data = response.json()
        self.assertIn('error', data,
                      "File with .html extension and image content-type should be rejected")

    def test_correct_extension_wrong_content_type(self):
        """Image file (.png) with wrong content-type (text/html) should be rejected."""
        img_data = self._create_test_image()
        uploaded = SimpleUploadedFile(
            'image.png', img_data.read(), content_type='text/html'
        )
        response = self.client.post(reverse('chat:upload_media'), {
            'file': uploaded,
            'user_id': self.receiver.pk,
        })
        data = response.json()
        self.assertIn('error', data,
                      "File with image extension but wrong content-type should be rejected")

    def test_exe_file_rejected(self):
        """Executable files should be rejected."""
        uploaded = SimpleUploadedFile(
            'malware.exe', b'MZ\x90\x00' * 100, content_type='application/octet-stream'
        )
        response = self.client.post(reverse('chat:upload_media'), {
            'file': uploaded,
            'user_id': self.receiver.pk,
        })
        data = response.json()
        self.assertIn('error', data, "Executable files should be rejected")

    def test_valid_pdf_upload(self):
        """Valid PDF with correct content-type and extension should succeed."""
        pdf_content = b'%PDF-1.4 test content'
        uploaded = SimpleUploadedFile(
            'document.pdf', pdf_content, content_type='application/pdf'
        )
        response = self.client.post(reverse('chat:upload_media'), {
            'file': uploaded,
            'user_id': self.receiver.pk,
        })
        data = response.json()
        self.assertNotIn('error', data, f"Valid PDF rejected: {data.get('error')}")
        self.assertEqual(data.get('media_type'), 'file')

    def test_file_too_large_rejected(self):
        """Files larger than 10MB should be rejected."""
        large_data = b'x' * (10 * 1024 * 1024 + 1)
        uploaded = SimpleUploadedFile(
            'large.txt', large_data, content_type='text/plain'
        )
        response = self.client.post(reverse('chat:upload_media'), {
            'file': uploaded,
            'user_id': self.receiver.pk,
        })
        data = response.json()
        self.assertIn('error', data, "Files over 10MB should be rejected")

    def test_no_file_returns_error(self):
        """Upload without file should return error."""
        response = self.client.post(reverse('chat:upload_media'), {
            'user_id': self.receiver.pk,
        })
        self.assertEqual(response.status_code, 400)

    def test_upload_requires_user_or_group_id(self):
        """Upload without user_id or group_id should fail."""
        img_data = self._create_test_image()
        uploaded = SimpleUploadedFile(
            'test.png', img_data.read(), content_type='image/png'
        )
        response = self.client.post(reverse('chat:upload_media'), {
            'file': uploaded,
        })
        data = response.json()
        self.assertIn('error', data)

    def test_upload_to_nonexistent_user_fails(self):
        """Upload to non-existent user should return 404."""
        img_data = self._create_test_image()
        uploaded = SimpleUploadedFile(
            'test.png', img_data.read(), content_type='image/png'
        )
        response = self.client.post(reverse('chat:upload_media'), {
            'file': uploaded,
            'user_id': 99999,
        })
        self.assertEqual(response.status_code, 404)

    def test_upload_requires_login(self):
        """Unauthenticated users cannot upload files."""
        self.client.logout()
        img_data = self._create_test_image()
        uploaded = SimpleUploadedFile(
            'test.png', img_data.read(), content_type='image/png'
        )
        response = self.client.post(reverse('chat:upload_media'), {
            'file': uploaded,
            'user_id': self.receiver.pk,
        })
        self.assertEqual(response.status_code, 302)  # Redirect to login


class GroupUploadSecurityTest(TestCase):
    """File upload access control for groups."""

    def setUp(self):
        self.client = Client()
        self.member = User.objects.create_user(
            email='member@test.com', password='Pass123!',
            full_name='Member', is_verified=True,
        )
        self.outsider = User.objects.create_user(
            email='outsider@test.com', password='Pass123!',
            full_name='Outsider', is_verified=True,
        )
        self.group = ChatGroup.objects.create(name='Test Group', created_by=self.member)
        GroupMember.objects.create(group=self.group, user=self.member, role='admin')

    def _create_test_image(self):
        buf = io.BytesIO()
        img = Image.new('RGB', (100, 100), color='blue')
        img.save(buf, format='PNG')
        buf.seek(0)
        return buf

    def test_non_member_cannot_upload_to_group(self):
        """Non-members should not be able to upload to a group."""
        self.client.force_login(self.outsider)
        img_data = self._create_test_image()
        uploaded = SimpleUploadedFile(
            'test.png', img_data.read(), content_type='image/png'
        )
        response = self.client.post(reverse('chat:upload_media'), {
            'file': uploaded,
            'group_id': self.group.pk,
        })
        self.assertEqual(response.status_code, 403)

    def test_member_can_upload_to_group(self):
        """Members should be able to upload to their group."""
        self.client.force_login(self.member)
        img_data = self._create_test_image()
        uploaded = SimpleUploadedFile(
            'test.png', img_data.read(), content_type='image/png'
        )
        response = self.client.post(reverse('chat:upload_media'), {
            'file': uploaded,
            'group_id': self.group.pk,
        })
        data = response.json()
        self.assertNotIn('error', data)


class WebSocketMessageLimitsTest(TestCase):
    """MED-3: WebSocket consumer must enforce message limits."""

    def test_max_msg_length_constant_exists(self):
        """MAX_MSG_LENGTH should be defined and reasonable."""
        self.assertIsNotNone(MAX_MSG_LENGTH)
        self.assertGreater(MAX_MSG_LENGTH, 0)
        self.assertLessEqual(MAX_MSG_LENGTH, 10000,
                             "MAX_MSG_LENGTH should not be excessively large")

    def test_max_msg_length_value(self):
        """MAX_MSG_LENGTH should be 5000 as configured."""
        self.assertEqual(MAX_MSG_LENGTH, 5000)


class WebSocketConsumerCodeTest(TestCase):
    """Verify consumer code has proper error handling."""

    def test_dm_consumer_has_json_error_handling(self):
        """DirectMessageConsumer.receive() should handle JSONDecodeError."""
        import inspect
        from chat.consumers import DirectMessageConsumer
        source = inspect.getsource(DirectMessageConsumer.receive)
        self.assertIn('JSONDecodeError', source,
                      "DM consumer must catch JSONDecodeError")

    def test_group_consumer_has_json_error_handling(self):
        """GroupChatConsumer.receive() should handle JSONDecodeError."""
        import inspect
        from chat.consumers import GroupChatConsumer
        source = inspect.getsource(GroupChatConsumer.receive)
        self.assertIn('JSONDecodeError', source,
                      "Group consumer must catch JSONDecodeError")

    def test_dm_consumer_truncates_body(self):
        """DM consumer should truncate message body to MAX_MSG_LENGTH."""
        import inspect
        from chat.consumers import DirectMessageConsumer
        source = inspect.getsource(DirectMessageConsumer.receive)
        self.assertIn('MAX_MSG_LENGTH', source,
                      "DM consumer must use MAX_MSG_LENGTH to limit message size")

    def test_group_consumer_truncates_body(self):
        """Group consumer should truncate message body to MAX_MSG_LENGTH."""
        import inspect
        from chat.consumers import GroupChatConsumer
        source = inspect.getsource(GroupChatConsumer.receive)
        self.assertIn('MAX_MSG_LENGTH', source,
                      "Group consumer must use MAX_MSG_LENGTH to limit message size")


class TemplateXSSPreventionTest(TestCase):
    """HIGH-4: Verify templates use safe URL handling."""

    def test_room_template_uses_escattr(self):
        """room.html should use escAttr for media URLs."""
        with open('templates/chat/room.html', 'r') as f:
            content = f.read()
        self.assertIn('escAttr', content,
                      "room.html must use escAttr() for media URL escaping")
        self.assertNotIn("onclick=\"openLightbox('${data.media_url}')", content,
                         "room.html must NOT use unescaped media_url in onclick")
        self.assertIn('data-lightbox', content,
                      "room.html should use data-lightbox instead of inline onclick")

    def test_group_room_template_uses_escattr(self):
        """group_room.html should use escAttr for media URLs."""
        with open('templates/chat/group_room.html', 'r') as f:
            content = f.read()
        self.assertIn('escAttr', content,
                      "group_room.html must use escAttr() for media URL escaping")
        self.assertNotIn("onclick=\"openLightbox('${data.media_url}')", content,
                         "group_room.html must NOT use unescaped media_url in onclick")

    def test_room_template_uses_wss_detection(self):
        """room.html should auto-detect wss:// protocol."""
        with open('templates/chat/room.html', 'r') as f:
            content = f.read()
        self.assertIn("location.protocol === 'https:'", content,
                      "room.html must detect HTTPS for wss:// protocol")
        self.assertNotIn("= `ws://", content,
                         "room.html must NOT hardcode ws://")

    def test_group_room_template_uses_wss_detection(self):
        """group_room.html should auto-detect wss:// protocol."""
        with open('templates/chat/group_room.html', 'r') as f:
            content = f.read()
        self.assertIn("location.protocol === 'https:'", content,
                      "group_room.html must detect HTTPS for wss:// protocol")


class ChatAccessControlTest(TestCase):
    """Access control tests for chat views."""

    def setUp(self):
        self.client = Client()
        self.user1 = User.objects.create_user(
            email='user1@test.com', password='Pass123!',
            full_name='User One', is_verified=True,
        )
        self.user2 = User.objects.create_user(
            email='user2@test.com', password='Pass123!',
            full_name='User Two', is_verified=True,
        )

    def test_chat_index_requires_login(self):
        """Chat index should redirect unauthenticated users."""
        response = self.client.get(reverse('chat:index'))
        self.assertEqual(response.status_code, 302)

    def test_dm_room_requires_login(self):
        """DM room should redirect unauthenticated users."""
        response = self.client.get(reverse('chat:dm_room', args=[self.user2.pk]))
        self.assertEqual(response.status_code, 302)

    def test_cannot_chat_with_self(self):
        """User should not be able to open DM with themselves."""
        self.client.force_login(self.user1)
        response = self.client.get(reverse('chat:dm_room', args=[self.user1.pk]))
        self.assertEqual(response.status_code, 302)  # Redirected away

    def test_group_room_requires_membership(self):
        """Non-members should be denied access to group rooms."""
        group = ChatGroup.objects.create(name='Private', created_by=self.user1)
        GroupMember.objects.create(group=group, user=self.user1, role='admin')

        self.client.force_login(self.user2)
        response = self.client.get(reverse('chat:group_room', args=[group.pk]))
        self.assertEqual(response.status_code, 302)  # Redirected

    def test_only_admin_can_add_member(self):
        """Only admins should be able to add members."""
        group = ChatGroup.objects.create(name='Test', created_by=self.user1)
        GroupMember.objects.create(group=group, user=self.user1, role='admin')
        GroupMember.objects.create(group=group, user=self.user2, role='member')

        user3 = User.objects.create_user(
            email='user3@test.com', password='Pass123!',
            full_name='User Three', is_verified=True,
        )

        # Non-admin trying to add member
        self.client.force_login(self.user2)
        response = self.client.post(reverse('chat:add_member', args=[group.pk]), {
            'user_id': user3.pk,
        })
        self.assertFalse(
            GroupMember.objects.filter(group=group, user=user3).exists(),
            "Non-admin should not be able to add members"
        )

    def test_only_admin_can_remove_member(self):
        """Only admins should be able to remove members."""
        group = ChatGroup.objects.create(name='Test', created_by=self.user1)
        GroupMember.objects.create(group=group, user=self.user1, role='admin')
        GroupMember.objects.create(group=group, user=self.user2, role='member')

        # Non-admin trying to remove
        self.client.force_login(self.user2)
        self.client.post(reverse('chat:remove_member', args=[group.pk]), {
            'user_id': self.user1.pk,
        })
        self.assertTrue(
            GroupMember.objects.filter(group=group, user=self.user1).exists(),
            "Non-admin should not be able to remove members"
        )
