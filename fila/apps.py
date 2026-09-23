from django.apps import AppConfig


class FilaConfig(AppConfig):
    """A fila da vez das lojas — o produto do Fila Zero.

    O registro do módulo roda em `ready()`, e não na importação de `modulo.py`,
    pelo motivo escrito em `modulos/exemplo/apps.py`: registrar no corpo do
    arquivo faria o registro depender da ordem de import entre os apps.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "fila"
    verbose_name = "Fila da vez"

    def ready(self) -> None:
        from comum.auditoria import declarar_acoes
        from contas.entrada import destino_depois_de_entrar
        from plataforma.caixas_da_empresa import CaixaDaEmpresa
        from plataforma.caixas_da_empresa import registrar as registrar_caixa
        from plataforma.caixas_da_filial import CaixaDaFilial
        from plataforma.caixas_da_filial import registrar as registrar_caixa_da_loja
        from plataforma.declaracao import registrar
        from plataforma.filiais import antes_de_desativar
        from plataforma.parametro_declaracao import registrar as registrar_parametro

        from .auditoria import ACOES_DA_FILA, ROTULOS_DA_FILA
        from .fluxo import caixa, gravar_do_post
        from .modulo import MODULO
        from .parametro import PARAMETRO_META_PARA_GESTOR
        from .sinais import destino_do_vendedor, recusar_desativar_loja_com_gente

        registrar(MODULO)
        # As ações da fila na trilha: declaradas aqui, e não na base, que não
        # conhece os módulos de negócio (`fila/auditoria.py`).
        declarar_acoes(ACOES_DA_FILA, ROTULOS_DA_FILA)
        # A caixa "Fila da vez" na tela de Empresas: o fluxo mora na tabela da
        # fila (`fila.FluxoDaEmpresa`), e não numa coluna da empresa.
        registrar_caixa(CaixaDaEmpresa(chave="fila_fluxo", desenhar=caixa,
                                       gravar=gravar_do_post))
        # A caixa "Fim do turno" na tela de Filiais: o turno mora na tabela da
        # fila (`fila.TurnoDaLoja`), e não numa coluna da filial.
        from .turno import caixa as caixa_do_turno
        from .turno import gravar_do_post as gravar_o_turno

        registrar_caixa_da_loja(CaixaDaFilial(chave="fila_turno",
                                              desenhar=caixa_do_turno,
                                              gravar=gravar_o_turno))
        # O parâmetro entra pelo mesmo caminho do módulo, e pelo mesmo motivo:
        # declarar no corpo de `parametro.py` faria o registro depender da
        # ordem de import entre os apps. Ele NÃO semeia linha nenhuma — o
        # banco só ganha linha quando uma instalação muda o valor
        # (`plataforma.models.Parametro`).
        registrar_parametro(PARAMETRO_META_PARA_GESTOR)
        # `dispatch_uid`: o `ready()` pode rodar mais de uma vez nos testes, e
        # o receptor ligado duas vezes responderia duas vezes.
        antes_de_desativar.connect(recusar_desativar_loja_com_gente,
                                   dispatch_uid="fila_loja_com_gente")
        destino_depois_de_entrar.connect(destino_do_vendedor,
                                         dispatch_uid="fila_destino_do_vendedor")
