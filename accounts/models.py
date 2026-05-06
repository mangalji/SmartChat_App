# Full model implemented in Phase 2
# Skeleton needed so migrations run cleanly

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    def create_user(self, email, username, password=None, **extra):
        if not email:
            raise ValueError('Email is required')
        if not username:
            raise ValueError('Username is required')
        email = self.normalize_email(email)
        user = self.model(email=email, username=username, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, username, password, **extra):
        extra.setdefault('is_staff', True)
        extra.setdefault('is_superuser', True)
        extra.setdefault('is_verified', True)
        return self.create_user(email, username, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    email       = models.EmailField(unique=True)
    username    = models.CharField(max_length=50, unique=True, db_index=True)
    full_name   = models.CharField(max_length=150)
    phone       = models.CharField(max_length=20, blank=True)
    avatar      = models.ImageField(upload_to='avatars/', blank=True, null=True)
    is_verified = models.BooleanField(default=False)
    is_active   = models.BooleanField(default=True)
    is_staff    = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    USERNAME_FIELD  = 'email'
    REQUIRED_FIELDS = ['username', 'full_name']
    objects = UserManager()

    def __str__(self):
        return self.username or self.email

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'


class OTP(models.Model):
    PURPOSE_CHOICES = [('signup', 'Signup'), ('login', 'Login')]
    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='otps')
    code       = models.CharField(max_length=6)
    purpose    = models.CharField(max_length=10, choices=PURPOSE_CHOICES)
    is_used    = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.user.email} — {self.code} ({self.purpose})'

    class Meta:
        verbose_name = 'OTP'
        verbose_name_plural = 'OTPs'
        ordering = ['-created_at']
