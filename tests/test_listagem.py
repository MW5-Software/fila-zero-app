"""`comum.listagem`: o helper de filtro + ordenação + paginação que
as telas de listagem chamam — testado isolado do HTTP, com `RequestFactory` e
um `QuerySet` de `Cargo` (qualquer model serviria; este tem `Meta.ordering`
pelo rótulo, útil para provar que o padrão bate com o que o model já fazia
sozinho). Era `Perfil`, que saiu em 14/09/2026.
"""

import pytest
from django.test import RequestFactory

from contas.models import Cargo
from comum.listagem import POR_PAGINA, ColunaFiltravel, montar_pagina

ORDENAVEIS = {"perfil": "rotulo"}


def _get(caminho="/perfis", **params):
    return RequestFactory().get(caminho, params)


#: A conta nasce com os cinco cargos de fábrica — os testes de ordenação
#: filtram por este prefixo para não precisar prever a posição deles no meio
#: do alfabeto.
_QUERY_BASE = Cargo.objects.filter(nome__startswith="perfil-")


def _conta():
    from contas.models import Nivel, Usuario

    conta, _ = Usuario.objects.get_or_create(
        email="conta-listagem@teste.com", defaults={"nivel": Nivel.TITULAR})
    return conta


@pytest.fixture
def perfis(db):
    """Nomeados fora de ordem alfabética, para o teste de ordenação
    distinguir "ordenado" de "ordem de criação"."""
    return [
        Cargo.objects.create(conta=_conta(), nome=f"perfil-{n}", rotulo=rotulo)
        for n, rotulo in enumerate(("Zeta", "Alfa", "Meio"))
    ]


class TestOrdenacao:
    def test_sem_ordenar_usa_o_padrao(self, perfis):
        pagina = montar_pagina(
            _get(), _QUERY_BASE, ordenaveis=ORDENAVEIS, padrao="perfil")
        assert [p.rotulo for p in pagina.linhas] == ["Alfa", "Meio", "Zeta"]

    def test_ordenar_descendente(self, perfis):
        pagina = montar_pagina(
            _get(ordenar="-perfil"), _QUERY_BASE,
            ordenaveis=ORDENAVEIS, padrao="perfil")
        assert [p.rotulo for p in pagina.linhas] == ["Zeta", "Meio", "Alfa"]

    def test_chave_desconhecida_cai_no_padrao_sem_levantar(self, perfis):
        pagina = montar_pagina(
            _get(ordenar="rotulo-secreto-que-nao-existe"), _QUERY_BASE,
            ordenaveis=ORDENAVEIS, padrao="perfil")
        assert [p.rotulo for p in pagina.linhas] == ["Alfa", "Meio", "Zeta"]

    def test_chave_vazia_cai_no_padrao(self, perfis):
        pagina = montar_pagina(
            _get(ordenar=""), _QUERY_BASE,
            ordenaveis=ORDENAVEIS, padrao="perfil")
        assert [p.rotulo for p in pagina.linhas] == ["Alfa", "Meio", "Zeta"]

    def test_nunca_interpola_o_parametro_cru_no_order_by(self, perfis):
        """Uma tentativa clássica de injeção: um valor com `__` que tentaria
        atravessar relação nenhuma tem, mesmo que parecesse um lookup do
        ORM válido. Só chega a `order_by` o que `ORDENAVEIS` mapeia."""
        pagina = montar_pagina(
            _get(ordenar="usuarios__password"), _QUERY_BASE,
            ordenaveis=ORDENAVEIS, padrao="perfil")
        assert [p.rotulo for p in pagina.linhas] == ["Alfa", "Meio", "Zeta"]

    def test_cabecalho_da_coluna_ativa_ascendente_aponta_pra_descendente(self, perfis):
        pagina = montar_pagina(
            _get(ordenar="perfil"), _QUERY_BASE,
            ordenaveis=ORDENAVEIS, padrao="perfil")
        html = pagina.cabecalho("perfil", "Perfil")
        assert 'href="/perfis?ordenar=-perfil"' in html
        assert "Perfil" in html

    def test_cabecalho_da_coluna_ativa_descendente_aponta_pra_ascendente(self, perfis):
        pagina = montar_pagina(
            _get(ordenar="-perfil"), _QUERY_BASE,
            ordenaveis=ORDENAVEIS, padrao="perfil")
        html = pagina.cabecalho("perfil", "Perfil")
        assert 'href="/perfis?ordenar=perfil"' in html

    def test_ordenar_atual_reflete_o_efetivo_nao_o_bruto(self, perfis):
        """Pedir uma ordenação forjada não deve fazer o campo oculto do
        filtro devolver a chave forjada — só o que de fato passou a valer."""
        pagina = montar_pagina(
            _get(ordenar="lixo"), _QUERY_BASE,
            ordenaveis=ORDENAVEIS, padrao="-perfil")
        assert pagina.ordenar_atual == "-perfil"


