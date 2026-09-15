"""A moeda brasileira formatada e arredondada — Bloco 5 do roadmap (item 30).

Ainda não existe campo de dinheiro em tabela nenhuma (o primeiro módulo de
negócio vai trazê-lo); o que a base entrega é a POLÍTICA, num lugar só:

- **pt-BR na saída**: `R$ 1.234,56` — ponto no milhar, vírgula no decimal,
  como o Brasil lê;
- **meio-ponto para CIMA** (`ROUND_HALF_UP`): é o arredondamento do balcão,
  o que o caixa e a Receita esperam — `1.005` vira `1,01`, e não `1,00`
  como o `round()` bancário do Python faria (`ROUND_HALF_EVEN`);
- **Decimal, nunca float**: `0.1 + 0.2` em binário é `0.30000000000000004`,
  e centavo perdido em soma é prejuízo de verdade.

Quem for o primeiro módulo a gravar `DecimalField`, formata por aqui.
"""

import pytest
from decimal import Decimal

from plataforma.formatos import arredondado, moeda, numero


class TestAArredondacao:
    def test_meio_ponto_para_cima_como_no_balcão(self):
        assert arredondado("1.005") == Decimal("1.01")
        assert arredondado("2.675", casas=2) == Decimal("2.68")

    def test_nao_e_o_bancario_do_python(self):
        """O motivo da função existir: `round(Decimal('1.005'))` com
        HALF-EVEN deixaria 1,00. O Brasil espera 1,01."""
        from decimal import ROUND_HALF_EVEN

        assert Decimal("1.005").quantize(
            Decimal("0.01"), rounding=ROUND_HALF_EVEN) == Decimal("1.00")
        assert arredondado("1.005") == Decimal("1.01")

    def test_casas_mais_que_dois(self):
        """Unidade com 3 casas (o quilo do balcão) usa a mesma política."""
        assert arredondado("0.0005", casas=3) == Decimal("0.001")

    def test_aceita_float_e_int_sem_susto(self):
        """Float chega de JSON e cálculo alheio; converter por string evita
        levar o ruído binário junto."""
        assert arredondado(1.005) == Decimal("1.01")
        assert arredondado(2) == Decimal("2.00")


class TestAMoeda:
    def test_o_formato_do_brasil(self):
        assert moeda("1234.56") == "R$ 1.234,56"
        assert moeda(Decimal("0.5")) == "R$ 0,50"
        assert moeda(0) == "R$ 0,00"

    def test_arredonda_antes_de_formatar(self):
        assert moeda("1234.567") == "R$ 1.234,57"

    def test_negativo_com_o_travesao_na_frente(self):
        assert moeda("-15.9") == "R$ -15,90"

    def test_grande_nao_perde_centavo(self):
        assert moeda("1234567890.12") == "R$ 1.234.567.890,12"


class TestONumero:
    def test_mesma_pontuacao_sem_o_cifrao(self):
        assert numero("1234.56") == "1.234,56"

    def test_casas_escolhidas(self):
        assert numero("12.3456", casas=3) == "12,346"

    def test_vazio_e_none_vazios(self):
        """Campo que veio vazio sai vazio — e não 'R$ 0,00' inventado."""
        assert moeda("") == ""
        assert numero(None) == ""
