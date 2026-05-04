"""
accounts/test_validations.py — Tests for field-level validation on SignupForm.

Covers every field:
  - full_name: required, min 2 chars, letters-only, no HTML, whitespace collapse
  - email: required, valid format, max 254, no double dots, duplicate detection
  - phone: optional, normalized, valid international format
  - password: min 8, uppercase + lowercase + digit + special, common password block
  - confirm_password: must match password
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model

from accounts.forms import SignupForm

User = get_user_model()


# Helper to build valid form data, then override specific fields for each test
def valid_data(**overrides):
    data = {
        'full_name': 'Raj Kumar',
        'email': 'testuser@example.com',
        'phone': '',
        'password': 'StrongP@ss1',
        'confirm_password': 'StrongP@ss1',
    }
    data.update(overrides)
    return data


# ══════════════════════════════════════════════
#  FULL NAME VALIDATION
# ══════════════════════════════════════════════
class FullNameValidationTest(TestCase):

    def test_valid_name(self):
        form = SignupForm(data=valid_data(full_name='Raj Kumar'))
        self.assertFalse(form.has_error('full_name'))

    def test_valid_name_with_hyphen(self):
        form = SignupForm(data=valid_data(full_name="Anne-Marie O'Brien"))
        self.assertFalse(form.has_error('full_name'))

    def test_valid_name_with_period(self):
        form = SignupForm(data=valid_data(full_name='Dr. Smith'))
        self.assertFalse(form.has_error('full_name'))

    def test_empty_name_rejected(self):
        form = SignupForm(data=valid_data(full_name=''))
        self.assertTrue(form.has_error('full_name'))

    def test_whitespace_only_name_rejected(self):
        form = SignupForm(data=valid_data(full_name='   '))
        self.assertTrue(form.has_error('full_name'))

    def test_single_char_name_rejected(self):
        """Names shorter than 2 characters should be rejected."""
        form = SignupForm(data=valid_data(full_name='A'))
        self.assertTrue(form.has_error('full_name'))

    def test_two_char_name_accepted(self):
        form = SignupForm(data=valid_data(full_name='Al'))
        self.assertFalse(form.has_error('full_name'))

    def test_numbers_in_name_rejected(self):
        """Names with digits should be rejected."""
        form = SignupForm(data=valid_data(full_name='User123'))
        self.assertTrue(form.has_error('full_name'))

    def test_special_chars_in_name_rejected(self):
        """Names with special characters like @, #, ! should be rejected."""
        form = SignupForm(data=valid_data(full_name='User@Name'))
        self.assertTrue(form.has_error('full_name'))

    def test_html_injection_in_name_rejected(self):
        """HTML/script tags in name should be rejected."""
        form = SignupForm(data=valid_data(full_name='<script>alert(1)</script>'))
        self.assertTrue(form.has_error('full_name'))

    def test_name_with_angle_brackets_rejected(self):
        form = SignupForm(data=valid_data(full_name='User <b>bold</b>'))
        self.assertTrue(form.has_error('full_name'))

    def test_name_with_curly_braces_rejected(self):
        form = SignupForm(data=valid_data(full_name='User {test}'))
        self.assertTrue(form.has_error('full_name'))

    def test_name_with_semicolon_rejected(self):
        form = SignupForm(data=valid_data(full_name='DROP; TABLE'))
        self.assertTrue(form.has_error('full_name'))

    def test_multiple_spaces_collapsed(self):
        """Multiple consecutive spaces should be collapsed to one."""
        form = SignupForm(data=valid_data(full_name='Raj    Kumar'))
        self.assertFalse(form.has_error('full_name'))
        if form.is_valid():
            self.assertEqual(form.cleaned_data['full_name'], 'Raj Kumar')

    def test_leading_trailing_spaces_stripped(self):
        """Leading and trailing spaces should be stripped."""
        form = SignupForm(data=valid_data(full_name='  Raj Kumar  '))
        self.assertFalse(form.has_error('full_name'))
        if form.is_valid():
            self.assertEqual(form.cleaned_data['full_name'], 'Raj Kumar')

    def test_max_length_151_rejected(self):
        """Names over 150 characters should be rejected."""
        long_name = 'A' * 151
        form = SignupForm(data=valid_data(full_name=long_name))
        self.assertTrue(form.has_error('full_name'))

    def test_max_length_150_accepted(self):
        """Names exactly 150 characters should be accepted."""
        long_name = 'A' * 150
        form = SignupForm(data=valid_data(full_name=long_name))
        self.assertFalse(form.has_error('full_name'))

    def test_only_dots_rejected(self):
        """Name with only dots and spaces should be rejected."""
        form = SignupForm(data=valid_data(full_name='.. . .'))
        self.assertTrue(form.has_error('full_name'))

    def test_only_hyphens_rejected(self):
        form = SignupForm(data=valid_data(full_name='---'))
        self.assertTrue(form.has_error('full_name'))


