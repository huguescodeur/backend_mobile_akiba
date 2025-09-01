from django.db import models
import uuid
from django.db import models
from django.conf import settings

# Create your models here.

class SanekWallet(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="wallet")
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    

    def deposit(self, amount):
        """Ajouter des fonds"""
        if amount > 0:
            self.balance += amount
            self.save()
            # SanekTransaction.objects.create(receiver=self.user, amount=amount, transaction_type='deposit')

    def withdraw(self, amount):
        """Retirer des fonds"""
        if amount > 0 and self.balance >= amount:
            self.balance -= amount
            self.save()
            # SanekTransaction.objects.create(sender=self.user, amount=amount, transaction_type='withdraw')
        else:
            raise ValueError("Solde insuffisant")

    def transfer(self, receiver_wallet, amount):
        """Transférer des fonds à un autre utilisateur"""
        if amount > 0 and self.balance >= amount:
            self.balance -= amount
            self.save()

            receiver_wallet.balance += amount
            receiver_wallet.save()

            # SanekTransaction.objects.create(sender=self.user, receiver=receiver_wallet.user, amount=amount, transaction_type='transfer')
        else:
            raise ValueError("Solde insuffisant ou montant invalide")

    def __str__(self):
        return f"Portefeuille de {self.user.full_name} - Solde : {self.balance} FCFA"


class SanekTransaction(models.Model):
    TRANSACTION_TYPES = [
        ('deposit', 'Dépôt'),
        ('withdraw', 'Retrait'),
        ('transfer', 'Transfert'),
        ('challenge', 'Challenge'),
    ]

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_transactions", null=True, blank=True)
    receiver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="received_transactions", null=True, blank=True)
    operator = models.CharField(max_length=50, null=True, blank=True)  # Ex. Wave, MTN
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        managed = False
        db_table = 'sanek_transaction'

    def __str__(self):
        if self.transaction_type == 'transfer':
            return f"Transfert de {self.amount} FCFA de {self.sender} à {self.receiver}"
        elif self.operator:
            return f"{self.transaction_type.capitalize()} de {self.amount} FCFA via {self.operator}"
        return f"{self.transaction_type.capitalize()} de {self.amount} FCFA"

