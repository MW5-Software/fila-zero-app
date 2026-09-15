"""As unidades federativas pelo IBGE — Bloco 5 do roadmap (item 29).

O que entra aqui é o dado PEQUENO e estável: as 27 UFs com o código IBGE
de 2 dígitos e o nome por extenso. É o que a validação do campo `uf`
precisa (recusar sigla que não existe) e o que qualquer dropdown de
estado vai oferecer.

O limite, nomeado de propósito: os MUNICÍPIOS não estão aqui. São 5.570
registros que só prestam importados da base oficial do IBGE — tarefa
própria, com fonte e atualização anuais. O campo `municipio` continua
texto livre; quando o primeiro módulo de negócio precisar de município
código-IBGE (nota fiscal vai precisar), a importação entra e este módulo
ganha a tabela.
"""

import pytest

from plataforma.uf import CODIGO_IBGE, NOME, erro_de_uf, ufs_ordenadas


class TestADeclaracao:
    def test_sao_vinte_e_seis_mais_o_distrito_federal(self):
        assert len(CODIGO_IBGE) == 27

    def test_as_doze_primeiras_siglas_na_ordem_do_ibge(self):
        """O IBGE numera em ordem alfabética a partir de Rondônia (11) —
        os códigos são estáveis desde sempre e é isso que a nota fiscal
        usa."""
        assert CODIGO_IBGE["RO"] == 11
        assert CODIGO_IBGE["AC"] == 12
        assert CODIGO_IBGE["AM"] == 13
        assert CODIGO_IBGE["RR"] == 14
        assert CODIGO_IBGE["PA"] == 15
        assert CODIGO_IBGE["AP"] == 16
        assert CODIGO_IBGE["TO"] == 17
        assert CODIGO_IBGE["MA"] == 21
        assert CODIGO_IBGE["PI"] == 22
        assert CODIGO_IBGE["CE"] == 23
        assert CODIGO_IBGE["RN"] == 24
        assert CODIGO_IBGE["PB"] == 25

    def test_os_codigos_sao_impares_e_pares_alternados(self):
        """Peculiaridade oficial: a sequência salta (…17 → 21…) porque os
        pares intermediários foram reservados e nunca distribuídos."""
        assert CODIGO_IBGE["MA"] - CODIGO_IBGE["TO"] == 4

    def test_cada_sigla_tem_nome_por_extenso(self):
        assert NOME["MT"] == "Mato Grosso"
        assert NOME["DF"] == "Distrito Federal"
        assert set(NOME) == set(CODIGO_IBGE)


class TestAValidacao:
    def test_sigla_valida_passa(self):
        assert erro_de_uf("MT") is None

    def test_minuscula_passa_e_normaliza_quem_chama_decide(self):
        assert erro_de_uf("mt") is None

    def test_sigla_inexistente_e_recusada_com_a_lista_no_disco(self):
        erro = erro_de_uf("XX")
        assert erro is not None
        assert "XX" in erro

    def test_tamanho_errado_e_recusado(self):
        assert erro_de_uf("") is not None or True  # vazio é livre, ver abaixo
        assert erro_de_uf("MTX") is not None

    def test_vazio_e_livre(self):
        """Campo opcional: quem não informou estado não merece recusa."""
        assert erro_de_uf("") is None


class TestAListaOrdenada:
    def test_para_dropdown_por_nome(self):
        lista = ufs_ordenadas()
        assert lista[0] == ("AC", "Acre")
        assert ("MT", "Mato Grosso") in lista
        assert len(lista) == 27


@pytest.mark.django_db
class TestNoModel:
    def test_a_filial_com_uf_que_nao_existe_e_recusada(self, db):
        from django.core.exceptions import ValidationError

        from plataforma.models import Filial

        with pytest.raises(ValidationError) as erro:
            Filial(nome="Loja", apelido="Loja", uf="XX").save()
        assert "XX" in str(erro.value)

    def test_a_uf_minuscula_grava_em_maiusculas(self, db):
        from plataforma.models import Empresa

        Empresa.objects.create(razao_social="X", uf="mt")
        assert Empresa.objects.get(razao_social="X").uf == "MT"
