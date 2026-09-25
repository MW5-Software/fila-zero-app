from django.urls import path

from . import (views, views_cadastros, views_historico, views_indicadores,
               views_metas)

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("fila", views.fila, name="fila"),
    path("fila/estado", views.estado, name="fila_estado"),
    path("fila/agir", views.agir, name="fila_agir"),
    path("fila/indicadores", views_indicadores.indicadores,
         name="fila_indicadores"),
    path("fila/grupos", views_cadastros.grupos, name="fila_grupos"),
    path("fila/motivos", views_cadastros.motivos, name="fila_motivos"),
    path("fila/pausas", views_cadastros.pausas, name="fila_pausas"),
    path("fila/midias", views_cadastros.midias, name="fila_midias"),
    path("fila/metas", views_metas.metas, name="fila_metas"),
    path("fila/historico", views_historico.historico, name="fila_historico"),
]
