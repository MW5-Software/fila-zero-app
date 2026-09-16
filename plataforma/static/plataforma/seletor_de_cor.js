/* O seletor de cor ao lado de um campo de cor em texto (15/09/2026).

   O TEXTO continua sendo o campo que o formulário envia: vazio quer dizer
   "herda da instalação", e o `<input type="color">` nativo não tem estado
   vazio — ele sempre manda alguma cor. Por isso o seletor é um ajudante sem
   `name`, sincronizado com o texto nos dois sentidos, e nunca o campo.

   Com o texto vazio, o seletor mostra a cor HERDADA (`data-cor-herdada`), que
   é a que vai valer; mexer nele escreve a cor no texto.

   Sem script o seletor não aparece e o texto funciona como sempre.
*/
(function () {
  "use strict";

  var HEX = /^#([0-9a-f]{3}|[0-9a-f]{6})$/i;

  // O seletor só aceita "#rrggbb". "#abc" é cor válida no texto (o servidor
  // aceita), e sem expandir o seletor recusaria o valor em silêncio.
  function seisDigitos(cor) {
    if (!HEX.test(cor)) return null;
    if (cor.length === 4) {
      cor = "#" + cor[1] + cor[1] + cor[2] + cor[2] + cor[3] + cor[3];
    }
    return cor.toLowerCase();
  }

  function montar(campo) {
    if (campo.hasAttribute("data-seletor-montado")) return;
    campo.setAttribute("data-seletor-montado", "1");

    var seletor = document.createElement("input");
    seletor.type = "color";
    seletor.className = "seletor-de-cor";
    seletor.setAttribute("aria-label", "Escolher " + (campo.labels && campo.labels[0]
      ? campo.labels[0].textContent.trim() : "cor"));
    var herdada = seisDigitos(campo.getAttribute("data-cor-herdada") || "") || "#000000";

    function doTexto() {
      seletor.value = seisDigitos(campo.value.trim()) || herdada;
    }

    seletor.addEventListener("input", function () {
      campo.value = seletor.value;
      // Quem escuta o campo (a validação do navegador, amanhã uma prévia)
      // precisa saber que ele mudou: atribuir `.value` não dispara evento.
      campo.dispatchEvent(new Event("input", {bubbles: true}));
    });
    campo.addEventListener("input", doTexto);

    var envolto = document.createElement("div");
    envolto.className = "com-seletor-de-cor";
    campo.parentNode.insertBefore(envolto, campo);
    envolto.appendChild(campo);
    envolto.appendChild(seletor);
    doTexto();
  }

  function ligar() {
    Array.prototype.forEach.call(
      document.querySelectorAll("input[data-seletor-de-cor]"), montar);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", ligar);
  } else {
    ligar();
  }
})();
