/* O bloco de Alocações do cadastro de usuário: acrescentar e remover linhas.
 *
 * **Cópia do padrão de `catalogo/static/catalogo/cadastro.js`
 * (`ligarRepetidores` e o "Remover"), e não um import dele.** A tela de
 * Usuários é da base (`contas`), e a base nunca depende de módulo de negócio
 * (`tests/test_camadas_nao_se_invertem.py`): um produto irmão sem catálogo
 * perderia o botão de acrescentar alocação.
 *
 * TUDO AQUI É CONFORTO. Sem este arquivo o formulário continua funcionando:
 * cada modal já vem com uma linha em branco desenhada pelo servidor, que é
 * ignorada no POST se ficar vazia.
 */
(function () {
  "use strict";

  function limpar(linha) {
    Array.prototype.forEach.call(
      linha.querySelectorAll("select"), function (campo) {
        campo.selectedIndex = 0;
      });
  }

  document.addEventListener("click", function (evento) {
    var mais = evento.target.closest("[data-aloc-mais]");
    if (mais) {
      var lista = document.getElementById(mais.getAttribute("data-aloc-mais"));
      if (!lista || !lista.lastElementChild) return;
      // O clone vem com o que estava escolhido na última linha; limpar é o
      // que faz "acrescentar" significar uma linha NOVA.
      var nova = lista.lastElementChild.cloneNode(true);
      limpar(nova);
      lista.appendChild(nova);
      var primeiro = nova.querySelector("select");
      if (primeiro) primeiro.focus();
      return;
    }
    var remover = evento.target.closest(".ct-aloc-remover");
    if (!remover) return;
    var linha = remover.closest(".ct-aloc-linha");
    var dona = linha && linha.parentElement;
    // Nunca apaga a última: sem ela não haveria o que clonar, e a pessoa
    // ficaria sem onde escolher. Limpa em vez de remover — linha em branco
    // não vira alocação no POST.
    if (!dona || dona.children.length <= 1) {
      limpar(linha);
      return;
    }
    dona.removeChild(linha);
  });
})();
