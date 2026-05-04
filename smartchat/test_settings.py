"""
Test settings — inherits from main settings but uses SQLite for speed.
Usage:  python manage.py test --settings=smartchat.test_settings
"""
from smartchat.settings import *  # noqa: F401, F403

# Use SQLite for tests (no MySQL CREATE DATABASE needed)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# Speed up password hashing in tests
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

# Use in-memory channel layer for tests
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer',
    },
}

# Console email backend for tests
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
