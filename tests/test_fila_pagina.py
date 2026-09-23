"""A página da fila vista por quem a usa: vendedor, gerente, supervisor.

Pelo `django.test.Client`, sem navegador. Cada teste diz a regra; os de
permissão e isolamento são os que o spec lista em "Como se prova".
"""

import json
from types import SimpleNamespace

import pytest
from django.urls import reverse

from tests.fila_cenario import (  # noqa: F401
    cadastros, logado, nova_loja, pessoa_na_loja, relogio, sylvia)

pytestmark = pytest.mark.django_db


@pytest.fixture
def loja(relogio):
    empresa, matriz, titular = sylvia()
    return SimpleNamespace(
        empresa=empresa, matriz=matriz,
        ana=pessoa_na_loja("ana", empresa, matriz),
        bia=pessoa_na_loja("bia", empresa, matriz),
        gil=pessoa_na_loja("gil", empresa, matriz, cargo="gerente"),
        cad=cadastros(empresa))


def _agir(cliente, **dados):
    return cliente.post(reverse("fila_agir"), dados)


def _agir_js(cliente, **dados):
    resposta = cliente.post(reverse("fila_agir"), dados, HTTP_X_FILA="1")
    return json.loads(resposta.content)


def _html(cliente, url="/fila"):
    resposta = cliente.get(url)
    assert resposta.status_code == 200
    return resposta.content.decode()


# --- O caminho do vendedor ---------------------------------------------------

def test_vendedor_bate_o_ponto_e_e_a_vez_dele(loja):
    ana = logado("ana")
    assert "Bater o ponto" in _html(ana)
    assert _agir(ana, acao="ponto").status_code == 302
    html = _html(ana)
    assert "É a sua vez" in html
    assert "Vou atender" in html


def test_o_segundo_ve_a_posicao(loja):
    _agir(logado("ana"), acao="ponto")
    bia = logado("bia")
    _agir(bia, acao="ponto")
    html = _html(bia)
    assert "Você é o 2º da fila" in html
    assert "Uma pessoa na sua frente" in html
    assert "Cliente pediu por mim" in html


def test_finalizar_com_venda_pela_pagina(loja):
    from fila.models import Atendimento

    ana = logado("ana")
    _agir(ana, acao="ponto")
    _agir(ana, acao="atender")
    assert 'name="grupo"' in _html(ana, "/fila?folha=finalizar")
    _agir(ana, acao="finalizar", resultado="vendeu",
          grupo=[str(loja.cad.grupo.pk), str(loja.cad.grupo2.pk), ""],
          valor=["1.500,50", "300", ""])
    atendimento = Atendimento.irrestritos.get()
    assert str(atendimento.total) == "1800.50"


def test_recusa_sem_javascript_aparece_uma_vez(loja):
    _agir(logado("ana"), acao="ponto")
    bia = logado("bia")
    _agir(bia, acao="ponto")
    _agir(bia, acao="atender")
    assert "A vez é de Ana. Você é o 2º da fila." in _html(bia)
    assert "A vez é de Ana" not in _html(bia)


def test_acao_com_javascript_devolve_o_estado_novo(loja):
    resposta = _agir_js(logado("ana"), acao="ponto")
    assert resposta["ok"] is True
    assert "É a sua vez" in resposta["html"]["painel"]
    assert set(resposta["html"]) == {"painel", "lista", "barra", "lancamentos",
                                    "meus"}
    recusa = _agir_js(logado("ana"), acao="ponto")
    assert recusa == {**recusa, "ok": False, "frase": "Você já está nesta loja."}


def test_estado_so_manda_html_quando_mudou(loja):
    ana = logado("ana")
    primeira = json.loads(ana.get(reverse("fila_estado")).content)
    assert primeira["mudou"] is True
    url = reverse("fila_estado") + "?versao=" + primeira["versao"]
    assert json.loads(ana.get(url).content) == {
        "versao": primeira["versao"], "mudou": False}
    _agir(logado("bia"), acao="ponto")
    depois = json.loads(ana.get(url).content)
    assert depois["mudou"] is True and "Bia" in depois["html"]["lista"]


