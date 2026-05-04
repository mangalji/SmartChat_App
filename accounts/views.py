from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, get_user_model
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required

from .forms import SignupForm, LoginForm, OTPVerifyForm
from .utils import create_otp, verify_otp

User = get_user_model()


# ──────────────────────────────────────────────
# SIGNUP
# ──────────────────────────────────────────────
@require_http_methods(['GET', 'POST'])
def signup_view(request):
    if request.user.is_authenticated:
        return redirect('chat:index')

    form = SignupForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        cd = form.cleaned_data

        # Create unverified user
        user = User.objects.create_user(
            email=cd['email'],
            password=cd['password'],
            full_name=cd['full_name'],
            phone=cd.get('phone', ''),
            is_verified=False,
        )

        # Generate & email OTP
        create_otp(user, purpose='signup')

        # Store user pk in session for OTP step
        request.session['otp_user_id'] = user.pk
        request.session['otp_purpose']  = 'signup'

        messages.info(request, f'OTP sent to {user.email}. Check your console.')
        return redirect('accounts:verify_otp')

    return render(request, 'accounts/signup.html', {'form': form})


# ──────────────────────────────────────────────
# LOGIN
# ──────────────────────────────────────────────
@require_http_methods(['GET', 'POST'])
def login_view(request):
    if request.user.is_authenticated:
        return redirect('chat:index')

    form = LoginForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        cd    = form.cleaned_data
        email = cd['email'].lower()

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            messages.error(request, 'No account found with that email.')
            return render(request, 'accounts/login.html', {'form': form})

        if not user.check_password(cd['password']):
            messages.error(request, 'Incorrect password.')
            return render(request, 'accounts/login.html', {'form': form})

        if not user.is_verified:
            # Re-send signup OTP so they can verify
            create_otp(user, purpose='signup')
            request.session['otp_user_id'] = user.pk
            request.session['otp_purpose']  = 'signup'
            messages.warning(request, 'Account not verified. OTP sent to your email.')
            return redirect('accounts:verify_otp')

        # Send login OTP
        create_otp(user, purpose='login')
        request.session['otp_user_id'] = user.pk
        request.session['otp_purpose']  = 'login'

        messages.info(request, f'OTP sent to {user.email}. Check your console.')
        return redirect('accounts:verify_otp')

    return render(request, 'accounts/login.html', {'form': form})


# ──────────────────────────────────────────────
# VERIFY OTP
# ──────────────────────────────────────────────
@require_http_methods(['GET', 'POST'])
def verify_otp_view(request):
    user_id = request.session.get('otp_user_id')
    purpose = request.session.get('otp_purpose')

    if not user_id or not purpose:
        messages.error(request, 'Session expired. Please start again.')
        return redirect('accounts:login')

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        messages.error(request, 'User not found.')
        return redirect('accounts:login')

    form = OTPVerifyForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        code = form.cleaned_data['otp']
        ok, error = verify_otp(user, code, purpose)

        if not ok:
            messages.error(request, error)
            return render(request, 'accounts/verify_otp.html', {
                'form': form, 'email': user.email, 'purpose': purpose
            })

        # Mark verified on signup
        if purpose == 'signup':
            user.is_verified = True
            user.save(update_fields=['is_verified'])

        # Log user in via Django session
        login(request, user, backend='accounts.backends.EmailBackend')

        # Clean session keys
        request.session.pop('otp_user_id', None)
        request.session.pop('otp_purpose', None)

        messages.success(request, f'Welcome, {user.full_name}!')
        return redirect('chat:index')

    return render(request, 'accounts/verify_otp.html', {
        'form': form, 'email': user.email, 'purpose': purpose
    })


# ──────────────────────────────────────────────
# RESEND OTP
# ──────────────────────────────────────────────
@require_http_methods(['POST'])
def resend_otp_view(request):
    user_id = request.session.get('otp_user_id')
    purpose = request.session.get('otp_purpose')

    if not user_id or not purpose:
        messages.error(request, 'Session expired.')
        return redirect('accounts:login')

    try:
        user = User.objects.get(pk=user_id)
        create_otp(user, purpose=purpose)
        messages.success(request, 'New OTP sent. Check your console.')
    except User.DoesNotExist:
        messages.error(request, 'User not found.')

    return redirect('accounts:verify_otp')


# ──────────────────────────────────────────────
# LOGOUT
# ──────────────────────────────────────────────
@require_http_methods(['POST'])
def logout_view(request):
    logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('accounts:login')
