"""A tela de leitura da auditoria — Bloco 4 do roadmap (item 24).

A trilha grava desde a entrega de contas; faltava onde lê-la. A tela é
SÓ DE LEITURA: a tabela é append-only por construção, e nenhuma ação aqui
pode sugerir o contrário — não há modal, botão nem POST. O que ela tem é
o trio de R46 em cima de uma tabela que só cresce: filtro por ação, autor,
alvo e período; ordenação; paginação pelo índice de `-quando` que o model
já carrega.
"""

import pytest
from django.contrib.auth.models import Permission
from contas.models import Usuario
from django.test import Client
from django.urls import reverse
from tests.conftest import dar_permissoes

SENHA = "segredo-de-teste"


@pytest.fixture
def admin_do_cliente(db):
    """Um usuário COMUM com `auditoria.ver` — quem responde pelas pessoas
    na instalação lê a própria trilha; superusuário passa sem teste novo."""
    pessoa = Usuario.objects.create_user(email="admin@teste.com", password=SENHA)
    dar_permissoes(pessoa, "auditoria_ver")
    return pessoa


@pytest.fixture
def cliente_admin(admin_do_cliente):
    c = Client()
    c.post(reverse("entrar"), {"usuario": "admin@teste.com", "senha": SENHA})
    return c


def _duas_acoes(db):
    """Duas ações reais gravadas, por gente diferente, para a lista ler."""
    from comum.auditoria import registrar

    zeca = Usuario.objects.create_user(email="zeca@teste.com", password=SENHA)
    ana = Usuario.objects.create_user(email="ana@teste.com", password=SENHA)
    registrar("usuario_criado", zeca, alvo="zeca@teste.com", detalhe="perfil Consulta")
    registrar("entrada_recusada", ana, alvo="ana@teste.com")
    return zeca, ana


class TestQuemEntra:
    def test_o_admin_com_a_permissao_abre(self, cliente_admin):
        assert cliente_admin.get(reverse("auditoria")).status_code == 200

    def test_usuario_comum_nao_descobre_que_a_tela_existe(self, db):
        Usuario.objects.create_user(email="comum@teste.com", password=SENHA)
        c = Client()
        c.post(reverse("entrar"), {"usuario": "comum@teste.com", "senha": SENHA})
        assert c.get(reverse("auditoria")).status_code == 404

    def test_quem_nao_entrou_vai_para_o_login(self, db):
        resposta = Client().get(reverse("auditoria"))
        assert resposta.status_code == 302
        assert reverse("entrar") in resposta["Location"]

    def test_modulo_desligado_e_404_mesmo_com_a_permissao(self, cliente_admin):
        from plataforma.models import Modulo

        Modulo.objects.filter(chave="auditoria").update(ativo=False)
        assert cliente_admin.get(reverse("auditoria")).status_code == 404


class TestALista:
    def test_mostra_o_que_foi_gravado_com_o_rotulo_legivel(self, cliente_admin, db):
        """`usuario_criado` é o vocabulário do banco; `Usuário criado` é o
        que a pessoa lê — a mesma tradução que a tela de Perfis faz com as
        permissões."""
        _duas_acoes(db)
        html = cliente_admin.get(reverse("auditoria")).content.decode()
        assert "Usuário criado" in html
        assert "Tentativa de entrada recusada" in html

    def test_mostra_autor_alvo_e_detalhe(self, cliente_admin, db):
        _duas_acoes(db)
        html = cliente_admin.get(reverse("auditoria")).content.decode()
        assert "zeca" in html
        assert "perfil Consulta" in html

    def test_detalhe_vazio_nao_fica_em_branco(self, cliente_admin, db):
        """A segunda ação de `_duas_acoes` não tem detalhe — a célula mostra
        um travessão, e não um buraco na linha."""
        _duas_acoes(db)
        html = cliente_admin.get(reverse("auditoria")).content.decode()
        assert "—" in html

    def test_a_mais_recente_vem_primeiro_sem_pedir_ordenacao(self, cliente_admin, db):
        """O padrão da tela é `-quando`, o sentido natural de uma trilha:
        o último acontecimento no topo, sem clique nenhum."""
        _duas_acoes(db)
        html = cliente_admin.get(reverse("auditoria")).content.decode()
        assert html.index("Tentativa de entrada") < html.index("Usuário criado")

    def test_nao_tem_acao_de_escrita_nenhuma(self, cliente_admin, db):
        """Leitura pura: nem botão de salvar, nem formulário de POST — a
        tabela é append-only e a tela não pode sugerir o contrário.

        **Olha o `<main>`, não a página inteira.** O CABEÇALHO é da casa e
        aparece em todas as telas: desde 09/09/2026 ele tem o seletor de
        idioma, que é um formulário com token. Ler o HTML todo faria este
        teste falar sobre o chrome do sistema em vez de sobre a trilha — e a
        regra que ele guarda é a da TRILHA: nada nesta tela escreve nela.
        """
        _duas_acoes(db)
        html = cliente_admin.get(reverse("auditoria")).content.decode()
        corpo = html[html.index("<main"):html.index("</main>")]

        assert 'method="post"' not in corpo.lower()

    def test_post_e_recusado(self, cliente_admin, db):
        assert cliente_admin.post(reverse("auditoria"), {}).status_code == 405