def test_a_pagina_nao_tem_tabela():
    """R46 vale para tabela; a fila é lista (Global Constraints)."""
    empresa, matriz, _ = sylvia()
    pessoa_na_loja("ana", empresa, matriz)
    assert "<table" not in _html(logado("ana"))


# --- Quem vê o quê -----------------------------------------------------------

def test_sem_fila_ver_as_tres_rotas_nao_existem(loja):
    pessoa_na_loja("rita", loja.empresa, loja.matriz, cargo="representante")
    rita = logado("rita")
    assert rita.get(reverse("fila")).status_code == 404
    assert rita.get(reverse("fila_estado")).status_code == 404
    assert _agir(rita, acao="ponto").status_code == 404


def test_supervisor_ve_a_fila_sem_bater_o_ponto_e_acha_no_menu(loja):
    pessoa_na_loja("sara", loja.empresa, None, cargo="supervisor")
    sara = logado("sara")
    html = _html(sara)
    assert "Bater o ponto" not in html
    assert _agir(sara, acao="ponto").status_code == 404
    assert 'href="/fila"' in _html(sara, "/")      # D-1


def test_vendedor_nao_corrige(loja):
    _agir(logado("bia"), acao="ponto")
    assert _agir(logado("ana"), acao="tirar",
                 pessoa=str(loja.bia.pk)).status_code == 404


def test_gerente_corrige_na_loja_dele(loja):
    from fila.models import LugarNaFila

    _agir(logado("ana"), acao="ponto")
    _agir(logado("gil"), acao="tirar", pessoa=str(loja.ana.pk),
          motivo_da_correcao="motivo do teste")
    assert not LugarNaFila.irrestritos.exists()


def test_gerente_de_outra_loja_nao_corrige_a_matriz(loja):
    from fila.models import LugarNaFila

    centro = nova_loja(loja.empresa, "Centro")
    pessoa_na_loja("caio", loja.empresa, centro, cargo="gerente")
    _agir(logado("ana"), acao="ponto")
    caio = logado("caio")
    _agir(caio, acao="tirar", pessoa=str(loja.ana.pk), motivo_da_correcao="motivo do teste")
    assert LugarNaFila.irrestritos.filter(pessoa=loja.ana).exists()
    assert "Essa pessoa não está nesta loja." in _html(caio)


def test_supervisor_corrige_na_empresa(loja):
    from fila.models import LugarNaFila

    pessoa_na_loja("sara", loja.empresa, None, cargo="supervisor")
    _agir(logado("ana"), acao="ponto")
    _agir(logado("sara"), acao="tirar", pessoa=str(loja.ana.pk),
          motivo_da_correcao="motivo do teste")
    assert not LugarNaFila.irrestritos.exists()


def test_gerente_edita_lancamento_de_hoje_pela_pagina(loja):
    from fila.models import Atendimento

    ana = logado("ana")
    _agir(ana, acao="ponto")
    _agir(ana, acao="atender")
    _agir(ana, acao="finalizar", resultado="nao_vendeu",
          motivo=str(loja.cad.motivo.pk))
    atendimento = Atendimento.irrestritos.get()
    gil = logado("gil")
    assert "Lançamentos de hoje" in _html(gil)
    assert 'name="atendimento"' in _html(
        gil, f"/fila?folha=editar&atendimento={atendimento.pk}")
    _agir(gil, acao="editar", atendimento=str(atendimento.pk),
          resultado="nao_vendeu", motivo=str(loja.cad.motivo.pk),
          observacao="volta amanhã", motivo_da_correcao="motivo do teste")
    atendimento.refresh_from_db()
    assert atendimento.observacao == "volta amanhã"


