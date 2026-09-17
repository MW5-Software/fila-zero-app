"""A tela onde a MW5 troca a cara de uma instalação.

O teste que fecha a promessa da entrega é o último: mudar a cor aqui muda o
sistema inteiro, sem tocar em código.

Nota: os fixtures postam `usuario`, não `login`, para `reverse("entrar")` —
é essa a chave que `LoginPage.campos_da_marca()` (nucleo/layout.py) realmente
emite como `name` do campo. Ver task-3-report.md para o porquê.
"""

import pytest
from django.contrib.auth.models import Group
from contas.models import Usuario
from django.test import Client
from django.urls import reverse

from plataforma import views
from tests.conftest import por_na_conta


@pytest.fixture
def cliente_mw5(db):
    """A MW5, do jeito que a regra exige: superusuário, não grupo.

    Acesso às telas da MW5 vem de `is_superuser`, nunca de um grupo chamado
    `mw5` — ver o comentário em `plataforma/views.py` e
    `test_grupo_chamado_mw5_nao_da_acesso_a_tela`, que trava o porquê.
    """
    Usuario.objects.create_superuser(email="raiz@teste.com", password="segredo-de-teste")
    c = Client()
    c.post(reverse("entrar"), {"usuario": "raiz@teste.com", "senha": "segredo-de-teste"})
    return c


@pytest.fixture
def cliente_comum(db):
    Usuario.objects.create_user(email="ana@teste.com", password="segredo-de-teste")
    c = Client()
    c.post(reverse("entrar"), {"usuario": "ana@teste.com", "senha": "segredo-de-teste"})
    return c


class TestQuemEntra:
    def test_a_mw5_abre_a_tela(self, cliente_mw5):
        assert cliente_mw5.get(reverse("aparencia")).status_code == 200

    def test_o_admin_do_cliente_nao_ve_a_tela(self, cliente_comum):
        """Aparência é só da MW5. 404: quem não pode não descobre que existe."""
        assert cliente_comum.get(reverse("aparencia")).status_code == 404

    def test_grupo_chamado_mw5_nao_da_acesso_a_tela(self, db):
        """A porta que esta regra fecha: quando a gestão de usuários existir,
        o admin do cliente vai poder criar grupos. Se o acesso da MW5 viesse
        do nome do grupo, ele cunharia a própria promoção."""
        u = Usuario.objects.create_user(
            email="esperto@teste.com", password="segredo-de-teste")
        u.groups.add(Group.objects.create(name="mw5"))
        c = Client()
        c.post(reverse("entrar"),
               {"usuario": "esperto@teste.com", "senha": "segredo-de-teste"})
        assert c.get(reverse("aparencia")).status_code == 404

    def test_quem_nao_entrou_vai_para_o_login(self, db):
        resposta = Client().get(reverse("aparencia"))
        assert resposta.status_code == 302


class TestATela:
    def test_desenha_os_campos_da_marca(self, cliente_mw5):
        html = cliente_mw5.get(reverse("aparencia")).content.decode()
        assert "Nome do cliente" in html
        assert "Cor primária" in html

    def test_traz_o_token_csrf(self, cliente_mw5):
        html = cliente_mw5.get(reverse("aparencia")).content.decode()
        assert "csrfmiddlewaretoken" in html

    def test_mostra_os_valores_que_estao_valendo(self, cliente_mw5):
        from plataforma.models import Marca

        Marca.objects.create(client_name="Sementes Premix", primary="#276b2e")
        html = cliente_mw5.get(reverse("aparencia")).content.decode()
        assert "Sementes Premix" in html
        assert "#276b2e" in html


class TestSalvar:
    def test_salvar_grava_no_banco(self, cliente_mw5):
        from plataforma.models import Marca

        cliente_mw5.post(reverse("aparencia"), {
            "client_name": "Sementes Premix", "primary": "#276b2e",
            "accent": "#872d00", "radius": "12px", "density": "normal",
            "sidebar_width": "256px",
        })
        assert Marca.objects.get().client_name == "Sementes Premix"

    def test_salvar_duas_vezes_nao_cria_duas_linhas(self, cliente_mw5):
        """Uma instalação, uma marca."""
        from plataforma.models import Marca

        for nome in ("Um", "Dois"):
            cliente_mw5.post(reverse("aparencia"), {
                "client_name": nome, "primary": "#1e40af", "accent": "#872d00",
                "radius": "12px", "density": "normal", "sidebar_width": "256px",
            })
        assert Marca.objects.count() == 1

    def test_cor_invalida_nao_grava_e_avisa(self, cliente_mw5):
        from plataforma.models import Marca

        resposta = cliente_mw5.post(reverse("aparencia"), {
            "client_name": "X", "primary": "nao-e-cor", "accent": "#872d00",
            "radius": "12px", "density": "normal", "sidebar_width": "256px",
        })
        assert resposta.status_code == 200
        assert Marca.objects.count() == 0
        assert "cor" in resposta.content.decode().lower()

    def test_cor_ilegivel_e_recusada(self, cliente_mw5):
        """Amarelo claríssimo de fundo de menu com texto branco não passa —
        a pessoa descobre na hora, não depois de salvar."""
        from plataforma.models import Marca

        resposta = cliente_mw5.post(reverse("aparencia"), {
            "client_name": "X", "primary": "#1e40af", "accent": "#872d00",
            "radius": "12px", "density": "normal", "sidebar_width": "256px",
            "sidebar_bg": "#fffde7", "sidebar_text": "#ffffff",
        })
        assert resposta.status_code == 200
        assert Marca.objects.count() == 0
        assert "leg" in resposta.content.decode().lower()


