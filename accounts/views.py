# from django.shortcuts import render
from datetime import datetime
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.contrib.auth.hashers import make_password
from django.utils import timezone
from django.conf import settings

from .models import CustomUser, PhoneVerification, UserSession
from .serializers import (
    RegisterSerializer, VerifyPhoneSerializer, CreatePinSerializer,
    VerifyPinSerializer, UserProfileSerializer, UpdateProfileSerializer,
    ResendCodeSerializer, LoginSerializer
)

from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from rest_framework_simplejwt.tokens import AccessToken
# from datetime import datetime, timezone
from django.utils import timezone

from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.authentication import JWTAuthentication


import requests
import logging


# Create your views here.

logger = logging.getLogger(__name__)


def send_sms(phone_number, message):
    """Envoyer un SMS via mtarget"""
    try:
        # Nettoyage du numéro de téléphone
        cleaned_number = phone_number.replace(' ', '').replace('+', '')
        if not cleaned_number.startswith('00'):
            cleaned_number = '00' + cleaned_number
        
        logger.debug(f"Numéro nettoyé : {cleaned_number}")
        print(f"Cleaned Number: {cleaned_number}")


        # URL de l'API mtarget
        api_url = settings.MTARGET_URL
        
        # Données à envoyer
        data = {
            "sender": settings.MTARGET_SENDER_NAME,
            "username": settings.MTARGET_USERNAME,
            "password": settings.MTARGET_PASSWORD,
            "msisdn": cleaned_number,
            "msg": message,
        }
        
        # Headers
        headers = {
            'Content-Type': 'application/json; charset=UTF-8',
        }
        
        # Envoi de la requête
        response = requests.post(api_url, json=data, headers=headers)
        
        if response.status_code == 200:
            response_data = response.json()
            
            # Vérifier si l'envoi a été accepté
            if (response_data.get('results') and 
                len(response_data['results']) > 0 and
                response_data['results'][0].get('reason') == 'ACCEPTED'):
                
                logger.info(f"SMS envoyé à {cleaned_number}")
                return True
            else:
                logger.error(f"SMS refusé pour {cleaned_number}")
                return False
        else:
            logger.error(f"Erreur HTTP {response.status_code} pour {cleaned_number}")
            return False
            
    except Exception as e:
        logger.error(f"Erreur envoi SMS à {phone_number}: {str(e)}")
        return False


def get_tokens_for_user(user):
    """Générer les tokens JWT pour un utilisateur"""
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }

