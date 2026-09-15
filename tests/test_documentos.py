"""A validação dos documentos brasileiros — Bloco 5 do roadmap (item 28).

A máscara já existe (`nucleo.campos.MASCARAS` + `mw5.js`): ela ajuda quem
digita. O que faltava era a VERIFICAÇÃO — quem cola CNPJ do vizinho errado
precisa descobrir na hora do cadastro, não na nota fiscal.

O limite, nomeado de propósito: CPF e CNPJ têm dígito verificador
verificável de verdade aqui. A Inscrição Estadual NÃO — cada UF tem os
próprios pesos, são vinte e sete regras que só prestam testadas contra dado
oficial; enquanto essa tabela não chegar, IE é validada na ESTRUTURA (só
dígitos, tamanho plausível), e isso está escrito onde a recusa acontece.
CEP é estrutural também: oito dígitos — existir ou não é consulta ao
serviço dos Correios, que é outra conversa.
"""

import pytest

from plataforma.documentos import (
    documento_limpo, erro_de_cnpj, erro_de_cep, erro_de_cpf, erro_de_ie,
)


class TestOCPF:
    def test_os_validos_passam(self):
        # O clássico da literatura sobre o algoritmo — não é documento de
        # ninguém: os dígitos foram escolhidos para fechar a conta.
        assert erro_de_cpf("111.444.777-35") is None
        assert erro_de_cpf("11144477735") is None

    def test_digito_errado_e_recusado(self):
        assert erro_de_cpf("111.444.777-34") is not None

    def test_todos_os_digitos_iguais_sao_recusados(self):
        """111.111.111-11 fecha a conta do verificador, mas nenhum órgão
        emite sequência assim — aceitar seria cadastrar ruído."""
        assert erro_de_cpf("111.111.111-11") is not None

    def test_tamanho_errado_e_recusado(self):
        assert erro_de_cpf("111.444.777") is not None

    def test_letras_e_recusadas(self):
        assert erro_de_cpf("abc.def.ghi-jk") is not None


class TestOCNPJ:
    def test_o_valido_passa(self):
        # Segundo dígito verificador do exemplo canônico do algoritmo.
        assert erro_de_cnpj("04.252.011/0001-10") is None

    def test_digito_errado_e_recusado(self):
        assert erro_de_cnpj("04.252.011/0001-11") is not None

    def test_tamanho_errado_e_recusado(self):
        assert erro_de_cnpj("04.252.011/0001") is not None

    def test_todos_zerados_e_recusado(self):
        assert erro_de_cnpj("00.000.000/0000-00") is not None


class TestOCEP:
    def test_oito_digitos_passam(self):
        assert erro_de_cep("80000-000") is None
        assert erro_de_cep("80000000") is None

    def test_sete_digitos_nao_passa(self):
        assert erro_de_cep("8000-000") is not None


class TestAIE:
    def test_vazio_e_livre(self):
        """IE em branco é o caso comum (pessoa física, empresa fora do
        regime); não pode virar exigência falsa."""
        assert erro_de_ie("") is None

    def test_isento_e_aceito(self):
        assert erro_de_ie("ISENTO") is None
        assert erro_de_ie("isenta") is None

    def test_so_digitos_de_tamanho_plausivel_passa(self):
        assert erro_de_ie("123456789") is None

    def test_letra_que_nao_seja_isento_e_recusada_com_a_explicacao(self):
        erro = erro_de_ie("123ABC789")
        assert erro is not None
        assert "UF" in erro or "estado" in erro.lower()

    def test_tamanho_impossivel_e_recusado(self):
        assert erro_de_ie("12345678901234567890") is not None


class TestODocumentoLimpo:
    """O formato que vai para o BANCO: só dígitos (e a IE pode ser ISENTO).
    Máscara é visual; dado gravado tem um formato só."""

    def test_cpf_e_cnpj_saem_somente_com_digitos(self):
        assert documento_limpo("cpf", "111.444.777-35") == "11144477735"
        assert documento_limpo("cnpj", "04.252.011/0001-10") == "04252011000110"

    def test_cep_sem_traco(self):
        assert documento_limpo("cep", "80000-000") == "80000000"

    def test_ie_mantem_isento_em_maiusculas(self):
        assert documento_limpo("ie", "isento") == "ISENTO"

    def test_vazio_continua_vazio(self):
        assert documento_limpo("cnpj", "") == ""


@pytest.mark.django_db
class TestNosModels:
    """A mesma porta do `Marca.save`: a validação mora no model, porque a
    tela nunca é a única porta — shell, script e importação gravam direto."""

    def test_empresa_com_cnpj_invalido_e_recusada(self, db):
        from django.core.exceptions import ValidationError

        from plataforma.models import Empresa

        linha = Empresa(razao_social="X", cnpj="04.252.011/0001-11")
        with pytest.raises(ValidationError) as erro:
            linha.save()
        assert "CNPJ" in str(erro.value)

    def test_filial_com_cep_invalido_e_recusada(self, db):
        from django.core.exceptions import ValidationError

        from plataforma.models import Filial

        with pytest.raises(ValidationError):
            Filial(nome="Loja", apelido="Loja", cep="8000-000").save()

    def test_os_validos_gravam_ja_normalizados(self, db):
        from plataforma.models import Empresa, Filial

        # A instalação já nasce com a própria empresa semeada — conte por
        # esta, e não por "a única".
        Empresa(razao_social="Teste Docs", cnpj="04.252.011/0001-10",
                cep="80000-000").save()
        gravada = Empresa.objects.get(razao_social="Teste Docs")
        assert gravada.cnpj == "04252011000110"
        assert gravada.cep == "80000000"

        Filial(empresa=gravada, nome="Loja", apelido="Loja",
               cnpj="04.252.011/0002-09").save()
        assert Filial.objects.get(apelido="Loja").cnpj == "04252011000209"
