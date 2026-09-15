"""A folha desta casa — as correções que ficam POR CIMA do design system.

`plataforma/static/plataforma/kronos.css` existe porque o `nucleo/` é porte
verbatim do `mw5_admin` e não se emenda aqui. Ela carrega depois da `mw5.css`,
e cada regra dentro dela conserta algo de lá.

O risco desse arranjo é o silêncio: a folha pode sumir do `Site`, ou uma regra
pode ser apagada por parecer sobra, e o defeito volta sem nada acusar — são
defeitos de LAYOUT, que teste de HTML não vê e olho distraído também não.
Estes testes seguram as duas pontas: a folha chega às telas, e as regras que
ela carrega continuam lá.
"""

import re
from pathlib import Path

import pytest

from plataforma.marca import FOLHA_DA_CASA


def _folha() -> str:
    raiz = Path(__file__).resolve().parent.parent
    caminho = raiz / "plataforma" / FOLHA_DA_CASA.replace("/static/", "static/")
    assert caminho.exists(), f"a folha da casa sumiu: {FOLHA_DA_CASA}"
    return caminho.read_text(encoding="utf-8")


def _regra(seletor: str) -> str:
    achado = re.search(
        r"(?m)^" + re.escape(seletor) + r"\s*\{([^}]*)\}", _folha())
    assert achado, f"a regra de `{seletor}` sumiu da folha da casa"
    return achado.group(1)


class TestAFolhaChegaNasTelas:
    """Uma correção que não é carregada não é correção."""

    @pytest.mark.django_db
    def test_o_shell_pede_a_folha(self, db):
        from plataforma.site import SiteDoProduto
        from plataforma.marca import marca_da_instalacao

        site = SiteDoProduto(brand=marca_da_instalacao(),
                             stylesheets=[FOLHA_DA_CASA])
        assert FOLHA_DA_CASA in site.stylesheets

    @pytest.mark.django_db
    def test_a_entrada_tambem(self, db):
        """A tela de entrada fica FORA do shell, e por isso fora do
        `montar_site`. Se ela não pedir a folha por conta própria, a correção
        vale em toda tela menos na primeira que alguém vê."""
        from django.test import Client

        html = Client().get("/entrar").content.decode()
        assert FOLHA_DA_CASA in html


class TestOLogoCabeNaFaixa:
    """A marca empilhada estourava para dentro do menu.

    `.side-logo` na `mw5.css` pede `width: 100%; height: 100%` dentro de um
    grid `place-items: center`, e ali o `height: 100%` não resolve — a altura
    do `<img>` vira a largura da barra vezes a proporção do desenho. Com marca
    deitada coube por coincidência; com a do KRONOS (proporção 1,43) o logo
    descia 36px para fora da faixa, e a linha "ERP | CRM" caía sobre o azul.
    """

    def test_a_altura_manda_e_a_largura_acompanha(self):
        regra = _regra(".side-logo")
        assert "height: var(--logo-side-h)" in regra
        assert "width: auto" in regra
        # Sem isto, marca muito deitada numa barra estreita vaza para os lados.
        assert "max-width: 100%" in regra
        # O `max-height` do design system é `min(...,100%)`, e aquele 100% é o
        # mesmo percentual que não resolve. Zerado aqui de propósito.
        assert "max-height: none" in regra

    def test_a_caixa_do_link_tem_altura_definida(self):
        """Sem ela a faixa volta a valer o que o conteúdo pedir — e muda de
        tamanho no dia em que o arquivo não carregar."""
        assert "height: var(--logo-side-h)" in _regra(".side-brand > a")


class TestOCantoDeBaixoFecha:
    """O "Recolher" e o rodapé terminam na mesma linha.

    O design system já faz esse encontro em cima: `header-h` é definido como
    `sidebar-brand-h`, para que a linha sob a marca e a linha sob o cabeçalho
    sejam uma linha só. Embaixo não existia — a faixa do "Recolher" tinha
    altura de conteúdo e o rodapé tem `--footer-h`, e o canto inferior
    esquerdo ficava com um degrau.
    """

    def test_a_faixa_do_recolher_tem_a_altura_do_rodape(self):
        regra = _regra(".side-foot")
        assert "height: var(--footer-h)" in regra
        # A altura passou a vir de fora; sem isto o botão encosta no topo.
        assert "align-items: center" in regra

    def test_recolhida_a_faixa_mantem_a_altura(self):
        """Só o respiro lateral encolhe. Se a altura viesse junto, o degrau
        voltaria com o menu recolhido — que é como muita gente trabalha."""
        regra = _regra(".side-collapsed .side-foot")
        assert "height" not in regra
        assert "padding" in regra


class TestOBotaoDentroDaLinhaDeItem:
    """As linhas de Equivalências, Aplicabilidade e Recomendações põem um
    `<form>` de um botão só dentro da `.itemrow`.

    O design system dá ritmo vertical ao formulário — `.form > * + * {
    margin-top: 20px }` —, e numa tela empilhada isso é o certo. Dentro da
    linha de item o formulário é UM BOTÃO com campos ocultos na frente, e
    campo oculto conta como irmão: o botão nascia 20px abaixo, e o "Remover"
    saía desalinhado do "Editar" ao lado (relatado em 10/09/2026).
    """

    def test_o_ritmo_vertical_do_formulario_e_desligado_na_linha(self):
        assert "margin-top: 0" in _regra(".itemrow .form > * + *")

    def test_o_formulario_da_linha_e_uma_fileira(self):
        """Sem isto o `<form>` se comporta como bloco e quebra a fileira dos
        dois botões."""
        corpo = _regra(".itemrow .form")
        assert "display: flex" in corpo
        assert "margin: 0" in corpo