@pytest.mark.django_db
def test_trocar_a_cor_muda_o_sistema_inteiro(cliente_mw5):
    """A promessa da entrega, num teste só."""
    antes = cliente_mw5.get(reverse("tema")).content.decode()
    cliente_mw5.post(reverse("aparencia"), {
        "client_name": "Sementes Premix", "primary": "#276b2e",
        "accent": "#872d00", "radius": "12px", "density": "normal",
        "sidebar_width": "256px",
    })
    depois = cliente_mw5.get(reverse("tema")).content.decode()
    assert antes != depois
    assert "276b2e" in depois


class TestAEstruturaQueOBancoJaGuardava:
    """Item 22 do Bloco 3: `radius_control`, `density`, `shadows` e `zebra`
    já têm coluna e já chegam ao CSS — só não tinham tela."""

    def test_a_tela_mostra_os_quatro_controles(self, cliente_mw5):
        html = cliente_mw5.get(reverse("aparencia")).content.decode()
        assert "Arredondamento dos controles" in html
        assert "Densidade" in html
        assert "Sombras" in html
        assert "Tabela listrada" in html

    def test_a_densidade_oferece_as_tres_opcoes(self, cliente_mw5):
        html = cliente_mw5.get(reverse("aparencia")).content.decode()
        for opcao in ("Compacta", "Normal", "Confortável"):
            assert opcao in html

    def test_salvar_grava_os_quatro(self, cliente_mw5):
        from plataforma.models import Marca

        cliente_mw5.post(reverse("aparencia"), {
            "client_name": "X", "primary": "#1e40af", "accent": "#872d00",
            "radius": "8px", "radius_control": "2px",
            "density": "compact", "sidebar_width": "256px",
            "shadows": "on", "zebra": "on",
        })
        marca = Marca.objects.get()
        assert marca.radius_control == "2px"
        assert marca.density == "compact"
        assert marca.shadows is True
        assert marca.zebra is True

    def test_caixinha_ausente_grava_falso(self, cliente_mw5):
        """Um `<input type="checkbox">` desmarcado NÃO vem no POST — ausência
        é o que diz "não quero", e não um sinal perdido."""
        from plataforma.models import Marca

        cliente_mw5.post(reverse("aparencia"), {
            "client_name": "X", "primary": "#1e40af", "accent": "#872d00",
            "radius": "8px", "density": "normal", "sidebar_width": "256px",
        })
        marca = Marca.objects.get()
        assert marca.shadows is False
        assert marca.zebra is False

    def test_campo_de_medida_em_branco_usa_o_que_esta_valendo(self, cliente_mw5):
        """Apagar a medida no navegador e salvar não pode ser uma recusa
        nem um 500: o campo em branco significa "mantém o de agora"."""
        from plataforma.models import Marca

        Marca.objects.create(client_name="Antes", radius_control="7px")
        cliente_mw5.post(reverse("aparencia"), {
            "client_name": "Depois", "primary": "#1e40af",
            "accent": "#872d00", "radius": "8px", "density": "normal",
            "sidebar_width": "256px",
        })
        assert Marca.objects.get().radius_control == "7px"

    def test_densidade_desconhecida_e_recusada(self, cliente_mw5):
        """O `Select` sempre manda uma das três; um POST forjado com outra
        coisa bate na validação do `Brand`, que já conhece as opções."""
        from plataforma.models import Marca

        resposta = cliente_mw5.post(reverse("aparencia"), {
            "client_name": "X", "primary": "#1e40af", "accent": "#872d00",
            "radius": "8px", "density": "apertadinho", "sidebar_width": "256px",
        })
        assert resposta.status_code == 200
        assert Marca.objects.count() == 0

    def test_o_que_esta_gravado_volta_marcado_na_tela(self, cliente_mw5):
        from plataforma.models import Marca

        Marca.objects.create(client_name="Listrada", density="comfortable",
                             zebra=True)
        html = cliente_mw5.get(reverse("aparencia")).content.decode()
        assert 'value="comfortable" selected' in html
        assert 'name="zebra"' in html and "checked" in html


