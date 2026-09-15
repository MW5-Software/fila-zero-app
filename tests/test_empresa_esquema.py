"""A conexão dentro de `Empresa` não pode derivar do esquema de origem.

As seis colunas de conexão vêm de `api_conexao`, do `kronos-api2`, que está
em produção. O cron que vai sincronizar os dois lados casa os campos pelo
NOME — então renomear uma coluna aqui não quebra nada nesta suíte, não quebra
nada na tela, e quebra a sincronia em silêncio, meses depois, na madrugada em
que ela rodar.

O retrato abaixo foi tirado do banco de origem em 27/08/2026
(`information_schema.columns` de `kronos_api`). **Se a origem mudar, este
arquivo muda junto** — de propósito: a atualização é o momento de decidir o
que fazer com a diferença, não um detalhe a descobrir depois.
"""

import pytest
from django.db import connection
from tests.conftest import matriz_do_teste

#: coluna -> (tipo, tamanho), como está em `api_conexao` no `kronos_api`.
DA_ORIGEM = {
    "host": ("character varying", 255),
    "porta": ("character varying", 10),
    "banco": ("character varying", 100),
    "tabela": ("character varying", 100),
    "usuario": ("character varying", 255),
    "senha": ("character varying", 255),
}

#: O que a origem tem e nós NÃO trouxemos, com o motivo. Ausência sem motivo
#: escrito é indistinguível de esquecimento.
NAO_COPIADO = {
    "nome_empresa": "aqui é `razao_social`/`nome_fantasia`, que este produto "
                    "já tinha e são mais precisos que um campo só",
    "cnpj_raiz e cnpj_complemento": "a origem parte o CNPJ em dois porque o "
                                    "Kronos legado guarda assim; aqui existe "
                                    "`cnpj` inteiro e validado por dígito. "
                                    "Manter os dois criaria duas verdades "
                                    "sobre o mesmo documento — o cron parte "
                                    "na hora de sincronizar",
    "created_at e updated_at": "`Empresa` não tinha carimbo de tempo antes "
                               "disto e continua sem; quando precisar, entra "
                               "com os nomes da origem",
    "usuarios (M2M)": "na origem liga usuário do painel a empresa. Aqui quem "
                      "vê o quê é permissão e filial, e duplicar isso criaria "
                      "duas verdades sobre acesso",
}


def _colunas(tabela: str) -> dict:
    with connection.cursor() as c:
        c.execute("""
            select column_name, data_type, character_maximum_length
            from information_schema.columns
            where table_name = %s and table_schema = 'public'""", [tabela])
        return {n: (t, tam) for n, t, tam in c.fetchall()}


@pytest.mark.django_db
class TestAConexaoBateComAOrigem:
    def test_toda_coluna_de_conexao_existe(self):
        nossas = _colunas("plataforma_empresa")
        faltando = sorted(set(DA_ORIGEM) - set(nossas))
        assert not faltando, (
            f"coluna de conexão que sumiu: {faltando}. Se a ausência é "
            f"deliberada, escreva o motivo em NAO_COPIADO."
        )

    def test_o_tipo_e_o_tamanho_batem(self):
        """`varchar(255)` virando `varchar(120)` corta o host do cliente na
        sincronia, e o corte é silencioso do lado que recebe."""
        nossas = _colunas("plataforma_empresa")
        divergentes = [
            f"{coluna}: origem {esperado}, aqui {nossas[coluna]}"
            for coluna, esperado in DA_ORIGEM.items()
            if coluna in nossas and nossas[coluna] != esperado
        ]
        assert not divergentes, divergentes

    def test_as_ausencias_tem_motivo(self):
        vazios = [c for c, motivo in NAO_COPIADO.items() if not motivo.strip()]
        assert not vazios, f"ausência sem motivo escrito: {vazios}"


@pytest.mark.django_db
class TestASenhaSoEntraPelaPortaCerta:
    """O model de origem confia num comentário — "nunca atribua `senha`
    direto". Comentário não impede ninguém: basta um `Empresa(senha=...)` num
    shell, ou um formulário novo que esqueça da regra, e a credencial do
    cliente do cliente fica em texto claro sem nada acusar.
    """

    def test_definir_senha_cifra_e_a_leitura_devolve(self, monkeypatch):
        from plataforma.cifra import VARIAVEL, gerar_chave
        from plataforma.models import Empresa

        monkeypatch.setenv(VARIAVEL, gerar_chave())
        e = Empresa(razao_social="Cliente Ltda")
        e.definir_senha("segredo-do-oracle")

        assert e.senha != "segredo-do-oracle"
        assert e.senha.startswith("gAAAAA")
        assert e.senha_clara == "segredo-do-oracle"

    def test_senha_atribuida_direto_e_recusada(self, monkeypatch):
        from django.core.exceptions import ValidationError

        from plataforma.cifra import VARIAVEL, gerar_chave
        from plataforma.models import Empresa

        monkeypatch.setenv(VARIAVEL, gerar_chave())
        e = Empresa(razao_social="Cliente Ltda", senha="segredo-em-claro")

        with pytest.raises(ValidationError) as erro:
            e.full_clean()
        assert "senha" in erro.value.message_dict

    def test_sem_chave_de_cifragem_recusa_gravar_a_senha(self, monkeypatch):
        """Falha no USO e não na subida: este produto pode ter instalação
        que nunca cadastra conexão nenhuma, e cobrar a chave de todas seria
        cobrar de quem não usa."""
        from django.core.exceptions import ImproperlyConfigured

        from plataforma.cifra import VARIAVEL
        from plataforma.models import Empresa

        monkeypatch.delenv(VARIAVEL, raising=False)
        with pytest.raises(ImproperlyConfigured, match=VARIAVEL):
            Empresa(razao_social="Cliente Ltda").definir_senha("x")

    def test_senha_vazia_continua_vazia(self, monkeypatch):
        """Não se cifra ausência de senha: um Fernet de string vazia seria
        indistinguível de uma senha de verdade para quem lê a coluna."""
        from plataforma.cifra import VARIAVEL, gerar_chave
        from plataforma.models import Empresa

        monkeypatch.setenv(VARIAVEL, gerar_chave())
        e = Empresa(razao_social="Cliente Ltda")
        e.definir_senha("")

        assert e.senha == ""
        assert e.senha_clara == ""


@pytest.mark.django_db
class TestAFilialSabeDeQuemE:
    """No KRONOS.net esta FK não existe: lá a empresa é uma só por
    instalação. Aqui ela é cadastro, e sem a FK uma filial ficaria pendurada
    no ar — e o seletor do cabeçalho não teria como oferecer só as filiais da
    empresa escolhida.
    """

    def test_a_matriz_semeada_nasce_ligada_a_empresa(self, db):
        from plataforma.models import Filial

        matriz = matriz_do_teste()
        assert matriz.empresa is not None

    def test_apagar_empresa_com_filial_e_recusado(self, db):
        """`PROTECT`, e não `CASCADE`: apagar uma empresa não pode levar as
        filiais dela junto em silêncio."""
        from django.db.models import ProtectedError

        from plataforma.models import Empresa

        with pytest.raises(ProtectedError):
            matriz_do_teste().empresa.delete()
