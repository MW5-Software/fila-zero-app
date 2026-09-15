from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("demonstracao", views.demonstracao, name="demonstracao"),
    path("tema.css", views.tema_css, name="tema"),
    path("versao", views.versao, name="versao"),
]
