import re
from django import forms
from django.contrib.auth import get_user_model
from django.core.validators import RegexValidator

User = get_user_model()

# ──────────────────────────────────────────────
# Validators
# ──────────────────────────────────────────────
phone_validator = RegexValidator(
    regex=r'^\+?[1-9]\d{7,14}$',
    message='Enter a valid phone number (e.g. +919876543210). 8–15 digits, optional leading +.'
)


# ──────────────────────────────────────────────
# SIGNUP FORM
# ──────────────────────────────────────────────
class SignupForm(forms.Form):
    full_name = forms.CharField(
        min_length=2,
        max_length=70,
        widget=forms.TextInput(attrs={
            'class': 'form-control sc-input',
            'placeholder': 'Your full name',
            'autofocus': True,
        }),
        error_messages={
            'required': 'Full name is required.',
            'min_length': 'Name must be at least 2 characters.',
            'max_length': 'Name cannot exceed 150 characters.',
        }
    )
    email = forms.EmailField(
        max_length=70,
        widget=forms.EmailInput(attrs={
            'class': 'form-control sc-input',
            'placeholder': 'you@example.com',
        }),
        error_messages={
            'required': 'Email address is required.',
            'invalid': 'Enter a valid email address (e.g. you@example.com).',
            'max_length': 'Email cannot exceed 254 characters.',
        }
    )
    phone = forms.CharField(
        required=False,
        max_length=15,
        widget=forms.TextInput(attrs={
            'class': 'form-control sc-input',
            'placeholder': '+91 98765 43210 (optional)',
        }),
    )
    password = forms.CharField(
        min_length=8,
        max_length=128,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control sc-input',
            'placeholder': 'Min. 8 characters',
        }),
        error_messages={
            'required': 'Password is required.',
            'min_length': 'Password must be at least 8 characters.',
            'max_length': 'Password cannot exceed 128 characters.',
        }
    )
    confirm_password = forms.CharField(
        max_length=128,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control sc-input',
            'placeholder': 'Repeat password',
        }),
        error_messages={
            'required': 'Please confirm your password.',
        }
    )

    # ── Field-level clean methods ──

    def clean_full_name(self):
        val = self.cleaned_data.get('full_name', '').strip()
        # Collapse multiple spaces
        val = re.sub(r'\s+', ' ', val)
        
        if len(val) < 3:
            raise forms.ValidationError('Full name must be at least 3 characters.')
        
        # Block digits and common security-sensitive symbols
        # Allows international letters, spaces, hyphens, dots
        blocked_chars = r'[0-9!@#$%^&*()_+={}\[\]|\\:;"<>,?/~`]'
        if re.search(blocked_chars, val):
            raise forms.ValidationError('Name contains invalid characters. Please use letters only.')

        # Must have at least some letters (anything that isn't space/dot/dash)
        letters_only = re.sub(r'[\s\.\-]', '', val)
        if len(letters_only) < 2:
            raise forms.ValidationError('Name must contain at least 2 letters.')

        return val

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()

        # Enforce max length (RFC 5321)
        if len(email) > 254:
            raise forms.ValidationError('Email cannot exceed 254 characters.')

        if '..' in email:
            raise forms.ValidationError('Email address contains invalid characters.')

        if User.objects.filter(email=email).exists():
            raise forms.ValidationError(
                'Unable to register with this email. Please try a different one.'
            )
        return email

    def clean_phone(self):
        phone = self.cleaned_data.get('phone', '').strip()
        if not phone:
            return ''

        # Strip spaces, dashes, parentheses for normalization
        normalized = re.sub(r'[\s\-\(\)]', '', phone)

        # Re-validate normalized form
        if not re.match(r'^\+?[1-9]\d{7,14}$', normalized):
            raise forms.ValidationError(
                'Enter a valid phone number (e.g. +919876543210). 8–15 digits.'
            )

        return normalized

    def clean_password(self):
        password = self.cleaned_data['password']

        errors = []

        if not re.search(r'[A-Z]', password):
            errors.append('one uppercase letter')
        if not re.search(r'[a-z]', password):
            errors.append('one lowercase letter')
        if not re.search(r'\d', password):
            errors.append('one digit')
        if not re.search(r'[!@#$%^&*()_+\-=\[\]{};:\'",.<>?/\\|`~]', password):
            errors.append('one special character (!@#$%^&*...)')

        if errors:
            raise forms.ValidationError(
                f'Password must contain at least: {", ".join(errors)}.'
            )

        # Block common weak passwords
        common = [
            'password', '12345678', 'qwerty12', 'abcdefgh',
            'password1', 'admin123', 'iloveyou', 'welcome1',
        ]
        if password.lower() in common:
            raise forms.ValidationError(
                'This password is too common. Choose a stronger one.'
            )

        return password

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get('password')
        p2 = cleaned.get('confirm_password')
        if p1 and p2 and p1 != p2:
            self.add_error('confirm_password', 'Passwords do not match.')
        return cleaned


# ──────────────────────────────────────────────
# LOGIN FORM
# ──────────────────────────────────────────────
class LoginForm(forms.Form):
    email = forms.EmailField(
        max_length=254,
        widget=forms.EmailInput(attrs={
            'class': 'form-control sc-input',
            'placeholder': 'you@example.com',
            'autofocus': True,
        }),
        error_messages={
            'required': 'Email address is required.',
            'invalid': 'Enter a valid email address.',
        }
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control sc-input',
            'placeholder': 'Your password',
        }),
        error_messages={
            'required': 'Password is required.',
        }
    )


# ──────────────────────────────────────────────
# OTP VERIFY FORM
# ──────────────────────────────────────────────
class OTPVerifyForm(forms.Form):
    otp = forms.CharField(
        max_length=6,
        min_length=6,
        widget=forms.HiddenInput(attrs={'id': 'otp-combined'}),
        error_messages={
            'required': 'OTP is required.',
            'min_length': 'OTP must be exactly 6 digits.',
            'max_length': 'OTP must be exactly 6 digits.',
        }
    )

    def clean_otp(self):
        otp = self.cleaned_data.get('otp', '').strip()
        if not otp.isdigit():
            raise forms.ValidationError('OTP must be 6 digits.')
        return otp
