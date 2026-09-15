"""A marca sai do arquivo e vai para o banco.

Arquivo se troca com implantação; banco se troca por tela. Mudar uma frase da
tela de login não pode exigir publicar versão nova em vinte instalações.
"""

import pytest
from django.core.exceptions import ValidationError

from nucleo.theme import Brand


@pytest.mark.django_db
class TestAMarcaDaInstalacao:
    def test_sem_linha_no_banco_vem_o_padrao_da_mw5(self):
        from plataforma.marca import marca_da_instalacao

        marca = marca_da_instalacao()
        assert isinstance(marca, Brand)
        # O nome DESTE produto. Veio "KRONOS.net" na cópia e ficou apontando
        # para o produto de onde este saiu — ver `plataforma/marca.py`.
        assert marca.client_name == "Fila Zero"

    def test_a_linha_do_banco_vence_o_padrao(self):
        from plataforma.marca import marca_da_instalacao
        from plataforma.models import Marca

        Marca.objects.create(client_name="Sementes Premix", primary="#276b2e")
        marca = marca_da_instalacao()
        assert marca.client_name == "Sementes Premix"
        assert marca.primary == "#276b2e"

    def test_a_cor_primaria_deriva_a_paleta(self):
        """A tabela guarda uma cor; as outras trinta saem dela."""
        from plataforma.models import Marca

        tokens = Marca(client_name="X", primary="#276b2e").para_brand().tokens("light")
        assert tokens["primary"] == "#276b2e"
        assert "surface" in tokens and "on-surface" in tokens

    def test_cor_invalida_e_recusada_na_montagem(self):
        """`Brand` já valida cor. A tabela não reimplementa isso."""
        from plataforma.models import Marca

        with pytest.raises(ValueError):
            Marca(client_name="X", primary="nao-e-cor").para_brand()

    def test_as_cores_de_area_chegam_ao_brand(self):
        from plataforma.models import Marca

        marca = Marca(client_name="X", sidebar_bg="#276b2e",
                      sidebar_text="#ffffff").para_brand()
        assert marca.areas.sidebar_bg == "#276b2e"

    def test_campo_vazio_nao_vira_cor_vazia(self):
        """Campo em branco herda do tema; não vira `''` num token.

        O padrão de `AreaColors` é `None` (verificado no código), e é o `None`
        que faz o token cair no valor derivado da paleta. Passar `""` produziria
        `--header-bg:;` no CSS — borda que some, texto invisível.

        O exemplo era o menu, que hoje NASCE com a cor do logo (ver
        `test_logo_do_produto.py`); trocado por um campo que continua em
        branco por padrão. A regra é a mesma, e o caso do menu esvaziado à
        mão está logo abaixo.
        """
        from plataforma.models import Marca

        marca = Marca(client_name="X").para_brand()
        assert marca.areas.header_bg is None
        tokens = marca.tokens("light")
        assert all(v for v in tokens.values()), "algum token saiu vazio"

    def test_o_menu_esvaziado_a_mao_tambem_herda(self):
        """Quem apaga o campo do menu está pedindo para herdar do tema — e
        recebe `None`, não `''`. O padrão da coluna ser preenchido não pode
        criar um caminho onde o vazio escapa da regra acima."""
        from plataforma.models import Marca

        marca = Marca(client_name="X", sidebar_bg="", sidebar_text="").para_brand()
        assert marca.areas.sidebar_bg is None
        assert marca.areas.sidebar_text is None
        assert all(v for v in marca.tokens("light").values())

    def test_o_default_da_coluna_acompanha_o_do_framework(self):
        """Se o padrão do `Brand` mudar, a coluna acompanha — em vez de
        divergir em silêncio. Este teste é a razão de o default ser derivado
        e não escrito à mão."""
        from nucleo.theme import Brand
        from plataforma.models import Marca

        campo = Marca._meta.get_field("primary")
        assert campo.default == Brand.__dataclass_fields__["primary"].default

    def test_gravar_cor_invalida_e_recusado(self):
        """A porta que a tela não cobre: shell, migração, script.

        `ValidationError`, não `ValueError`: `save()` chama `full_clean()`
        (mudança desta correção), que é o idioma que um `ModelForm` sabe
        transformar em erro de campo em vez de 500 — ver `Marca.clean()`."""
        from plataforma.models import Marca

        with pytest.raises(ValidationError):
            Marca.objects.create(client_name="X", primary="nao-e-cor")
        assert Marca.objects.count() == 0

    def test_gravar_contraste_ruim_nao_e_recusado_aqui(self):
        """`save()` guarda o que quebra a renderização — cor que não vira
        `Brand`. Legibilidade é julgamento de tela, e fica na Aparência: uma
        marca legítima importada de outro cliente não pode ser impedida de
        existir por causa de contraste."""
        from plataforma.models import Marca

        Marca.objects.create(client_name="X", primary="#1e40af",
                             sidebar_bg="#fffde7", sidebar_text="#ffffff")
        assert Marca.objects.count() == 1


@pytest.mark.django_db
def test_a_folha_de_tema_usa_a_marca_do_banco(client):
    from plataforma.models import Marca

    Marca.objects.create(client_name="Sementes Premix", primary="#276b2e")
    css = client.get("/tema.css").content.decode()
    assert "#276b2e" in css or "276b2e" in css


@pytest.mark.django_db
class TestOsRotulosDoContexto:
    """Item 7 do Bloco 3: o cliente chama filial de "loja", empresa de
    "bandeira" — o seletor do cabeçalho já lê `Brand.header.context_labels`,
    e o que faltava era onde o cliente ESCREVE isso. Campo em branco herda
    o padrão da casa, como toda área de cor da marca."""

    def test_os_rotulos_gravados_chegam_a_marca_da_instalacao(self, db):
        from plataforma.marca import marca_da_instalacao
        from plataforma.models import Marca

        Marca.objects.create(client_name="Rede X",
                             rotulo_da_empresa="Bandeira",
                             rotulo_da_filial="Loja")
        assert marca_da_instalacao().header.context_labels == \
            ("Bandeira", "Loja")

    def test_em_branco_vale_o_padrao_da_casa(self, db):
        from plataforma.marca import marca_da_instalacao

        assert marca_da_instalacao().header.context_labels == \
            ("Empresa", "Filial")

    def test_so_um_preenchido_o_outro_cai_no_padrao(self, db):
        """A rede que só troca "Filial" por "Loja" não é obrigada a
        redigir "Empresa" também."""
        from plataforma.marca import marca_da_instalacao
        from plataforma.models import Marca

        Marca.objects.create(client_name="Rede X", rotulo_da_filial="Loja")
        assert marca_da_instalacao().header.context_labels == \
            ("Empresa", "Loja")
