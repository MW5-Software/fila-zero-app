"""A tela de Usuários não mostra — nem deixa mexer em — gente de outra empresa.

O portal atende várias empresas na mesma instalação. A tela herdada do
KRONOS.net listava `User.objects.filter(is_superuser=False)`, o que lá estava
certo (uma instalação, um cliente) e aqui seria vazamento: um admin da Alfa
saberia o nome, o login e o e-mail da equipe da Beta.

**Escrito por ataque.** Um teste que só confirma que o admin vê a própria
equipe passaria igual com o filtro removido — e é justamente esse o defeito.
Cada caso aqui tem a forma "quem não deveria, não consegue", e os de AÇÃO
mandam o id direto no POST, sem nunca ter visto a linha na tela: é assim que
o ataque de verdade acontece.
"""

import pytest
from django.contrib.auth.models import Permission
from contas.models import Usuario
from django.test import Client
from django.urls import reverse

from contas.models import Nivel
from plataforma.models import Empresa
from tests.conftest import email_de, por_na_conta

SENHA = "segredo-de-teste"


@pytest.fixture
def cenario(db):
    alfa = Empresa.objects.create(razao_social="Alfa Ltda")
    beta = Empresa.objects.create(razao_social="Beta Ltda")

    def pessoa(login, nivel, empresas, admin_de_gente=False):
        u = Usuario.objects.create_user(
            email=email_de(login), password=SENHA)
        if admin_de_gente:
            u.user_permissions.add(
                Permission.objects.get(codename="usuarios_editar"))
        u.nivel = nivel
        u.save(update_fields=["nivel"])
        por_na_conta(u, empresas[0] if empresas else None)
        return u

    return {
        "alfa": alfa, "beta": beta,
        "admin_alfa": pessoa("admin_alfa", Nivel.TITULAR, [alfa], True),
        # A segunda CONTA. Sem ela não há de onde vir o id alheio que os
        # testes de POST forjado precisam mandar.
        "admin_beta": pessoa("admin_beta", Nivel.TITULAR, [beta]),
        "vend_alfa": pessoa("vend_alfa", Nivel.MEMBRO, [alfa], True),
        "gente_alfa": pessoa("gente_alfa", Nivel.MEMBRO, [alfa]),
        "gente_beta": pessoa("gente_beta", Nivel.MEMBRO, [beta]),
    }


def _logado(login):
    c = Client()
    c.post(reverse("entrar"), {"usuario": email_de(login), "senha": SENHA})
    return c


@pytest.mark.django_db
class TestAListagem:
    def test_o_admin_ve_a_equipe_da_empresa_dele(self, cenario):
        html = _logado("admin_alfa").get(reverse("usuarios")).content.decode()
        assert "gente_alfa" in html

    def test_o_admin_NAO_ve_a_equipe_da_outra_empresa(self, cenario):
        """O vazamento que esta tela tinha: nome, login e e-mail de gente de
        outro cliente do portal."""
        html = _logado("admin_alfa").get(reverse("usuarios")).content.decode()
        assert "gente_beta" not in html

    def test_o_vendedor_nao_administra_ninguem(self, cenario):
        """Ver o orçamento de um comprador não dá direito de mexer na conta
        dele. `compradores_alcancados` e `pessoas_alcancadas` respondem
        perguntas diferentes, e é por isso que são duas funções."""
        html = _logado("vend_alfa").get(reverse("usuarios")).content.decode()
        assert "gente_alfa" not in html
        assert "gente_beta" not in html


@pytest.mark.django_db
class TestAsAcoes:
    """O POST forjado: o id vai direto, sem a linha ter aparecido na tela."""

    def test_editar_alguem_de_outra_empresa_nao_encontra_o_alvo(self, cenario):
        alvo = cenario["gente_beta"]
        resposta = _logado("admin_alfa").post(reverse("usuarios"), {
            "acao": "editar", "id": str(alvo.pk),
            "login": "invadido", "nome": "Invadido",
        })

        alvo.refresh_from_db()
        assert alvo.email == email_de("gente_beta")
        assert resposta.status_code in (200, 302, 404)

    def test_desativar_alguem_de_outra_empresa_nao_desativa(self, cenario):
        alvo = cenario["gente_beta"]
        _logado("admin_alfa").post(reverse("usuarios"), {
            "acao": "desativar", "id": str(alvo.pk)})

        alvo.refresh_from_db()
        assert alvo.is_active is True

    def test_remover_alguem_de_outra_empresa_nao_remove(self, cenario):
        alvo = cenario["gente_beta"]
        _logado("admin_alfa").post(reverse("usuarios"), {
            "acao": "remover", "id": str(alvo.pk)})

        assert Usuario.objects.filter(pk=alvo.pk).exists()

    def test_a_exportacao_leva_o_mesmo_alcance_da_tela(self, cenario):
        """Um relatório é o caminho mais fácil para o dado escapar: se a
        exportação usasse outro queryset, a tela esconderia e o Excel
        entregaria."""
        resposta = _logado("admin_alfa").get(
            reverse("usuarios"), {"formato": "impressao"})
        corpo = resposta.content.decode()

        assert "gente_alfa" in corpo
        assert "gente_beta" not in corpo


