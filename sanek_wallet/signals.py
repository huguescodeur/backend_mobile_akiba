from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import SanekWallet, SanekTransaction
from .serializers import SanekWalletSerializer, SanekTransactionSerializer
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import logging
from datetime import datetime, timedelta
from django.core.cache import cache
import hashlib

logger = logging.getLogger(__name__)
channel_layer = get_channel_layer()

def get_update_key(user_id, update_type, data_hash):
    """Génère une clé unique pour éviter les doublons"""
    return f"ws_update:{update_type}:{user_id}:{data_hash}"

def should_send_update(user_id, update_type, data, cooldown_seconds=1):
    """Vérifie si on doit envoyer la mise à jour (déduplication intelligente)"""
    try:
        # Pour les wallets, utiliser balance + timestamp
        if update_type == 'wallet':
            # Créer un hash plus spécifique incluant l'heure précise
            relevant_data = f"{data.get('balance', '')}{data.get('updated_at', '')}{datetime.now().timestamp()}"
        elif update_type == 'transaction':
            # Pour les transactions, utiliser l'UUID unique
            relevant_data = data.get('uuid', str(datetime.now().timestamp()))
        else:
            relevant_data = str(data)
        
        data_hash = hashlib.md5(relevant_data.encode()).hexdigest()[:8]
        cache_key = get_update_key(user_id, update_type, data_hash)
        
        # Vérifier si cette mise à jour a déjà été envoyée récemment
        if cache.get(cache_key):
            logger.debug(f"Mise à jour {update_type} dupliquée ignorée pour user {user_id}")
            return False
        
        # Marquer cette mise à jour comme envoyée avec un délai plus court
        cache.set(cache_key, True, timeout=cooldown_seconds)
        return True
        
    except Exception as e:
        logger.error(f"Erreur should_send_update: {e}")
        return True  # En cas d'erreur, envoyer quand même

@receiver(post_save, sender=SanekWallet)
def notify_wallet_update(sender, instance, created, **kwargs):
    """Signal déclenché après sauvegarde du wallet"""
    try:
        wallet_serializer = SanekWalletSerializer(instance)
        wallet_data = wallet_serializer.data
        
        # Réduire le cooldown pour les wallets à 0.5 secondes
        if not should_send_update(instance.user.id, 'wallet', wallet_data, cooldown_seconds=0.5):
            return
        
        group_name = f"wallet_{instance.user.id}"
        
        # Ajouter des métadonnées avec force_update si nécessaire
        update_data = {
            **wallet_data,
            'update_timestamp': datetime.now().isoformat(),
            'source': 'wallet_signal',
            'created': created,
            'force_update': True,  # Force l'update côté client
            'user_id': instance.user.id
        }
        
        # Envoyer via WebSocket avec retry
        try:
            async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    "type": "wallet_update",
                    "data": update_data
                }
            )
            logger.info(f" Signal wallet_update envoyé pour user {instance.user.id}")
            logger.info(f" Nouveau solde: {instance.balance}")
            
            # Envoyer aussi un événement générique pour forcer le refresh
            async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    "type": "force_refresh",
                    "data": {
                        "reason": "wallet_updated",
                        "user_id": instance.user.id,
                        "timestamp": datetime.now().isoformat()
                    }
                }
            )
            
        except Exception as send_error:
            logger.error(f" Erreur envoi wallet signal: {send_error}")
            
    except Exception as e:
        logger.error(f" Erreur signal wallet update: {e}")

@receiver(post_save, sender=SanekTransaction)
def notify_transaction_created(sender, instance, created, **kwargs):
    """Signal déclenché après création/modification d'une transaction"""
    if not created:
        return  # Ignorer les modifications
    
    try:
        transaction_serializer = SanekTransactionSerializer(instance)
        transaction_data = transaction_serializer.data
        
        # Identifier tous les utilisateurs concernés
        users_to_notify = []
        
        if instance.sender:
            users_to_notify.append(instance.sender.id)
        if instance.receiver and instance.receiver.id not in users_to_notify:
            users_to_notify.append(instance.receiver.id)
        
        # Ajouter des métadonnées
        update_data = {
            **transaction_data,
            'update_timestamp': datetime.now().isoformat(),
            'source': 'transaction_signal',
            'created': True,
            'transaction_uuid': str(instance.uuid) if hasattr(instance, 'uuid') else str(instance.id)
        }
        
        # Notifier chaque utilisateur concerné
        for user_id in users_to_notify:
            # Vérifier les doublons par utilisateur avec cooldown réduit
            if not should_send_update(user_id, 'transaction', transaction_data, cooldown_seconds=1):
                continue
                
            group_name = f"wallet_{user_id}"
            
            try:
                async_to_sync(channel_layer.group_send)(
                    group_name,
                    {
                        "type": "transaction_created",
                        "data": update_data
                    }
                )
                
                logger.info(f" Signal transaction_created envoyé pour user {user_id}")
                logger.info(f" Transaction: {instance.transaction_type} - {instance.amount}")
                
                # Déclencher aussi une mise à jour wallet pour ce user
                try:
                    wallet = SanekWallet.objects.get(user_id=user_id)
                    # Cela va déclencher le signal wallet automatiquement
                    wallet.save()
                except SanekWallet.DoesNotExist:
                    logger.warning(f"Wallet non trouvé pour user {user_id}")
                
            except Exception as e:
                logger.error(f" Erreur envoi transaction_created pour user {user_id}: {e}")
        
    except Exception as e:
        logger.error(f" Erreur signal transaction created: {e}")

# Nouvelle fonction pour forcer la mise à jour
def force_wallet_update(user_id, reason="manual_refresh"):
    """Force une mise à jour du wallet sans vérification de doublons"""
    try:
        from .models import SanekWallet
        wallet = SanekWallet.objects.get(user_id=user_id)
        wallet_serializer = SanekWalletSerializer(wallet)
        wallet_data = wallet_serializer.data
        
        group_name = f"wallet_{user_id}"
        
        update_data = {
            **wallet_data,
            'update_timestamp': datetime.now().isoformat(),
            'source': 'force_update',
            'reason': reason,
            'force_update': True,
            'user_id': user_id
        }
        
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                "type": "wallet_update",
                "data": update_data
            }
        )
        
        logger.info(f" Force update wallet envoyé pour user {user_id} - raison: {reason}")
        return True
        
    except Exception as e:
        logger.error(f" Erreur force_wallet_update: {e}")
        return False

# Fonction pour nettoyer le cache périodiquement
def cleanup_websocket_cache():
    """Nettoie le cache WebSocket"""
    try:
        pattern = "ws_update:*"
        if hasattr(cache, 'keys'):
            keys = list(cache.keys(pattern))
            if keys:
                cache.delete_many(keys)
                logger.info(f" Cache WebSocket nettoyé: {len(keys)} entrées")
        else:
            logger.info(" Nettoyage cache non supporté par ce backend")
    except Exception as e:
        logger.error(f" Erreur nettoyage cache: {e}")