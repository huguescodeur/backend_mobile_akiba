# from rest_framework import serializers
# from .models import SanekWallet, SanekTransaction
# from django.contrib.auth import get_user_model

# User = get_user_model()

# class SanekWalletSerializer(serializers.ModelSerializer):
#     user_id = serializers.SerializerMethodField()
    
#     class Meta:
#         model = SanekWallet
#         fields = ['uuid', 'balance', 'created_at', 'updated_at', 'user_id']
    
#     def get_user_id(self, instance):
#         """Retourne l'UUID ou l'ID de l'utilisateur"""
#         if hasattr(instance.user, 'uuid'):
#             return str(instance.user.uuid)
#         return str(instance.user.id)

# class SanekTransactionSerializer(serializers.ModelSerializer):
#     sender_name = serializers.SerializerMethodField()
#     receiver_name = serializers.SerializerMethodField()
#     sender_id = serializers.SerializerMethodField()
#     receiver_id = serializers.SerializerMethodField()
    
#     class Meta:
#         model = SanekTransaction
#         fields = [
#             'uuid', 'sender_id', 'receiver_id', 'sender_name', 
#             'receiver_name', 'operator', 'amount', 'transaction_type', 'created_at'
#         ]
    
#     def get_sender_name(self, obj):
#         """Retourne le nom complet de l'expéditeur"""
#         if obj.sender:
#             return obj.sender.get_full_name()
#         return None
    
#     def get_receiver_name(self, obj):
#         """Retourne le nom complet du destinataire"""
#         if obj.receiver:
#             return obj.receiver.get_full_name()
#         return None
    
#     def get_sender_id(self, obj):
#         """Retourne l'UUID ou l'ID de l'expéditeur"""
#         if obj.sender:
#             if hasattr(obj.sender, 'uuid'):
#                 return str(obj.sender.uuid)
#             return str(obj.sender.id)
#         return None
    
#     def get_receiver_id(self, obj):
#         """Retourne l'UUID ou l'ID du destinataire"""
#         if obj.receiver:
#             if hasattr(obj.receiver, 'uuid'):
#                 return str(obj.receiver.uuid)
#             return str(obj.receiver.id)
#         return None

from rest_framework import serializers
from .models import SanekWallet, SanekTransaction
from django.contrib.auth import get_user_model

User = get_user_model()

class SanekWalletSerializer(serializers.ModelSerializer):
    user_id = serializers.SerializerMethodField()
    
    class Meta:
        model = SanekWallet
        fields = ['uuid', 'balance', 'created_at', 'updated_at', 'user_id']
    
    def get_user_id(self, instance):
        """Retourne l'UUID ou l'ID de l'utilisateur"""
        if hasattr(instance.user, 'uuid'):
            return str(instance.user.uuid)
        return str(instance.user.id)

class SanekTransactionSerializer(serializers.ModelSerializer):
    sender_name = serializers.SerializerMethodField()
    receiver_name = serializers.SerializerMethodField()
    sender_id = serializers.SerializerMethodField()
    receiver_id = serializers.SerializerMethodField()
    
    class Meta:
        model = SanekTransaction
        fields = [
            'uuid', 'sender_id', 'receiver_id', 'sender_name', 
            'receiver_name', 'operator', 'amount', 'transaction_type', 'created_at'
        ]
    
    def get_sender_name(self, obj):
        """Retourne le nom de l'expéditeur"""
        if obj.sender:
            # Si full_name contient le username comme mentionné dans votre commentaire
            return getattr(obj.sender, 'full_name', None) or \
                   getattr(obj.sender, 'username', None) or \
                   getattr(obj.sender, 'phone_number', None) or \
                   "Utilisateur"
        return None
    
    def get_receiver_name(self, obj):
        """Retourne le nom du destinataire"""
        if obj.receiver:
            # Si full_name contient le username comme mentionné dans votre commentaire
            return getattr(obj.receiver, 'full_name', None) or \
                   getattr(obj.receiver, 'username', None) or \
                   getattr(obj.receiver, 'phone_number', None) or \
                   "Utilisateur"
        return None
    
    def get_sender_id(self, obj):
        """Retourne l'UUID ou l'ID de l'expéditeur"""
        if obj.sender:
            if hasattr(obj.sender, 'uuid'):
                return str(obj.sender.uuid)
            return str(obj.sender.id)
        return None
    
    def get_receiver_id(self, obj):
        """Retourne l'UUID ou l'ID du destinataire"""
        if obj.receiver:
            if hasattr(obj.receiver, 'uuid'):
                return str(obj.receiver.uuid)
            return str(obj.receiver.id)
        return None