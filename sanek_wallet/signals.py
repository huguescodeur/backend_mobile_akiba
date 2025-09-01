# from django.db.models.signals import post_save
# from django.dispatch import receiver
# from .models import SanekWallet
# from .serializers import SanekWalletSerializer
# from .views import send_wallet_update

# @receiver(post_save, sender=SanekWallet)
# def notify_wallet_update(sender, instance, created, **kwargs):
#     wallet_serializer = SanekWalletSerializer(instance)
#     send_wallet_update(instance.user, wallet_data=wallet_serializer.data)


# sanek_wallet/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import SanekWallet
from .serializers import SanekWalletSerializer
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import logging

logger = logging.getLogger(__name__)
channel_layer = get_channel_layer()

@receiver(post_save, sender=SanekWallet)
def notify_wallet_update(sender, instance, created, **kwargs):
    """Signal déclenché après sauvegarde du wallet"""
    try:
        wallet_serializer = SanekWalletSerializer(instance)
        group_name = f"wallet_{instance.user.id}"
        
        # Envoyer la mise à jour via WebSocket
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                "type": "wallet_update",
                "data": wallet_serializer.data
            }
        )
        
        logger.info(f"✅ Signal wallet_update envoyé pour user {instance.user.id}")
        logger.info(f"💰 Nouveau solde: {instance.balance}")
        
    except Exception as e:
        logger.error(f"❌ Erreur signal wallet update: {e}")