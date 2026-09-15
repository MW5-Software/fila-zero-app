"""A biblioteca de ícones: o conjunto da casa e a cauda longa do Lucide.

O que estes testes protegem é a fronteira entre os dois. Os 67 desenhados a
partir dos mocks definem o traço do design system; os ~2000 do Lucide existem
para o menu que alguém vai montar amanhã. Trocar um pelo outro por acidente
muda a cara de todos os sistemas gerados de uma vez.
"""

import pytest
from nucleo import icons


class TestOsDoisConjuntos:
    def test_o_conjunto_da_casa_continua_de_pe(self):
        assert len(icons.nomes_do_design_system()) == 67

    def test_a_cauda_longa_chegou(self):
        assert len(icons.names()) > 1500

    def test_o_desenho_da_casa_ganha_do_lucide(self):
        """`mail` e `home` existem nos dois. Se o Lucide vencesse, o cabeçalho
        e o menu de todo sistema gerado mudariam de desenho sem ninguém pedir."""
        for nome in ("mail", "home", "user", "settings", "bell"):
            assert icons.get(nome) == icons.ICONS[nome], f"{nome} veio do Lucide"

    def test_existe_enxerga_os_dois(self):
        assert icons.existe("home")        # da casa
        assert icons.existe("warehouse")   # do Lucide
        assert not icons.existe("nao-existe-mesmo")

    def test_nome_desconhecido_explica_como_procurar(self):
        # `match` casa o caminho completo `nucleo.icons.buscar`, não só a
        # palavra "buscar" — uma regressão que reintroduzisse
        # `mw5_admin.icons.buscar` na mensagem (o defeito que a Ruling R10
        # corrigiu) passaria pelo match antigo sem ninguém notar.
        with pytest.raises(KeyError, match=r"nucleo\.icons\.buscar"):
            icons.get("nao-existe-mesmo")


class TestFormato:
    """Um ícone fora do padrão aparece torto no meio dos outros."""

    def test_o_lucide_nao_traz_o_wrapper_svg(self):
        """Só o miolo é guardado — o `<svg>` externo, com o traço de 1.9, vem
        do nosso componente. Com o wrapper junto, o traço do Lucide venceria."""
        for nome in ("warehouse", "truck", "banknote"):
            conteudo = icons.get(nome)
            assert "<svg" not in conteudo
            assert "stroke-width" not in conteudo

    def test_nada_de_cor_fixa(self):
        """Cor fixa não acompanha a troca de tema nem a cor do menu."""
        for nome in icons.buscar("", 80):
            conteudo = icons.get(nome)
            assert "#" not in conteudo, f"{nome} tem cor fixa"

    def test_o_miolo_e_uma_linha_so(self):
        for nome in ("warehouse", "truck"):
            assert "\n" not in icons.get(nome)


class TestBusca:
    def test_acha_pelo_nome(self):
        assert "truck" in icons.buscar("truck")

    def test_acha_por_palavra_chave_em_ingles(self):
        assert "truck" in icons.buscar("delivery")

    @pytest.mark.parametrize("termo,esperado", [
        ("estoque", "package"),
        ("financeiro", "banknote"),
        ("cliente", "users"),
        ("usuario", "user"),
        ("frota", "truck"),
        ("permissao", "key"),
        ("relatorio", "chart-column"),
    ])
    def test_acha_em_portugues(self, termo, esperado):
        """Quem monta o menu de um ERP brasileiro digita "estoque", não
        "inventory". Sem a ponte, o seletor devolve vazio na palavra mais
        provável de todas."""
        assert esperado in icons.buscar(termo)

    def test_acento_nao_atrapalha(self):
        assert icons.buscar("relatório") == icons.buscar("relatorio")

    def test_termo_de_duas_palavras_acha_pelas_duas(self):
        """"nota fiscal" são duas chaves separadas; casar a frase inteira não
        acharia nenhuma delas."""
        assert "receipt" in icons.buscar("nota fiscal")

    def test_o_sinonimo_vem_antes_do_resto(self):
        """Quem digitou "estoque" quer os escolhidos a dedo no topo, não os
        que têm "stock" perdido em alguma etiqueta."""
        assert icons.buscar("estoque")[0] == "package"

    def test_sem_termo_mostra_os_da_casa_primeiro(self):
        """São os que combinam com o resto do sistema — quem não vai procurar
        nada deveria esbarrar neles."""
        primeiros = icons.buscar("", 20)
        assert set(primeiros) <= set(icons.nomes_do_design_system())

    def test_termo_sem_resultado_devolve_lista_vazia(self):
        assert icons.buscar("zzzzzznadaaqui") == []

    def test_a_busca_nao_repete(self):
        resultado = icons.buscar("estoque", 60)
        assert len(resultado) == len(set(resultado))

    def test_o_limite_e_respeitado(self):
        assert len(icons.buscar("a", 10)) <= 10


class TestSinonimos:
    def test_todo_sinonimo_aponta_para_icone_que_existe(self):
        """Um sinônimo apontando para nome errado some em silêncio: a busca
        devolve menos resultados e ninguém descobre por quê."""
        quebrados = [
            f"{chave} → {nome}"
            for chave, nomes in icons.SINONIMOS.items()
            for nome in nomes
            if not icons.existe(nome)
        ]
        assert not quebrados


class TestLicenca:
    def test_o_arquivo_vendorizado_declara_a_origem(self):
        import json
        from pathlib import Path

        import nucleo

        dados = json.loads(
            (Path(nucleo.__file__).parent / "icons_lucide.json").read_text(
                encoding="utf-8")
        )
        assert "ISC" in dados["_licenca"]
        assert "Lucide" in dados["_licenca"]

    def test_o_notice_existe_no_repositorio(self):
        from pathlib import Path

        import nucleo

        raiz = Path(nucleo.__file__).resolve().parents[1]
        notice = raiz / "NOTICE"
        if not notice.is_file():
            pytest.skip("rodando fora do repositório (pacote instalado)")
        assert "Lucide" in notice.read_text(encoding="utf-8")
