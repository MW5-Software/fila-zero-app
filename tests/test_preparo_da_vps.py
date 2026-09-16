"""O repositório preparado para a VPS MW5 (guia "preparar-repositorio" da VPS,
consultado em 15/09/2026).

A VPS roda a IMAGEM, sem código-fonte, e cada exigência do guia tem um motivo
que só aparece em produção: imagem como root transforma um furo da aplicação
em root no container; `latest` não diz o que está rodando nem deixa voltar;
um `.dockerignore` frouxo leva a mídia e os backups da máquina de quem
construiu para dentro da imagem publicada. Estes testes leem os arquivos, e
não os comentários sobre eles.
"""

from pathlib import Path

import json

RAIZ = Path(__file__).resolve().parent.parent
PUBLICAR = RAIZ / ".github" / "workflows" / "publicar-imagem.yml"


def _instrucoes(caminho: Path) -> "list[str]":
    """As linhas do arquivo que não são comentário nem vazias."""
    return [linha.strip() for linha in caminho.read_text(encoding="utf-8").splitlines()
            if linha.strip() and not linha.lstrip().startswith("#")]


class TestAImagem:
    def test_roda_como_usuario_sem_privilegio(self):
        """O último `USER` do Dockerfile não é root, e vem antes do `CMD`."""
        linhas = _instrucoes(RAIZ / "Dockerfile")
        usuarios = [i for i, l in enumerate(linhas) if l.startswith("USER ")]
        assert usuarios, "Dockerfile sem USER: a aplicação roda como root"
        ultimo = linhas[usuarios[-1]].split()[1]
        assert ultimo not in ("root", "0", "0:0")
        comando = max(i for i, l in enumerate(linhas) if l.startswith("CMD"))
        assert usuarios[-1] < comando

    def test_o_socket_do_gunicorn_fica_fora_da_pasta_do_codigo(self):
        """Sem root, `/app` não é gravável: o socket de controle do gunicorn
        26 dava "Permission denied" em todo boot. Pela variável, que vale
        mesmo com o comando trocado pelo compose da VPS."""
        linhas = _instrucoes(RAIZ / "Dockerfile")
        assert 'ENV GUNICORN_CMD_ARGS="--control-socket /tmp/gunicorn.ctl"' in linhas

    def test_escuta_na_8000_e_grava_a_versao(self):
        linhas = _instrucoes(RAIZ / "Dockerfile")
        assert "EXPOSE 8000" in linhas
        assert any(l.startswith("ARG GIT_SHA") for l in linhas)
        assert any("/app/VERSAO" in l for l in linhas)

    def test_o_dockerignore_deixa_de_fora_o_que_e_da_maquina(self):
        """Mídia, backups e qualquer `.env` são dado ou segredo de quem
        construiu, e dentro da imagem iriam para o registry."""
        ignorados = set(_instrucoes(RAIZ / ".dockerignore"))
        for padrao in (".git/", ".env*", "midia/", "backups/"):
            assert padrao in ignorados, padrao


class TestOCi:
    def test_publica_so_pelo_commit(self):
        """Nunca `latest`: a VPS implanta um commit, e voltar versão é pedir o
        commit anterior."""
        texto = "\n".join(_instrucoes(PUBLICAR))
        assert ":latest" not in texto
        assert "ghcr.io/mw5-software/fila-zero:${{ github.event.workflow_run.head_sha }}" in texto

    def test_implanta_em_homologacao_o_commit_testado(self):
        """O commit implantado é o que a suíte testou (`head_sha` do
        `workflow_run`), e não o `github.sha`, que neste gatilho é a ponta da
        `main` na hora em que o workflow começou.

        O `head_sha` pode chegar ao `deploy` direto ou por uma variável do
        job; o que se cobra é que ele seja a origem e que o `github.sha` não
        apareça em lugar nenhum."""
        texto = "\n".join(_instrucoes(PUBLICAR))
        assert "deploy " in texto, "o CI não chama o `deploy` da VPS"
        assert "github.event.workflow_run.head_sha" in texto
        assert "github.sha" not in texto

    def test_producao_nao_entra_no_ci(self):
        """Produção só recebe por promoção do que foi aprovado em
        homologação; a chave do CI nem alcança produção."""
        texto = "\n".join(_instrucoes(PUBLICAR)).lower()
        assert "producao" not in texto and "produção" not in texto
        assert "promover" not in texto


def test_o_claude_code_do_projeto_conhece_a_vps():
    dados = json.loads((RAIZ / ".claude" / "settings.json").read_text(encoding="utf-8"))
    assert dados["enabledPlugins"]["mw5@mw5"] is True
    assert (dados["extraKnownMarketplaces"]["mw5"]["source"]
            == {"source": "github", "repo": "MW5-Software/claude-mw5"})
