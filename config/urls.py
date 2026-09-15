from django.urls import include, path

from plataforma.falhas import pagina_de_erro, pagina_nao_encontrada

#: As páginas de erro são de produção (Bloco 7): o 500 do Django padrão é
#: uma página em inglês sem cara nenhuma, e a de 404 parecia defeito do
#: cliente. Assinatura exata que o Django espera dos handlers.
handler404 = "plataforma.falhas.pagina_nao_encontrada"
handler500 = "plataforma.falhas.pagina_de_erro"

urlpatterns = [
    path("", include("contas.urls")),
    # Antes do `nucleo`: a raiz `/` da fila manda quem só tem a fila direto
    # para ela, e o primeiro padrão que casa é o que vale.
    path("", include("fila.urls")),
    path("", include("nucleo.urls")),
    path("", include("plataforma.urls")),
    path("", include("modulos.exemplo.urls")),
]