def test_sem_loja_a_pagina_diz_o_que_falta(db):
    from contas.models import Usuario

    Usuario.objects.create_superuser(email="raiz@teste.com", password="x")
    from django.test import Client

    raiz = Client()
    raiz.post(reverse("entrar"), {"usuario": "raiz@teste.com", "senha": "x"})
    html = _html(raiz)
    assert "Você ainda não está em nenhuma loja" in html


# --- Isolamento --------------------------------------------------------------

def test_tipo_de_pausa_de_outra_conta_e_recusado(loja):
    from fila.models import Pausa, TipoDePausa
    from plataforma.models import Empresa
    from tests.conftest import abrir_conta

    outra = Empresa.objects.create(razao_social="Concorrente",
                                   nome_fantasia="Concorrente")
    abrir_conta(outra, "concorrente")
    outra.refresh_from_db()
    alheio = TipoDePausa.irrestritos.create(empresa=outra, nome="Almoço")
    ana = logado("ana")
    _agir(ana, acao="ponto")
    _agir(ana, acao="pausar", tipo=str(alheio.pk))
    assert not Pausa.irrestritos.exists()
    assert "Escolha o tipo de pausa." in _html(ana)


def test_id_que_nao_e_numero_nao_estoura(loja):
    ana = logado("ana")
    _agir(ana, acao="ponto")
    assert _agir(ana, acao="pausar", tipo="abc").status_code == 302
    assert _agir(ana, acao="finalizar", resultado="vendeu", grupo=["x"],
                 valor=["10"]).status_code == 302


# --- Onde se cai depois de entrar (spec 2026-09-16, V1) ------------------------

def _entrar(pessoa):
    from django.test import Client

    return Client().post(reverse("entrar"), {
        "usuario": pessoa.email, "senha": "segredo-de-teste"})


def test_quem_so_tem_a_fila_entra_por_ela(loja):
    """Sem `follow`: é o LOGIN que manda para a fila, e não a raiz."""
    assert _entrar(loja.ana)["Location"] == reverse("fila")


def test_quem_tem_mais_que_a_fila_entra_pela_raiz(loja):
    assert _entrar(loja.gil)["Location"] == "/"


def test_o_vendedor_abre_a_raiz_sem_ser_mandado_para_a_fila(loja):
    resposta = logado("ana").get("/")
    assert resposta.status_code == 200


def test_quem_tem_mais_que_a_fila_cai_no_painel(loja):
    resposta = logado("gil").get("/")
    assert resposta.status_code == 200


def test_quem_participa_acha_o_painel_pela_fila(loja):
    """Sem menu na página da fila, o link é o caminho do vendedor até o
    painel dele (spec 2026-09-16)."""
    html = _html(logado("ana"))
    assert 'href="/" data-meu-painel' in html and "Meu painel" in html


def test_o_supervisor_tambem_acha_o_painel_pela_fila(loja):
    """O link é de quem TEM painel na raiz, e não só de quem atende.

    O supervisor de fábrica gerencia a loja e não bate ponto, mas a raiz dele
    é o painel da gestão (`fila.relatorios`) — e sem o link ele não tinha
    caminho nenhum até lá (18/09/2026, pedido do cliente: "dono, supervisor e
    gerente não tem o meu painel na página da fila").
    """
    pessoa_na_loja("sara", loja.empresa, None, cargo="supervisor")
    assert 'href="/" data-meu-painel' in _html(logado("sara"))


def test_o_gerente_e_o_dono_tambem_acham(loja):
    for login in ("gil", "sylvia"):
        assert 'href="/" data-meu-painel' in _html(logado(login)), login


