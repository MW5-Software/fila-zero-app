from django.apps import AppConfig
from django.db.models.signals import post_migrate


def _semear_apos_migrar(sender, **kwargs):
    """Semeia os módulos declarados depois de cada `migrate`.

    Não é migração de dados de propósito. Uma migração roda uma vez e semeia
    o que estava declarado naquele dia — módulo criado depois nunca ganharia
    linha nas instalações que já a aplicaram, e ligar pela tela atualizaria
    zero linhas, sem erro. A promessa da matriz é "módulo novo aparece
    sozinho nas vinte bases", e só um gancho que roda a cada `migrate`
    entrega isso.

    É o mesmo mecanismo que o Django usa para `Permission` e `ContentType`,
    pelo mesmo motivo — ver `django.contrib.auth.apps` e
    `django.contrib.contenttypes.apps`.
    """
    from .catalogo import semear

    apps = kwargs.get("apps")
    using = kwargs.get("using")
    semear(apps, using=using)

    # Depois de semear, nunca antes: a permissão de um módulo só faz sentido
    # quando o módulo já existe no catálogo. Import tardio, dentro da função,
    # porque `contas` no topo deste arquivo criaria dependência de ordem de
    # carga entre os dois apps — `plataforma` é importado antes de `contas`
    # estar pronto. O próximo passo deste receptor (os cargos de fábrica)
    # entra depois deste, pelo mesmo motivo: pressupõe o catálogo de
    # permissões já materializado. O usuário da MW5, mais adiante, não pressupõe nada
    # disso — ver o comentário dele.
    from contas.permissoes import materializar

    materializar(apps, using=using)

    # Depois de materializar, nunca antes: os cargos de fábrica nascem com
    # `Permission` de módulo, e elas só existem depois de `materializar`. É por
    # isso que isto é `post_migrate` e não migração de dados — ver
    # `contas/cargos_de_fabrica.py`. Import tardio pelo mesmo motivo dos de cima.
    from contas.cargos_de_fabrica import garantir_cargos_de_fabrica

    garantir_cargos_de_fabrica(apps, using=using)

    # Depois dos dois de cima, mas sem depender de nenhum: o usuário da MW5
    # nasce superusuário, e superusuário passa em qualquer verificação de
    # permissão sem precisar ler `Cargo` nem `Permission`
    # (`nucleo.permissoes.pode`). Entra por último porque é o passo que este
    # plano acrescenta agora, não porque o dado exija essa posição — ficar
    # depois dos três já prontos evita reabrir uma ordem que já estava
    # correta. Import tardio pelo mesmo motivo dos de cima.
    from contas.mw5 import garantir_usuario_mw5

    garantir_usuario_mw5(apps, using=using)

    # **A empresa e a Matriz NÃO são mais semeadas** (09/09/2026).
    #
    # Elas nasciam em todo `migrate` porque a instalação era de UM cliente e
    # a empresa era dado da instalação, como a marca. Com uma conta por
    # empresa isso virou o contrário do que se quer: o que o `post_migrate`
    # criava era uma empresa SEM DONO — ninguém a abre, ela fica na lista da
    # MW5 sem nada explicando o que falta nela, e é exatamente o estado cujo
    # caminho de criação foi fechado quando "Nova empresa" saiu da tela.
    #
    # Hoje a primeira empresa de uma instalação aparece quando a MW5 cadastra
    # o primeiro TITULAR, e nasce com dono. Uma instalação nova sobe com zero
    # empresas, que é a verdade: ela ainda não vendeu conta nenhuma.
    #
    # A Matriz ia junto e não podia ficar: ela nascia pendurada na empresa
    # semeada (`empresas.first()`), e sem a empresa criaria uma filial órfã.


def _criar_a_matriz(sender, instance, created, **kwargs):
    """A empresa nova nasce com a filial Matriz (spec 2026-09-14, D7).

    No `post_save` e não na tela: empresa nasce por mais de um caminho (a tela
    do titular, o shell, a restauração de um backup, um teste), e cada caminho
    que lembrasse seria um que um dia esquece — e empresa sem filial não tem
    onde alocar ninguém.

    **Esta semeadura já existiu e saiu** em 09/09/2026: ela rodava no
    `post_migrate` e criava uma Matriz pendurada numa empresa sem dono. Aqui ela
    nasce presa à empresa que acabou de ser criada, e só no `created`.

    `raw`: protege um eventual `loaddata` de fixture, que gravaria a Matriz
    que já vem no arquivo — criar outra aqui bateria na
    `uma_matriz_por_empresa`. A restauração de verdade
    (`plataforma/management/commands/restaurar.py`) não passa por aqui: ela é
    `pg_restore`, que grava direto no banco e não dispara sinal nenhum do
    Django. `loaddata` não é usado neste projeto — a checagem é só a mesma
    cautela que o Django já recomenda para qualquer receptor de `post_save`.
    """
    if not created or kwargs.get("raw"):
        return
    from .models import Filial

    Filial.objects.create(empresa=instance, nome="Matriz", apelido="Matriz",
                          e_matriz=True)


class PlataformaConfig(AppConfig):
    """A identidade desta instalação: a marca e quais módulos estão ligados.

    É a parte "controlado por banco de dados" da spec: o código diz quais
    módulos existem, e as linhas daqui dizem quais estão ligados para este
    cliente.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "plataforma"

    def ready(self) -> None:
        # A declaração roda em `ready()`, não na importação de `modulo.py` —
        # mesmo motivo de `contas.apps.ContasConfig.ready()`: registrar no
        # corpo do módulo dependeria da ordem de import entre os apps.
        from .declaracao import registrar
        from .modulo import (
            MODULO_APARENCIA, MODULO_EMPRESA, MODULO_FALHAS, MODULO_FILIAIS,
            MODULO_MODULOS, MODULO_PARAMETROS,
        )

        registrar(MODULO_EMPRESA)
        registrar(MODULO_FILIAIS)
        registrar(MODULO_PARAMETROS)
        # As três da MW5 entram pelo mesmo caminho das outras — é isso que
        # tira o bloco à parte do `menu.py` e devolve a base a um grupo só.
        registrar(MODULO_APARENCIA)
        registrar(MODULO_MODULOS)
        registrar(MODULO_FALHAS)

        # Mesmo raciocínio, para o catálogo de PARÂMETROS: a declaração roda
        # aqui, nunca na importação de `parametro.py` — e nunca semeia linha
        # nenhuma (ver o docstring de `plataforma.models.Parametro`), então
        # não há passo equivalente a `semear()` para conectar no
        # `post_migrate` abaixo.
        from .parametro import (
            PARAMETRO_ITENS_POR_PAGINA, PARAMETRO_NOVA_FILIAL_NASCE_ATIVA,
        )
        from .parametro_declaracao import registrar as registrar_parametro

        registrar_parametro(PARAMETRO_ITENS_POR_PAGINA)
        registrar_parametro(PARAMETRO_NOVA_FILIAL_NASCE_ATIVA)

        # `sender=self`: sem isso o receptor dispara uma vez por app
        # instalado (todo `post_migrate` de toda `migrate`), não uma vez por
        # `migrate` de verdade.
        post_migrate.connect(_semear_apos_migrar, sender=self)

        from django.db.models.signals import post_save

        post_save.connect(_criar_a_matriz, sender="plataforma.Empresa",
                          dispatch_uid="plataforma_criar_a_matriz")
