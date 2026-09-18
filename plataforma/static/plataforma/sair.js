/* O "Sair" do menu do avatar abre o diálogo em vez de trocar de página.
 *
 * O item é um `<a href="/sair">` de verdade (ver `plataforma/sair.py`): sem
 * este script ele navega para a confirmação de sempre, e é assim que a tela
 * continua funcionando sem JavaScript. Com ele, a pergunta acontece por cima
 * da página em que a pessoa estava.
 *
 * Abrir é pôr `.open` no `.overlay`, como a fila já faz com as folhas dela;
 * fechar (o X, o fundo, o Esc) é trabalho do `mw5.js` e não se repete aqui.
 */
(function () {
  "use strict";

  document.addEventListener("click", function (evento) {
    var alvo = evento.target;
    if (!alvo || !alvo.closest) return;
    var gatilho = alvo.closest("[data-sair]");
    if (!gatilho) return;
    var dialogo = document.getElementById("sair-dialogo");
    if (!dialogo) return;  // tela sem shell: o link segue para /sair

    evento.preventDefault();
    // O menu do avatar fica aberto por trás do diálogo, e reaparece no
    // cancelar — sair dele é parte de abrir isto.
    document.querySelectorAll(".dropdown.open").forEach(function (menu) {
      menu.classList.remove("open");
    });
    dialogo.classList.add("open");
    // O foco no "Sair", que é o motivo de a pessoa estar aqui; o Esc e o
    // clique fora continuam cancelando.
    var confirmar = dialogo.querySelector("button[type=submit]");
    if (confirmar) confirmar.focus();
  });
})();
