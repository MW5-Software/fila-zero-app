"""O que os módulos de Perfis e Usuários dizem sobre si.

Só a declaração mora aqui — quem registra é `apps.ContasConfig.ready()`, e
não a importação deste arquivo. Ver o comentário lá, e o de
`modulos/exemplo/modulo.py`, para o motivo.

Os dois módulos moram no mesmo arquivo porque nascem juntos, do mesmo app, e
pela mesma razão de existir: sem qualquer um dos dois, o admin do cliente tem
metade do meio de administrar gente e nenhuma. `perfis` decide o que cada
papel concede; `usuarios` decide quem está em cada papel.
"""

from __future__ import annotations

from plataforma.declaracao import ModuloSpec
from django.utils.translation import gettext_lazy as _

#: "Eu sou os Cargos. Meu ícone é a maleta. Eu moro no grupo Cadastro.
#: Minha rota é /cargos. Eu crio a permissão cargos.editar."
#:
#: **Nasceu em 14/09/2026** no lugar de Perfis, para o titular (pedido do João:
#: a terminologia do produto é Cargo). Edita `contas.Cargo`. **A permissão
#: `cargos.editar` só põe a tela no menu**: quem tranca é o NÍVEL, dentro da
#: view (`contas/views_cargos.py`) — senão um cargo que carregasse esta
#: permissão deixaria alguém promover o próprio cargo.
#:
#: `ordem=-1`, a mesma de Perfis: o desempate alfabético põe Cargos antes.
#: `ativo_por_padrao=True`: é cadastro da base, como Usuários e Empresa.
MODULO_CARGOS = ModuloSpec(
    chave="cargos",
    rotulo=_("Cargos"),
    icone="briefcase",
    grupo="Configuração",
    ordem=-1,
    rota="/cargos",
    permissoes=("cargos.editar",),
    ativo_por_padrao=True,
)


#: "Eu sou o Usuários. Meu ícone são as pessoas. Eu moro no grupo
#: Administração. Minha rota é /usuarios. Eu crio a permissão
#: usuarios.editar."
#:
#: `ativo_por_padrao=True`: sem a tela de Usuários ligada desde o primeiro dia,
#: o titular não teria como cadastrar nem alocar ninguém — e `semear` cria toda
#: linha desligada.
MODULO_USUARIOS = ModuloSpec(
    chave="usuarios",
    rotulo=_("Usuários"),
    icone="users",
    #: **Cadastro, e não Administração.** Cadastrar gente é trabalho do dia
#: de quem administra uma empresa — entra junto com produto e empresa,
#: não junto de aparência, módulos e falhas, que são configuração da
#: INSTALAÇÃO e se mexe uma vez por ano.
#:
#: `ordem=-2`: dentro do Cadastro, depois de Empresa e Filiais — o titular
#: cadastra as pessoas depois dos lugares a que elas pertencem (ver o
#: comentário de ordem em `plataforma/modulo.py`, `MODULO_EMPRESA`). E não a
#: -100 da Administração: com ela, o grupo Cadastro herdaria a menor ordem
#: dos seus e empataria com a Administração no topo.
    grupo="Configuração",
    ordem=-2,
    rota="/usuarios",
    permissoes=("usuarios.editar",),
    ativo_por_padrao=True,
)

#: "Eu sou a Auditoria. Meu ícone é a lupa sobre o arquivo. Eu moro no grupo
#: Administração. Minha rota é /auditoria. Eu crio a permissão auditoria.ver."
#:
#: `ativo_por_padrao=True`: a trilha grava desde a primeira ação de sempre —
#: o primeiro login da instalação —, e uma instalação que sobe com a leitura
#: desligada tem um registro que ninguém consegue consultar. Ver é diferente
#: de editar: esta tela não tem ação nenhuma, e a permissão que ela cria é
#: `.ver`, não `.editar`.
MODULO_AUDITORIA = ModuloSpec(
    chave="auditoria",
    rotulo=_("Auditoria"),
    icone="file-search",
    grupo="Administração",
    ordem=-100,
    rota="/auditoria",
    permissoes=("auditoria.ver",),
    ativo_por_padrao=True,
)