def test_quem_so_ve_a_fila_nao_tem_o_link_do_painel(loja):
    """`fila.ver` sozinho abre a fila e mais nada: em `/` a pessoa recebe a
    saudação, e o link não teria para onde levar."""
    from contas.models import Usuario
    from tests.conftest import alocar, cargo_com, email_de
    from tests.fila_cenario import SENHA

    cargo = cargo_com(loja.empresa, "fila.ver", nome="so-ve")
    vera = Usuario.objects.create_user(email=email_de("vera"), password=SENHA,
                                       nome="Vera",
                                       dono_id=loja.empresa.dono_id)
    alocar(vera, loja.empresa, cargo, filial=loja.matriz)
    assert "data-meu-painel" not in _html(logado("vera"))


def test_as_folhas_abrem_pela_url(loja):
    """Sem JavaScript, a folha abre por `?folha=`. Cada uma desenha o
    formulário que o POST espera; a de corrigir só abre com alvo desta loja."""
    ana = logado("ana")
    _agir(ana, acao="ponto")
    assert 'name="tipo"' in _html(ana, "/fila?folha=pausa")
    _agir(ana, acao="atender")
    gil = logado("gil")
    fechar = _html(gil, f"/fila?folha=fechar&pessoa={loja.ana.pk}")
    assert f'name="pessoa" value="{loja.ana.pk}"' in fechar
    assert '<div class="overlay open" id="folha-fechar"' in fechar
    tirar = _html(gil, f"/fila?folha=tirar&pessoa={loja.ana.pk}")
    assert '<div class="overlay open" id="folha-tirar"' in tirar
    corrigir = _html(gil, f"/fila?folha=corrigir&pessoa={loja.ana.pk}")
    assert '<div class="overlay open" id="folha-corrigir"' in corrigir
    forjada = _html(gil, "/fila?folha=tirar&pessoa=999999")
    assert '<div class="overlay open" id="folha-tirar"' not in forjada


class TestAFilaEUmaTelaDoSistema:
    """A fila veste o design system (pedido de 15/09/2026, depois de a
    primeira versão, com folha e paleta próprias, sair com cara de outro
    produto): o shell com o cabeçalho da casa, sem a barra lateral, e uma
    folha que só usa os tokens do tema. Sem navegador (regra da casa): o que
    se prova aqui é o que a página carrega e declara."""

    FOLHA = "fila/static/fila/fila.css"
    SCRIPT = "fila/static/fila/fila.js"

    def _folha(self):
        from pathlib import Path

        return Path(self.FOLHA).read_text(encoding="utf-8")

    @pytest.mark.django_db
    def test_a_pagina_esta_no_shell_sem_a_barra_lateral(self, loja):
        html = _html(logado("ana"))
        assert "/tema.css" in html and "mw5.css" in html
        assert "<header>" in html
        assert 'class="side"' not in html
        assert 'class="fila-pagina"' in html

    def test_o_numero_sobe_para_a_linha_do_titulo(self):
        """23/09/2026, ajuste do cliente: "não era centralizado no meio do
        trem, era centralizado na linha ali, era só subir ele um pouco".

        O número é centrado contra o bloco de texto inteiro — título, apoio e a
        trilha —, e por isso nascia abaixo da linha do "na fila agora". O que
        se prova aqui é o ajuste: o número sobe dez pixels, e o estado NÃO é
        centralizado no cartão (a primeira leitura disto, que o cliente
        corrigiu).
        """
        folha = self._folha()
        numero = folha[folha.index(".fila-numeral {"):]
        numero = numero[:numero.index("}")]
        assert "translateY(-10px)" in numero
        estado = folha[folha.index(".fila-estado {"):]
        estado = estado[:estado.index("}")]
        assert "justify-content: center" not in estado

    def test_a_folha_nao_inventa_cor(self):
        """Toda cor vem do tema: uma cor escrita à mão aqui não acompanharia a
        marca do cliente, e a fila voltaria a parecer outro sistema. O único
        literal aceito é o branco do ícone sobre o verde da venda."""
        import re

        literais = set(re.findall(r"#[0-9a-fA-F]{3,8}\b", self._folha()))
        assert literais <= {"#fff"}, literais

    def test_o_que_a_pagina_esconde_some_de_verdade(self):
        """A recusa, a parte de venda e a de não venda das folhas e os blocos
        do "Corrigir" são escondidos com `hidden`. A varredura da casa
        (`tests/test_esconder_vence_o_display.py`) só reconhece o elemento
        criado por `createElement`, e o script da fila esconde o que o
        servidor desenhou."""
        import re

        assert re.search(r"\[hidden\]\s*\{\s*display:\s*none\s*!important",
                         self._folha())

    def test_movimento_respeita_quem_pediu_menos(self):
        assert "prefers-reduced-motion" in self._folha()

    def test_o_script_consulta_a_cada_tres_segundos(self):
        from pathlib import Path

        script = Path(self.SCRIPT).read_text(encoding="utf-8")
        assert "3000" in script
        assert "X-Fila" in script

    @pytest.mark.django_db
    def test_a_pagina_carrega_folha_e_script_versionados(self, loja):
        html = _html(logado("ana"))
        assert "/static/fila/fila.css?v=" in html
        assert "/static/fila/fila.js?v=" in html


