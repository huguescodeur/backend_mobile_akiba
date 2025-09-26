import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth import get_user_model
from django.conf import settings
from rest_framework_simplejwt.tokens import UntypedToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from jwt import decode as jwt_decode
import asyncio
from datetime import datetime

from .models import SanekWallet, SanekTransaction
from .serializers import SanekWalletSerializer, SanekTransactionSerializer

User = get_user_model()
logger = logging.getLogger(__name__)

class WalletConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = None
        self.group_name = None
        self.last_activity = datetime.now()
        self.ping_task = None
        
        # Récupérer le token depuis l'URL
        query_string = self.scope['query_string'].decode()
        token = None
        
        if 'token=' in query_string:
            token = query_string.split('token=')[-1].split('&')[0]
        
        if token:
            self.user = await self.get_user_from_token(token)
        
        if self.user and not isinstance(self.user, AnonymousUser):
            self.group_name = f"wallet_{self.user.id}"
            
            # Accepter la connexion
            await self.accept()
            
            # Ajouter au groupe
            await self.channel_layer.group_add(
                self.group_name,
                self.channel_name
            )
            
            logger.info(f" WebSocket connecté pour l'utilisateur {self.user.id}")
            
            # Envoyer confirmation de connexion avec données wallet
            wallet_data = await self.get_wallet_data()
            await self.send(text_data=json.dumps({
                'type': 'connection_established',
                'message': 'WebSocket connecté avec succès',
                'user_id': self.user.id,
                'wallet_data': wallet_data
            }))
            
            # Démarrer le ping automatique
            self.ping_task = asyncio.create_task(self.ping_loop())
            
        else:
            # Rejeter la connexion si pas d'authentification
            await self.close(code=4001)
            logger.warning(" Connexion WebSocket rejetée - authentification échouée")

    async def disconnect(self, close_code):
        # Annuler le ping
        if self.ping_task:
            self.ping_task.cancel()
            
        # Quitter le groupe
        if self.group_name:
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )
            logger.info(f"🔌 WebSocket déconnecté pour l'utilisateur {self.user.id if self.user else 'Unknown'}")

    async def ping_loop(self):
        """Ping périodique pour maintenir la connexion"""
        try:
            while True:
                await asyncio.sleep(30)  # Ping toutes les 30 secondes
                await self.send(text_data=json.dumps({
                    'type': 'ping',
                    'timestamp': datetime.now().isoformat()
                }))
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Erreur ping loop: {e}")

    async def receive(self, text_data):
        try:
            self.last_activity = datetime.now()
            data = json.loads(text_data)
            message_type = data.get('type')
            
            logger.debug(f" Message reçu: {message_type}")
            
            if message_type == 'ping':
                await self.send(text_data=json.dumps({
                    'type': 'pong',
                    'timestamp': data.get('timestamp')
                }))
            
            elif message_type == 'pong':
                # Client répond au ping
                logger.debug(" Pong reçu du client")
            
            elif message_type == 'get_wallet_data':
                await self.send_wallet_data()
            
            elif message_type == 'get_transactions':
                await self.send_transaction_history()
                
            elif message_type == 'heartbeat':
                await self.send(text_data=json.dumps({
                    'type': 'heartbeat_ack',
                    'timestamp': datetime.now().isoformat()
                }))
            
            else:
                logger.warning(f"Type de message non reconnu: {message_type}")
                
        except json.JSONDecodeError:
            logger.error("Format JSON invalide reçu")
        except Exception as e:
            logger.error(f"Erreur receive: {e}")

    async def send_wallet_data(self):
        """Envoyer les données du wallet"""
        try:
            wallet_data = await self.get_wallet_data()
            if wallet_data:
                await self.send(text_data=json.dumps({
                    'type': 'wallet_data',
                    'data': wallet_data,
                    'timestamp': datetime.now().isoformat()
                }))
        except Exception as e:
            logger.error(f"Erreur send_wallet_data: {e}")

    async def send_transaction_history(self):
        """Envoyer l'historique des transactions"""
        try:
            transactions_data = await self.get_transactions_data()
            await self.send(text_data=json.dumps({
                'type': 'transaction_history',
                'data': transactions_data,
                'timestamp': datetime.now().isoformat()
            }))
        except Exception as e:
            logger.error(f"Erreur send_transaction_history: {e}")

    # Handlers pour les messages du groupe
    async def wallet_update(self, event):
        """Envoyer une mise à jour du wallet"""
        try:
            logger.info(f" Envoi wallet_update pour user {self.user.id}")
            
            # Vérifier que la connexion est toujours active
            if hasattr(self, 'channel_name') and self.channel_name:
                await self.send(text_data=json.dumps({
                    'type': 'wallet_update',
                    'data': event['data'],
                    'timestamp': datetime.now().isoformat(),
                    'source': 'signal'
                }))
                logger.info(f" Wallet update envoyé pour user {self.user.id}")
            else:
                logger.warning(f" Connexion fermée, impossible d'envoyer wallet_update")
                
        except Exception as e:
            logger.error(f" Erreur envoi wallet_update: {e}")

    async def transaction_created(self, event):
        """Envoyer une nouvelle transaction"""
        try:
            logger.info(f" Envoi transaction_created pour user {self.user.id}")
            
            if hasattr(self, 'channel_name') and self.channel_name:
                await self.send(text_data=json.dumps({
                    'type': 'transaction_created',
                    'data': event['data'],
                    'timestamp': datetime.now().isoformat(),
                    'source': 'signal'
                }))
                logger.info(f" Transaction update envoyé pour user {self.user.id}")
            else:
                logger.warning(f" Connexion fermée, impossible d'envoyer transaction_created")
                
        except Exception as e:
            logger.error(f" Erreur envoi transaction_created: {e}")

    async def balance_changed(self, event):
        """Envoyer un changement de solde"""
        try:
            logger.info(f" Envoi balance_changed pour user {self.user.id}")
            
            if hasattr(self, 'channel_name') and self.channel_name:
                await self.send(text_data=json.dumps({
                    'type': 'balance_changed',
                    'data': event['data'],
                    'timestamp': datetime.now().isoformat(),
                    'source': 'signal'
                }))
            
        except Exception as e:
            logger.error(f" Erreur envoi balance_changed: {e}")

    # Méthodes utilitaires (inchangées)
    @database_sync_to_async
    def get_user_from_token(self, token):
        """Récupérer l'utilisateur depuis le token JWT"""
        try:
            UntypedToken(token)
            decoded_data = jwt_decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            user_id = decoded_data.get('user_id')
            
            if user_id:
                user = User.objects.get(id=user_id)
                logger.info(f" Utilisateur authentifié: {user.id}")
                return user
            return AnonymousUser()
            
        except (InvalidToken, TokenError, User.DoesNotExist) as e:
            logger.error(f" Erreur authentification token: {e}")
            return AnonymousUser()

    @database_sync_to_async
    def get_wallet_data(self):
        """Récupérer les données du wallet"""
        try:
            wallet, created = SanekWallet.objects.get_or_create(user=self.user)
            serializer = SanekWalletSerializer(wallet)
            return serializer.data
        except Exception as e:
            logger.error(f"Erreur get_wallet_data: {e}")
            return None

    @database_sync_to_async
    def get_transactions_data(self):
        """Récupérer les données des transactions"""
        try:
            from django.db import models
            transactions = SanekTransaction.objects.filter(
                models.Q(sender=self.user) | models.Q(receiver=self.user)
            ).order_by('-created_at')[:20]
            
            serializer = SanekTransactionSerializer(transactions, many=True)
            return serializer.data
        except Exception as e:
            logger.error(f"Erreur get_transactions_data: {e}")
            return []
        
    async def force_refresh(self, event):
        """Forcer l’actualisation côté client"""
        try:
            logger.info(f" Envoi force_refresh pour user {self.user.id}")
            
            if hasattr(self, 'channel_name') and self.channel_name:
                await self.send(text_data=json.dumps({
                    'type': 'force_refresh',
                    'data': event['data'],
                    'timestamp': datetime.now().isoformat(),
                    'source': 'signal'
                }))
            else:
                logger.warning(" Connexion fermée, impossible d’envoyer force_refresh")
        except Exception as e:
            logger.error(f" Erreur envoi force_refresh: {e}")
