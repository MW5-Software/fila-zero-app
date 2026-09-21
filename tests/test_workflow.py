"""O CI deste produto roda a suíte e NÃO publica imagem de outro.

Este arquivo substitui o `test_imagem.py` que veio da cópia do KRONOS.net.
Lá ele guardava o workflow que publica em `ghcr.io/mw5-software/kronosnet`;
aqui ele estava EXIGINDO que este produto publicasse na imagem do outro — a
que as sessenta instalações do KRONOS baixam. Um `push` na `main` com o
workflow herdado teria sobrescrito aquela imagem, e o teste teria dado
verde.

Então a varredura foi invertida: o que se prova agora é que nenhum workflow
daqui publica em imagem que não seja deste produto.
"""

from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
WORKFLOWS = RAIZ / ".github" / "workflows"

#: Imagens que NÃO são deste produto. Publicar em qualquer uma delas
#: sobrescreve o que outro sistema entrega.
#: A KRONOS base entra na lista desde que o Fila Zero nasceu dela: o workflow
#: herdado publicava na imagem da base.
DE_OUTROS = ("ghcr.io/mw5-software/kronosnet", "ghcr.io/mw5-software/kronos-base")


def _arquivos():
    return sorted(WORKFLOWS.glob("*.yml")) + sorted(WORKFLOWS.glob("*.yaml"))


def _sem_comentario(arquivo: Path) -> str:
    """O conteúdo do workflow sem as linhas de comentário.

    Existe porque os comentários destes arquivos EXPLICAM as decisões — "em
    Postgres e não em SQLite", "não publica na imagem do KRONOS" —, e uma
    varredura que lesse o arquivo inteiro acusaria justamente o texto que
    documenta a regra que ela protege.
    """
    return "\n".join(
        linha for linha in arquivo.read_text().splitlines()
        if not linha.lstrip().startswith("#")
    )


class TestONossoCiNaoPublicaImagemAlheia:
    def test_nenhum_workflow_menciona_a_imagem_de_outro_produto(self):
        culpados = [
            f"{a.name}: {imagem}"
            for a in _arquivos()
            for imagem in DE_OUTROS
            if imagem in _sem_comentario(a)
        ]
        assert not culpados, (
            "workflow publicando na imagem de outro produto: "
            f"{culpados}. Ver o cabeçalho de `.github/workflows/testes.yml`."
        )

    def test_quem_publica_publica_na_imagem_DESTE_produto(self):
        """A regra mudou de forma quando a condição dela deixou de valer.

        Ela dizia: "enquanto este produto não tiver repositório e nome de
        imagem próprios, publicar é sempre publicar no lugar errado" — e
        recusava qualquer `push: true`. Era uma trava de PERÍODO, não um
        princípio: o produto nasceu como cópia do KRONOS.net e por um tempo
        não tinha para onde publicar.

        Hoje tem (`ghcr.io/mw5-software/fila-zero`, no repositório
        próprio), e `publicar-imagem.yml` publica lá depois de a suíte passar.
        O que continua valendo — e é o que este teste passa a provar — é o
        princípio de baixo: quem publica só publica na imagem DESTE produto.
        A outra metade, "nunca na imagem de outro", segue no teste acima.
        """
        nossa = "ghcr.io/mw5-software/fila-zero"
        culpados = [a.name for a in _arquivos()
                    if "push: true" in _sem_comentario(a)
                    and nossa not in _sem_comentario(a)]
        assert not culpados, (
            f"workflow publicando imagem que não é a deste produto: "
            f"{culpados}")


    def test_so_publica_o_que_veio_de_push_neste_repositorio(self):
        """`workflow_run` com `branches: main` filtra o NOME do branch, e o
        `testes.yml` roda também em `pull_request`. Um PR de fork com um
        branch chamado "main" terminava a suíte "na main" e subia para a GHCR
        e para a homologação com os segredos daqui (auditoria de 21/09/2026).
        A condição do job tem de exigir o `push` e o repositório de origem."""
        texto = _sem_comentario(WORKFLOWS / "publicar-imagem.yml")
        assert "github.event.workflow_run.event == 'push'" in texto
        assert ("github.event.workflow_run.head_repository.full_name"
                " == github.repository") in texto

class TestASuiteRodaNoCi:
    """Sem isto, o CI existe e não prova nada — foi o estado do KRONOS até
    hoje: o workflow construía e publicava sem rodar um teste sequer."""

    def test_existe_um_workflow_que_roda_a_suite(self):
        assert any("pytest" in a.read_text() for a in _arquivos()), (
            "nenhum workflow roda a suíte"
        )

    def test_a_suite_do_ci_roda_em_postgres(self):
        """Provar num banco e entregar noutro é provar a coisa errada."""
        textos = "\n".join(_sem_comentario(a) for a in _arquivos()).lower()
        assert "postgres" in textos
        assert "sqlite" not in textos

    def test_nenhum_workflow_forca_o_settings_da_suite(self):
        """`DJANGO_SETTINGS_MODULE` no ambiente VENCE o `pytest.ini`, e o
        `pytest.ini` aponta para `config.settings_test` de propósito: é ele
        que troca o hasher de senha por um rápido e que carrega
        `tests.app_do_inquilino`.

        Este teste existe porque aconteceu: o workflow veio da cópia com
        `DJANGO_SETTINGS_MODULE: config.settings`, o CI rodou meses contra a
        configuração errada, e só apareceu no dia em que o app de teste
        passou a existir — aí a suíte não coletou. Localmente nunca aparece,
        porque ninguém exporta essa variável para rodar `pytest`.
        """
        for caminho in _arquivos():
            texto = caminho.read_text(encoding="utf-8")
            for numero, linha in enumerate(texto.splitlines(), 1):
                if linha.lstrip().startswith("#"):
                    continue
                assert "DJANGO_SETTINGS_MODULE" not in linha, (
                    f"{caminho.name}:{numero} declara DJANGO_SETTINGS_MODULE "
                    f"— a variável de ambiente vence o pytest.ini e faz a "
                    f"suíte rodar contra config.settings em vez de "
                    f"config.settings_test")

    def test_os_workflows_parseiam_como_yaml(self):
        yaml = pytest.importorskip("yaml")
        for arquivo in _arquivos():
            yaml.safe_load(arquivo.read_text())
