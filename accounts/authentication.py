from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken

class DebugJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        user_auth_tuple = super().authenticate(request)
        if user_auth_tuple:
            user, token = user_auth_tuple
            if BlacklistedToken.objects.filter(token__jti=token['jti']).exists():
                print(f"🔒 Token {token['jti']} est blacklisté")
                raise AuthenticationFailed("Le token est blacklisté et donc invalide.")
            else:
                print(f"✅ Token {token['jti']} est autorisé")
        return user_auth_tuple
