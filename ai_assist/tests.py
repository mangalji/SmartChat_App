"""
ai_assist/tests.py — Security tests for Gemini AI integration.

Covers:
  - HIGH-5: Gemini safety filters must NOT be BLOCK_NONE
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model

User = get_user_model()


class GeminiSafetySettingsTest(TestCase):
    """HIGH-5: Gemini safety filters must block harmful content."""

    def test_safety_settings_not_block_none(self):
        """Safety settings should NOT use BLOCK_NONE."""
        with open('ai_assist/gemini.py', 'r') as f:
            content = f.read()
        self.assertNotIn("'threshold': 'BLOCK_NONE'", content,
                         "Gemini safety filters must NOT be BLOCK_NONE")

    def test_safety_settings_use_block_medium(self):
        """Safety settings should use BLOCK_MEDIUM_AND_ABOVE or stricter."""
        with open('ai_assist/gemini.py', 'r') as f:
            content = f.read()
        self.assertIn('BLOCK_MEDIUM_AND_ABOVE', content,
                      "Gemini safety filters should use BLOCK_MEDIUM_AND_ABOVE")

    def test_all_four_categories_configured(self):
        """All 4 harm categories must have safety settings."""
        with open('ai_assist/gemini.py', 'r') as f:
            content = f.read()
        categories = [
            'HARM_CATEGORY_HARASSMENT',
            'HARM_CATEGORY_HATE_SPEECH',
            'HARM_CATEGORY_SEXUALLY_EXPLICIT',
            'HARM_CATEGORY_DANGEROUS_CONTENT',
        ]
        for cat in categories:
            self.assertIn(cat, content,
                          f"Safety category {cat} is missing from Gemini config")

    def test_safety_category_count(self):
        """Should have exactly 4 safety setting entries."""
        with open('ai_assist/gemini.py', 'r') as f:
            content = f.read()
        count = content.count('HARM_CATEGORY_')
        self.assertEqual(count, 4,
                         f"Expected 4 HARM_CATEGORY entries, found {count}")

    def test_model_name_is_current(self):
        """Gemini model should use a current model name, not deprecated."""
        with open('ai_assist/gemini.py', 'r') as f:
            content = f.read()
        self.assertNotIn('gemini-1.5-flash', content,
                         "gemini-1.5-flash is deprecated — use gemini-2.5-flash or newer")


class AIAssistAccessControlTest(TestCase):
    """AI assistant should require authentication."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='ai_test@test.com', password='Pass123!',
            full_name='AI Tester', is_verified=True,
        )

    def test_assistant_page_requires_login(self):
        """AI assistant page should require authentication."""
        response = self.client.get(reverse('ai_assist:assistant'))
        self.assertEqual(response.status_code, 302)

    def test_chat_endpoint_requires_login(self):
        """AI chat API should require authentication."""
        response = self.client.post(
            reverse('ai_assist:chat'),
            data='{"message": "hello"}',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 302)

    def test_chat_empty_message_returns_error(self):
        """Empty message should return error."""
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('ai_assist:chat'),
            data='{"message": ""}',
            content_type='application/json',
        )
        data = response.json()
        self.assertIn('error', data)

    def test_chat_invalid_json_returns_error(self):
        """Invalid JSON body should return error."""
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('ai_assist:chat'),
            data='not json at all',
            content_type='application/json',
        )
        data = response.json()
        self.assertIn('error', data)
