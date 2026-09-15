"""Campos de formulário.

Cada controle já desenha o próprio invólucro (rótulo, marca de obrigatório,
texto de ajuda, mensagem de erro) e sabe quantas das 12 colunas ocupa. É
deliberado: nos mocks, todo campo aparece nessa mesma estrutura, e deixar que
cada tela a remonte à mão é justamente como formulários começam a divergir um do
outro. Quem escreve a tela declara o campo; o alinhamento vem junto.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar, Sequence

from ..rendering import Component, Renderable

__all__ = [
    "Checkbox",
    "FormGrid",
    "InputGroup",
    "Option",
    "Select",
    "SearchInput",
    "TextInput",
    "Textarea",
]


@dataclass
class _Control(Component):
    """O que todo campo tem em comum."""

    name: str = ""
    label: str = ""
    value: Any = ""
    span: int = 12
    required: bool = False
    disabled: bool = False
    readonly: bool = False
    help: str | None = None
    error: str | None = None
    placeholder: str = ""
    #: Força este campo a começar uma fileira nova da grade.
    #:
    #: A largura sozinha não responde "ao lado ou embaixo": dois campos de meia
    #: largura SEMPRE emparelham, e não havia como pôr o segundo embaixo do
    #: primeiro sem alargar um dos dois. Este é o controle que faltava — "quero
    #: meia largura, e quero numa linha nova".
    quebra_linha: bool = False
    attrs: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not 1 <= self.span <= 12:
            raise ValueError(f"span deve ficar entre 1 e 12, veio {self.span}")

    @property
    def field_classes(self) -> str:
        parts = ["f", f"c{self.span}"]
        if self.quebra_linha:
            parts.append("quebra")
        if self.error:
            parts.append("invalid")
        return " ".join(parts)

    @property
    def described_by(self) -> str | None:
        if self.error:
            return f"{self.name}-error"
        if self.help:
            return f"{self.name}-help"
        return None


@dataclass
class TextInput(_Control):
    """Campo de texto. `type` cobre email, tel, password, number e afins."""

    template: ClassVar[str] = "components/text_input.html"

    type: str = "text"
    maxlength: int | None = None
    autocomplete: str | None = None
    #: Ícone à esquerda, pelo nome do catálogo — nunca um caminho de arquivo.
    icon: str = ""
    #: Unidade à direita: `kg`, `%`, `R$`. Curta e fixa; quem preenche não a
    #: escolhe, ela é do campo.
    suffix: str = ""

    @property
    def com_adorno(self) -> bool:
        return bool(self.icon or self.suffix)


@dataclass
class Option:
    value: str
    label: str
    disabled: bool = False


@dataclass
class Select(_Control):
    template: ClassVar[str] = "components/select.html"

    options: Sequence[Option] = ()
    empty_label: str | None = None  # primeira opção neutra, tipo "Selecione…"

    def __post_init__(self) -> None:
        super().__post_init__()
        self.options = [
            opt if isinstance(opt, Option) else Option(str(opt[0]), str(opt[1]))
            for opt in self.options
        ]

    def is_selected(self, option: Option) -> bool:
        return str(self.value) == str(option.value)


@dataclass
class Textarea(_Control):
    template: ClassVar[str] = "components/textarea.html"

    rows: int | None = None


@dataclass
class Checkbox(_Control):
    template: ClassVar[str] = "components/checkbox.html"

    checked: bool = False


@dataclass
class SearchInput(_Control):
    """Campo de busca com a lupa por dentro, como na barra de filtros."""

    template: ClassVar[str] = "components/search_input.html"


@dataclass
class FileInput(_Control):
    """Seleção de arquivo.

    O `<input type="file">` nativo não aceita a estilização dos outros campos:
    o botão embutido tem altura própria e o nome do arquivo é cortado por
    dentro. Aqui ele continua no HTML — é ele que envia o arquivo e responde ao
    teclado — mas fica invisível, com um rótulo por cima fazendo o papel de
    gatilho. O nome escolhido aparece ao lado, e imagem ganha miniatura, porque
    conferir o logo enviado sem vê-lo é pedir para errar.
    """

    template: ClassVar[str] = "components/file_input.html"

    accept: str = ""
    button_label: str = "Escolher arquivo"
    empty_label: str = "Nenhum arquivo escolhido"
    preview: bool = True
    #: O que JÁ está guardado, quando há. Um `<input type="file">` volta sempre
    #: vazio — o navegador nunca repõe arquivo —, e sem isto reabrir uma tela
    #: mostrava "Nenhum arquivo escolhido" ao lado de uma imagem que o sistema
    #: tem guardada: a pessoa escolhe de novo, ou pior, acha que perdeu.
    #:
    #: `current_url` desenha a miniatura; `current_label` é o texto ao lado.
    #: Escolher outro arquivo troca os dois (ver `mw5.js`), e limpar o campo
    #: volta ao `empty_label` — a partir daí não há mais o que restaurar.
    current_url: str = ""
    current_label: str = ""


@dataclass
class InputGroup(_Control):
    """Campo colado a um botão — o CEP com a lupa dos mocks."""

    template: ClassVar[str] = "components/input_group.html"

    button_icon: str = "search"
    button_title: str = "Buscar"
    button_attrs: dict[str, Any] = field(default_factory=dict)


@dataclass
class FormGrid(Component):
    """A grade de 12 colunas que organiza os campos."""

    template: ClassVar[str] = "components/form_grid.html"

    children: Renderable = ""
    #: Escotilha de atributos crus na grade. A prévia do construtor a usa para
    #: carimbar o `data-mw5-caminho` da linha: sem ele, só as CÉLULAS tinham
    #: endereço, e a linha era o único contêiner que não dava para escolher —
    #: nem mover, nem apagar.
    attrs: dict[str, Any] = field(default_factory=dict)


@dataclass
class Form(Component):
    """O `<form>` que envolve uma tela de cadastro.

    Precisa existir como componente porque a barra de ações fixa fica fora do
    fluxo visual mas dentro do formulário: sem envolver a página inteira, o
    botão "Salvar" no rodapé não teria os campos para enviar. O `enctype` vira
    multipart sozinho quando há upload, que é o erro mais comum de esquecer.
    """

    template: ClassVar[str] = "components/form.html"

    children: Renderable = ""
    action: str = ""
    method: str = "post"
    multipart: bool = False
    attrs: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.method.lower() not in ("get", "post"):
            raise ValueError("formulário HTML só aceita get ou post")

    @property
    def enctype(self) -> str | None:
        return "multipart/form-data" if self.multipart else None