# ══════════════════════════════════════════════
#  EMAIL VALIDATION
# ══════════════════════════════════════════════
class EmailValidationTest(TestCase):

    def test_valid_email(self):
        form = SignupForm(data=valid_data(email='user@example.com'))
        self.assertFalse(form.has_error('email'))

    def test_empty_email_rejected(self):
        form = SignupForm(data=valid_data(email=''))
        self.assertTrue(form.has_error('email'))

    def test_invalid_email_no_at(self):
        form = SignupForm(data=valid_data(email='userexample.com'))
        self.assertTrue(form.has_error('email'))

    def test_invalid_email_no_domain(self):
        form = SignupForm(data=valid_data(email='user@'))
        self.assertTrue(form.has_error('email'))

    def test_invalid_email_no_tld(self):
        form = SignupForm(data=valid_data(email='user@example'))
        self.assertTrue(form.has_error('email'))

    def test_email_normalized_to_lowercase(self):
        """Email should be lowercased during cleaning."""
        form = SignupForm(data=valid_data(email='User@EXAMPLE.COM'))
        if not form.has_error('email'):
            self.assertEqual(form.cleaned_data['email'], 'user@example.com')

    def test_email_with_double_dots_rejected(self):
        form = SignupForm(data=valid_data(email='user@example..com'))
        self.assertTrue(form.has_error('email'))

    def test_email_exceeding_254_chars_rejected(self):
        long_local = 'a' * 250
        form = SignupForm(data=valid_data(email=f'{long_local}@example.com'))
        self.assertTrue(form.has_error('email'))

    def test_duplicate_email_rejected(self):
        """Duplicate email should show generic error (no user enumeration)."""
        User.objects.create_user(
            email='taken@example.com', password='Pass123!',
            full_name='Existing', is_verified=True,
        )
        form = SignupForm(data=valid_data(email='taken@example.com'))
        self.assertTrue(form.has_error('email'))

    def test_duplicate_email_case_insensitive(self):
        """Email uniqueness check should be case-insensitive."""
        User.objects.create_user(
            email='taken@example.com', password='Pass123!',
            full_name='Existing', is_verified=True,
        )
        form = SignupForm(data=valid_data(email='TAKEN@EXAMPLE.COM'))
        self.assertTrue(form.has_error('email'))

    def test_email_with_spaces_rejected(self):
        form = SignupForm(data=valid_data(email='user @example.com'))
        self.assertTrue(form.has_error('email'))

    def test_email_with_valid_subdomain(self):
        form = SignupForm(data=valid_data(email='user@mail.example.com'))
        self.assertFalse(form.has_error('email'))


