from django.urls import path

from . import (
    views, views_aparencia_da_empresa, views_empresa, views_empresa_contexto,
    views_falhas, views_filial, views_filiais, views_marca, views_parametros,
)

urlpatterns = [
    path("mw5/aparencia", views.aparencia, name="aparencia"),
    path("mw5/aparencia/logos", views_marca.aparencia_logo, name="aparencia_logo"),
    path("mw5/aparencia/previa.css", views.aparencia_previa, name="aparencia_previa"),
    path("mw5/modulos", views.modulos, name="modulos"),
    path("mw5/falhas", views_falhas.falhas, name="falhas"),
    path("marca/imagem/<str:lugar>", views_marca.marca_imagem, name="marca_imagem"),
    # O menu da EMPRESA de quem pede (15/09/2026): com sessão, e sem nada na
    # URL que diga qual empresa — ver `views_marca.logo_da_empresa`.
    path("marca/empresa/menu", views_marca.logo_da_empresa,
         name="logo_da_empresa"),
    path("tema-da-empresa.css", views_marca.tema_da_empresa,
         name="tema_da_empresa"),
    path("filial/trocar", views_filial.filial_trocar, name="filial_trocar"),
    path("empresa/trocar", views_empresa_contexto.empresa_trocar,
         name="empresa_trocar"),
    path("empresa", views_empresa.empresa, name="empresa"),
    # A senha do banco de UMA empresa, buscada quando o olho é clicado.
    # Rota própria porque o valor não pode viajar no HTML da lista — ver o
    # docstring de `senha_do_banco`.
    path("empresa/<int:pk>/senha", views_empresa.senha_do_banco,
         name="empresa_senha"),
    # O menu (logo e cores) de UMA empresa, só para a MW5 — ver
    # `views_aparencia_da_empresa`.
    path("empresa/<int:pk>/menu", views_aparencia_da_empresa.menu_da_empresa,
         name="empresa_menu"),
    # A senha do banco de UMA empresa, buscada quando o olho é clicado.
    # Rota própria porque o valor não pode viajar no HTML da lista — ver o
    # docstring de `senha_do_banco`.
    path("empresa/<int:pk>/senha", views_empresa.senha_do_banco,
         name="empresa_senha"),
    path("filiais", views_filiais.filiais, name="filiais"),
    path("parametros", views_parametros.parametros, name="parametros"),
]
