/* Trocar de empresa ou de loja pergunta por cima da página.
 *
 * O seletor do cabeçalho é um `<form method="get">` cujo `<select>` tem
 * `data-auto-enviar`: o `mw5.js` envia o formulário na hora em que a escolha
 * muda, e a resposta era a página nua de confirmação. Aqui a mudança abre o
 * diálogo que o servidor já desenhou (`plataforma/trocar.py`).
 *
 * **Na fase de captura, e de propósito.** O ouvinte do design system está no
 * mesmo `document` e foi registrado antes; na fase normal ele correria
 * primeiro e a página já teria navegado. Capturando, este corre antes e o
 * `stopPropagation` segura o envio.
 *
 * O campo volta na hora para o valor de agora: a troca só acontece no
 * "Confirmar", e assim cancelar (o X, o fundo, o Esc) não deixa o cabeçalho
 * mostrando um lugar onde a pessoa não está.
 */
(function () {
  "use strict";

  document.addEventListener("change", function (evento) {
    var campo = evento.target;
    if (!campo || !campo.classList || !campo.classList.contains("ctx-sel")) return;
    var dialogo = document.getElementById("trocar-dialogo");
    if (!dialogo) return;  // sem o que trocar: o design system segue com o dele

    var opcao = campo.options[campo.selectedIndex];
    if (!opcao) return;
    evento.stopPropagation();

    var para = campo.id === "ctx-empresa_id" ? "empresa" : "filial";
    // O valor de agora é o que estava marcado no HTML que o servidor mandou.
    var atual = campo.querySelector("option[selected]");
    if (atual) campo.value = atual.value;

    dialogo.querySelectorAll("[data-alvo-da-troca]").forEach(function (alvo) {
      alvo.textContent = opcao.textContent.trim();
    });
    dialogo.querySelectorAll("form[data-para]").forEach(function (formulario) {
      var e_esse = formulario.dataset.para === para;
      formulario.hidden = !e_esse;
      if (!e_esse) return;
      var id = formulario.querySelector("[data-id-escolhido]");
      if (id) id.value = opcao.value;
    });

    dialogo.classList.add("open");
    var confirmar = dialogo.querySelector("form[data-para]:not([hidden]) "
                                          + "button[type=submit]");
    if (confirmar) confirmar.focus();
  }, true);
})();
