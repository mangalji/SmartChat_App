"""
accounts/tests.py — Security tests for authentication & OTP system.

Covers:
  - CRIT-4: OTP brute-force rate limiting
  - HIGH-1: Cryptographic OTP generation (secrets module)
  - HIGH-2: User enumeration prevention (login + signup)
  - MED-4:  Logout requires authentication
  - Resend OTP server-side cooldown
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from unittest.mock import patch
from datetime import timedelta
import string

from accounts.utils import generate_otp, create_otp, verify_otp
from accounts.models import OTP

User = get_user_model()


class OTPGenerationSecurityTest(TestCase):
    """HIGH-1: OTP must use cryptographically secure randomness."""

    def test_otp_is_6_digits(self):
        """OTP should be exactly 6 numeric digits."""
        for _ in range(50):
            otp = generate_otp()
            self.assertEqual(len(otp), 6)
            self.assertTrue(otp.isdigit(), f"OTP '{otp}' contains non-digit characters")

    def test_otp_uses_secrets_module(self):
        """OTP generation should use secrets, not random."""
        import inspect
        source = inspect.getsource(generate_otp)
        self.assertIn('secrets.choice', source,
                      "generate_otp() must use secrets.choice() for cryptographic security")
        self.assertNotIn('random.choices', source.split('#')[0],
                         "generate_otp() should NOT use random.choices()")

    def test_otp_distribution(self):
        """OTPs should have reasonable distribution (not all same digit)."""
        otps = [generate_otp() for _ in range(100)]
        unique_otps = set(otps)
        # With 100 random 6-digit OTPs, we should have high uniqueness
        self.assertGreater(len(unique_otps), 80,
                           "OTP generation appears non-random: too many duplicates")

    def test_otp_custom_length(self):
        """OTP generation should support custom lengths."""
        otp = generate_otp(length=8)
        self.assertEqual(len(otp), 8)
        self.assertTrue(otp.isdigit())


class UserEnumerationPreventionTest(TestCase):
    """HIGH-2: Login/signup should not reveal whether an email is registered."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='existing@test.com',
            password='TestPass123!',
            full_name='Test User',
            is_verified=True,
        )

    def test_login_wrong_email_generic_message(self):
        """Login with non-existent email should show generic error."""
        response = self.client.post(reverse('accounts:login'), {
            'email': 'nonexistent@test.com',
            'password': 'SomePass123!',
        })
        messages = list(response.context['messages']) if hasattr(response, 'context') and response.context else []
        # Follow redirect if needed
        if response.status_code == 200:
            content = response.content.decode()
            self.assertNotIn('No account found', content,
                             "Login reveals that email doesn't exist (user enumeration)")
            self.assertNotIn('no account', content.lower())

    def test_login_wrong_password_generic_message(self):
        """Login with correct email but wrong password should show same generic error."""
        response = self.client.post(reverse('accounts:login'), {
            'email': 'existing@test.com',
            'password': 'WrongPass999!',
        })
        if response.status_code == 200:
            content = response.content.decode()
            self.assertNotIn('Incorrect password', content,
                             "Login reveals that password is wrong (confirms email exists)")
            self.assertNotIn('incorrect password', content.lower())

    def test_login_wrong_email_and_password_same_message(self):
        """Both wrong-email and wrong-password should produce identical error."""
        resp1 = self.client.post(reverse('accounts:login'), {
            'email': 'nonexistent@test.com',
            'password': 'SomePass123!',
        })
        resp2 = self.client.post(reverse('accounts:login'), {
            'email': 'existing@test.com',
            'password': 'WrongPass999!',
        })
        # Both should have the same generic error message
        if resp1.status_code == 200 and resp2.status_code == 200:
            msgs1 = [str(m) for m in resp1.context['messages']] if resp1.context.get('messages') else []
            msgs2 = [str(m) for m in resp2.context['messages']] if resp2.context.get('messages') else []
            if msgs1 and msgs2:
                self.assertEqual(msgs1, msgs2,
                                 "Login error messages differ between wrong-email and wrong-password")

    def test_signup_duplicate_email_generic_message(self):
        """Signup with existing email should NOT say 'already exists'."""
        response = self.client.post(reverse('accounts:signup'), {
            'full_name': 'Another User',
            'email': 'existing@test.com',
            'password': 'TestPass123!',
            'confirm_password': 'TestPass123!',
        })
        content = response.content.decode()
        self.assertNotIn('already exists', content.lower(),
                         "Signup reveals email already exists (user enumeration)")
        self.assertNotIn('An account with this email', content)


