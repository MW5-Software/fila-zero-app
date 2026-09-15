/* Prévia ao vivo da Aparência.
 *
 * Enquanto o formulário da marca é editado, o `href` da folha de tema
 * (`/tema.css`) passa a apontar para a rota da prévia com os valores do
 * formulário. Os tokens continuam derivados NO SERVIDOR — aqui não existe
 * nenhuma cor, só a troca de endereço: o que a prévia mostra é exatamente
 * o que valeria salvo.
 *
 * A ligação entre formulário e rota vem do atributo `data-mw5-previa` no
 * próprio `<form>` — este script não sabe nenhum caminho nem nome de campo
 * além do que lê da página.
 */
(function () {
  "use strict";

  var FOLHA = 'link[rel="stylesheet"][href^="/tema.css"]';

  function consulta(form) {
    var params = new URLSearchParams();
    form.querySelectorAll("input[name], select[name]").forEach(function (el) {
      if (el.type === "checkbox") {
        // Checkbox desmarcado não viaja num POST, mas na prévia "desmarcado"
        // é um valor de verdade: sem mandar o 0, o servidor manteria o que
        // está gravado e a prévia mentiria.
        params.set(el.name, el.checked ? "1" : "0");
        return;
      }
      if (!el.value) return; // vazio = mantém o gravado
      params.set(el.name, el.value);
    });
    return params.toString();
  }

  function liga(form) {
    var alvo = form.getAttribute("data-mw5-previa");
    var folha = document.querySelector(FOLHA);
    if (!alvo || !folha) return;

    var timer = null;
    function aplica() {
      var qs = consulta(form);
      if (!qs) return;
      // O `t=` é o bustador: sem ele, um navegador apressado guardava a
      // folha da cor de há dois segundos e a prévia parecia boba.
      folha.setAttribute("href", alvo + "?" + qs + "&t=" + Date.now());
    }

    form.addEventListener("input", function () {
      clearTimeout(timer);
      timer = setTimeout(aplica, 150);
    });
    form.addEventListener("change", aplica);
  }

  document.querySelectorAll("form[data-mw5-previa]").forEach(liga);
})();
