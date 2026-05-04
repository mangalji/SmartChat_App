import random
import string
from django.utils import timezone
from django.conf import settings
from django.core.mail import send_mail


def generate_otp(length=6):
    """Generate a numeric OTP of given length."""
    return ''.join(random.choices(string.digits, k=length))


def send_otp_email(user, otp_code, purpose):
    """Send OTP to user's email via console backend."""
    subject_map = {
        'signup': 'SmartChat — Verify your account',
        'login':  'SmartChat — Your login OTP',
    }
    subject = subject_map.get(purpose, 'SmartChat — OTP')
    message = f"""
Hi {user.full_name},

Your SmartChat OTP is:

  {otp_code}

This code expires in 5 minutes.
Do not share it with anyone.

— SmartChat Team
"""
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )


def create_otp(user, purpose):
    """
    Invalidate all previous OTPs for this user+purpose,
    create a fresh one, send it, and return the OTP instance.
    """
    from .models import OTP

    # Expire old OTPs
    OTP.objects.filter(user=user, purpose=purpose, is_used=False).update(is_used=True)

    code = generate_otp()
    otp  = OTP.objects.create(user=user, code=code, purpose=purpose)
    send_otp_email(user, code, purpose)
    return otp


def verify_otp(user, code, purpose):
    """
    Returns (True, None) on success.
    Returns (False, error_message) on failure.
    """
    from .models import OTP

    try:
        otp = OTP.objects.filter(
            user=user,
            code=code,
            purpose=purpose,
            is_used=False,
        ).latest('created_at')
    except OTP.DoesNotExist:
        return False, 'Invalid OTP. Please try again.'

    expiry_seconds = getattr(settings, 'OTP_EXPIRY_SECONDS', 300)
    age = (timezone.now() - otp.created_at).total_seconds()
    if age > expiry_seconds:
        otp.is_used = True
        otp.save(update_fields=['is_used'])
        return False, 'OTP has expired. Please request a new one.'

    otp.is_used = True
    otp.save(update_fields=['is_used'])
    return True, None
