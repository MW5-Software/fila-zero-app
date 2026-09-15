"""A política de acesso: quanto tempo a sessão dura e quando a senha vence.

Dois parâmetros da instalação (`so_mw5`: política de acesso é decisão de
quem opera a plataforma, não de cada cliente), uma coluna do usuário
(`Usuario.senha_definida_em` — QUANDO a senha foi definida, para a contagem
poder correr) e três regras:

- **Sessão com relógio de inatividade**: `minutos_de_sessao` renova a cada
  requisição — é o tempo que ela fica parada que derruba, não o tempo desde
  o login. Quem está trabalhando não é deslogado no meio do movimento.
- **Senha que expira**: `dias_para_expirar_senha`; vencida, a pessoa entra e
  é levada a trocar — nada mais dela até trocar. A marca nasce no primeiro
  login (a senha do `manage.py` não passa pelo app) e NÃO é recriada nos
  seguintes — senão a expiração nunca vencia.
- **Reset pelo admin também reinicia a contagem** do alvo: a senha temporária
  que ele entregou é a senha nova de verdade.
"""

from datetime import timedelta

import pytest
from contas.models import Usuario
from django.test import Client
from django.urls import reverse
from django.utils import timezone

SENHA = "segredo-de-teste"


@pytest.fixture
def ana(db):
    return Usuario.objects.create_user(email="ana@teste.com", password=SENHA)


@pytest.fixture
def ana_logada(ana):
    c = Client()
    c.post(reverse("entrar"), {"usuario": "ana@teste.com", "senha": SENHA})
    return c


def _parametro(nome, valor):
    from plataforma.models import Parametro

    Parametro.objects.update_or_create(chave=nome, defaults={"valor": str(valor)})


def _marca(ana, dias_atras):
    """Define `senha_definida_em` COM o instante que o teste quer, direto
    pelo SQL (`update`) — um `ana.save()` marcaria o agora de verdade, e o
    ponto do teste é poder simular uma marca velha."""
    Usuario.objects.filter(pk=ana.pk).update(
        senha_definida_em=timezone.now() - timedelta(days=dias_atras))
    ana.refresh_from_db()
    return ana


class TestOTempoDeSessao:
    def test_o_login_durante_o_que_o_parametro_diz(self, ana, db):
        _parametro("minutos_de_sessao", 480)
        c = Client()
        c.post(reverse("entrar"), {"usuario": "ana@teste.com", "senha": SENHA})
        idade = c.session.get_expiry_age()
        assert 470 * 60 < idade <= 480 * 60

    def test_a_atividade_renova_o_relogio(self, ana, db):
        """Quem está trabalhando não cai: cada requisição re-arma o tempo —
        é inatividade que expira, não idade da sessão."""
        _parametro("minutos_de_sessao", 480)
        c = Client()
        c.post(reverse("entrar"), {"usuario": "ana@teste.com", "senha": SENHA})
        # Uma requisição qualquer passou pela guarda → o relógio re-armou.
        c.get(reverse("perfil"))
        idade = c.session.get_expiry_age()
        assert 470 * 60 < idade <= 480 * 60

    def test_zero_mantem_o_padrao_do_django(self, ana, db):
        """`0` = "não mexo": vale o `SESSION_COOKIE_AGE` de sempre."""
        _parametro("minutos_de_sessao", 0)
        c = Client()
        c.post(reverse("entrar"), {"usuario": "ana@teste.com", "senha": SENHA})
        from django.conf import settings

        assert c.session.get_expiry_age() == pytest.approx(
            settings.SESSION_COOKIE_AGE, rel=0.01)