# ══════════════════════════════════════════════
#  PHONE VALIDATION
# ══════════════════════════════════════════════
class PhoneValidationTest(TestCase):

    def test_phone_is_optional(self):
        """Phone should be optional — empty is fine."""
        form = SignupForm(data=valid_data(phone=''))
        self.assertFalse(form.has_error('phone'))

    def test_valid_indian_phone(self):
        form = SignupForm(data=valid_data(phone='+919876543210'))
        self.assertFalse(form.has_error('phone'))

    def test_valid_phone_without_plus(self):
        form = SignupForm(data=valid_data(phone='9876543210'))
        self.assertFalse(form.has_error('phone'))

    def test_valid_us_phone(self):
        form = SignupForm(data=valid_data(phone='+12025551234'))
        self.assertFalse(form.has_error('phone'))

    def test_phone_with_spaces_normalized(self):
        """Phone with spaces should be normalized."""
        form = SignupForm(data=valid_data(phone='+91 98765 43210'))
        self.assertFalse(form.has_error('phone'))
        if form.is_valid():
            self.assertEqual(form.cleaned_data['phone'], '+919876543210')

    def test_phone_with_dashes_normalized(self):
        """Phone with dashes should be normalized."""
        form = SignupForm(data=valid_data(phone='+91-9876-543210'))
        self.assertFalse(form.has_error('phone'))
        if form.is_valid():
            self.assertEqual(form.cleaned_data['phone'], '+919876543210')

    def test_phone_with_parentheses_normalized(self):
        form = SignupForm(data=valid_data(phone='+1 (202) 555-1234'))
        self.assertFalse(form.has_error('phone'))
        if form.is_valid():
            self.assertEqual(form.cleaned_data['phone'], '+12025551234')

    def test_too_short_phone_rejected(self):
        """Phone shorter than 8 digits should be rejected."""
        form = SignupForm(data=valid_data(phone='12345'))
        self.assertTrue(form.has_error('phone'))

    def test_too_long_phone_rejected(self):
        """Phone longer than 15 digits should be rejected."""
        form = SignupForm(data=valid_data(phone='+1234567890123456'))
        self.assertTrue(form.has_error('phone'))

    def test_letters_in_phone_rejected(self):
        form = SignupForm(data=valid_data(phone='+91abc123'))
        self.assertTrue(form.has_error('phone'))

    def test_phone_starting_with_zero_rejected(self):
        """Phone starting with 0 after + should be rejected."""
        form = SignupForm(data=valid_data(phone='+091234567890'))
        self.assertTrue(form.has_error('phone'))


# ══════════════════════════════════════════════
#  PASSWORD VALIDATION
# ══════════════════════════════════════════════
class PasswordValidationTest(TestCase):

    def test_valid_strong_password(self):
        form = SignupForm(data=valid_data(
            password='MyP@ss123', confirm_password='MyP@ss123'
        ))
        self.assertFalse(form.has_error('password'))

    def test_too_short_password_rejected(self):
        """Password shorter than 8 characters should be rejected."""
        form = SignupForm(data=valid_data(
            password='Aa1!', confirm_password='Aa1!'
        ))
        self.assertTrue(form.has_error('password'))

    def test_password_without_uppercase_rejected(self):
        form = SignupForm(data=valid_data(
            password='lowercase1!', confirm_password='lowercase1!'
        ))
        self.assertTrue(form.has_error('password'))
        errors = form.errors['password']
        self.assertTrue(any('uppercase' in str(e).lower() for e in errors))

    def test_password_without_lowercase_rejected(self):
        form = SignupForm(data=valid_data(
            password='UPPERCASE1!', confirm_password='UPPERCASE1!'
        ))
        self.assertTrue(form.has_error('password'))
        errors = form.errors['password']
        self.assertTrue(any('lowercase' in str(e).lower() for e in errors))

    def test_password_without_digit_rejected(self):
        form = SignupForm(data=valid_data(
            password='NoDigits!@', confirm_password='NoDigits!@'
        ))
        self.assertTrue(form.has_error('password'))
        errors = form.errors['password']
        self.assertTrue(any('digit' in str(e).lower() for e in errors))

    def test_password_without_special_char_rejected(self):
        form = SignupForm(data=valid_data(
            password='NoSpecial1A', confirm_password='NoSpecial1A'
        ))
        self.assertTrue(form.has_error('password'))
        errors = form.errors['password']
        self.assertTrue(any('special' in str(e).lower() for e in errors))

    def test_common_password_rejected(self):
        """Common passwords should be blocked."""
        for pwd in ['password', 'Password', '12345678', 'qwerty12']:
            form = SignupForm(data=valid_data(
                password=pwd, confirm_password=pwd
            ))
            self.assertTrue(
                form.has_error('password'),
                f"Common password '{pwd}' should be rejected"
            )

    def test_password_with_all_requirements(self):
        """Password meeting all requirements should pass."""
        passwords = ['Test@1234', 'Str0ng!Pass', 'H3llo#World', 'P@$$w0rd!X']
        for pwd in passwords:
            form = SignupForm(data=valid_data(
                password=pwd, confirm_password=pwd
            ))
            self.assertFalse(
                form.has_error('password'),
                f"Valid password '{pwd}' was rejected: {form.errors.get('password')}"
            )

    def test_password_max_length_exceeded(self):
        """Password over 128 characters should be rejected."""
        long_pwd = 'Aa1!' * 33  # 132 characters
        form = SignupForm(data=valid_data(
            password=long_pwd, confirm_password=long_pwd
        ))
        self.assertTrue(form.has_error('password'))

    def test_empty_password_rejected(self):
        form = SignupForm(data=valid_data(password=''))
        self.assertTrue(form.has_error('password'))


