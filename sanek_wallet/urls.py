from django.urls import path
from . import views

urlpatterns = [
    path('', views.get_wallet_data, name='get_wallet_data'),
    path('transactions/', views.get_transaction_history, name='get_transaction_history'),
    path('deposit/', views.make_deposit, name='make_deposit'),
    path('withdraw/', views.make_withdrawal, name='make_withdrawal'),
    path('transfer/', views.make_transfer, name='make_transfer'),
    path('challenge/', views.make_challenge, name='make_challenge'),
]
    # path('wallet_update/', views.send_wallet_update, name='wallet_update'),