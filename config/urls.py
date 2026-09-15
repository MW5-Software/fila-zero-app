from django.urls import include, path

from plataforma.falhas import pagina_de_erro, pagina_nao_encontrada

#: As páginas de erro são de produção (Bloco 7): o 500 do Django padrão é
#: uma página em inglês sem cara nenhuma, e a de 404 parecia defeito do
#: cliente. Assinatura exata que o Django espera dos handlers.
handler404 = "plataforma.falhas.pagina_nao_encontrada"
handler500 = "plataforma.falhas.pagina_de_erro"

urlpatterns = [
    path("", include("contas.urls")),
    path("", include("nucleo.urls")),
    path("", include("plataforma.urls")),
    path("", include("modulos.exemplo.urls")),
]
