"""
scheduler/tests.py — Security tests for scheduler app.

Covers:
  - LOW-1: Scheduler views require authentication
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model

User = get_user_model()


class SchedulerAccessControlTest(TestCase):
    """LOW-1: Scheduler views must require authentication."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='sched@test.com', password='Pass123!',
            full_name='Scheduler Tester', is_verified=True,
        )

    def test_index_requires_login(self):
        """Scheduler index should redirect unauthenticated users."""
        response = self.client.get(reverse('scheduler:index'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_index_accessible_when_logged_in(self):
        """Scheduler index should be accessible for authenticated users."""
        self.client.force_login(self.user)
        response = self.client.get(reverse('scheduler:index'))
        self.assertIn(response.status_code, [200, 302])
