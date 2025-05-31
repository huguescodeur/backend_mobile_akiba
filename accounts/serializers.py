from rest_framework import serializers
from django.contrib.auth.hashers import make_password
from .models import CustomUser, PhoneVerification
import re

class RegisterSerializer(serializers.Serializer):
    """Serializer pour l'inscription initiale (avant vérification SMS)"""
    full_name = serializers.CharField(max_length=255, required=True)
    phone_number = serializers.CharField(max_length=20, required=True)
    password = serializers.CharField(min_length=6, required=True, error_messages={
            'min_length': 'Le mot de passe doit contenir au moins 6 caractères.',
            'blank': 'Le mot de passe est requis.',
            'required': 'Le mot de passe est requis.'
        })
    
    
    def validate_phone_number(self, value):
        """Valider le format du numéro de téléphone"""
        # Supprimer tous les espaces et caractères spéciaux sauf +
        cleaned_phone = re.sub(r'[^\d+]', '', value)
        
        if not cleaned_phone.startswith('+'):
            raise serializers.ValidationError("Le numéro doit commencer par le code pays (+)")
        
        
        # Vérifier si le numéro existe déjà
        if CustomUser.objects.filter(phone_number=cleaned_phone).exists():
            raise serializers.ValidationError("Ce numéro de téléphone est déjà utilisé")
        
        return cleaned_phone
    
    def validate_full_name(self, value):
        """Valider le nom complet"""
        if len(value.strip()) < 2:
            raise serializers.ValidationError("Le nom complet doit contenir au moins 2 caractères")
        return value.strip()
    
    


class VerifyPhoneSerializer(serializers.Serializer):
    """Serializer pour la vérification du code SMS"""
    phone_number = serializers.CharField(max_length=20, required=True)
    verification_code = serializers.CharField(max_length=6, required=True)
    
    def validate_verification_code(self, value):
        """Valider le code de vérification"""
        if not value.isdigit() or len(value) != 6:
            raise serializers.ValidationError("Le code doit contenir exactement 6 chiffres")
        return value


class CreatePinSerializer(serializers.Serializer):
    """Serializer pour la création du code PIN"""
    pin_code = serializers.CharField(max_length=6, required=True)
    confirm_pin_code = serializers.CharField(max_length=6, required=True)
    
    def validate_pin_code(self, value):
        """Valider que le code PIN contient exactement 4 chiffres"""

    # Forcer la conversion en chaîne au cas où un entier est envoyé
        value = str(value)

        if not value.isdigit():
            raise serializers.ValidationError("Le code PIN doit contenir uniquement des chiffres")

        if len(value) != 4:
            raise serializers.ValidationError("Le code PIN doit contenir exactement 4 chiffres")

        return value
    
    def validate(self, data):
        """Valider que les deux codes PIN correspondent"""
        if data['pin_code'] != data['confirm_pin_code']:
            raise serializers.ValidationError("Les codes PIN ne correspondent pas")
        return data


class VerifyPinSerializer(serializers.Serializer):
    """Serializer pour la vérification du code PIN"""
    pin_code = serializers.CharField(max_length=6, required=True)
    
    def validate_pin_code(self, value):
        """Valider le format du code PIN"""
        if not value.isdigit():
            raise serializers.ValidationError("Le code PIN ne doit contenir que des chiffres")
        return value


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer pour le profil utilisateur"""
    class Meta:
        model = CustomUser
        fields = ['id', 'full_name', 'phone_number', 'profile_picture', 
                 'is_phone_verified', 'has_pin_code', 'date_joined']
        read_only_fields = ['id', 'phone_number', 'is_phone_verified', 
                           'has_pin_code', 'date_joined']


class UpdateProfileSerializer(serializers.ModelSerializer):
    """Serializer pour la mise à jour du profil"""
    class Meta:
        model = CustomUser
        fields = ['full_name', 'profile_picture']
        
    def validate_full_name(self, value):
        """Valider le nom complet"""
        if len(value.strip()) < 2:
            raise serializers.ValidationError("Le nom complet doit contenir au moins 2 caractères")
        return value.strip()


class ResendCodeSerializer(serializers.Serializer):
    """Serializer pour renvoyer un code de vérification"""
    phone_number = serializers.CharField(max_length=20, required=True)
    
    def validate_phone_number(self, value):
        """Valider le numéro de téléphone"""
        cleaned_phone = re.sub(r'[^\d+]', '', value)
        
        if not cleaned_phone.startswith('+'):
            raise serializers.ValidationError("Le numéro doit commencer par le code pays (+)")
        
        return cleaned_phone


class LoginSerializer(serializers.Serializer):
    """Serializer pour la connexion"""
    phone_number = serializers.CharField(max_length=20, required=True)
    password = serializers.CharField(required=True, error_messages={
            'blank': 'Le mot de passe est requis.',
            'required': 'Le mot de passe est requis.'
        })
    
    def validate_phone_number(self, value):
        """Valider et nettoyer le numéro de téléphone"""
        cleaned_phone = re.sub(r'[^\d+]', '', value)
        return cleaned_phone