class TestPaginacao:
    @pytest.fixture
    def muitos_perfis(self, db):
        conta = _conta()
        Cargo.objects.bulk_create([
            Cargo(conta=conta, nome=f"perfil-{n}", rotulo=f"Perfil {n:02d}")
            for n in range(60)
        ])

    def test_primeira_pagina_tem_por_pagina_linhas(self, muitos_perfis):
        pagina = montar_pagina(
            _get(), _QUERY_BASE, ordenaveis=ORDENAVEIS, padrao="perfil")
        assert len(pagina.linhas) == POR_PAGINA
        assert pagina.paginacao.total == 60

    def test_segunda_pagina_continua_de_onde_a_primeira_parou(self, muitos_perfis):
        primeira = montar_pagina(
            _get(), _QUERY_BASE, ordenaveis=ORDENAVEIS, padrao="perfil")
        segunda = montar_pagina(
            _get(pagina="2"), _QUERY_BASE,
            ordenaveis=ORDENAVEIS, padrao="perfil")
        assert primeira.linhas[-1].pk != segunda.linhas[0].pk
        assert len(segunda.linhas) == POR_PAGINA

    def test_pagina_alem_do_fim_volta_pra_primeira(self, muitos_perfis):
        pagina = montar_pagina(
            _get(pagina="999"), _QUERY_BASE,
            ordenaveis=ORDENAVEIS, padrao="perfil")
        assert pagina.paginacao.page == 1
        assert len(pagina.linhas) == POR_PAGINA

    def test_pagina_zero_nao_estoura_e_vira_primeira(self, muitos_perfis):
        pagina = montar_pagina(
            _get(pagina="0"), _QUERY_BASE,
            ordenaveis=ORDENAVEIS, padrao="perfil")
        assert pagina.paginacao.page == 1

    def test_pagina_negativa_nao_estoura_e_vira_primeira(self, muitos_perfis):
        pagina = montar_pagina(
            _get(pagina="-3"), _QUERY_BASE,
            ordenaveis=ORDENAVEIS, padrao="perfil")
        assert pagina.paginacao.page == 1

    def test_pagina_nao_numerica_nao_estoura_e_vira_primeira(self, muitos_perfis):
        pagina = montar_pagina(
            _get(pagina="abacate"), _QUERY_BASE,
            ordenaveis=ORDENAVEIS, padrao="perfil")
        assert pagina.paginacao.page == 1

    def test_sem_nenhum_registro_nao_estoura(self, db):
        pagina = montar_pagina(
            _get(pagina="5"), _QUERY_BASE,
            ordenaveis=ORDENAVEIS, padrao="perfil")
        assert pagina.linhas == []
        assert pagina.paginacao.total == 0

    def test_itens_por_pagina_e_o_parametro_da_instalacao_nao_a_constante(
        self, muitos_perfis,
    ):
        """R47: `POR_PAGINA` continua sendo o PADRÃO (`plataforma.parametro.
        PARAMETRO_ITENS_POR_PAGINA`), mas quem `montar_pagina` de fato usa é
        `plataforma.parametro_catalogo.valor_de` — uma instalação que mudou
        o parâmetro pagina com o próprio número, não com o do código."""
        from plataforma.parametro_catalogo import definir

        definir("itens_por_pagina", "10")
        pagina = montar_pagina(
            _get(), _QUERY_BASE, ordenaveis=ORDENAVEIS, padrao="perfil")
        assert len(pagina.linhas) == 10
        assert pagina.paginacao.per_page == 10


