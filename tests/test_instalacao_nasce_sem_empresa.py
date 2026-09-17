"""Uma instalação nova sobe com ZERO empresas, e isso é a verdade dela.

**Este arquivo substitui `tests/test_semeadura_empresa_filial.py`**, apagado
em 09/09/2026. O que aquele provava — que o `post_migrate` criava uma
`Empresa` e a filial "Matriz" em toda instalação, e que rodar de novo nunca
mexia no que já existia — deixou de ser verdade, e a regra que caiu vale ser
registrada.

A semeadura fazia sentido enquanto a instalação era de UM cliente e a empresa
era dado dela, como a marca: a tela de Empresa precisava de uma linha para
editar desde o primeiro `migrate`.

O que aquele `post_migrate` criava era uma empresa SEM DONO — ninguém a abre, ela fica na lista da MW5 sem nada
explicando o que falta nela, e é exatamente o estado cujo caminho de criação
foi fechado quando "Nova empresa" saiu da tela de Empresas.

Hoje a primeira empresa aparece quando a MW5 cadastra o primeiro TITULAR, e
nasce com dono. A instalação nova não está manca: ela ainda não vendeu conta
nenhuma, e mostrar zero é dizer isso.
"""

import pytest


@pytest.mark.django_db
class TestNadaESemeado:
    def test_a_instalacao_sobe_sem_empresa(self):
        """O `post_migrate` roda na criação do banco de teste, então esta
        asserção mede o estado real de uma instalação recém-migrada."""
        from plataforma.models import Empresa

        assert not Empresa.objects.exists()

    def test_a_instalacao_sobe_sem_filial(self):
        """A Matriz ia junto e não podia ficar: ela nascia pendurada na
        empresa semeada (`empresas.first()`), e sem a empresa criaria uma
        filial órfã."""
        from plataforma.models import Filial

        assert not Filial.objects.exists()

    def test_as_funcoes_de_semear_nao_existem_mais(self):
        """Deixá-las no módulo sem ninguém chamar seria um gatilho carregado:
        a próxima pessoa que precisar de uma empresa de partida acha
        `garantir_empresa`, chama, e o defeito volta sem discussão."""
        import plataforma.empresa as modulo

        assert not hasattr(modulo, "garantir_empresa")
        assert not hasattr(modulo, "garantir_matriz")


@pytest.mark.django_db
class TestATelaContinuaAlcancavel:
    """**O módulo continua nascendo LIGADO**, e o motivo se inverteu.

    Ele era ligado porque "a empresa já vem semeada, então a tela precisa
    existir para editá-la". Agora é o contrário e é mais forte: a instalação
    sobe com zero empresas, e é a MW5 quem precisa da tela desde o primeiro
    dia para ver as contas que ela criar.
    """

    def test_o_modulo_empresa_nasce_ligado(self):
        from plataforma.catalogo import semear
        from plataforma.models import Modulo

        semear()
        assert Modulo.objects.get(chave="empresa").ativo

    def test_o_modulo_filiais_continua_desligado(self):
        """Ele nasceu ligado enquanto a Matriz era semeada — sem filial
        nenhuma, uma tela de filiais no menu de toda instalação é um item que
        ninguém usa."""
        from plataforma.catalogo import semear
        from plataforma.models import Modulo

        semear()
        assert not Modulo.objects.get(chave="filiais").ativo
