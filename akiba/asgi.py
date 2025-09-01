"""
ASGI config for akiba project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

# import os

# from django.core.asgi import get_asgi_application

# from channels.routing import ProtocolTypeRouter, URLRouter
# from channels.auth import AuthMiddlewareStack
# from sanek_wallet.routing import websocket_urlpatterns
# import django



# os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'akiba.settings')
# django.setup()

# from sanek_wallet.routing import websocket_urlpatterns

# # application = get_asgi_application()

# application = ProtocolTypeRouter({
#     "http": get_asgi_application(),
#     "websocket": AuthMiddlewareStack(
#         URLRouter(websocket_urlpatterns)
#     ),
# })


# import os
# import django
# from django.core.asgi import get_asgi_application

# # ÉTAPE 1: Configurer Django en premier
# os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'akiba.settings')
# django.setup()

# # ÉTAPE 2: Importer les modules Django Channels après la configuration
# from channels.routing import ProtocolTypeRouter, URLRouter
# from channels.auth import AuthMiddlewareStack
# from sanek_wallet.routing import websocket_urlpatterns

# # ÉTAPE 3: Créer l'application ASGI
# application = ProtocolTypeRouter({
#     "http": get_asgi_application(),
#     "websocket": AuthMiddlewareStack(
#         URLRouter(websocket_urlpatterns)
#     ),
# })


import os
import django
from django.core.asgi import get_asgi_application

# ÉTAPE 1: Configurer Django en premier
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'akiba.settings')
django.setup()

# ÉTAPE 2: Importer les modules Django Channels après la configuration
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

# Importer vos patterns WebSocket
try:
    from sanek_wallet.routing import websocket_urlpatterns
except ImportError:
    # Si le module n'existe pas encore, créer une liste vide
    websocket_urlpatterns = []

# ÉTAPE 3: Créer l'application ASGI
application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    ),
})