"""Trocar de empresa ou de loja sem trocar de página (18/09/2026).

Escolher outra empresa no cabeçalho levava para a mesma página nua do sair —
"Trabalhar em Sylvia Móveis?", um cartão encostado no canto, sem menu e sem
contexto nenhum. Quem cancelava voltava para a raiz, e não para onde estava.

Agora a pergunta é o mesmo diálogo do sair, por cima da página. O caminho por
URL (`/empresa/trocar?empresa_id=N`) continua existindo e continua sendo quem
age — o POST é o único jeito de trocar, e um `<img src="...">` não muda o
contexto de ninguém.

**O seletor do cabeçalho já dependia de JavaScript** (`data-auto-enviar`, do
design system): sem ele o `<form>` do contexto não tem botão nenhum e nunca
enviou nada. O diálogo não tira caminho de ninguém.
"""

import pytest
from django.test import Client
from django.urls import reverse

from tests.conftest import abrir_conta

SENHA = "segredo-de-teste"


def _duas_empresas(login="sylvia"):
    from plataforma.models import Empresa

    alfa = Empresa.objects.create(razao_social="Alfa Ltda")
    titular = abrir_conta(alfa, login, SENHA)
    Empresa.objects.create(razao_social="Beta Ltda", dono=titular)
    return titular


def _logado(login="sylvia") -> Client:
    c = Client()
    c.post(reverse("entrar"), {"usuario": f"{login}@teste.com", "senha": SENHA})
    return c


@pytest.fixture
def com_duas(db):
    _duas_empresas()
    return _logado()


def _home(cliente) -> str:
    resposta = cliente.get(reverse("home"))
    assert resposta.status_code == 200
    return resposta.content.decode()


def test_quem_tem_o_que_trocar_recebe_o_dialogo_fechado(com_duas):
    html = _home(com_duas)

    assert 'class="overlay" id="trocar-dialogo"' in html, \
        "o diálogo não existe, ou nasceu aberto"
    assert f'action="{reverse("empresa_trocar")}"' in html


def test_so_vem_o_formulario_do_nivel_que_a_pessoa_troca(com_duas):
    """Duas empresas, uma loja em cada: não há troca de loja para fazer, e um
    campo `filial_id` escondido numa página de quem não troca de loja é um
    campo que ninguém esperava ali."""
    html = _home(com_duas)
    # Só o DIÁLOGO: desde 25/09/2026 o cabeçalho mostra a loja mesmo quando é
    # uma só, e o `<select name="filial_id">` dele é esperado lá.
    dialogo = html.split('id="trocar-dialogo"')[1]

    assert f'action="{reverse("filial_trocar")}"' not in dialogo
    assert 'name="filial_id"' not in dialogo


def test_quem_nao_tem_o_que_trocar_nao_recebe_o_dialogo(db):
    """Uma empresa e uma filial: não há faixa de contexto no cabeçalho, e um
    diálogo sem gatilho é peso morto em toda página — dois formulários e mais
    um token de CSRF."""
    from plataforma.models import Empresa

    abrir_conta(Empresa.objects.create(razao_social="Alfa Ltda"), "so_uma", SENHA)

    assert "trocar-dialogo" not in _home(_logado("so_uma"))


def test_o_dialogo_leva_o_token_de_cada_formulario(com_duas):
    """Um token por formulário: sem o dele, a troca morre em 403."""
    html = _home(com_duas)
    depois_do_dialogo = html.split('id="trocar-dialogo"')[1]

    assert depois_do_dialogo.count("csrfmiddlewaretoken") >= 1
    assert "data-id-escolhido" in depois_do_dialogo


def test_o_formulario_da_loja_volta_para_a_pagina_de_onde_se_trocou(db):
    """A troca de loja já sabia voltar (`_voltar_seguro`), e é o que a fila
    precisa: o vendedor troca de loja e continua na fila, não na raiz."""
    from tests.fila_cenario import logado, nova_loja, sylvia

    empresa, _matriz, _titular = sylvia()
    # A titular, que alcança as duas lojas — o gerente de fábrica alcança só a
    # dele, e para quem alcança uma loja só não há faixa de contexto nenhuma.
    nova_loja(empresa, "Centro")
    html = logado("sylvia").get("/fila").content.decode()

    assert 'id="trocar-dialogo"' in html
    assert 'name="voltar" value="/fila"' in html


def test_o_caminho_por_url_continua_perguntando(com_duas):
    """O diálogo é a porta nova, e não a única: `/empresa/trocar` em GET
    continua mostrando a confirmação, e só o POST age."""
    from plataforma.models import Empresa

    beta = Empresa.objects.get(razao_social="Beta Ltda")
    resposta = com_duas.get(f"{reverse('empresa_trocar')}?empresa_id={beta.pk}")

    assert resposta.status_code == 200
    assert "Trabalhar em Beta Ltda?" in resposta.content.decode()


def test_o_script_da_troca_vem_em_toda_pagina(com_duas):
    assert "/static/plataforma/contexto.js" in _home(com_duas)