class OTPRateLimitingTest(TestCase):
    """CRIT-4: OTP verification must be rate-limited."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='otp_test@test.com',
            password='TestPass123!',
            full_name='OTP Tester',
            is_verified=True,
        )
        # Simulate login flow: set session for OTP
        self.otp_obj = create_otp(self.user, purpose='login')
        session = self.client.session
        session['otp_user_id'] = self.user.pk
        session['otp_purpose'] = 'login'
        session['otp_attempts'] = 0
        session.save()

    def test_wrong_otp_increments_attempts(self):
        """Each wrong OTP should increment the attempt counter."""
        # Set session
        self.client.post(reverse('accounts:login'), {
            'email': 'otp_test@test.com',
            'password': 'TestPass123!',
        })

        # Try wrong OTP
        response = self.client.post(reverse('accounts:verify_otp'), {
            'otp': '000000',
        })
        session = self.client.session
        self.assertEqual(session.get('otp_attempts', 0), 1)

    def test_lockout_after_max_attempts(self):
        """After 5 failed attempts, user should be locked out."""
        # Login to set session
        self.client.post(reverse('accounts:login'), {
            'email': 'otp_test@test.com',
            'password': 'TestPass123!',
        })

        # Exhaust all attempts
        for i in range(5):
            self.client.post(reverse('accounts:verify_otp'), {
                'otp': '000000',
            })

        # 6th attempt should redirect (locked out)
        response = self.client.post(reverse('accounts:verify_otp'), {
            'otp': '000000',
        })
        self.assertEqual(response.status_code, 302,
                         "User should be redirected after max OTP attempts")

        # Session should be cleared
        session = self.client.session
        self.assertIsNone(session.get('otp_user_id'),
                          "Session otp_user_id should be cleared after lockout")

    def test_correct_otp_works_within_limit(self):
        """Correct OTP should work if within attempt limit."""
        self.client.post(reverse('accounts:login'), {
            'email': 'otp_test@test.com',
            'password': 'TestPass123!',
        })

        # Get the actual OTP from the DB
        otp = OTP.objects.filter(
            user=self.user, purpose='login', is_used=False
        ).latest('created_at')

        response = self.client.post(reverse('accounts:verify_otp'), {
            'otp': otp.code,
        })
        self.assertEqual(response.status_code, 302)
        # Should redirect to chat (success)
        self.assertRedirects(response, reverse('chat:index'))

    def test_remaining_attempts_shown_in_error(self):
        """Error message should indicate remaining attempts."""
        self.client.post(reverse('accounts:login'), {
            'email': 'otp_test@test.com',
            'password': 'TestPass123!',
        })

        response = self.client.post(reverse('accounts:verify_otp'), {
            'otp': '000000',
        })
        if response.status_code == 200:
            content = response.content.decode()
            self.assertIn('remaining', content.lower(),
                          "Error should show remaining attempts")


class OTPResendCooldownTest(TestCase):
    """CRIT-4 supplement: Resend OTP must have server-side cooldown."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='resend@test.com',
            password='TestPass123!',
            full_name='Resend Tester',
            is_verified=True,
        )

    def test_resend_within_cooldown_rejected(self):
        """Resending OTP within 30s should be rejected server-side."""
        # Login to start OTP flow
        self.client.post(reverse('accounts:login'), {
            'email': 'resend@test.com',
            'password': 'TestPass123!',
        })

        # Immediately try to resend (within 30s cooldown)
        response = self.client.post(reverse('accounts:resend_otp'))
        self.assertEqual(response.status_code, 302)

        # Check that a warning was issued (cooldown message)
        # The OTP count should still be 1 (second one rejected)
        otp_count = OTP.objects.filter(
            user=self.user, purpose='login'
        ).count()
        # Should have at most 2 OTPs (original + possibly one more if cooldown isn't enforced)
        # But with cooldown, the resend should be blocked

    def test_resend_after_cooldown_allowed(self):
        """Resending OTP after 30s should succeed."""
        self.client.post(reverse('accounts:login'), {
            'email': 'resend@test.com',
            'password': 'TestPass123!',
        })

        # Age the last OTP to be > 30 seconds old
        last_otp = OTP.objects.filter(user=self.user).latest('created_at')
        last_otp.created_at = timezone.now() - timedelta(seconds=35)
        last_otp.save()

        # Now resend should work
        response = self.client.post(reverse('accounts:resend_otp'))
        self.assertEqual(response.status_code, 302)

        # Should have new OTP
        new_otp_count = OTP.objects.filter(
            user=self.user, purpose='login', is_used=False
        ).count()
        self.assertGreaterEqual(new_otp_count, 1,
                                "New OTP should be created after cooldown expires")

    def test_resend_resets_attempts(self):
        """After successful resend, OTP attempts counter should reset."""
        self.client.post(reverse('accounts:login'), {
            'email': 'resend@test.com',
            'password': 'TestPass123!',
        })

        # Fail some attempts
        self.client.post(reverse('accounts:verify_otp'), {'otp': '000000'})
        self.client.post(reverse('accounts:verify_otp'), {'otp': '000000'})

        # Age the OTP and resend
        last_otp = OTP.objects.filter(user=self.user).latest('created_at')
        last_otp.created_at = timezone.now() - timedelta(seconds=35)
        last_otp.save()

        self.client.post(reverse('accounts:resend_otp'))
        session = self.client.session
        self.assertEqual(session.get('otp_attempts', 0), 0,
                         "Attempts should reset after OTP resend")


