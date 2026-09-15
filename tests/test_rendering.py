"""A base do componente e a ponte com o Django.

O que importa aqui é que a árvore de componentes renderiza sozinha (um filho
que é componente vira HTML sem ninguém pedir) e que o HTML sai escapado por
padrão — um rótulo com `<script>` dentro não pode virar script na tela.
"""

from dataclasses import dataclass
from typing import ClassVar

import pytest
from markupsafe import Markup

from nucleo.rendering import (
    Component,
    create_environment,
    html_attrs,
    render_all,
    use_environment,
)
from nucleo.resposta import render


@dataclass
class Caixa(Component):
    template: ClassVar[str] = ""
    conteudo: object = ""

    def render(self, env=None) -> Markup:
        return Markup(f"<div>{render_all(self.conteudo)}</div>")


def test_componente_dentro_de_componente_renderiza_sozinho():
    fora = Caixa(conteudo=Caixa(conteudo="oi"))
    assert str(fora.render()) == "<div><div>oi</div></div>"


def test_lista_de_filhos_vira_html_concatenado():
    assert str(render_all([Caixa(conteudo="a"), Caixa(conteudo="b")])) == (
        "<div>a</div><div>b</div>"
    )


def test_texto_cru_sai_escapado():
    assert str(render_all("<script>x</script>")) == (
        "&lt;script&gt;x&lt;/script&gt;"
    )


def test_none_e_false_nao_desenham_nada():
    assert str(render_all(None)) == ""
    assert str(render_all(False)) == ""


def test_atributos_html_escapam_valor_e_trocam_underscore_por_traco():
    saida = str(html_attrs({"hx_get": "/a?b=1&c=2", "data_x": True, "y": None}))
    assert 'hx-get="/a?b=1&amp;c=2"' in saida
    assert "data-x" in saida
    assert "y" not in saida


def test_componente_sem_template_declarado_recusa_renderizar():
    @dataclass
    class SemTemplate(Component):
        pass

    with pytest.raises(NotImplementedError):
        SemTemplate().render()


def test_o_ambiente_acha_os_templates_do_pacote():
    # O template concreto (components/button.html) só chega na Task 6; aqui a
    # promessa da Task 2 é o ambiente em si: ele constrói, aponta para o
    # pacote `nucleo` e já vem com os globais e filtros do design system.
    env = create_environment()
    with use_environment(env):
        loader = env.loader.loaders[-1]
        assert loader.package_name == "nucleo"
        assert loader.package_path == "templates"
        assert "icon" in env.globals
        assert "estatico" in env.globals
        assert env.filters["render"] is render_all
        assert env.filters["attrs"] is html_attrs


def test_render_devolve_resposta_do_django_com_html_dentro():
    resposta = render(Caixa(conteudo="pronto"))
    assert resposta.status_code == 200
    assert resposta["Content-Type"].startswith("text/html")
    assert resposta.content.decode() == "<div>pronto</div>"