@pytest.mark.django_db
class TestNaoDaParaSubirDeNivel:
    """A escalação por procuração: um ADMIN que pudesse criar um MASTER
    criaria uma conta acima dele e, por ela, promoveria a si mesmo.

    É a mesma fronteira que a tela já guarda para `is_superuser`, com outro
    nome — e por isso os testes têm a mesma forma: o POST vai forjado, com o
    valor que a tela nunca ofereceu.
    """

    def test_o_titular_nao_ve_caixa_de_nivel(self, cenario):
        """Só a MW5 escolhe nível (14/09/2026): o titular cadastra membros da
        conta dele, e o que cada um faz vem do cargo da alocação. Uma caixa
        com uma opção só seria uma pergunta sem escolha.

        Olha o `<select name="nivel">`, e não um `value` solto na página: o
        filtro de Situação também tem `value="0"`, e uma asserção que casa com
        a página toda não prova nada sobre um campo.
        """
        import re

        html = _logado("admin_alfa").get(reverse("usuarios")).content.decode()
        assert not re.findall(r'<select[^>]*name="nivel"', html)

    def test_post_forjado_com_titular_nao_abre_outra_conta(self, cenario):
        """Esconder a opção não é proteger, e aqui o que passaria não é um
        rótulo errado: seria um cliente novo dentro do portal, com empresa e
        catálogo próprios, aberto por quem não vende conta."""
        from contas.models import Nivel

        _logado("admin_alfa").post(reverse("usuarios"), {
            "acao": "criar", "nome": "Outro Titular",
            "email": "outro-titular@teste.com",
            "nivel": str(int(Nivel.TITULAR)),
        })

        novo = Usuario.objects.get(email="outro-titular@teste.com")
        assert novo.nivel != Nivel.TITULAR

    def test_post_forjado_com_master_nao_promove(self, cenario):
        """Esconder a opção não é proteger: o POST vem do cliente."""
        from contas.models import Nivel

        alvo = cenario["gente_alfa"]
        _logado("admin_alfa").post(reverse("usuarios"), {
            "acao": "editar", "id": str(alvo.pk), "nome": "Fulano",
            "nivel": str(int(Nivel.MASTER)),
        })

        alvo.refresh_from_db()
        assert alvo.nivel != Nivel.MASTER

    def test_post_forjado_com_empresa_alheia_nao_vincula(self, cenario):
        """O outro lado da mesma regra: um id de CONTA que quem edita não é
        não entra — senão o admin da Alfa mudaria alguém para a Beta, e
        mudar de conta é mudar de cliente."""
        from contas.alcance import conta_de, usuario_de

        alvo = cenario["gente_alfa"]
        antes = conta_de(alvo)
        _logado("admin_alfa").post(reverse("usuarios"), {
            "acao": "editar", "id": str(alvo.pk), "nome": "Fulano",
            "conta": str(cenario["admin_beta"].pk),
        })

        alvo.refresh_from_db()
        assert conta_de(alvo) == antes

    def test_editar_sem_falar_de_conta_nao_desliga_ninguem(self, cenario):
        """Era `test_editar_nao_arranca_empresa_que_quem_edita_nao_alcanca`.

        A forma do defeito sobreviveu à mudança de modelo: um `.set()`
        ingênuo com o que a tela ofereceu arrancava em silêncio o que ninguém
        decidiu revogar. Hoje o campo nem é desenhado para o Admin, e o POST
        dele vem sem `conta` — o que não pode acontecer é isso ser lido como
        "tire a pessoa da conta".
        """
        from contas.alcance import conta_de

        alvo = cenario["gente_alfa"]
        antes = conta_de(alvo)
        assert antes is not None

        _logado("admin_alfa").post(reverse("usuarios"), {
            "acao": "editar", "id": str(alvo.pk), "nome": "Fulano",
        })

        alvo.refresh_from_db()
        assert conta_de(alvo) == antes