# ══════════════════════════════════════════════
#  CONFIRM PASSWORD VALIDATION
# ══════════════════════════════════════════════
class ConfirmPasswordValidationTest(TestCase):

    def test_matching_passwords_accepted(self):
        form = SignupForm(data=valid_data(
            password='Test@1234', confirm_password='Test@1234'
        ))
        self.assertFalse(form.has_error('confirm_password'))

    def test_mismatched_passwords_rejected(self):
        form = SignupForm(data=valid_data(
            password='Test@1234', confirm_password='Different@1'
        ))
        self.assertTrue(form.has_error('confirm_password'))
        errors = form.errors['confirm_password']
        self.assertTrue(any('match' in str(e).lower() for e in errors))

    def test_empty_confirm_password_rejected(self):
        form = SignupForm(data=valid_data(confirm_password=''))
        self.assertTrue(form.has_error('confirm_password'))


# ══════════════════════════════════════════════
#  FULL FORM INTEGRATION TESTS
# ══════════════════════════════════════════════
class SignupFormIntegrationTest(TestCase):

    def test_all_valid_fields_pass(self):
        """Form with all valid fields should be valid."""
        form = SignupForm(data=valid_data())
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")

    def test_all_valid_with_phone(self):
        """Form with valid phone should also pass."""
        form = SignupForm(data=valid_data(phone='+919876543210'))
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")

    def test_multiple_errors_reported(self):
        """Form should report errors on all invalid fields simultaneously."""
        form = SignupForm(data={
            'full_name': '',
            'email': 'invalid',
            'phone': 'abc',
            'password': 'weak',
            'confirm_password': '',
        })
        self.assertFalse(form.is_valid())
        self.assertGreater(len(form.errors), 2,
                           "Multiple invalid fields should produce multiple errors")


class SignupViewIntegrationTest(TestCase):
    """Test validation through the actual signup view."""

    def setUp(self):
        self.client = Client()

    def test_signup_with_weak_password_shows_error(self):
        """Signup view should show password validation errors."""
        response = self.client.post(reverse('accounts:signup'), {
            'full_name': 'Test User',
            'email': 'new@test.com',
            'password': 'weakpass',
            'confirm_password': 'weakpass',
        })
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        # Should show password requirement errors
        self.assertTrue(
            'uppercase' in content.lower() or 'special' in content.lower() or 'digit' in content.lower(),
            "Signup should show specific password requirement errors"
        )

    def test_signup_with_invalid_name_shows_error(self):
        response = self.client.post(reverse('accounts:signup'), {
            'full_name': '123',
            'email': 'new@test.com',
            'password': 'Test@1234',
            'confirm_password': 'Test@1234',
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('full_name', response.context['form'].errors)

    def test_successful_signup_redirects(self):
        """Valid signup should redirect to OTP verification."""
        response = self.client.post(reverse('accounts:signup'), {
            'full_name': 'Raj Kumar',
            'email': 'newuser@test.com',
            'phone': '+919876543210',
            'password': 'Test@1234',
            'confirm_password': 'Test@1234',
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn('verify', response.url)
