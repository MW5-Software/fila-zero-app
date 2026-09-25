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


def test_o_trocar_de_loja_da_fila_abre_o_mesmo_dialogo(db):
    """25/09/2026, pedido do cliente: "na fila, quando troca de filial, tem que
    ser modal igual o seletor". O "Trocar de loja" da página da fila levava à
    página nua de confirmação; agora cada link diz ao `contexto.js` qual loja
    é, e ele abre o diálogo do cabeçalho. O `href` continua sendo o da
    confirmação, para a troca funcionar sem script."""
    import re

    from tests.fila_cenario import logado, nova_loja, sylvia

    empresa, _matriz, _titular = sylvia()
    centro = nova_loja(empresa, "Centro")
    html = logado("sylvia").get("/fila").content.decode()

    link = re.search(r'<a [^>]*data-trocar-loja="(\d+)"[^>]*>([^<]*)</a>', html)
    assert link, "o link de trocar de loja não diz qual loja é"
    assert (link.group(1), link.group(2)) == (str(centro.pk), "Centro")
    assert f'href="{reverse("filial_trocar")}?filial_id={centro.pk}' in link.group(0)
    assert 'id="trocar-dialogo"' in html


def test_o_trocar_de_loja_das_metas_abre_o_mesmo_dialogo(db):
    from tests.fila_cenario import logado, nova_loja, sylvia

    empresa, _matriz, _titular = sylvia()
    centro = nova_loja(empresa, "Centro")
    html = logado("sylvia").get(reverse("fila_metas")).content.decode()

    assert f'data-trocar-loja="{centro.pk}"' in html
    assert 'id="trocar-dialogo"' in html
    assert 'name="voltar" value="/fila/metas' in html


def test_o_script_abre_o_dialogo_pelo_link_de_loja():
    """O outro lado do contrato: o script procura o atributo que os links
    levam. Sem este teste, renomear um dos dois deixaria o link caindo na
    página nua sem erro nenhum."""
    from pathlib import Path

    script = Path("plataforma/static/plataforma/contexto.js").read_text()
    assert "[data-trocar-loja]" in script


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


class TestAPerguntaDizEmpresaEFilial:
    """25/09/2026, pedido do cliente: "Trocar Empresa/Filial? Você vai passar
    a trabalhar na empresa - filial selecionada". A pergunta dizia só o nome
    escolhido ("Trocar de lugar? Você vai passar a trabalhar em Centro"), e
    não em qual empresa aquela loja estava.

    O script escreve os dois nomes, e o servidor entrega o que ele não sabe:
    na troca de loja, a empresa de agora; na troca de empresa, a loja em que
    a pessoa vai CAIR — a Matriz, ou a primeira que alcança
    (`plataforma.contexto.filial_de_entrada`), a mesma que a sessão escolhe
    depois de trocar."""

    def _dialogo(self, html):
        return html.split('id="trocar-dialogo"')[1].split("</form></div>")[0]

    def test_o_titulo_e_a_frase(self, com_duas):
        html = _home(com_duas)
        assert "Trocar Empresa/Filial?" in html
        assert "Você vai passar a trabalhar na" in html

    def test_a_troca_de_loja_leva_o_nome_da_empresa_de_agora(self, db):
        from tests.fila_cenario import logado, nova_loja, sylvia

        empresa, _matriz, _titular = sylvia()
        nova_loja(empresa, "Centro")
        html = logado("sylvia").get("/fila").content.decode()

        assert f'data-empresa="{empresa}"' in html

    def test_a_troca_de_empresa_leva_a_loja_em_que_se_cai(self, com_duas):
        import json
        import re

        from plataforma.models import Empresa, Filial

        beta = Empresa.objects.get(razao_social="Beta Ltda")
        Filial.objects.create(empresa=beta, nome="Aaa Primeira", apelido="Aaa Primeira")
        html = _home(com_duas)

        bruto = re.search(r"data-chegada='([^']*)'", html) or re.search(
            r'data-chegada="([^"]*)"', html)
        assert bruto, "o formulário da empresa não diz em que loja se cai"
        from html import unescape

        chegada = json.loads(unescape(bruto.group(1)))
        assert chegada[str(beta.pk)] == "Matriz", (
            "a Matriz vem antes de quem a passa no alfabeto, como na sessão")


def test_a_filial_de_entrada_e_a_mesma_da_sessao(db):
    """A frase e a sessão perguntam à MESMA função: se divergissem, o
    diálogo diria uma loja e a pessoa cairia noutra."""
    import inspect

    from plataforma import contexto

    assert "filial_de_entrada(" in inspect.getsource(contexto._decidir_filial)