@pytest.mark.django_db
class TestAExpiracaoDaSenha:
    def _logar(self, senha=SENHA):
        c = Client()
        resposta = c.post(reverse("entrar"),
                          {"usuario": "ana@teste.com", "senha": senha}, follow=False)
        return c, resposta

    def test_zero_nunca_expira(self, ana):
        _parametro("dias_para_expirar_senha", 0)
        _marca(ana, dias_atras=400)
        c, _ = self._logar()
        # Sem flag na sessão: navega livre.
        assert "senha_expirada" not in c.session

    def test_vencida_e_levara_trocar(self, ana):
        _parametro("dias_para_expirar_senha", 30)
        _marca(ana, dias_atras=40)
        c, resposta = self._logar()
        assert "senha_expirada" in c.session
        # Qualquer tela vira a porta da troca de senha.
        r = c.get(reverse("usuarios"))
        assert r.status_code == 302
        assert reverse("perfil") in r["Location"]
        assert "expirada=1" in r["Location"]

    def test_a_tela_de_perfil_abre_e_diz_o_motivo(self, ana):
        _parametro("dias_para_expirar_senha", 30)
        _marca(ana, dias_atras=40)
        c, _ = self._logar()
        html = c.get(reverse("perfil") + "?expirada=1").content.decode()
        assert "expirou" in html.lower()

    def test_trocar_a_senha_libera_a_pessoa(self, db):
        # Superusuário de propósito: depois de liberada, precisa abrir uma
        # tela de verdade (e a `ana` comum não passa na guarda de permissão
        # de /usuarios — 404 dela diria pouco sobre a política).
        raiz = Usuario.objects.create_superuser(email="raiz@teste.com",
                                                      password=SENHA)
        _parametro("dias_para_expirar_senha", 30)
        _marca(raiz, dias_atras=40)
        c = Client()
        c.post(reverse("entrar"), {"usuario": "raiz@teste.com", "senha": SENHA})
        assert c.get(reverse("usuarios")).status_code == 302
        resposta = c.post(reverse("perfil_senha"), {
            "senha_atual": SENHA, "senha_nova": "a-senha-nova-2026",
            "senha_confirma": "a-senha-nova-2026",
        })
        assert resposta.status_code == 302
        assert "senha_expirada" not in c.session
        assert c.get(reverse("usuarios"), follow=True).status_code == 200

    def test_a_marca_nasce_no_primeiro_login_e_nao_renasce_no_segundo(self, ana):
        """A senha pode ter sido definida fora do app (`changepassword`); a
        contagem começa quando ela entra PELA PRIMEIRA vez com ela. Se cada
        login recriasse a marca, a expiração nunca vencia."""
        _parametro("dias_para_expirar_senha", 30)
        c = Client()
        c.post(reverse("entrar"), {"usuario": "ana@teste.com", "senha": SENHA})
        ana.refresh_from_db()
        assert ana.senha_definida_em is not None
        # Segundo login NÃO recria: a marca antiga (velha de propósito
        # abaixo) continua valendo.
        Usuario.objects.filter(pk=ana.pk).update(
            senha_definida_em=timezone.now() - timedelta(days=40))
        c2 = Client()
        c2.post(reverse("entrar"), {"usuario": "ana@teste.com", "senha": SENHA})
        assert "senha_expirada" in c2.session

    def test_o_reset_do_admin_reinicia_a_conta_do_alvo(self, ana, db):
        _parametro("dias_para_expirar_senha", 30)
        _marca(ana, dias_atras=40)
        Usuario.objects.create_superuser(email="raiz@teste.com",
                                               password=SENHA)
        c = Client()
        c.post(reverse("entrar"), {"usuario": "raiz@teste.com", "senha": SENHA})
        # A chave da ação é `"senha"` (`ACOES_COM_ALVO`, em
        # `contas/views_usuarios.py`) — não `"resetar"`. Com a chave errada
        # este POST sempre foi um no-op silencioso (`usuarios` devolve 302
        # sem tocar em ninguém para `acao` desconhecida), e o teste passava
        # do mesmo jeito: `ana.marcadesenha` (o `OneToOneField` de antes)
        # ficava com o valor do INSTANTE em que `_marca` criou a linha — o
        # Django cacheia o reverso no `usuario=ana` do `get_or_create`, e o
        # `.filter().update()` seguinte, sendo SQL cru, nunca invalida esse
        # cache. A leitura antiga sempre devolvia "agora", tivesse o reset
        # rodado ou não. `refresh_from_db()`, na coluna nova, força ler o
        # banco de verdade — e foi isso que expôs a chave errada.
        c.post(reverse("usuarios"), {
            "acao": "senha", "id": str(ana.pk),
        })
        ana.refresh_from_db()
        idade = timezone.now() - ana.senha_definida_em
        assert idade < timedelta(minutes=1)

    def test_com_a_senha_vencida_nem_personificar_dá(self, db):
        """A política não tem janela: com a própria senha vencida, a MW5
        também está presa na troca — abrir personificação seria agir no
        sistema com a senha vencida, e "trocar senha" dentro dela trocaria
        a do ALVO por engano. A porta fecha antes de o `iniciar` rodar uma
        linha; a saída é a mesma de todo mundo: trocar a senha (ou sair)."""
        raiz = Usuario.objects.create_superuser(email="raiz@teste.com",
                                                      password=SENHA)
        alvo = Usuario.objects.create_user(email="zeca@teste.com",
                                                 password=SENHA)
        _parametro("dias_para_expirar_senha", 30)
        _marca(raiz, dias_atras=40)
        c = Client()
        c.post(reverse("entrar"), {"usuario": "raiz@teste.com", "senha": SENHA})
        resposta = c.post(reverse("personificar"), {"id": str(alvo.pk)})
        assert resposta.status_code == 302
        assert reverse("perfil") in resposta["Location"]
        # Nada começou: nem alvo na sessão, nem linha na trilha.
        assert "usuario_personificado_id" not in c.session


@pytest.mark.django_db
class TestOsParametrosSaoDaMw5:
    def test_os_dois_nascem_declarados_e_so_mw5(self):
        from plataforma.parametro_catalogo import parametros_efetivos

        efetivos = {p.chave: p for p in parametros_efetivos()}
        assert efetivos["minutos_de_sessao"].no_padrao is True
        assert efetivos["dias_para_expirar_senha"].no_padrao is True
        from plataforma.parametro_declaracao import declarados

        specs = {p.chave: p for p in declarados()}
        assert specs["minutos_de_sessao"].so_mw5 is True
        assert specs["dias_para_expirar_senha"].so_mw5 is True
