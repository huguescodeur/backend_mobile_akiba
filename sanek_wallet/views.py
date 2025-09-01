from decimal import Decimal
from django.shortcuts import render, get_object_or_404
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db import models
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import logging

from .models import SanekWallet, SanekTransaction
from .serializers import SanekWalletSerializer, SanekTransactionSerializer

User = get_user_model()
logger = logging.getLogger(__name__)
channel_layer = get_channel_layer()

def send_wallet_update(user, wallet_data=None, transaction_data=None):
    """Envoyer une mise à jour via WebSocket"""
    try:
        group_name = f"wallet_{user.id}"
        
        if wallet_data:
            async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    "type": "wallet_update",
                    "data": wallet_data
                }
            )
            logger.info(f"✅ Wallet update envoyé pour user {user.id}")
        
        if transaction_data:
            async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    "type": "transaction_created",
                    "data": transaction_data
                }
            )
            logger.info(f"✅ Transaction update envoyé pour user {user.id}")
            
    except Exception as e:
        logger.error(f"❌ Erreur envoi WebSocket: {e}")

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_wallet_data(request):
    """Récupérer les données du wallet"""
    try:
        # Créer le wallet s'il n'existe pas
        wallet, created = SanekWallet.objects.get_or_create(user=request.user)
        
        # Récupérer les transactions récentes
        transactions = SanekTransaction.objects.filter(
            models.Q(sender=request.user) | models.Q(receiver=request.user)
        ).order_by('-created_at')[:20]
        
        wallet_serializer = SanekWalletSerializer(wallet)
        transaction_serializer = SanekTransactionSerializer(transactions, many=True)
        
        return Response({
            'success': True,
            'message': 'Données récupérées avec succès',
            'wallet': wallet_serializer.data,
            'transactions': transaction_serializer.data
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Erreur get_wallet_data: {e}")
        return Response({
            'success': False,
            'message': 'Erreur lors de la récupération des données'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_transaction_history(request):
    """Récupérer l'historique des transactions"""
    try:
        limit = int(request.GET.get('limit', 50))
        offset = int(request.GET.get('offset', 0))
        transaction_type = request.GET.get('type')
        
        queryset = SanekTransaction.objects.filter(
            models.Q(sender=request.user) | models.Q(receiver=request.user)
        )
        
        if transaction_type:
            queryset = queryset.filter(transaction_type=transaction_type)
        
        queryset = queryset.order_by('-created_at')[offset:offset+limit]
        
        serializer = SanekTransactionSerializer(queryset, many=True)
        
        return Response({
            'success': True,
            'message': 'Historique récupéré avec succès',
            'transactions': serializer.data
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Erreur get_transaction_history: {e}")
        return Response({
            'success': False,
            'message': 'Erreur lors de la récupération de l\'historique'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def make_deposit(request):
    """Effectuer un dépôt"""
    try:
        amount = Decimal(request.data.get('amount', '0'))
        operator = request.data.get('operator', '')
        reference = request.data.get('reference', '')
        
        if amount <= 0:
            return Response({
                'success': False,
                'message': 'Montant invalide'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        with transaction.atomic():
            wallet, created = SanekWallet.objects.get_or_create(user=request.user)
            wallet.deposit(amount)
            
            # Créer la transaction avec l'opérateur
            sanek_transaction = SanekTransaction.objects.create(
                receiver=request.user,
                operator=operator,
                amount=amount,
                transaction_type='deposit'
            )
            
            # Sérialiser les données
            wallet_serializer = SanekWalletSerializer(wallet)
            transaction_serializer = SanekTransactionSerializer(sanek_transaction)
            
            # Envoyer via WebSocket
            send_wallet_update(
                request.user,
                wallet_data=wallet_serializer.data,
                transaction_data=transaction_serializer.data
            )
            
            return Response({
                'success': True,
                'message': 'Dépôt effectué avec succès',
                'wallet': wallet_serializer.data,
                'transaction': transaction_serializer.data
            }, status=status.HTTP_200_OK)
            
    except Exception as e:
        logger.error(f"Erreur make_deposit: {e}")
        return Response({
            'success': False,
            'message': 'Erreur lors du dépôt'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def make_withdrawal(request):
    """Effectuer un retrait"""
    try:
        amount = Decimal(request.data.get('amount', '0'))
        operator = request.data.get('operator', '')
        
        if amount <= 0:
            return Response({
                'success': False,
                'message': 'Montant invalide'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        with transaction.atomic():
            wallet = get_object_or_404(SanekWallet, user=request.user)
            
            if wallet.balance < amount:
                return Response({
                    'success': False,
                    'message': 'Solde insuffisant'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            wallet.withdraw(amount)
            
            # Créer la transaction avec l'opérateur
            sanek_transaction = SanekTransaction.objects.create(
                sender=request.user,
                operator=operator,
                amount=amount,
                transaction_type='withdraw'
            )
            
            # Sérialiser les données
            wallet_serializer = SanekWalletSerializer(wallet)
            transaction_serializer = SanekTransactionSerializer(sanek_transaction)
            
            # Envoyer via WebSocket
            send_wallet_update(
                request.user,
                wallet_data=wallet_serializer.data,
                transaction_data=transaction_serializer.data
            )
            
            return Response({
                'success': True,
                'message': 'Retrait effectué avec succès',
                'wallet': wallet_serializer.data,
                'transaction': transaction_serializer.data
            }, status=status.HTTP_200_OK)
            
    except ValueError as e:
        return Response({
            'success': False,
            'message': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Erreur make_withdrawal: {e}")
        return Response({
            'success': False,
            'message': 'Erreur lors du retrait'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def make_transfer(request):
    """Effectuer un transfert"""
    try:
        receiver_phone = request.data.get('receiver_phone', '')
        amount = Decimal(request.data.get('amount', '0'))
        message = request.data.get('message', '')
        
        if amount <= 0:
            return Response({
                'success': False,
                'message': 'Montant invalide'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Trouver le destinataire par téléphone
        try:
            receiver = User.objects.get(phone_number=receiver_phone)
        except User.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Destinataire non trouvé'
            }, status=status.HTTP_404_NOT_FOUND)
        
        if receiver == request.user:
            return Response({
                'success': False,
                'message': 'Impossible de transférer à soi-même'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        with transaction.atomic():
            sender_wallet = get_object_or_404(SanekWallet, user=request.user)
            receiver_wallet, created = SanekWallet.objects.get_or_create(user=receiver)
            
            if sender_wallet.balance < amount:
                return Response({
                    'success': False,
                    'message': 'Solde insuffisant'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            sender_wallet.transfer(receiver_wallet, amount)
            
            # Créer la transaction
            sanek_transaction = SanekTransaction.objects.create(
                sender=request.user,
                receiver=receiver,
                amount=amount,
                transaction_type='transfer',
                operator='sanek'
            )
            
            # Sérialiser les données
            sender_wallet_serializer = SanekWalletSerializer(sender_wallet)
            receiver_wallet_serializer = SanekWalletSerializer(receiver_wallet)
            transaction_serializer = SanekTransactionSerializer(sanek_transaction)
            
            # Envoyer via WebSocket aux deux utilisateurs
            send_wallet_update(
                request.user,
                wallet_data=sender_wallet_serializer.data,
                transaction_data=transaction_serializer.data
            )
            
            send_wallet_update(
                receiver,
                wallet_data=receiver_wallet_serializer.data,
                transaction_data=transaction_serializer.data
            )
            
            return Response({
                'success': True,
                'message': 'Transfert effectué avec succès',
                'wallet': sender_wallet_serializer.data,
                'transaction': transaction_serializer.data
            }, status=status.HTTP_200_OK)
            
    except ValueError as e:
        return Response({
            'success': False,
            'message': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Erreur make_transfer: {e}")
        return Response({
            'success': False,
            'message': 'Erreur lors du transfert'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def make_challenge(request):
    """Effectuer un bonus challenge"""
    try:
        amount = Decimal(request.data.get('amount', '0'))
        challenge_name = request.data.get('challenge_name', '')
        description = request.data.get('description', '')
        
        if amount <= 0:
            return Response({
                'success': False,
                'message': 'Montant invalide'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        with transaction.atomic():
            wallet, created = SanekWallet.objects.get_or_create(user=request.user)
            wallet.deposit(amount)  # Les bonus challenge sont ajoutés au solde
            
            # Créer la transaction challenge
            sanek_transaction = SanekTransaction.objects.create(
                receiver=request.user,  # L'utilisateur reçoit le bonus
                operator=challenge_name,  # Le nom du challenge dans operator
                amount=amount,
                transaction_type='challenge'
            )
            
            # Sérialiser les données
            wallet_serializer = SanekWalletSerializer(wallet)
            transaction_serializer = SanekTransactionSerializer(sanek_transaction)
            
            # Envoyer via WebSocket
            send_wallet_update(
                request.user,
                wallet_data=wallet_serializer.data,
                transaction_data=transaction_serializer.data
            )
            
            return Response({
                'success': True,
                'message': 'Bonus challenge ajouté avec succès',
                'wallet': wallet_serializer.data,
                'transaction': transaction_serializer.data
            }, status=status.HTTP_200_OK)
            
    except Exception as e:
        logger.error(f"Erreur make_challenge: {e}")
        return Response({
            'success': False,
            'message': 'Erreur lors de l\'ajout du bonus challenge'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)