def test_seus_numeros_mostram_so_a_propria_pessoa(loja):
    ana = logado("ana")
    _agir(ana, acao="ponto")
    _agir(ana, acao="atender")
    _agir(ana, acao="finalizar", resultado="vendeu",
          grupo=[str(loja.cad.grupo.pk)], valor=["1.200"])
    bia = logado("bia")
    _agir(bia, acao="ponto")
    _agir(bia, acao="atender")
    _agir(bia, acao="finalizar", resultado="nao_vendeu",
          motivo=str(loja.cad.motivo.pk))
    html = _html(ana)
    assert "Seus números" in html
    assert "R$ 1.200,00" in html
    assert "1º de 1" in html
    bia_html = _html(bia)
    assert "R$ 1.200,00" not in bia_html
    assert "Sem vendas no mês" in bia_html


def test_quem_so_ve_nao_tem_seus_numeros(loja):
    pessoa_na_loja("sara", loja.empresa, None, cargo="supervisor")
    assert "Seus números" not in _html(logado("sara"))


def test_a_consulta_traz_o_pedaco_dos_numeros(loja):
    ana = logado("ana")
    resposta = _agir_js(ana, acao="ponto")
    assert "meus" in resposta["html"]


# --- Correções da revisão final (15/09/2026) -------------------------------

def test_trocar_de_vendeu_para_nao_vendeu_ignora_os_campos_escondidos(loja):
    """M1: a folha só esconde o bloco da venda; os campos continuam indo no
    POST. O que vale é o resultado escolhido."""
    from fila.models import Atendimento

    ana = logado("ana")
    _agir(ana, acao="ponto")
    _agir(ana, acao="atender")
    _agir(ana, acao="finalizar", resultado="nao_vendeu",
          motivo=str(loja.cad.motivo.pk),
          grupo=[str(loja.cad.grupo.pk)], valor=["1500"])
    assert Atendimento.irrestritos.get().resultado == "nao_vendeu"


def test_trocar_de_nao_vendeu_para_vendeu_ignora_o_motivo(loja):
    from fila.models import Atendimento

    ana = logado("ana")
    _agir(ana, acao="ponto")
    _agir(ana, acao="atender")
    _agir(ana, acao="finalizar", resultado="vendeu", motivo=str(loja.cad.motivo.pk),
          observacao="nada", grupo=[str(loja.cad.grupo.pk)], valor=["100"])
    atendimento = Atendimento.irrestritos.get()
    assert (atendimento.resultado, atendimento.motivo_id) == ("vendeu", None)


