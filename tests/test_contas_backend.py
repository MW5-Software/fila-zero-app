"""A tradução entre o usuário do Django e o usuário que o núcleo desenha.

O `nucleo.permissoes.User` é de propósito um retrato pobre: só o que a tela
precisa. É o que permite trocar a origem da gente — base do Django hoje,
Oracle do cliente amanhã — sem que nada acima perceba.
"""

import pytest
from django.contrib.auth.models import Group, Permission
from django.db import connection
from django.test.utils import CaptureQueriesContext
from contas.models import Usuario

from contas.backend import BackendDjango, permissoes_de
from nucleo.permissoes import User, pode


@pytest.fixture
def backend():
    return BackendDjango()


@pytest.fixture
def modulo_frete_declarado():
    """Declara `frete` no catálogo do código, só para a duração do teste.

    Os testes de permissão usam `frete` como módulo de exemplo há tarefas
    anteriores a esta; `permissoes_de` só traduz permissão de módulo que
    exista no catálogo — sem a declaração, nenhuma `Permission` com prefixo
    `frete_` viraria `frete.*` nem `frete.<acao>`.

    `permissoes=("frete.ver",)`: os testes desta tarefa chamam
    `contas.permissoes.materializar()` e esperam achar a `Permission`
    `frete_ver` já criada — sem isto no `ModuloSpec`, `materializar` só
    criaria o coringa `frete_*`, e não a ação `ver`.
    """
    from plataforma.declaracao import ModuloSpec, registrar

    especie = ModuloSpec(chave="frete", rotulo="Frete", permissoes=("frete.ver",))
    registrar(especie)
    yield
    from plataforma import declaracao

    declaracao._DECLARADOS.pop("frete", None)


@pytest.fixture
def ana(db):
    return Usuario.objects.create_user(
        email="ana@teste.com", password="segredo-de-teste",
        # Um campo só, e não `first_name` + `last_name`: é a mudança que o
        # usuário próprio trouxe, e o nome composto continua aqui para provar
        # que o retrato do núcleo recebe o nome INTEIRO.
        nome="Ana Paula Souza",
    )


class TestAutenticar:
    def test_login_certo_devolve_o_usuario_do_nucleo(self, backend, ana):
        u = backend.autenticar("ana@teste.com", "segredo-de-teste")
        assert isinstance(u, User)
        assert u.login == "ana@teste.com"
        assert u.name == "Ana Paula Souza"

    def test_senha_errada_devolve_nada(self, backend, ana):
        assert backend.autenticar("ana@teste.com", "errada") is None

    def test_login_inexistente_devolve_nada(self, backend, db):
        assert backend.autenticar("ninguem", "seja-la") is None

    def test_usuario_inativo_nao_entra(self, backend, ana):
        """Desativar alguém tem que valer na hora, não no próximo deploy."""
        ana.is_active = False
        ana.save()
        assert backend.autenticar("ana@teste.com", "segredo-de-teste") is None

    def test_login_inexistente_e_senha_errada_nao_se_distinguem(self, backend, ana):
        """Quem chama não pode descobrir quais logins existem."""
        assert backend.autenticar("ana@teste.com", "errada") is None
        assert backend.autenticar("ninguem", "errada") is None


