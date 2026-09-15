"""O usuário deste produto: próprio, e com login por e-mail.

`auth_user` é criado por uma migração dentro do pacote do Django. Não é
possível acrescentar coluna nela — e era por isso que `nivel` morava em
`acesso_acesso`, uma tabela 1:1 ao lado. Com o produto virando SaaS, viriam
mais três colunas (`dono`, `plano`, `guid`) para o mesmo lugar.

Quatro tabelas viram uma.
"""

import pytest
from django.contrib.auth import get_user_model


@pytest.mark.django_db
class TestOUsuarioProprio:
    def test_o_model_do_projeto_e_o_nosso(self):
        assert get_user_model()._meta.label == "contas.Usuario"

    def test_entra_por_email_e_nao_por_apelido(self):
        """Num sistema que se assina, ninguém inventa apelido para entrar."""
        Usuario = get_user_model()
        assert Usuario.USERNAME_FIELD == "email"
        assert not any(f.name == "username" for f in Usuario._meta.fields)

    def test_o_email_e_unico(self):
        """É o login. Dois iguais seriam duas pessoas com a mesma porta."""
        from django.db import IntegrityError

        Usuario = get_user_model()
        Usuario.objects.create_user(email="a@b.com", nome="A", password="x")
        with pytest.raises(IntegrityError):
            Usuario.objects.create_user(email="a@b.com", nome="B", password="x")

    def test_nome_e_um_campo_so(self):
        """Como no `kronos-api2`. `first_name`/`last_name` obrigam toda tela a
        decidir como juntar os dois, e a primeira que decidir diferente das
        outras vira o defeito."""
        Usuario = get_user_model()
        pessoa = Usuario.objects.create_user(
            email="c@d.com", nome="Vera Souza", password="x")
        assert pessoa.nome == "Vera Souza"
        assert pessoa.get_full_name() == "Vera Souza"

    def test_o_superusuario_nasce_pelo_email(self):
        """O endereço aqui NÃO é o `contas.mw5.EMAIL`: aquele já existe no
        banco de teste, semeado pelo `post_migrate`, e criar de novo bateria
        na unicidade do e-mail — que é justamente o que o teste acima prova."""
        Usuario = get_user_model()
        chefe = Usuario.objects.create_superuser(
            email="chefe@teste.com", nome="Chefe", password="x")
        assert chefe.is_superuser and chefe.is_staff

    def test_a_carteira_tem_lado(self):
        """`compradores` é M2M para `self` com `symmetrical=False`.

        Num M2M para `"self"` o Django assume simetria por padrão, e a
        simetria aqui daria ao comprador a carteira do vendedor dele — o
        vendedor passaria a ser "comprador atendido" pelo próprio comprador.
        O caso que prova é este: pôr A na carteira de B NÃO põe B na de A.
        """
        Usuario = get_user_model()
        vendedor = Usuario.objects.create_user(
            email="vend@teste.com", nome="Vend", password="x")
        comprador = Usuario.objects.create_user(
            email="compr@teste.com", nome="Compr", password="x")

        vendedor.compradores.add(comprador)

        assert list(vendedor.compradores.all()) == [comprador]
        assert list(comprador.compradores.all()) == []
        assert list(comprador.vendedores.all()) == [vendedor]

    def test_o_endereco_e_gravado_como_a_pessoa_escreveu(self):
        """`normalize_email` baixa o DOMÍNIO para minúsculas e preserva a
        parte antes do @: o RFC deixa a caixa postal diferenciar maiúscula, e
        reescrever o endereço de alguém é estragar um dado de contato.

        **Isto não é o mesmo que a PORTA ser sensível à caixa** — o caso
        abaixo prova o contrário. O que se grava é o que a pessoa escreveu; o
        que se aceita na entrada é qualquer grafia.
        """
        Usuario = get_user_model()
        pessoa = Usuario.objects.create_user(
            email="Vera.Souza@Premix.COM.BR", nome="Vera", password="x")
        assert pessoa.email == "Vera.Souza@premix.com.br"

    def test_a_porta_nao_olha_a_caixa(self):
        """Cadastrada como `Ana@empresa.com`, a pessoa digita
        `ana@empresa.com` no dia seguinte e entra.

        Sem isto ela recebia "Credenciais inválidas" sem pista nenhuma, e o
        suporte não reproduzia — quem confere copia e cola do cadastro, na
        grafia certa. Quem responde é `GerenteDeUsuario.get_by_natural_key`,
        que é o que o `ModelBackend` chama.
        """
        Usuario = get_user_model()
        pessoa = Usuario.objects.create_user(
            email="Ana@Empresa.com", nome="Ana", password="x")

        for grafia in ("Ana@empresa.com", "ana@empresa.com",
                       "ANA@EMPRESA.COM"):
            assert Usuario.objects.get_by_natural_key(grafia) == pessoa

    def test_o_banco_recusa_o_mesmo_email_em_outra_caixa(self):
        """**A tranca é do BANCO, e é esta linha que prova a diferença.**

        `contas.views_usuarios._login_ocupado` também recusa, e é ela que dá a
        frase amigável — mas ela mora na view, e um `INSERT` por shell, por
        script de carga ou por migração de dados passa por baixo dela. Por
        isso este caso cria as duas linhas por `create_user` direto, sem view
        nenhuma no caminho: o que se está provando é "não é possível", e não
        "a tela recusa".

        Sem a tranca, as duas nasciam — a coluna é única em caixa EXATA, e
        `ana@` e `Ana@` são valores diferentes para o Postgres. Aí
        `get_by_natural_key`, que é insensível, achava as DUAS, e a tela de
        entrada estourava com `MultipleObjectsReturned`: as duas contas
        ficavam inacessíveis, sem nenhuma mensagem que explicasse.

        `IntegrityError` e não `ValidationError`: `create_user` chama `save()`,
        e `save()` não chama `full_clean()` — quem recusa é o Postgres. A
        `violation_error_message` da constraint só aparece para quem passa
        por `full_clean()`, e é o caso de baixo.
        """
        from django.db import IntegrityError, transaction

        Usuario = get_user_model()
        Usuario.objects.create_user(
            email="Ana@Empresa.com", nome="Ana", password="x")

        with pytest.raises(IntegrityError) as erro:
            with transaction.atomic():
                Usuario.objects.create_user(
                    email="ana@empresa.com", nome="Outra", password="x")

        # O NOME da constraint, e não só "deu erro": a coluna também é única
        # em caixa exata (`contas_usuario_email_key`), e sem conferir o nome
        # este caso passaria verde contra a tranca ERRADA — a que não vê
        # `ana@` e `Ana@` como iguais.
        assert "email_unico_sem_caixa" in str(erro.value)

    def test_full_clean_recusa_com_a_frase_da_constraint(self):
        """A outra ponta da mesma tranca: quem valida antes de gravar recebe a
        frase, e não o texto do Postgres. É o que a `violation_error_message`
        existe para dar."""
        from django.core.exceptions import ValidationError

        Usuario = get_user_model()
        Usuario.objects.create_user(
            email="Bento@Empresa.com", nome="Bento", password="x")

        outra = Usuario(email="bento@empresa.com", nome="Outro")
        # Senha definida (ainda que inutilizável) para o `full_clean` não
        # reclamar dela também: o que este caso afirma é a frase da
        # constraint, e um segundo erro no mesmo dicionário deixaria a
        # asserção passar por motivo alheio.
        outra.set_unusable_password()

        with pytest.raises(ValidationError) as erro:
            outra.full_clean()
        assert erro.value.messages == ["Já existe alguém com este e-mail."]

    def test_tem_guid(self):
        Usuario = get_user_model()
        pessoa = Usuario.objects.create_user(
            email="e@f.com", nome="E", password="x")
        assert pessoa.guid is not None
