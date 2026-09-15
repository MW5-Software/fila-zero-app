from django.urls import path

from . import views

urlpatterns = [
    path("fila", views.fila, name="fila"),
]