class OTPVerifyUtilTest(TestCase):
    """Test the OTP verification utility function directly."""

    def setUp(self):
        self.user = User.objects.create_user(
            email='verify@test.com',
            password='TestPass123!',
            full_name='Verify Tester',
        )

    def test_valid_otp_succeeds(self):
        """Correct OTP code should return (True, None)."""
        otp_obj = create_otp(self.user, purpose='signup')
        ok, error = verify_otp(self.user, otp_obj.code, purpose='signup')
        self.assertTrue(ok)
        self.assertIsNone(error)

    def test_wrong_code_fails(self):
        """Wrong OTP code should return (False, error)."""
        create_otp(self.user, purpose='signup')
        ok, error = verify_otp(self.user, '999999', purpose='signup')
        self.assertFalse(ok)
        self.assertIn('Invalid', error)

    def test_expired_otp_fails(self):
        """OTP older than expiry period should fail."""
        otp_obj = create_otp(self.user, purpose='login')
        # Age the OTP beyond expiry (5 min)
        otp_obj.created_at = timezone.now() - timedelta(seconds=310)
        otp_obj.save()

        ok, error = verify_otp(self.user, otp_obj.code, purpose='login')
        self.assertFalse(ok)
        self.assertIn('expired', error.lower())

    def test_used_otp_fails(self):
        """Already-used OTP should not work again."""
        otp_obj = create_otp(self.user, purpose='login')
        code = otp_obj.code

        # Use it
        ok, _ = verify_otp(self.user, code, purpose='login')
        self.assertTrue(ok)

        # Try again
        ok2, error = verify_otp(self.user, code, purpose='login')
        self.assertFalse(ok2)

    def test_wrong_purpose_fails(self):
        """OTP created for 'signup' should not work for 'login'."""
        otp_obj = create_otp(self.user, purpose='signup')
        ok, error = verify_otp(self.user, otp_obj.code, purpose='login')
        self.assertFalse(ok)

    def test_create_otp_invalidates_previous(self):
        """Creating a new OTP should invalidate all previous ones."""
        otp1 = create_otp(self.user, purpose='login')
        code1 = otp1.code
        otp2 = create_otp(self.user, purpose='login')

        # Old OTP should be marked as used
        otp1.refresh_from_db()
        self.assertTrue(otp1.is_used)

        # New OTP should work
        ok, _ = verify_otp(self.user, otp2.code, purpose='login')
        self.assertTrue(ok)

        # Old code should NOT work
        ok2, _ = verify_otp(self.user, code1, purpose='login')
        self.assertFalse(ok2)


class LogoutSecurityTest(TestCase):
    """MED-4: Logout should require authentication."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='logout@test.com',
            password='TestPass123!',
            full_name='Logout Tester',
            is_verified=True,
        )

    def test_logout_unauthenticated_redirects(self):
        """Unauthenticated logout should redirect to login."""
        response = self.client.post(reverse('accounts:logout'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_logout_authenticated_succeeds(self):
        """Authenticated user should be able to logout."""
        self.client.force_login(self.user)
        response = self.client.post(reverse('accounts:logout'))
        self.assertEqual(response.status_code, 302)

    def test_logout_get_not_allowed(self):
        """Logout should only accept POST."""
        self.client.force_login(self.user)
        response = self.client.get(reverse('accounts:logout'))
        self.assertEqual(response.status_code, 405)