@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    """
    Étape 1: Inscription initiale - créer une vérification en attente
    """
    serializer = RegisterSerializer(data=request.data)
    
    if serializer.is_valid():
        phone_number = serializer.validated_data['phone_number']
        full_name = serializer.validated_data['full_name']
        password = serializer.validated_data['password']
        
        # Supprimer les anciennes vérifications pour ce numéro
        PhoneVerification.objects.filter(phone_number=phone_number).delete()
        
        # Créer une nouvelle vérification
        verification = PhoneVerification.objects.create(
            phone_number=phone_number,
            full_name=full_name,
            password=make_password(password)
        )
        
        # Préparer le message SMS
        message = f"Votre code de vérification est: {verification.verification_code}. Ce code expire dans 10 minutes."
        
        # Envoyer le SMS
        sms_sent = send_sms(phone_number, message)
        
        if sms_sent:
            return Response({
                'success': True,
                'message': 'Code de vérification envoyé par SMS',
                'phone_number': phone_number
            }, status=status.HTTP_200_OK)
        else:
            verification.delete()
            return Response({
                'success': False,
                'message': 'Erreur lors de l\'envoi du SMS'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    errors = serializer.errors
    first_key = next(iter(errors))
    first_error = errors[first_key][0] if isinstance(errors[first_key], list) else errors[first_key]

    
    return Response({
        'success': False,
        'errors': serializer.errors,
        'message': first_error
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def verify_phone(request):
    """
    Étape 2: Vérifier le code SMS et créer l'utilisateur
    """
    serializer = VerifyPhoneSerializer(data=request.data)
    
    if serializer.is_valid():
        phone_number = serializer.validated_data['phone_number']
        verification_code = serializer.validated_data['verification_code']
        
        try:
            verification = PhoneVerification.objects.get(
                phone_number=phone_number,
                verification_code=verification_code,
                is_verified=False
            )
            
            # Vérifier si le code n'a pas expiré
            if verification.is_expired():
                return Response({
                    'success': False,
                    'message': 'Le code de vérification a expiré'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Vérifier le nombre de tentatives
            if not verification.can_attempt():
                return Response({
                    'success': False,
                    'message': 'Trop de tentatives. Demandez un nouveau code.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Marquer comme vérifié
            verification.is_verified = True
            verification.save()
            
            # Créer l'utilisateur maintenant
            user = CustomUser.objects.create(
                phone_number=phone_number,
                full_name=verification.full_name,
                password=verification.password,
                is_phone_verified=True,
                username=phone_number  
            )
            
            # Supprimer la vérification
            verification.delete()
            
            # Générer les tokens JWT
            tokens = get_tokens_for_user(user)
            
            # Créer la session utilisateur
            UserSession.objects.create(
                user=user,
                jwt_token=tokens['access']
            )
            
            return Response({
                'success': True,
                'message': 'Numéro vérifié avec succès',
                'user_id': user.id,
                'tokens': tokens,
                'requires_pin_setup': not user.has_pin_code
            }, status=status.HTTP_200_OK)
            
        except PhoneVerification.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Code de vérification invalide. Veuillez réessayer.'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    errors = serializer.errors
    first_key = next(iter(errors))
    first_error = errors[first_key][0] if isinstance(errors[first_key], list) else errors[first_key]
    return Response({
        'success': False,
        'errors': serializer.errors,
        'message': first_error
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_pin(request):
    """
    Étape 3: Créer le code PIN
    """
    logger = logging.getLogger('accounts')
    logger.info(f"create_pin called by user: {request.user}, has_pin_code={getattr(request.user, 'has_pin_code', None)}")
    
    print(f"create_pin called by user: {request.user}, has_pin_code={getattr(request.user, 'has_pin_code', None)}")
    
    serializer = CreatePinSerializer(data=request.data)
    
    if serializer.is_valid():
        pin_code = serializer.validated_data['pin_code']
        
        user = request.user
        user.set_pin_code(pin_code)
        user.update_pin_entry_time()
        
        return Response({
            'success': True,
            'message': 'Code PIN créé avec succès',
            'registration_complete': True
        }, status=status.HTTP_200_OK)
    
    errors = serializer.errors
    first_key = next(iter(errors))
    first_error = errors[first_key][0] if isinstance(errors[first_key], list) else errors[first_key]
    return Response({
        'success': False,
        'errors': serializer.errors,
        'message': first_error
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def verify_pin(request):
    """
    Vérifier le code PIN pour l'authentification rapide
    """
    serializer = VerifyPinSerializer(data=request.data)
    
    if serializer.is_valid():
        pin_code = serializer.validated_data['pin_code']
        
        user = request.user
        
        if not user.has_pin_code:
            return Response({
                'success': False,
                'message': 'Aucun code PIN configuré'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if user.check_pin_code(pin_code):
            user.update_pin_entry_time()
            
            return Response({
                'success': True,
                'message': 'Code PIN vérifié avec succès'
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'success': False,
                'message': 'Code PIN incorrect'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    errors = serializer.errors
    first_key = next(iter(errors))
    first_error = errors[first_key][0] if isinstance(errors[first_key], list) else errors[first_key]
    return Response({
        'success': False,
        'errors': serializer.errors,
        'message': first_error
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def auth_status(request):
    """Vérifie l'état de connexion et si le code PIN est configuré"""
    user = request.user
    
    should_require_pin = user.should_require_pin()
    
    if user.requires_pin_auth != should_require_pin:
        user.requires_pin_auth = should_require_pin
        user.save(update_fields=['requires_pin_auth'])
    
    response_data = {
        'success': True,
        'has_pin_code': user.has_pin_code,
        'user_id': user.id,
        'requires_pin_auth': user.should_require_pin(), 
    }
    return Response(response_data, status=status.HTTP_200_OK)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_background_time(request):
    user = request.user
    user.last_background_time = timezone.now()
    print(f"User Last Background Time avant Save: {user.last_background_time}")
    user.save()
    print(f"Update Background Last Time User AFter Save: {user.last_background_time}")
    return Response({'success': True})



@api_view(['POST'])
@permission_classes([AllowAny])
def resend_code(request):
    """
    Renvoyer un code de vérification
    """
    serializer = ResendCodeSerializer(data=request.data)
    
    if serializer.is_valid():
        phone_number = serializer.validated_data['phone_number']
        
        try:
            # Récupérer la vérification en cours
            verification = PhoneVerification.objects.get(
                phone_number=phone_number,
                is_verified=False
            )
            
            # Générer un nouveau code
            verification.verification_code = verification.generate_code()
            verification.expires_at = timezone.now() + timezone.timedelta(minutes=10)
            verification.attempts = 0  # Réinitialiser les tentatives
            verification.save()
            
            # Envoyer le nouveau code
            message = f"Votre nouveau code de vérification est: {verification.verification_code}. Ce code expire dans 10 minutes."
            sms_sent = send_sms(phone_number, message)
            
            if sms_sent:
                return Response({
                    'success': True,
                    'message': 'Nouveau code envoyé par SMS'
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'success': False,
                    'message': 'Erreur lors de l\'envoi du SMS'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
        except PhoneVerification.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Aucune vérification en cours pour ce numéro'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    errors = serializer.errors
    first_key = next(iter(errors))
    first_error = errors[first_key][0] if isinstance(errors[first_key], list) else errors[first_key]
    return Response({
        'success': False,
        'errors': serializer.errors,
        'message': first_error
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    """
    Connexion utilisateur
    """
    serializer = LoginSerializer(data=request.data)
    
    if serializer.is_valid():
        phone_number = serializer.validated_data['phone_number']
        password = serializer.validated_data['password']
        
        print(f"Phone Number: {phone_number}")
        print(f"Password: {password}")
        
        user = authenticate(username=phone_number, password=password)
        
        if user:
            if not user.is_phone_verified:
                return Response({
                    'success': False,
                    'message': 'Numéro de téléphone non vérifié'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Générer les tokens
            tokens = get_tokens_for_user(user)
            
            # Mettre à jour ou créer la session
            session, created = UserSession.objects.get_or_create(user=user)
            session.jwt_token = tokens['access']
            session.is_active = True
            session.update_activity()
            
            # Vérifier si l'utilisateur a besoin de saisir son PIN
            requires_pin = user.should_require_pin() if user.has_pin_code else False
            
            return Response({
                'success': True,
                'message': 'Connexion réussie',
                'tokens': tokens,
                'user': UserProfileSerializer(user).data,
                'requires_pin_setup': not user.has_pin_code,
                'requires_pin_auth': requires_pin
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'success': False,
                'message': 'Identifiants incorrects'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    errors = serializer.errors
    first_key = next(iter(errors))
    first_error = errors[first_key][0] if isinstance(errors[first_key], list) else errors[first_key]
    return Response({
        'success': False,
        'errors': serializer.errors,
        'message': first_error
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_profile(request):
    """
    Récupérer le profil utilisateur
    """
    serializer = UserProfileSerializer(request.user)
    return Response({
        'success': True,
        'user': serializer.data,
        'requires_pin_setup': not request.user.has_pin_code,
        'requires_pin_auth': request.user.should_require_pin() if request.user.has_pin_code else False
    }, status=status.HTTP_200_OK)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_profile(request):
    """
    Mettre à jour le profil utilisateur
    """
    serializer = UpdateProfileSerializer(request.user, data=request.data, partial=True)
    
    if serializer.is_valid():
        serializer.save()
        return Response({
            'success': True,
            'message': 'Profil mis à jour avec succès',
            'user': UserProfileSerializer(request.user).data
        }, status=status.HTTP_200_OK)
    
    errors = serializer.errors
    first_key = next(iter(errors))
    first_error = errors[first_key][0] if isinstance(errors[first_key], list) else errors[first_key]
    return Response({
        'success': False,
        'errors': serializer.errors,
        'message': first_error
    }, status=status.HTTP_400_BAD_REQUEST)




@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout(request):
    try:
        UserSession.objects.filter(user=request.user).delete()

        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            token_str = auth_header.split(' ')[1]
            token_obj = OutstandingToken.objects.filter(token=token_str).first()
            if not token_obj:
                access_token = AccessToken(token_str)
                expires_at = datetime.fromtimestamp(access_token['exp'], tz=timezone.utc)
                token_obj, _ = OutstandingToken.objects.get_or_create(
                    jti=access_token['jti'],
                    user=request.user,
                    expires_at=expires_at,
                    token=token_str
                )
            BlacklistedToken.objects.get_or_create(token=token_obj)

        for token in OutstandingToken.objects.filter(user=request.user):
            BlacklistedToken.objects.get_or_create(token=token)

        return Response({
            'success': True,
            'message': 'Déconnexion réussie'
        }, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({
            'success': False,
            'message': f"Erreur de déconnexion : {str(e)}"
        }, status=status.HTTP_400_BAD_REQUEST)



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def test_blacklist(request):
    try:
        user_auth_tuple = JWTAuthentication().authenticate(request)
        if user_auth_tuple is None:
            return Response({"detail": "No credentials provided."}, status=401)
        user, token = user_auth_tuple
        return Response({"detail": "Token valide", "user": user.username})
    except TokenError as e:
        return Response({"detail": f"Token invalide: {str(e)}"}, status=401)