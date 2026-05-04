"""
tests/test_security_settings.py — Tests for Django settings security hardening.

Covers:
  - CRIT-2: SECRET_KEY has no insecure fallback
  - CRIT-3: DEBUG defaults safely, ALLOWED_HOSTS restricted
  - MED-1:  Security headers enabled in production mode
  - LOW-2:  No hardcoded database defaults
  - LOW-4:  Session cookie security
"""

from django.test import TestCase, override_settings
from django.conf import settings
import inspect


class SecretKeySecurityTest(TestCase):
    """CRIT-2: SECRET_KEY must not have an insecure fallback."""

    def test_secret_key_is_set(self):
        """SECRET_KEY should be set and non-empty."""
        self.assertTrue(bool(settings.SECRET_KEY), "SECRET_KEY is not set")

    def test_secret_key_not_default_insecure(self):
        """SECRET_KEY should not be the Django default insecure key."""
        self.assertNotEqual(
            settings.SECRET_KEY,
            'django-insecure-fallback-key',
            "SECRET_KEY is using the insecure fallback value"
        )
        self.assertFalse(
            settings.SECRET_KEY.startswith('django-insecure-'),
            "SECRET_KEY starts with 'django-insecure-' prefix"
        )

    def test_settings_file_has_no_default_secret(self):
        """settings.py should NOT have a default= for SECRET_KEY."""
        with open('smartchat/settings.py', 'r') as f:
            content = f.read()
        # Find the SECRET_KEY line
        for line in content.split('\n'):
            if 'SECRET_KEY' in line and 'config(' in line:
                self.assertNotIn('default=', line,
                                 "SECRET_KEY config() must NOT have a default fallback")
                break


class DebugAndAllowedHostsTest(TestCase):
    """CRIT-3: DEBUG and ALLOWED_HOSTS must be properly configured."""

    def test_production_allowed_hosts_no_wildcard(self):
        """settings.py should NOT allow wildcard in production mode."""
        with open('smartchat/settings.py', 'r') as f:
            content = f.read()
        # The wildcard should only appear inside 'if DEBUG:' block
        # Production block should use config() without default wildcard
        self.assertIn("if DEBUG:", content,
                      "settings.py should gate ALLOWED_HOSTS by DEBUG mode")
        # The else (production) block should call config() without a '*' default
        lines = content.split('\n')
        in_else = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('else:'):
                in_else = True
            if in_else and 'ALLOWED_HOSTS' in stripped:
                self.assertNotIn("'*'", stripped,
                                 "Production ALLOWED_HOSTS must NOT have '*' wildcard")
                break

    def test_allowed_hosts_not_empty(self):
        """ALLOWED_HOSTS should have at least one entry."""
        self.assertTrue(len(settings.ALLOWED_HOSTS) > 0,
                        "ALLOWED_HOSTS is empty")

    def test_debug_not_hardcoded_true(self):
        """settings.py should NOT have 'DEBUG = True' hardcoded."""
        with open('smartchat/settings.py', 'r') as f:
            content = f.read()
        # Check that DEBUG uses config()
        for line in content.split('\n'):
            stripped = line.strip()
            if stripped.startswith('DEBUG') and '=' in stripped and not stripped.startswith('#'):
                self.assertIn('config(', stripped,
                              "DEBUG should be loaded from config(), not hardcoded")
                break


class SecurityHeadersTest(TestCase):
    """MED-1: Security headers should be configured for production."""

    def test_settings_file_has_security_headers_block(self):
        """settings.py should have security headers that activate in production."""
        with open('smartchat/settings.py', 'r') as f:
            content = f.read()

        security_settings = [
            'SECURE_BROWSER_XSS_FILTER',
            'SECURE_CONTENT_TYPE_NOSNIFF',
            'SECURE_HSTS_SECONDS',
            'SECURE_SSL_REDIRECT',
            'SESSION_COOKIE_SECURE',
            'CSRF_COOKIE_SECURE',
            'CSRF_COOKIE_HTTPONLY',
            'X_FRAME_OPTIONS',
        ]

        for setting in security_settings:
            self.assertIn(setting, content,
                          f"{setting} not found in settings.py — missing security header")

    def test_security_headers_gated_by_debug(self):
        """Security headers should be gated by 'if not DEBUG'."""
        with open('smartchat/settings.py', 'r') as f:
            content = f.read()
        self.assertIn('if not DEBUG:', content,
                      "Security headers should be activated with 'if not DEBUG:' guard")


class SessionSecurityTest(TestCase):
    """Session cookie security settings."""

    def test_session_cookie_httponly(self):
        """SESSION_COOKIE_HTTPONLY should be True."""
        self.assertTrue(settings.SESSION_COOKIE_HTTPONLY,
                        "SESSION_COOKIE_HTTPONLY must be True to prevent JS access")

    def test_session_engine_is_db(self):
        """Session engine should be database-backed."""
        self.assertEqual(
            settings.SESSION_ENGINE,
            'django.contrib.sessions.backends.db',
        )

    def test_session_cookie_age_reasonable(self):
        """Session cookie age should be reasonable (not infinite)."""
        self.assertLessEqual(
            settings.SESSION_COOKIE_AGE, 86400 * 7,  # max 7 days
            "Session cookie age is too long"
        )


class DatabaseConfigTest(TestCase):
    """LOW-2: Database credentials should not have hardcoded defaults."""

    def test_settings_no_hardcoded_db_password(self):
        """DB_PASSWORD in settings.py should NOT have default='root'."""
        with open('smartchat/settings.py', 'r') as f:
            content = f.read()
        # Check DB config section
        self.assertNotIn("default='root'", content,
                         "Database config has hardcoded 'root' default — remove it")

    def test_settings_no_hardcoded_db_user(self):
        """DB_USER in settings.py should NOT have default='root'."""
        with open('smartchat/settings.py', 'r') as f:
            lines = f.readlines()
        for line in lines:
            if 'DB_USER' in line and 'config(' in line:
                self.assertNotIn("default='root'", line,
                                 "DB_USER has hardcoded 'root' default")


class PasswordValidationTest(TestCase):
    """Verify password validators are configured."""

    def test_password_validators_exist(self):
        """At least 4 password validators should be configured."""
        self.assertGreaterEqual(
            len(settings.AUTH_PASSWORD_VALIDATORS), 4,
            "Should have at least 4 password validators"
        )

    def test_min_length_validator_present(self):
        """MinimumLengthValidator should be in password validators."""
        validator_names = [v['NAME'] for v in settings.AUTH_PASSWORD_VALIDATORS]
        self.assertIn(
            'django.contrib.auth.password_validation.MinimumLengthValidator',
            validator_names,
        )
