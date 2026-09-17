/* A máscara dos campos de dinheiro (17/09/2026): só números, e os centavos
   empurram ("150000" vira "1.500,00"), como numa maquininha. No celular o
   teclado decimal varia (vírgula, ponto ou nenhum dos dois), e assim ninguém
   depende dele para acertar os centavos.

   É conveniência, e não regra: sem este script o campo aceita texto livre,
   e quem decide o número é `fila.valores.ler_valor`, que lê tudo o que esta
   máscara produz. Carrega ANTES de quem soma o campo, para a soma ler o valor
   já formatado. */
(function () {
  "use strict";

  function mascararValor(texto) {
    var digitos = String(texto || "").replace(/\D/g, "").replace(/^0+/, "");
    if (!digitos) return "";
    while (digitos.length < 3) digitos = "0" + digitos;
    var inteiro = digitos.slice(0, -2).replace(/\B(?=(\d{3})+(?!\d))/g, ".");
    return inteiro + "," + digitos.slice(-2);
  }

  window.mascararValor = mascararValor;

  document.addEventListener("input", function (e) {
    var campo = e.target;
    if (!campo.matches || !campo.matches("input[data-valor]")) return;
    var formatado = mascararValor(campo.value);
    if (formatado !== campo.value) campo.value = formatado;
  });
})();
