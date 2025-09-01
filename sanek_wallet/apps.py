from django.apps import AppConfig


class SanekWalletConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'sanek_wallet'
    
    def ready(self):
        import sanek_wallet.signals