def test_valor_alto_demais_e_recusado_com_frase(loja):
    """M3: um código de barras colado no valor estourava a coluna com 500."""
    ana = logado("ana")
    _agir(ana, acao="ponto")
    _agir(ana, acao="atender")
    resposta = _agir(ana, acao="finalizar", resultado="vendeu",
                     grupo=[str(loja.cad.grupo.pk)], valor=["7891234567890"])
    assert resposta.status_code == 302
    assert "Valor alto demais" in _html(ana)


def test_editar_lancamento_com_grupo_desativado_oferece_o_grupo(loja):
    """M4: a folha de correção precisa oferecer o grupo e o motivo do próprio
    atendimento, mesmo desativados depois."""
    from fila.models import Atendimento, GrupoDeItem, MotivoDeNaoVenda

    ana = logado("ana")
    _agir(ana, acao="ponto")
    _agir(ana, acao="atender")
    _agir(ana, acao="finalizar", resultado="vendeu",
          grupo=[str(loja.cad.grupo2.pk)], valor=["300"])
    atendimento = Atendimento.irrestritos.get()
    GrupoDeItem.irrestritos.filter(pk=loja.cad.grupo2.pk).update(ativo=False)
    html = _html(logado("gil"), f"/fila?folha=editar&atendimento={atendimento.pk}")
    assert f'<option value="{loja.cad.grupo2.pk}" selected>Tapetes</option>' in html


def test_id_com_digito_unicode_nao_estoura(loja):
    """B5: "²".isdigit() é verdade, e int("²") estourava."""
    ana = logado("ana")
    _agir(ana, acao="ponto")
    assert _agir(ana, acao="pausar", tipo="²").status_code == 302


def test_quem_esta_em_duas_lojas_troca_de_loja_pela_propria_fila(loja):
    """No celular o cabeçalho do sistema esconde o seletor de filial (abaixo de
    1000px), e o vendedor de duas lojas não tinha como trocar pela fila."""
    from contas.models import Alocacao, Cargo

    centro = nova_loja(loja.empresa, "Centro")
    Alocacao.objects.create(pessoa=loja.ana, empresa=loja.empresa, filial=centro,
                            cargo=Cargo.objects.get(conta_id=loja.empresa.conta_id,
                                                    nome="vendedor"))
    html = _html(logado("ana"))
    # A loja da sessão é uma das duas; o link oferecido é o da outra.
    oferecidas = {pk for pk in (loja.matriz.pk, centro.pk)
                  if f"/filial/trocar?filial_id={pk}&amp;voltar=%2Ffila" in html}
    assert len(oferecidas) == 1
    assert "/filial/trocar?" not in _html(logado("bia"))


# --- A meta em "Seus números" (entrega 3) -------------------------------------

def _meta(loja, pessoa, valor, filial=None):
    from decimal import Decimal

    from django.utils import timezone

    from fila.models import MetaDeVenda

    return MetaDeVenda.irrestritos.create(
        empresa=loja.empresa, filial=filial or loja.matriz, pessoa=pessoa,
        mes=timezone.localdate().replace(day=1), valor=Decimal(valor))


def test_seus_numeros_mostram_a_meta_da_propria_pessoa(loja):
    _meta(loja, loja.ana, "4000")
    ana = logado("ana")
    _agir(ana, acao="ponto")
    _agir(ana, acao="atender")
    _agir(ana, acao="finalizar", resultado="vendeu",
          grupo=[str(loja.cad.grupo.pk)], valor=["1.000"])
    html = _html(ana)
    assert "Meta do mês" in html and "R$ 4.000,00" in html and "25%" in html
    assert "Faltam R$ 3.000,00" in html
    assert "Meta do mês" not in _html(logado("bia"))


def test_meta_de_outra_loja_nao_aparece(loja):
    centro = nova_loja(loja.empresa, "Centro")
    _meta(loja, loja.ana, "4000", filial=centro)
    assert "Meta do mês" not in _html(logado("ana"))


