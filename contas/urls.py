from django.urls import path

from . import (
    views, views_auditoria, views_cargos, views_idioma, views_perfil,
    views_usuarios,
)

urlpatterns = [
    path("entrar", views.entrar, name="entrar"),
    path("sair", views.sair, name="sair"),
    path("idioma", views_idioma.idioma, name="idioma"),
    path("perfil", views_perfil.perfil, name="perfil"),
    path("perfil/senha", views_perfil.perfil_senha, name="perfil_senha"),
    path("perfil/foto", views_perfil.perfil_foto, name="perfil_foto"),
    path("avatar/<int:usuario_id>", views_perfil.avatar, name="avatar"),
    path("cargos", views_cargos.cargos, name="cargos"),
    path("usuarios", views_usuarios.usuarios, name="usuarios"),
    path("auditoria", views_auditoria.auditoria, name="auditoria"),
    path("personificar", views.personificar, name="personificar"),
    path("voltar-a-ser-eu", views.voltar_a_ser_eu, name="voltar_a_ser_eu"),
]
