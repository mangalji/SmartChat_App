from django import forms
from django.contrib.auth import get_user_model
from django.core.validators import RegexValidator

User = get_user_model()

phone_validator = RegexValidator(
    regex=r'^\+?1?\d{9,15}$',
    message='Enter a valid phone number (e.g. +919876543210).'
)


class SignupForm(forms.Form):
    full_name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control sc-input',
            'placeholder': 'Your full name',
            'autofocus': True,
        })
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control sc-input',
            'placeholder': 'you@example.com',
        })
    )
    phone = forms.CharField(
        required=False,
        validators=[phone_validator],
        widget=forms.TextInput(attrs={
            'class': 'form-control sc-input',
            'placeholder': '+91 98765 43210 (optional)',
        })
    )
    password = forms.CharField(
        min_length=8,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control sc-input',
            'placeholder': 'Min. 8 characters',
        })
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control sc-input',
            'placeholder': 'Repeat password',
        })
    )

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('An account with this email already exists.')
        return email

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get('password')
        p2 = cleaned.get('confirm_password')
        if p1 and p2 and p1 != p2:
            self.add_error('confirm_password', 'Passwords do not match.')
        return cleaned


class LoginForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control sc-input',
            'placeholder': 'you@example.com',
            'autofocus': True,
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control sc-input',
            'placeholder': 'Your password',
        })
    )


class OTPVerifyForm(forms.Form):
    otp = forms.CharField(
        max_length=6,
        min_length=6,
        widget=forms.HiddenInput(attrs={'id': 'otp-combined'})
    )

    def clean_otp(self):
        otp = self.cleaned_data.get('otp', '')
        if not otp.isdigit():
            raise forms.ValidationError('OTP must be 6 digits.')
        return otp