def test_a_versao_muda_quando_a_meta_muda(loja):
    from fila.estado import versao_da_fila

    antes = versao_da_fila(loja.matriz)
    m = _meta(loja, loja.ana, "4000")
    depois = versao_da_fila(loja.matriz)
    assert depois != antes
    m.valor = m.valor + 1
    m.save()
    assert versao_da_fila(loja.matriz) != depois


# --- Quem está logado (17/09/2026) ------------------------------------------

def test_o_nome_de_quem_esta_logado_fica_no_topo(loja):
    """O celular da loja passa de mão em mão: o nome em cima diz de quem é a
    fila que está aberta, antes de alguém bater o ponto no lugar de outro.

    Desde 23/09/2026 ele sai FORA do cartão, numa faixa própria acima do painel
    (pedido do cliente: "o nome do usuário e filial tem que sair do cargo e
    aumentar o tamanho para melhor visualição"), com a loja ao lado.
    """
    import re

    from contas.models import Usuario

    Usuario.objects.filter(pk=loja.ana.pk).update(nome="Ana Souza")
    html = _html(logado("ana"))
    faixa = re.search(r'<div class="fila-quem-onde">(.*?)<section class="fila-hero"',
                      html, re.S)
    assert faixa and 'data-quem' in faixa.group(1)
    assert "Ana Souza" in faixa.group(1)
    # A loja vai junto: "eu, na Matriz" é a mesma pergunta.
    assert "Matriz" in faixa.group(1)
    # E a faixa vem ANTES do cartão do painel.
    assert html.index('class="fila-quem-onde"') < html.index('<section class="fila-hero"')
    assert "Ana Souza" in _html(logado("ana"), "/fila?folha=pausa")


# --- O motivo da correção (spec 2026-09-17) ---------------------------------

def test_correcao_pela_pagina_sem_motivo_volta_com_a_frase(loja):
    from fila.models import LugarNaFila

    _agir(logado("ana"), acao="ponto")
    gil = logado("gil")
    _agir(gil, acao="tirar", pessoa=str(loja.ana.pk))
    assert LugarNaFila.irrestritos.filter(pessoa=loja.ana).exists()
    assert "Escreva o motivo da correção." in _html(gil)
    _agir(gil, acao="tirar", pessoa=str(loja.ana.pk), motivo_da_correcao="foi embora")
    assert not LugarNaFila.irrestritos.filter(pessoa=loja.ana).exists()


def test_as_folhas_de_correcao_pedem_o_motivo(loja):
    ana = logado("ana")
    _agir(ana, acao="ponto")
    gil = logado("gil")
    for folha in ("sair", "tirar_pausa", "fechar", "tirar"):
        html = _html(gil, f"/fila?folha={folha}&pessoa={loja.ana.pk}")
        aberta = html[html.index(f'id="folha-{folha}"'):]
        aberta = aberta[:aberta.index("</form>")]
        assert 'name="motivo_da_correcao"' in aberta and "required" in aberta, folha


def test_gerente_move_pela_folha_sem_javascript(loja):
    from fila.estado import na_fila

    ana, bia = logado("ana"), logado("bia")
    _agir(ana, acao="ponto")
    _agir(bia, acao="ponto")
    gil = logado("gil")
    corrigir = _html(gil, f"/fila?folha=corrigir&pessoa={loja.bia.pk}")
    assert "?folha=mover&amp;pessoa=" in corrigir or "?folha=mover&pessoa=" in corrigir
    folha = _html(gil, f"/fila?folha=mover&pessoa={loja.bia.pk}")
    aberta = folha[folha.index('id="folha-mover"'):]
    aberta = aberta[:aberta.index("</form>")]
    assert 'name="posicao" value="1"' in aberta and 'name="motivo_da_correcao"' in aberta
    _agir(gil, acao="mover", pessoa=str(loja.bia.pk), posicao="1",
          motivo_da_correcao="chegou antes")
    assert [l.pessoa_id for l in na_fila(loja.matriz)] == [loja.bia.pk, loja.ana.pk]


