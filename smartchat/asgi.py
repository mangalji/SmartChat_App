"""
ASGI config for SmartChat project.
Handles both HTTP (Django) and WebSocket (Channels) connections.
"""

import os
import django
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smartchat.settings')
django.setup()

# Import routing AFTER django.setup()
from chat.routing import websocket_urlpatterns

application = ProtocolTypeRouter({
    # HTTP → standard Django ASGI app
    'http': get_asgi_application(),

    # WebSocket → Channels with session-based auth
    'websocket': AllowedHostsOriginValidator(
        AuthMiddlewareStack(
            URLRouter(websocket_urlpatterns)
        )
    ),
})
