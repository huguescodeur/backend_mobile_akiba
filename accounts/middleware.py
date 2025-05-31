# middleware.py
from django.utils.deprecation import MiddlewareMixin
from django.http import JsonResponse
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework.exceptions import AuthenticationFailed

from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.views import TokenRefreshView

import json

# ? Pin Auth Middleware
class PinAuthMiddleware(MiddlewareMixin):
    """
    Middleware pour vérifier si l'utilisateur doit ressaisir son PIN
    Similaire à DJamo/Wave - après 1 minute d'inactivité
    """
    
    # URLs qui ne nécessitent pas de vérification PIN
    EXEMPT_URLS = [
        '/api/accounts/register/',
        '/api/accounts/login/',
        '/api/accounts/verify-phone/',
        '/api/accounts/create-pin/',
        '/api/accounts/verify-pin/',
        '/api/accounts/resend-code/',
        '/api/accounts/auth-status/',
        '/api/accounts/update-background-time/',
        '/api/accounts/token/refresh/',
        '/admin/',
    ]
    
    def process_request(self, request):
        # Ignorer les URLs exemptées
        if any(request.path.startswith(url) for url in self.EXEMPT_URLS):
            return None
        
        # Ignorer les requêtes non-API
        if not request.path.startswith('/api/'):
            return None
        
        # Vérifier si c'est une requête authentifiée
        auth = JWTAuthentication()
        try:
            user_auth_tuple = auth.authenticate(request)
            if user_auth_tuple is None:
                return None
            
            user, token = user_auth_tuple
            
            # Vérifier si l'utilisateur a un code PIN configuré
            if not user.has_pin_code:
                # Si pas de PIN, demander la création
                return JsonResponse({
                    'success': False,
                    'requires_pin_setup': True,
                    'message': 'Veuillez configurer votre code PIN'
                }, status=400)
            
            # Vérifier si l'utilisateur doit ressaisir son PIN
            if user.should_require_pin():
                user.requires_pin_auth = True
                user.save()
                
                return JsonResponse({
                    'success': False,
                    'requires_pin_auth': True,
                    'message': 'Veuillez saisir votre code PIN pour continuer'
                }, status=401)
            
            # Mettre à jour l'activité de l'utilisateur
            if hasattr(user, 'session_info'):
                user.session_info.update_activity()
                
        except (InvalidToken, AuthenticationFailed):
            return None
        
        return None


class RequestLoggingMiddleware(MiddlewareMixin):
    """
    Middleware pour logger les requêtes importantes
    """
    
    def process_request(self, request):
        # Logger les tentatives d'authentification
        if request.path in ['/api/accounts/login/', '/api/accounts/register/', '/api/accounts/verify-phone/', '/api/accounts/update-background-time']:
            import logging
            logger = logging.getLogger('accounts')
            
            try:
                if request.content_type == 'application/json':
                    data = json.loads(request.body)
                    phone = data.get('phone_number', 'Unknown')
                    logger.info(f"Auth attempt from {request.META.get('REMOTE_ADDR')} for phone: {phone}")
            except:
                pass
        
        return None
    
    def process_response(self, request, response):
        # Logger les réponses d'erreur d'authentification
        if request.path.startswith('/api/') and response.status_code >= 400:
            import logging
            logger = logging.getLogger('accounts')
            logger.warning(f"API error {response.status_code} for {request.path} from {request.META.get('REMOTE_ADDR')}")
        
        return response


class SecurityHeadersMiddleware(MiddlewareMixin):
    """
    Middleware pour ajouter des en-têtes de sécurité
    """
    
    def process_response(self, request, response):
        # Ajouter des en-têtes de sécurité pour les API
        if request.path.startswith('/api/'):
            response['X-Content-Type-Options'] = 'nosniff'
            response['X-Frame-Options'] = 'DENY'
            response['X-XSS-Protection'] = '1; mode=block'
            response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        return response
    
    
    # ? Token Middleware
    from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
from rest_framework.response import Response
from rest_framework import status

# class TokenMiddleware:
#     def __init__(self, get_response):
#         self.get_response = get_response

#     def __call__(self, request):
#         response = self.get_response(request)

#         if response.status_code == 401 and 'refresh' in request.data:
#             try:
#                 refresh_view = TokenRefreshView.as_view()
#                 return refresh_view(request)
#             except (TokenError, InvalidToken):
#                 return Response({'error': 'Session expirée. Veuillez vous reconnecter.'}, status=status.HTTP_403_FORBIDDEN)

#         return response


class TokenMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if response.status_code == 401:
            try:
                request_data = json.loads(request.body)  # Lire les données manuellement
                if 'refresh' in request_data:
                    refresh_view = TokenRefreshView.as_view()
                    return refresh_view(request)
            except json.JSONDecodeError:
                pass  # Évite une erreur si le corps de la requête est vide

            except (TokenError, InvalidToken):
                return Response({'error': 'Session expirée. Veuillez vous reconnecter.'}, status=status.HTTP_403_FORBIDDEN)

        return response