class TestOFiltroEAPaginacao:
    def test_filtra_por_acao_pela_caixa_de_escolha(self, cliente_admin, db):
        """Ação é coluna de valores fechados: caixa de escolha, e não campo
        de digitar (mesma regra das telas anteriores). O que some é a LINHA
        da ação filtrada fora — o rótulo continua na caixa, onde sempre
        esteve."""
        _duas_acoes(db)
        html = cliente_admin.get(
            reverse("auditoria"), {"f:acao:igual": "usuario_criado"}).content.decode()
        assert "Usuário criado" in html
        # A linha da entrada recusada tinha `ana` como autor e alvo; com o
        # filtro dela fora da tabela, `ana` não aparece em lugar nenhum.
        assert "ana" not in html

    def test_filtra_autor_por_parte_do_login(self, cliente_admin, db):
        _duas_acoes(db)
        html = cliente_admin.get(
            reverse("auditoria"), {"f:autor:contem": "zec"}).content.decode()
        assert "zeca" in html
        # A linha de `ana` saiu inteira: nem o alvo dela sobrou.
        assert "ana" not in html

    def test_filtra_pelo_periodo(self, cliente_admin, db):
        """Coluna de data ganha "de"/"até" (`OPERADORES["data"]`) — é o
        filtro que responde "o que aconteceu sexta-feira?"."""
        _duas_acoes(db)
        resposta = cliente_admin.get(
            reverse("auditoria"),
            {"f:quando:de": "2100-01-01", "f:quando:ate": "2100-01-02"})
        html = resposta.content.decode()
        # Nenhuma linha sobra — os dois autores sumiram da tabela.
        assert "zeca" not in html
        assert "ana" not in html

    def test_pagina_alem_do_fim_volta_para_a_primeira(self, cliente_admin, db):
        """30 linhas, 25 por página: duas páginas de verdade, e uma página
        forjada (`?pagina=9`) volta para a primeira em vez de desenhar
        tabela vazia — comportamento garantido por `montar_pagina`, provado
        aqui numa tabela real."""
        from comum.auditoria import registrar

        for i in range(30):
            registrar("usuario_criado", None, alvo=f"pessoa-{i}")
        filtro = {"f:alvo:contem": "pessoa-"}

        # A primeira página traz os MAIS NOVOS (o padrão é `-quando`).
        primeira = cliente_admin.get(reverse("auditoria"), filtro).content.decode()
        assert "pessoa-29" in primeira
        # A segunda existe e traz os mais velhos que sobraram.
        segunda = cliente_admin.get(
            reverse("auditoria"), {**filtro, "pagina": "2"}).content.decode()
        assert "pessoa-0" in segunda
        assert "pessoa-29" not in segunda
        # E a forjada volta para a primeira em vez de vir vazia.
        forjada = cliente_admin.get(
            reverse("auditoria"), {**filtro, "pagina": "9"}).content.decode()
        assert "pessoa-29" in forjada