def test_posicao_forjada_no_post_nao_derruba(loja):
    _agir(logado("ana"), acao="ponto")
    gil = logado("gil")
    resposta = _agir(gil, acao="mover", pessoa=str(loja.ana.pk), posicao="²",
                     motivo_da_correcao="teste ok")
    assert resposta.status_code == 302
    assert "Escolha uma posição da fila." in _html(gil)


def test_gerente_poe_em_pausa_pela_folha(loja):
    from fila.models import Estado, LugarNaFila

    _agir(logado("ana"), acao="ponto")
    gil = logado("gil")
    folha = _html(gil, f"/fila?folha=por_em_pausa&pessoa={loja.ana.pk}")
    aberta = folha[folha.index('id="folha-por_em_pausa"'):]
    aberta = aberta[:aberta.index("</form>")]
    assert f'name="tipo" value="{loja.cad.tipo.pk}"' in aberta
    assert 'name="motivo_da_correcao"' in aberta
    _agir(gil, acao="por_em_pausa", pessoa=str(loja.ana.pk), tipo=str(loja.cad.tipo.pk),
          motivo_da_correcao="foi ao banco")
    assert LugarNaFila.irrestritos.get(pessoa=loja.ana).estado == Estado.EM_PAUSA


# --- O fluxo de espera (spec 2026-09-17-fluxo-da-fila-por-empresa) ----------

def _empresa_em_espera(loja):
    from fila.fluxo import FluxoDaFila, definir_fluxo

    definir_fluxo(loja.empresa, FluxoDaFila.ESPERA)


def _lancar(cliente, loja):
    _agir(cliente, acao="ponto")
    _agir(cliente, acao="atender")
    _agir(cliente, acao="finalizar", resultado="nao_vendeu",
          motivo=str(loja.cad.motivo.pk))


def test_quem_esta_em_espera_ve_o_cartao_e_o_botao(loja):
    _empresa_em_espera(loja)
    ana = logado("ana")
    _lancar(ana, loja)
    html = _html(ana)
    assert "Você está em espera" in html
    assert 'value="entrar_na_fila"' in html
    assert "Em espera" in html          # o bloco da lista
    _agir(ana, acao="entrar_na_fila")
    # Sozinha na loja, ela volta como a primeira: o painel diz "É a sua vez".
    depois = _html(ana)
    assert "É a sua vez" in depois
    assert "Você está em espera" not in depois


def test_no_fluxo_de_hoje_nao_ha_espera_na_tela(loja):
    ana = logado("ana")
    _lancar(ana, loja)
    html = _html(ana)
    assert "Em espera" not in html and 'value="entrar_na_fila"' not in html


def test_entrar_na_fila_de_quem_nao_esta_em_espera_volta_com_a_frase(loja):
    ana = logado("ana")
    _agir(ana, acao="ponto")
    _agir(ana, acao="entrar_na_fila")
    assert "Você já está na fila." in _html(ana)


def test_a_folha_corrigir_oferece_por_na_fila_para_quem_espera(loja):
    from fila.models import Estado, LugarNaFila

    _empresa_em_espera(loja)
    ana = logado("ana")
    _lancar(ana, loja)
    gil = logado("gil")
    corrigir = _html(gil, f"/fila?folha=corrigir&pessoa={loja.ana.pk}")
    assert "folha=por_na_fila" in corrigir
    folha = _html(gil, f"/fila?folha=por_na_fila&pessoa={loja.ana.pk}")
    aberta = folha[folha.index('id="folha-por_na_fila"'):]
    assert 'name="motivo_da_correcao"' in aberta[:aberta.index("</form>")]
    _agir(gil, acao="por_na_fila", pessoa=str(loja.ana.pk),
          motivo_da_correcao="cliente chegou")
    assert LugarNaFila.irrestritos.get(pessoa=loja.ana).estado == Estado.NA_FILA