class TestAPreviaAoVivo:
    """Item 23 do Bloco 3: mexer no formulário recolora a tela ANTES de
    salvar.

    O caminho é o mesmo `/tema.css` de sempre — só que apontando para uma
    rota que gera a folha do CANDIDATO a partir dos parâmetros da própria
    tela. Os tokens continuam derivados no servidor (`render_theme_css`),
    então o que a prévia mostra é exatamente o que valeria salvo: não há
    uma segunda implementação das cores em JavaScript para divergir.
    """

    def test_a_folha_da_previa_responde_com_a_cor_candidata(self, cliente_mw5):
        resposta = cliente_mw5.get(reverse("aparencia_previa"),
                                   {"primary": "#276b2e"})
        assert resposta.status_code == 200
        assert "text/css" in resposta["Content-Type"]
        assert "276b2e" in resposta.content.decode()

    def test_a_previa_comeca_do_que_esta_gravado(self, cliente_mw5):
        """Candidato parcial: muda SÓ o que veio na URL, e não volta ao
        padrão da casa nas coisas que não vieram."""
        from plataforma.models import Marca

        Marca.objects.create(client_name="X", primary="#111827",
                             accent="#872d00", footer_bg="#0f172a")
        css = cliente_mw5.get(reverse("aparencia_previa"),
                              {"primary": "#276b2e"}).content.decode()
        assert "276b2e" in css      # o candidato
        assert "0f172a" in css      # o que já estava gravado

    def test_valor_invalido_e_ignorado_sem_quebrar_a_folha(self, cliente_mw5):
        """A prévia digita-se letra por letra: um hex inválido não pode
        derrubar a folha nem mostrar cor que não valeria — cai no gravado."""
        from plataforma.models import Marca

        Marca.objects.create(client_name="X", primary="#111827")
        css = cliente_mw5.get(reverse("aparencia_previa"),
                              {"primary": "nao-e-cor"}).content.decode()
        assert "276b2e" not in css
        assert "111827" in css

    def test_as_caixinhas_participam_da_previa(self, cliente_mw5):
        com_zebra = cliente_mw5.get(reverse("aparencia_previa"),
                                    {"zebra": "1"}).content.decode()
        sem_zebra = cliente_mw5.get(reverse("aparencia_previa")).content.decode()
        assert com_zebra != sem_zebra

    def test_a_rota_da_previa_e_soh_da_mw5(self, db):
        from contas.models import Usuario

        Usuario.objects.create_user(email="ana@teste.com", password="segredo-de-teste")
        c = Client()
        c.post(reverse("entrar"), {"usuario": "ana@teste.com", "senha": "segredo-de-teste"})
        assert c.get(reverse("aparencia_previa")).status_code == 404

    def test_a_tela_liga_o_formulario_a_previa(self, cliente_mw5):
        """O formulário carrega o endereço da prévia como atributo — quem
        liga os dois é a tela, não um seletor solto dentro do script."""
        html = cliente_mw5.get(reverse("aparencia")).content.decode()
        assert reverse("aparencia_previa") in html
        assert "/static/plataforma/previa.js" in html


