/* Os blocos do cadastro de usuário que dependem do nível escolhido.
 *
 * Só a MW5 escolhe nível, e o que muda com a escolha são dois blocos: a
 * EMPRESA da conta, que só vale para quem vira titular, e a CONTA, que não
 * vale para quem é titular ou MW5 (o titular É a conta; a MW5 não é cliente
 * de nenhuma).
 *
 * POR QUE NASCE VISÍVEL. Sem JavaScript os blocos ficam na tela. Um campo que
 * só aparece com script é um campo que um dia não aparece; campo visível a
 * mais se ignora, campo escondido a menos não se preenche.
 *
 * Cada modal é um formulário próprio (criar, e um editar por linha), então o
 * par nível↔bloco é resolvido DENTRO do formulário — nunca por
 * `document.querySelector`, que acharia o primeiro da página e faria o
 * seletor de uma pessoa comandar o bloco de outra.
 *
 * Até 14/09/2026 este arquivo também montava as fichas da carteira e o painel
 * "o que ela vai poder". Os dois saíram com a virada dos cargos: a carteira
 * deixou de ser regra, e o que a pessoa pode vem do cargo da alocação.
 */
(function () {
  "use strict";

  function desligar(bloco, esconder) {
    // DESLIGAR os campos escondidos é opção do bloco
    // (`data-desligar-escondido`): campo escondido continua sendo enviado, e
    // quem digitasse a razão social e trocasse o seletor cadastraria uma
    // empresa que ninguém pediu. `disabled` também tira o campo da validação
    // do navegador, sem o que um `required` invisível trava o envio.
    if (!bloco.hasAttribute("data-desligar-escondido")) return;
    Array.prototype.forEach.call(
      bloco.querySelectorAll("input, select, textarea"),
      function (campo) { campo.disabled = esconder; });
  }

  function sincronizar(formulario) {
    var seletor = formulario.querySelector('select[name="nivel"]');
    if (!seletor) return;

    // Bloco que só vale para UM nível. O atributo carrega o número do nível,
    // o mesmo valor que o `<option>` manda: não há uma segunda tabela de
    // tradução para divergir da primeira.
    var titular = formulario.querySelector("[data-nivel-titular]");
    if (titular) {
      var esconder = seletor.value !== titular.getAttribute("data-nivel-titular");
      titular.style.display = esconder ? "none" : "";
      desligar(titular, esconder);
    }

    // O inverso: blocos que somem para ALGUNS níveis. Lista de níveis (`0,1`)
    // e não "todos menos um": o dia em que existir outro nível, quem o criar
    // decide de que lado ele cai, em vez de herdar a resposta por acidente.
    //
    // TODOS os blocos, e não o primeiro: desde 15/09/2026 são dois — a Conta
    // e as Alocações, que também não valem para titular nem MW5 — e um
    // `querySelector` só esconderia a Conta.
    var caixas = formulario.querySelectorAll("[data-nivel-sem-conta], [data-nivel-sem-alocacao]");
    Array.prototype.forEach.call(caixas, function (caixa) {
      var lista = caixa.getAttribute("data-nivel-sem-conta")
        || caixa.getAttribute("data-nivel-sem-alocacao");
      var some = lista.split(",").indexOf(seletor.value) !== -1;
      caixa.style.display = some ? "none" : "";
      desligar(caixa, some);
    });
  }

  function ligar() {
    var formularios = document.querySelectorAll("form");
    for (var i = 0; i < formularios.length; i++) {
      (function (formulario) {
        var seletor = formulario.querySelector('select[name="nivel"]');
        if (!seletor) return;
        // `change` e não `input`: num <select> os dois chegam juntos, e ouvir
        // um só evita rodar a função duas vezes por escolha.
        seletor.addEventListener("change", function () {
          sincronizar(formulario);
        });
        sincronizar(formulario);
      })(formularios[i]);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", ligar);
  } else {
    ligar();
  }
})();