class TestPreservaOsOutrosParametros:
    def test_link_de_pagina_preserva_filtro_e_ordenacao(self, perfis):
        pagina = montar_pagina(
            _get(q="Meio", ordenar="-perfil"), _QUERY_BASE,
            ordenaveis=ORDENAVEIS, padrao="perfil")
        href = pagina.paginacao.url_for_page(1)
        assert "q=Meio" in href
        assert "ordenar=-perfil" in href
        assert "pagina=1" in href

    def test_link_de_ordenar_preserva_o_filtro(self, perfis):
        pagina = montar_pagina(
            _get(q="Meio"), _QUERY_BASE,
            ordenaveis=ORDENAVEIS, padrao="perfil")
        html = pagina.cabecalho("perfil", "Perfil")
        assert "q=Meio" in html

    def test_link_de_ordenar_solta_a_pagina_em_curso(self, perfis):
        """Trocar de ordenação com a página em 3 e continuar em 3 mostraria,
        na prática, o mesmo intervalo de linhas com outro critério — quase
        sempre vazio. Reordenar volta para a primeira página."""
        pagina = montar_pagina(
            _get(pagina="3"), _QUERY_BASE,
            ordenaveis=ORDENAVEIS, padrao="perfil")
        html = pagina.cabecalho("perfil", "Perfil")
        assert "pagina=" not in html


class TestDataEmCampoDeDataEHora:
    """Coluna de data sobre um `DateTimeField` (a Auditoria é o caso real):
    "até 02/01" tem que incluir o DIA 02 inteiro, e não parar na meia-noite
    dele — e nenhum aviso de datetime ingênuo pode sair, porque em produção
    este filtro roda a cada busca."""

    @pytest.fixture
    def registros(self, db):
        """Duas linhas com instantes fixados: 01/08 às 9h e 02/08 às 15h30.
        `quando` é `auto_now_add`, então o instante entra por `update` —
        que passa direto pelo SQL e não toca no `save()` append-only."""
        from datetime import datetime

        from django.utils import timezone

        from contas.models import RegistroDeAuditoria

        cedo = timezone.make_aware(datetime(2026, 8, 1, 9, 0))
        tarde = timezone.make_aware(datetime(2026, 8, 2, 15, 30))
        RegistroDeAuditoria.objects.create(acao="entrou")
        RegistroDeAuditoria.objects.create(acao="saiu")
        pks = list(RegistroDeAuditoria.objects.order_by("pk")
                   .values_list("pk", flat=True))
        RegistroDeAuditoria.objects.filter(pk=pks[0]).update(quando=cedo)
        RegistroDeAuditoria.objects.filter(pk=pks[1]).update(quando=tarde)
        return list(RegistroDeAuditoria.objects.order_by("pk"))

    COLUNAS_DATA = {
        "quando": ColunaFiltravel("quando", "Data", tipo="data"),
    }

    def test_ate_inclui_o_dia_inteiro(self, registros, db):
        from contas.models import RegistroDeAuditoria

        pagina = montar_pagina(
            _get(**{"f:quando:ate": "2026-08-02"}),
            RegistroDeAuditoria.objects.all(),
            ordenaveis={"quando": "quando"}, padrao="-quando",
            filtraveis=self.COLUNAS_DATA)
        assert len(pagina.linhas) == 2

    def test_de_ja_comeca_a_meia_noite_do_dia(self, registros, db):
        from contas.models import RegistroDeAuditoria

        pagina = montar_pagina(
            _get(**{"f:quando:de": "2026-08-02"}),
            RegistroDeAuditoria.objects.all(),
            ordenaveis={"quando": "quando"}, padrao="-quando",
            filtraveis=self.COLUNAS_DATA)
        assert [r.pk for r in pagina.linhas] == [registros[1].pk]

    def test_data_invalida_nao_derruba_a_busca(self, registros, db):
        from contas.models import RegistroDeAuditoria

        pagina = montar_pagina(
            _get(**{"f:quando:de": "nao-e-data"}),
            RegistroDeAuditoria.objects.all(),
            ordenaveis={"quando": "quando"}, padrao="-quando",
            filtraveis=self.COLUNAS_DATA)
        assert len(pagina.linhas) == 2
