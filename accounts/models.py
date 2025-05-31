from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from datetime import timedelta
import random
import string

# Create your models here.
class CustomUser(AbstractUser):
    phone_number = models.CharField(max_length=20, unique=True)
    full_name = models.CharField(max_length=255)
    is_phone_verified = models.BooleanField(default=False)
    has_pin_code = models.BooleanField(default=False)
    pin_code = models.CharField(max_length=128, null=True, blank=True)  # Haché
    profile_picture = models.ImageField(upload_to='profiles/', null=True, blank=True)
    last_pin_entry = models.DateTimeField(null=True, blank=True)
    last_background_time = models.DateTimeField(null=True, blank=True)
    requires_pin_auth = models.BooleanField(default=False)
    
    # Utiliser le numéro de téléphone comme identifiant unique
    USERNAME_FIELD = 'phone_number'
    REQUIRED_FIELDS = ['full_name']
    
    def __str__(self):
        return f"{self.full_name} ({self.phone_number})"
    
    def set_pin_code(self, pin):
        """Hasher et sauvegarder le code PIN"""
        from django.contrib.auth.hashers import make_password
        self.pin_code = make_password(pin)
        self.has_pin_code = True
        self.save()
    
    def check_pin_code(self, pin):
        """Vérifier le code PIN"""
        from django.contrib.auth.hashers import check_password
        return check_password(pin, self.pin_code)
    
    def update_pin_entry_time(self):
        """Mettre à jour le temps de dernière saisie du PIN"""
        self.last_pin_entry = timezone.now()
        self.requires_pin_auth = False
        self.save()
        
    def should_require_pin(self):
        if not self.has_pin_code:
            print("[PIN CHECK] L'utilisateur n’a pas encore de code PIN.")
            return True

        if not self.last_pin_entry:
            print("[PIN CHECK] Aucune entrée PIN enregistrée précédemment pour le last pin entry.")
            return True

        if not self.last_background_time:
            print("[PIN CHECK] Aucune entrée PIN enregistrée précédemment pour last background.")
            return False  # Pas encore passé en arrière-plan

        time_diff = timezone.now() - self.last_background_time
        print(f"[PIN CHECK] Depuis arrière-plan : {time_diff}")

        # Vérifie seulement le temps hors app (pas dans l'app)
        if time_diff > timedelta(minutes=1):  # ou 5 minutes selon ton besoin
            print("[PIN CHECK] + de 1 minute écoulée → demander de nouveau le PIN.")
            return True
        
        print("[PIN CHECK] Moins d’1 minute écoulée → accès autorisé.")

        return False

        
    # def should_require_pin(self):
    #     if not self.has_pin_code:
    #         print("[PIN CHECK] L'utilisateur n’a pas encore de code PIN.")
    #         return True

    #     if not self.last_pin_entry:
    #         print("[PIN CHECK] Aucune entrée PIN enregistrée précédemment.")
    #         return True

    #     time_diff = timezone.now() - self.last_pin_entry
    #     print(f"[PIN CHECK] Temps depuis dernière saisie PIN : {time_diff}")

    #     if time_diff > timedelta(minutes=1):
    #         print("[PIN CHECK] + de 1 minute écoulée → demander de nouveau le PIN.")
    #         return True

    #     print("[PIN CHECK] Moins d’1 minute écoulée → accès autorisé.")
    #     return False

    
    # def should_require_pin(self):
    #     """Vérifier si l'utilisateur doit ressaisir son PIN (après 1 minute d'inactivité)"""
    #     if not self.has_pin_code or not self.last_pin_entry:
    #         return True
        
    #     time_diff = timezone.now() - self.last_pin_entry
    #     return time_diff > timedelta(minutes=1)


class PhoneVerification(models.Model):
    phone_number = models.CharField(max_length=20)
    verification_code = models.CharField(max_length=6)
    full_name = models.CharField(max_length=255)
    password = models.CharField(max_length=128)  # Mot de passe temporaire haché
    created_at = models.DateTimeField(auto_now_add=True)
    is_verified = models.BooleanField(default=False)
    expires_at = models.DateTimeField()
    attempts = models.IntegerField(default=0)
    max_attempts = models.IntegerField(default=3)
    
    class Meta:
        unique_together = ['phone_number', 'verification_code']
    
    def save(self, *args, **kwargs):
        if not self.verification_code:
            self.verification_code = self.generate_code()
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(minutes=10)  # Expire après 10 minutes
        super().save(*args, **kwargs)
    
    def generate_code(self):
        """Générer un code de vérification à 6 chiffres"""
        return ''.join(random.choices(string.digits, k=6))
    
    def is_expired(self):
        """Vérifier si le code a expiré"""
        return timezone.now() > self.expires_at
    
    def increment_attempts(self):
        """Incrémenter le nombre de tentatives"""
        self.attempts += 1
        self.save()
    
    def can_attempt(self):
        """Vérifier si l'utilisateur peut encore essayer"""
        return self.attempts < self.max_attempts
    
    def __str__(self):
        return f"Verification for {self.phone_number} - {self.verification_code}"


class UserSession(models.Model):
    """Modèle pour gérer les sessions utilisateur et l'authentification PIN"""
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='session_info')
    jwt_token = models.TextField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    device_info = models.JSONField(default=dict, blank=True)  # Stocker info appareil
    
    def __str__(self):
        return f"Session for {self.user.phone_number}"
    
    def is_session_active(self):
        """Vérifier si la session est toujours active"""
        # Session active si dernière activité < 24h
        time_diff = timezone.now() - self.last_activity
        return time_diff < timedelta(hours=24)
    
    def update_activity(self):
        """Mettre à jour la dernière activité"""
        self.last_activity = timezone.now()
        self.save()