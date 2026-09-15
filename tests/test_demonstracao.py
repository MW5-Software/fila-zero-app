"""A tela que prova a entrega: todo componente desenhando dentro do shell.

Ela não é decorativa. É o que se abre no navegador para comparar lado a lado
com o `sementes-premix`, e é o que quebra quando um componente portado perde
o template pelo caminho.
"""

import pytest
from contas.models import Usuario
from django.test import Client
from django.urls import reverse

# O arquivo inteiro bate em `/` (via `html`) ou em `/tema.css` diretamente, e
# as duas rotas passaram a ler a marca do banco a cada requisição (Task 5) —
# por isso o banco de teste precisa estar de pé para qualquer teste daqui.
pytestmark = pytest.mark.django_db


@pytest.fixture
def html():
    # `demonstracao` exige login (Task 4): sem entrar antes, `/demonstracao`
    # redireciona para `entrar` em vez de desenhar a tela. Mudou de endereço
    # (era "/") quando a home virou uma saudação simples — ver o relatório
    # do retrabalho visual.
    Usuario.objects.create_user(email="ana@teste.com", password="segredo-de-teste")
    c = Client()
    c.post(reverse("entrar"), {
        "usuario": "ana@teste.com",
        "senha": "segredo-de-teste",
    })
    resposta = c.get(reverse("demonstracao"))
    assert resposta.status_code == 200
    return resposta.content.decode()


class TestATelaDesenha:
    def test_a_pagina_abre(self, html):
        assert "<html" in html.lower()

    def test_o_shell_esta_em_volta(self, html):
        """Afirma o shell pela marcação estrutural, e não por texto que
        sobrevive a `chrome=False` — "KRONOS.net" vem de `document_title` e
        aparece em `<title>` mesmo sem sidebar, header ou rodapé."""
        assert "<aside" in html and 'class="side-nav"' in html
        assert "<header" in html
        assert "<footer" in html

    def test_a_folha_de_tema_e_carregada(self, html):
        assert "/tema.css" in html

    def test_o_css_do_design_system_e_carregado_com_versao(self, html):
        assert "/static/nucleo/mw5.css?v=" in html


class TestOsComponentesAparecem:
    """Um por família, pelo texto que a tela mostra.

    Pelo texto, e não pela classe CSS: o nome de uma classe é detalhe interno
    do template, e um teste preso a ele quebra numa renomeação que não mudou
    nada para quem olha a tela. Se um template sumiu no porte, a renderização
    levanta antes de chegar aqui — o valor deste teste é dizer qual família.
    """

    @pytest.mark.parametrize(
        "familia,texto",
        [
            ("PageHeader", "O design system inteiro, numa tela"),
            ("StatCard", "Instalações"),
            ("Alert", "Um aviso de atenção."),
            ("Pill", "Ativo"),
            ("Badge", "Badge de teste"),
            ("Avatar", "Rita Oliveira"),
            ("Button", "Primário"),
            ("Table", "Ribeirão Preto"),
            ("Tabs", "Conteúdo da primeira."),
            ("Timeline", "Há dois dias"),
            ("EmptyState", "Nenhum registro ainda."),
            ("Modal", "O conteúdo do modal."),
            # Famílias acrescentadas na correção final da revisão de branch:
            # a tela desenhava 17 dos 58 componentes exportados por
            # `nucleo.components`; agora desenha todos os desenháveis
            # sozinhos (ver a docstring de `_miolo()` para os 7 que não são).
            ("ErrorState", "Tentativa de leitura falhou — tente novamente."),
            ("Heading", "Valores da última simulação de frete"),
            ("SectionLabel", "Detalhamento"),
            ("DefinitionList", "Total estimado"),
            ("Summary", "Pedidos em aberto"),
            ("ItemRow", "Motorista credenciado"),
            ("DashedButton", "Adicionar parada"),
            ("Slot", "Este bloco é o alvo de uma troca HTMX."),
            ("Dropdown", "Ações rápidas"),
            ("Accordion", "Perguntas frequentes"),
            ("Stepper", "Em rota"),
            ("ModuleGrid", "Simulação e acompanhamento"),
            ("Mapa", "Mapa sem endereço"),
            ("Toast", "Registro salvo com sucesso."),
            ("FilterBar", "Aplicar filtro"),
            ("Pagination", "11–20 de 47"),
            # Os nove tipos de campo (`forms.py`): 47 testes unitários e,
            # até esta correção, nenhum pixel — nenhum tinha desenhado
            # dentro do shell, claro ou escuro.
            ("TextInput", "Nome completo"),
            ("Textarea", "Observações"),
            ("Select", "UF de origem"),
            ("Checkbox", "Entrega urgente"),
            ("SearchInput", "Buscar cliente"),
            ("FileInput", "Comprovante de endereço"),
            ("InputGroup", "CEP de destino"),
            ("Form", 'class="form"'),
            # `Chart`: 64 testes unitários, mesma lacuna. Os cinco `kind`
            # desenham lado a lado no card "Gráficos" — este marcador prova
            # a família; os outros quatro títulos foram conferidos à mão
            # (ver o relatório desta correção).
            ("Chart", ">Entregas por mês<"),
            ("IconButton", 'title="Ver notificações de teste"'),
            ("Spinner", "Carregando relatório..."),
            ("Icon", "Favorito"),
            ("ActionBar", "Alterações não salvas"),
            ("Drawer", "Informações completas do pedido selecionado."),
            ("Protected", "Aprovar solicitação"),
        ],
    )
    def test_a_familia_aparece_na_tela(self, html, familia, texto):
        """Cada marcador é texto que só aquele componente emite — conferido
        por contagem de ocorrência (exatamente uma vez) no HTML renderizado
        no momento em que cada um foi acrescentado."""
        assert texto in html, f"{familia} não desenhou"

    def test_o_card_desenha_a_moldura(self, html):
        """Uma asserção estrutural, para o caso de o texto aparecer solto na
        página porque o `Card` em volta parou de renderizar."""
        assert 'class="card' in html


class TestOsDoisTemas:
    def test_o_css_serve_claro_e_escuro(self):
        corpo = Client().get(reverse("tema")).content.decode()
        assert ':root[data-theme="light"]' in corpo
        assert ':root[data-theme="dark"]' in corpo

    def test_a_pagina_aplica_o_tema_salvo_no_navegador(self, html):
        """Não há botão de tema — o design system o removeu de propósito
        (ver `test_nao_ha_mais_botao_de_tema` em `test_components.py`). O que
        existe é o script de bootstrap embutido em `page.html`, que lê
        `mw5-theme` do `localStorage` e aplica `data-theme` na raiz do
        documento antes da primeira pintura."""
        assert 'localStorage.getItem("mw5-theme")' in html
        assert 'document.documentElement.setAttribute("data-theme",t)' in html
