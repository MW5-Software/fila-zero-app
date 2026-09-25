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
 *
 * Os links `[data-trocar-loja]` (a fila e as metas) abrem o mesmo diálogo.
 */
(function () {
  "use strict";

  // Preenche e abre o diálogo para trocar `para` ("empresa" ou "filial") pelo
  // lugar `id`, escrevendo `nome` como TEXTO. Devolve se abriu: sem diálogo,
  // ou sem o formulário desse nível, quem chamou segue com o caminho dele.
  function abrir(para, id, nome) {
    var dialogo = document.getElementById("trocar-dialogo");
    if (!dialogo || !dialogo.querySelector('form[data-para="' + para + '"]')) {
      return false;
    }
    dialogo.querySelectorAll("[data-alvo-da-troca]").forEach(function (alvo) {
      alvo.textContent = nome;
    });
    dialogo.querySelectorAll("form[data-para]").forEach(function (formulario) {
      var e_esse = formulario.dataset.para === para;
      formulario.hidden = !e_esse;
      if (!e_esse) return;
      var campo = formulario.querySelector("[data-id-escolhido]");
      if (campo) campo.value = id;
    });
    dialogo.classList.add("open");
    var confirmar = dialogo.querySelector("form[data-para]:not([hidden]) "
                                          + "button[type=submit]");
    if (confirmar) confirmar.focus();
    return true;
  }

  document.addEventListener("change", function (evento) {
    var campo = evento.target;
    if (!campo || !campo.classList || !campo.classList.contains("ctx-sel")) return;

    var opcao = campo.options[campo.selectedIndex];
    if (!opcao) return;
    var para = campo.id === "ctx-empresa_id" ? "empresa" : "filial";
    if (!abrir(para, opcao.value, opcao.textContent.trim())) return;  // o design system segue com o dele
    evento.stopPropagation();
    // O valor de agora é o que estava marcado no HTML que o servidor mandou.
    var atual = campo.querySelector("option[selected]");
    if (atual) campo.value = atual.value;
  }, true);

  // O "Trocar de loja" da página da fila e das metas (25/09/2026, pedido do
  // cliente: "tem que ser modal igual o seletor"). O link leva à página de
  // confirmação, que continua valendo sem script; com ele, a pergunta é o
  // MESMO diálogo do cabeçalho. Por delegação no `document`, porque a fila
  // troca o HTML dela a cada consulta e o link de agora não é o de antes.
  document.addEventListener("click", function (evento) {
    var link = evento.target.closest && evento.target.closest("[data-trocar-loja]");
    if (!link) return;
    if (!abrir("filial", link.dataset.trocarLoja, link.textContent.trim())) return;
    evento.preventDefault();
    var menu = link.closest("details");
    if (menu) menu.open = false;
  });
})();
