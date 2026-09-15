"""O compose que roda no cliente — o que ele tem de fazer, e o que não pode.

Existe porque um defeito passou por aqui sem nenhum teste vermelho: o compose
de DESENVOLVIMENTO migrava o banco na subida, o do CLIENTE não, e a diferença
não estava escrita em lugar nenhum. `deploy/atualizar.sh` faz `pull` e
`up -d`; o `CMD` da imagem é só o gunicorn. Uma versão nova com migração subia
contra o banco velho, e a instalação quebrava na primeira tela que tocasse a
coluna nova — em todas as instalações ao mesmo tempo.

O README já afirmava, na letra, que a `app` roda `migrate` na subida. Este
arquivo é o que faz a afirmação continuar verdadeira.

**Lê o YAML, não o texto.** A primeira versão destes testes procurava a
palavra `migrate` no arquivo inteiro — e passava verde com o `command`
apagado, porque a palavra estava no comentário que explica o `command`. Um
teste que se satisfaz com o comentário sobre a regra, em vez da regra, é pior
que teste nenhum: dá o verde no dia em que a regra sai.
"""

from pathlib import Path

import pytest
import yaml

RAIZ = Path(__file__).resolve().parent.parent
VPS = RAIZ / "deploy" / "docker-compose.vps.yml"
LOCAL = RAIZ / "docker-compose.yml"


def _servico_app(caminho: Path) -> dict:
    dados = yaml.safe_load(caminho.read_text(encoding="utf-8"))
    return dados["services"]["app"]


def _subida(caminho: Path) -> str:
    """O que o container roda ao subir, como texto. Vazio se não houver
    `command` — e é justamente o caso que este arquivo existe para impedir."""
    return str(_servico_app(caminho).get("command", ""))


@pytest.fixture
def subida() -> str:
    return _subida(VPS)


def test_o_compose_do_cliente_existe():
    assert VPS.is_file(), VPS


def test_migra_o_banco_antes_de_servir(subida):
    """A ordem importa e é a metade que se erra.

    `gunicorn && migrate` serviria requisição contra o esquema velho por
    alguns segundos — tempo curto, dado errado igual. `migrate && gunicorn`
    é a única ordem em que o processo que atende já encontra o banco pronto.
    """
    assert "migrate" in subida, (
        "o compose do cliente não migra o banco na subida: uma versão com "
        f"migração sobe contra o esquema velho. command={subida!r}")
    assert "gunicorn" in subida, subida
    assert subida.index("migrate") < subida.index("gunicorn"), subida


def test_a_migracao_nao_pergunta_nada(subida):
    """Não há ninguém no terminal para responder. Sem `--noinput` a subida
    trava esperando uma tecla que nunca vem, e o container fica de pé sem
    servir — pior que cair, porque o `restart` não resolve e nada avisa."""
    assert "--noinput" in subida


def test_a_falha_da_migracao_impede_o_gunicorn(subida):
    """`&&`, nunca `;` nem `||`.

    Subir com o esquema errado é pior do que não subir: o segundo é um erro
    visível em `docker ps`, o primeiro é dado gravado torto durante horas.
    """
    entre = subida[subida.index("migrate"):subida.index("gunicorn")]
    assert "&&" in entre, subida
    assert ";" not in entre and "||" not in entre, subida


def test_o_cliente_nunca_compila_a_imagem():
    """A decisão B da spec do painel: uma imagem construída, N instalações
    rodando os MESMOS bytes. Uma chave `build:` aqui faria cada VPS compilar
    o seu, e "roda na minha máquina" voltaria a valer por instalação."""
    app = _servico_app(VPS)
    assert "build" not in app, app
    assert str(app.get("image", "")).startswith("ghcr.io/"), app


def test_os_dois_composes_sobem_do_mesmo_jeito():
    """O de desenvolvimento e o do cliente têm de fazer a MESMA coisa na
    subida. Foi a divergência entre os dois — invisível, porque ninguém abre
    os dois arquivos lado a lado — que produziu o defeito original."""
    for rotulo, caminho in (("desenvolvimento", LOCAL), ("cliente", VPS)):
        comando = _subida(caminho)
        assert "migrate --noinput" in comando, (rotulo, comando)
        assert comando.index("migrate") < comando.index("gunicorn"), rotulo