class TestOsRotulosDoContexto:
    """Item 7 do Bloco 3: o campo que deixa o cliente chamar filial de
    "loja" mora na Aparência, ao lado do resto da marca."""

    def test_a_tela_mostra_os_dois_campos(self, cliente_mw5):
        html = cliente_mw5.get(reverse("aparencia")).content.decode()
        assert "Rótulo da empresa" in html
        assert "Rótulo da filial" in html

    def test_salvar_grava_os_rotulos(self, cliente_mw5):
        from plataforma.models import Marca

        cliente_mw5.post(reverse("aparencia"), {
            "client_name": "Rede X", "primary": "#1e40af",
            "accent": "#872d00", "radius": "8px", "density": "normal",
            "sidebar_width": "256px",
            "rotulo_da_empresa": "Bandeira", "rotulo_da_filial": "Loja",
        })
        marca = Marca.objects.get()
        assert marca.rotulo_da_empresa == "Bandeira"
        assert marca.rotulo_da_filial == "Loja"

    def test_o_cabecalho_da_tela_passa_a_dizer_bandeira(self, cliente_mw5, db):
        """O teste que fecha o ciclo: gravou aqui, o seletor do cabeçalho de
        TODA tela muda, sem tocar código.

        Era `rotulo_da_filial` → "Loja", quando o seletor do cabeçalho era o
        de filial. Neste produto o seletor é o de EMPRESA (ver
        `plataforma/contexto.py`), então quem fecha o ciclo é
        `rotulo_da_empresa`. A promessa é a mesma; mudou qual dos dois
        rótulos chega lá.

        O seletor, que tem opções, desenha o rótulo sem dois-pontos — ver
        `nucleo/templates/layout/context_switcher.html`.
        """
        from django.test import Client

        from contas.models import Nivel, Usuario
        from plataforma.models import Empresa

        # **Quem OLHA o cabeçalho é um titular com DUAS empresas**
        # (17/09/2026): com uma empresa só não há seletor, e para a MW5 o
        # rótulo é sempre "Conta" — a marca diz como o CLIENTE chama as
        # coisas dele, e a MW5 não está dentro de cliente nenhum
        # (`plataforma.site.construir_context_switcher`).
        titular = Usuario.objects.create_user(
            email="dono-bandeira@teste.com", password="segredo-de-teste",
            nivel=Nivel.TITULAR)
        Empresa.objects.create(razao_social="Alfa Ltda", dono=titular)
        Empresa.objects.create(razao_social="Beta Ltda", dono=titular)

        cliente_mw5.post(reverse("aparencia"), {
            "client_name": "Rede X", "primary": "#1e40af",
            "accent": "#872d00", "radius": "8px", "density": "normal",
            "sidebar_width": "256px", "rotulo_da_empresa": "Bandeira",
        })
        dele = Client()
        dele.post(reverse("entrar"), {"usuario": "dono-bandeira@teste.com",
                                      "senha": "segredo-de-teste"})
        html = dele.get(reverse("home")).content.decode()
        assert ">Bandeira</label>" in html


@pytest.mark.django_db
class TestATelaEstaOrganizadaPorAssunto:
    """A tela nasceu com os dezessete campos numa grade só, sob um título só —
    "Nome do cliente" ao lado de "Arredondamento dos controles". Cada campo
    estava certo e o conjunto era ilegível: para achar a cor do menu era
    preciso ler os dezessete.

    O que estes testes seguram não é o desenho, é o que o desenho promete:
    que existe agrupamento por assunto, que campo em branco EXPLICA o que
    acontece, e que a lista de campos da tela e a que o POST grava são a mesma.
    """

    def test_os_cartoes_aparecem_com_o_titulo_e_a_frase_de_apoio(self, cliente_mw5):
        html = cliente_mw5.get(reverse("aparencia")).content.decode()
        for titulo, apoio, _ in views.CARTOES:
            assert titulo in html, titulo
            assert apoio in html, titulo

    def test_as_cores_de_area_dizem_o_que_o_vazio_faz(self, cliente_mw5):
        """Campo em branco herda do tema. Sem essa frase, um campo vazio
        parece campo por preencher — e a pessoa inventa uma cor."""
        html = cliente_mw5.get(reverse("aparencia")).content.decode()
        assert views._HERDA in html
        # Uma vez por cor de área, e não uma só no alto da tela: quem está
        # olhando o campo já passou do aviso lá em cima.
        assert html.count(views._HERDA) >= 7

    def test_o_menu_e_o_cabecalho_sao_secoes_separadas(self, cliente_mw5):
        html = cliente_mw5.get(reverse("aparencia")).content.decode()
        for rotulo in ("Menu", "Cabeçalho", "Conteúdo e rodapé"):
            assert f'class="seclabel"' in html
            assert f">{rotulo}</div>" in html, rotulo

    def test_a_lista_da_tela_e_a_lista_que_grava_sao_a_mesma(self):
        """`CAMPOS` é derivado de `CARTOES`. Duas listas do mesmo conjunto
        divergem no dia em que alguém acrescentar um campo numa e esquecer da
        outra — e o sintoma seria um campo que a tela mostra e o POST ignora.
        """
        das_secoes = [
            nome
            for _, _, secoes in views.CARTOES
            for _, campos in secoes
            for nome, _, _, _ in campos
        ]
        assert [nome for nome, _, _ in views.CAMPOS] == das_secoes
        assert sorted(views.AJUDA) == sorted(das_secoes)

    def test_todo_campo_tem_ajuda(self):
        """Ajuda vazia é pior que nenhuma: ocupa o lugar de uma explicação e
        parece que alguém já pensou naquele campo."""
        vazios = [nome for nome, texto in views.AJUDA.items() if not texto.strip()]
        assert not vazios, f"campos sem ajuda: {vazios}"

    def test_um_salvar_so_para_todos_os_cartoes(self, cliente_mw5):
        """Os cartões são a leitura; o formulário é a gravação. Quem trocou a
        cor do menu e o rótulo da filial não pode precisar salvar duas vezes
        porque a tela desenhou dois quadros."""
        html = cliente_mw5.get(reverse("aparencia")).content.decode()
        assert html.count(">Salvar<") == 1