class TestBuscar:
    def test_reconstroi_a_sessao_sem_senha(self, backend, ana):
        u = backend.buscar(str(ana.pk))
        assert u is not None and u.login == "ana@teste.com"

    def test_usuario_desativado_some(self, backend, ana):
        ana.is_active = False
        ana.save()
        assert backend.buscar(str(ana.pk)) is None

    def test_id_que_nao_existe_devolve_nada(self, backend, db):
        assert backend.buscar("999999") is None

    def test_id_que_nao_e_numero_nao_derruba(self, backend, db):
        """Cookie adulterado não pode virar erro 500."""
        assert backend.buscar("nao-e-numero") is None

    def test_nao_traz_os_bytes_do_avatar(self, backend, ana):
        """`buscar` roda em TODA requisição autenticada (`usuario_da_sessao`
        chama a cada uma) — e o `BinaryField` da foto, se vier junto do
        `SELECT`, é peso que toda tela paga sem nenhuma delas pedir.

        `ana` PRECISA ter avatar de verdade: sem bytes gravados, um
        `.defer("avatar")` esquecido e um presente são indistinguíveis por
        aqui — os dois devolveriam `avatar` vazio/`None` sem diferença de
        consulta nenhuma. Só com bytes de verdade um acesso indevido ao
        campo adiado (`usuario.avatar`) dispara o `SELECT` extra que este
        teste pega.
        """
        Usuario.objects.filter(pk=ana.pk).update(
            avatar=b"\x89PNG\r\n\x1a\n" + b"\x00" * 64,
            avatar_tipo="image/png")

        with CaptureQueriesContext(connection) as capturadas:
            resultado = backend.buscar(str(ana.pk))

        # Prova que o caminho que IMPORTA rodou: a pessoa tem avatar, e o
        # retrato do núcleo mostra o link — não é um `tem_avatar` que deu
        # sorte de ser falso.
        assert resultado.avatar != ""

        consultas_do_usuario = [
            q["sql"] for q in capturadas.captured_queries
            if "contas_usuario" in q["sql"] and q["sql"].startswith("SELECT")
        ]
        assert consultas_do_usuario, "esperava um SELECT em contas_usuario"
        for sql in consultas_do_usuario:
            # `avatar_tipo` PODE estar na lista de colunas (é barato, e é o
            # sinal que `_para_o_nucleo` usa); `avatar` — o `BinaryField` —
            # não pode. Descarta as ocorrências de `avatar_tipo` antes de
            # procurar por `avatar` sozinho, senão a substring bate nela.
            assert '"avatar"' not in sql.replace('"avatar_tipo"', "")

        # E nenhuma consulta A MAIS: se algo tocasse no campo adiado depois
        # do fetch, o Django buscaria a coluna que faltou numa consulta
        # extra — é essa consulta extra que provaria o vazamento. É UMA: `ana`
        # é membro, e membro nasce sem permissão no backend (a dele vem do
        # cargo, no lugar), então nem a consulta de permissões acontece.
        assert len(capturadas.captured_queries) == 1


