-- Onde mora o acesso de cada pessoa, em SQL.
--
-- Existe para responder, com o banco aberto na frente, a pergunta que sempre
-- vem depois de a tela mostrar "Vendedor · Cadastrar produto: sim":
-- "onde está isso, e como funciona?".
--
-- SÃO CINCO TABELAS, e nenhuma delas se chama "permissão do nível":
--
--   auth_user                     a pessoa (login, nome, e-mail, ativa)
--   acesso_acesso                 o NÍVEL dela, um inteiro: 0 Master,
--                                 1 Gestor, 2 Vendedor, 3 Comprador
--   acesso_acesso_empresas        quais empresas ela alcança (N por pessoa)
--   acesso_acesso_compradores     a carteira, se ela for vendedora
--   auth_user_user_permissions    o que ela pode, já resolvido
--
-- COMO FUNCIONA, em uma frase: o nível é o que se ESCOLHE, e as permissões
-- são o que o sistema GRAVA por causa dele. Quem faz a tradução é
-- `acesso/fabrica.py` (a tabela `DE_FABRICA`), no CÓDIGO — e o resultado
-- vira linha em `auth_user_user_permissions` no instante em que o nível é
-- salvo.
--
-- POR QUE A REGRA NÃO É UMA TABELA. Porque tabela o cliente edita. Se
-- "Comprador dá catalogo.ver" fosse uma linha no banco, o admin de uma
-- empresa acrescentaria `catalogo.editar` nela e promoveria todos os
-- compradores de TODAS as empresas de uma vez, sem passar por tela de
-- usuário nenhuma. O nível é a fronteira do produto; ela mora no código, que
-- o cliente não altera. O que o cliente PODE ajustar por pessoa é o Perfil —
-- a exceção, que soma por cima e não é tocada quando o nível muda.
--
-- O QUE ISTO NÃO FAZ: mudar `DE_FABRICA` não reescreve quem já existe. As
-- permissões de alguém são regravadas quando o nível daquela pessoa é salvo
-- de novo. Não há comando para reaplicar em todo mundo — se um dia a regra
-- mudar com gente cadastrada, isso precisa existir antes.


-- 1. Quem é quem -------------------------------------------------------------
SELECT u.username                      AS login,
       u.first_name                    AS nome,
       a.nivel                         AS nivel,
       CASE a.nivel WHEN 0 THEN 'Master'   WHEN 1 THEN 'Gestor'
                    WHEN 2 THEN 'Vendedor' WHEN 3 THEN 'Comprador'
       END                             AS nivel_por_extenso,
       u.is_active                     AS ativo
FROM auth_user u
LEFT JOIN acesso_acesso a ON a.usuario_id = u.id
ORDER BY a.nivel NULLS LAST, u.username;
-- `LEFT JOIN`: pessoa sem linha em `acesso_acesso` não alcança nada, e some
-- da lista se o JOIN for fechado — o que esconderia justamente o caso torto.


-- 2. O que cada um pode ------------------------------------------------------
SELECT u.username AS login,
       string_agg(p.codename, ', ' ORDER BY p.codename) AS permissoes
FROM auth_user u
JOIN auth_user_user_permissions up ON up.user_id = u.id
JOIN auth_permission p             ON p.id = up.permission_id
GROUP BY u.username
ORDER BY u.username;
-- Estas são as DIRETAS, escritas pelo nível. O que vem de Perfil não aparece
-- aqui — ver a consulta 6.


-- 3. Quais empresas cada um alcança -----------------------------------------
SELECT u.username AS login, e.razao_social AS empresa
FROM auth_user u
JOIN acesso_acesso           a  ON a.usuario_id = u.id
JOIN acesso_acesso_empresas  ae ON ae.acesso_id = a.id
JOIN plataforma_empresa      e  ON e.id = ae.empresa_id
ORDER BY u.username, e.razao_social;


-- 4. A carteira do vendedor --------------------------------------------------
SELECT v.username AS vendedor, c.username AS comprador_atendido
FROM acesso_acesso                a
JOIN auth_user                    v  ON v.id = a.usuario_id
JOIN acesso_acesso_compradores    ac ON ac.acesso_id = a.id
JOIN auth_user                    c  ON c.id = ac.user_id
ORDER BY v.username, c.username;
-- É esta tabela que decide quais orçamentos um vendedor enxerga e para quem
-- ele precifica. Vendedor e comprador alcançam a MESMA empresa: a parede do
-- inquilino não separa um do outro; quem separa é esta linha.


-- 5. A ficha inteira de uma pessoa -------------------------------------------
SELECT u.username, u.email,
       CASE a.nivel WHEN 0 THEN 'Master'   WHEN 1 THEN 'Gestor'
                    WHEN 2 THEN 'Vendedor' WHEN 3 THEN 'Comprador'
       END AS nivel,
       (SELECT count(*) FROM acesso_acesso_empresas     x WHERE x.acesso_id = a.id) AS empresas,
       (SELECT count(*) FROM acesso_acesso_compradores  x WHERE x.acesso_id = a.id) AS carteira,
       (SELECT count(*) FROM auth_user_user_permissions x WHERE x.user_id  = u.id)  AS permissoes
FROM auth_user u
JOIN acesso_acesso a ON a.usuario_id = u.id
WHERE u.username = 'vera.vendedora';


-- 6. A exceção: o que veio de Perfil, e não do nível -------------------------
SELECT u.username AS login, pf.rotulo AS perfil,
       string_agg(p.codename, ', ' ORDER BY p.codename) AS permissoes_do_perfil
FROM auth_user u
JOIN contas_perfil_usuarios   pu ON pu.user_id = u.id
JOIN contas_perfil            pf ON pf.id = pu.perfil_id
LEFT JOIN contas_perfil_permissoes pp ON pp.perfil_id = pf.id
LEFT JOIN auth_permission          p  ON p.id = pp.permission_id
GROUP BY u.username, pf.rotulo
ORDER BY u.username;
-- Vazio é o esperado: perfil é a exceção, concedida à mão pela MW5 quando
-- alguém precisa de algo que o nível não dá. Numa instalação nova não existe
-- nenhum.


-- 7. A prova de que a tela não mente -----------------------------------------
-- Roda ao lado do painel "O que ela vai poder" e compara linha a linha.
SELECT u.username,
       bool_or(p.codename = 'catalogo_ver')            AS ve_catalogo,
       bool_or(p.codename = 'catalogo_editar')         AS cadastra_produto,
       bool_or(p.codename = 'orcamentos_ver')          AS ve_orcamentos,
       bool_or(p.codename = 'orcamentos_acompanhar')   AS acompanha_orcamentos,
       bool_or(p.codename = 'usuarios_editar')         AS cadastra_gente,
       bool_or(p.codename = 'empresa_editar')          AS mexe_na_empresa
FROM auth_user u
LEFT JOIN auth_user_user_permissions up ON up.user_id = u.id
LEFT JOIN auth_permission            p  ON p.id = up.permission_id
GROUP BY u.username
ORDER BY u.username;
