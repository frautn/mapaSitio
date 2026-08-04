# main/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('articulos/', views.articles, name='articles'),
    path('importar-exportar/', views.import_export, name='import_export'),
]