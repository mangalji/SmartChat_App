"""
WSGI config for SmartChat project.
Used for non-async fallback. Primary server is Daphne (ASGI).
"""

import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smartchat.settings')
application = get_wsgi_application()