class TestPermissoes:
    def test_sem_grupo_nenhum_nao_pode_nada(self, backend, ana):
        u = backend.autenticar("ana@teste.com", "segredo-de-teste")
        assert pode(u, "exemplo.ver") is False

    def test_permissao_de_modulo_ganha_o_ponto(
            self, backend, ana, db, modulo_frete_declarado):
        """O Django não aceita ponto em codename, então a permissão de módulo
        se escreve `frete_ver` no banco e vira `frete.ver` aqui.

        O `ContentType` é criado à mão, e não derivado de um model: o que a
        tradução lê é o `app_label`, e amarrar este teste ao model `Modulo`
        (que chega numa tarefa posterior) o faria depender da ordem de
        execução sem ganhar nada em rigor.

        Precisa de `frete` declarado no catálogo: a tradução só concede
        permissão de módulo que exista no catálogo (ver
        `test_permissao_de_modulo_inexistente_nao_entra`), então sem a
        declaração não concederia nada.
        """
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        tipo, _ = ContentType.objects.get_or_create(
            app_label="plataforma", model="modulo")
        ana.user_permissions.add(Permission.objects.create(
            codename="frete_ver", name="ver frete", content_type=tipo))

        assert "frete.ver" in permissoes_de(ana)

    def test_permissao_nativa_do_django_nao_entra_no_vocabulario_do_nucleo(
            self, backend, ana, db):
        """`auth.add_user` continua valendo por `user.has_perm`, no mundo do
        Django. Ela não entra aqui porque o `pode()` fala um vocabulário só.

        Isto não é preciosismo de nomenclatura: enquanto os dois vocabulários
        dividiam o mesmo conjunto, um grupo chamado `auth` concedia
        `auth.add_user` dentro do `pode()`, porque o coringa `X.*` cobre
        `X.qualquer-coisa`. Com um vocabulário só, a colisão deixa de ser
        possível em vez de depender de ninguém batizar um grupo com o nome de
        um app.
        """
        # `add_usuario` e não `add_user`: com o `AUTH_USER_MODEL` sendo
        # nosso, `auth.User` está trocado e o Django não gera mais permissão
        # para ele — a permissão nativa equivalente é a do model desta casa.
        ana.user_permissions.add(Permission.objects.get(codename="add_usuario"))
        assert "contas.add_usuario" not in permissoes_de(ana)
        assert "add.usuario" not in permissoes_de(ana)

    def test_grupo_nao_concede_permissao_nenhuma_por_nome(
            self, backend, ana, db, modulo_frete_declarado):
        """A raiz do coringa por nome de grupo foi arrancada (correção final
        da revisão de branch): um grupo chamado `frete` — mesmo com `frete`
        de fato declarado no catálogo — não concede `frete.*` nem nada mais
        sozinho. O nome do grupo é só rótulo; quem concede é `Permission`.

        Prova o oposto do que `test_o_nome_do_grupo_vira_permissao_coringa`
        afirmava antes desta correção: aquele teste, e o mecanismo que ele
        cobria, foram removidos de propósito — ver o docstring de
        `permissoes_de`."""
        ana.groups.add(Group.objects.create(name="frete"))
        assert permissoes_de(ana) == frozenset()

    def test_permissao_com_codename_coringa_concede_o_modulo_inteiro(
            self, backend, ana, db, modulo_frete_declarado):
        """A forma canônica de conceder um módulo inteiro, agora que o nome
        do grupo não faz mais isso: uma `Permission` com
        `codename="<modulo>_*"`. Ela passa pelo mesmo caminho de tradução de
        qualquer outra permissão de módulo — não há mecanismo separado."""
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        tipo, _ = ContentType.objects.get_or_create(
            app_label="plataforma", model="modulo")
        ana.user_permissions.add(Permission.objects.create(
            codename="frete_*", name="tudo de frete", content_type=tipo))

        assert "frete.*" in permissoes_de(ana)

    def test_permissao_cujo_sufixo_coincide_com_nome_de_model_nao_e_descartada(
            self, backend, ana, db, modulo_frete_declarado):
        """`plataforma.frete_marca` é uma permissão de módulo legítima
        (`frete.marca`) cujo sufixo, por coincidência, é igual ao nome do
        model `Marca`. O critério de exclusão das permissões autogeradas
        pelo Django compara o CODENAME INTEIRO (`{verbo}_{model}`, lido de
        `default_permissions`) contra o codename da permissão — não o sufixo
        isolado contra a lista de nomes de model — então essa colisão de
        sufixo não produz falso-negativo."""
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        tipo, _ = ContentType.objects.get_or_create(
            app_label="plataforma", model="modulo")
        ana.user_permissions.add(Permission.objects.create(
            codename="frete_marca", name="marca de frete", content_type=tipo))

        assert "frete.marca" in permissoes_de(ana)

    def test_permissao_autogerada_do_model_modulo_nao_vira_permissao_de_modulo(
            self, backend, ana, db):
        """Ao criar o model `Modulo`, o Django gera sozinho `add_modulo`,
        `change_modulo`, `delete_modulo` e `view_modulo` no app `plataforma`.
        Com a tradução ingênua elas virariam `add.modulo`, `change.modulo` —
        nomes sem sentido no vocabulário do núcleo. O critério que as barra é
        o codename inteiro (`{verbo}_{model}`, lido do registro de apps via
        `default_permissions`), não uma lista fixa de verbos: uma lista
        envelheceria assim que a próxima tabela nascesse — e comparar só o
        sufixo contra o nome do model descartaria por engano uma permissão
        de módulo legítima cujo sufixo coincidisse com um nome de model (ver
        `test_permissao_cujo_sufixo_coincide_com_nome_de_model_nao_e_descartada`).
        """
        ana.user_permissions.add(Permission.objects.get(
            codename="add_modulo", content_type__app_label="plataforma"))

        concedidas = permissoes_de(ana)

        assert "add.modulo" not in concedidas
        assert concedidas == frozenset()

    def test_permissao_de_modulo_inexistente_nao_entra(self, backend, ana, db):
        """Criar `plataforma.mw5_aparencia` e conceder daria acesso às telas
        da MW5 se `concedidas` não conferisse o catálogo. Módulo que não
        existe não concede nada — a mesma regra que fecharia a porta do
        nome de grupo, se ela ainda existisse."""
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        tipo, _ = ContentType.objects.get_or_create(
            app_label="plataforma", model="modulo")
        ana.user_permissions.add(Permission.objects.create(
            codename="mw5_aparencia", name="aparencia mw5", content_type=tipo))

        assert "mw5.aparencia" not in permissoes_de(ana)

    def test_superusuario_passa_em_tudo(self, backend, db):
        raiz = Usuario.objects.create_superuser(
            email="raiz@teste.com", password="segredo-de-teste"
        )
        u = BackendDjango().buscar(str(raiz.pk))
        assert u.superuser is True
        assert pode(u, "qualquer.coisa") is True


class TestONome:
    def test_sem_nome_proprio_cai_no_login(self, backend, db):
        Usuario.objects.create_user(email="sonome@teste.com", password="segredo-de-teste")
        u = backend.autenticar("sonome@teste.com", "segredo-de-teste")
        # O login é o e-mail, então é o e-mail que aparece no lugar do nome —
        # e ele é uma frase que serve para chamar a pessoa, ao contrário da
        # string vazia que apareceria sem esta saída.
        assert u.name == "sonome@teste.com"


