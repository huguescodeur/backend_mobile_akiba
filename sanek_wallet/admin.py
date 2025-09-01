from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import SanekWallet, SanekTransaction

admin.site.register(SanekWallet)
admin.site.register(SanekTransaction)
