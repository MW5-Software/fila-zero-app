from django.urls import path

from . import views, views_cadastros

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("fila", views.fila, name="fila"),
    path("fila/estado", views.estado, name="fila_estado"),
    path("fila/agir", views.agir, name="fila_agir"),
    path("fila/grupos", views_cadastros.grupos, name="fila_grupos"),
    path("fila/motivos", views_cadastros.motivos, name="fila_motivos"),
    path("fila/pausas", views_cadastros.pausas, name="fila_pausas"),
]
