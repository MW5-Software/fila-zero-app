/* A tela de metas ao vivo (17/09/2026). O servidor desenha tudo; aqui só se
   recalculam larguras e números do que já está na página, e nenhum HTML é
   montado. As frases vêm do servidor, no idioma de quem abriu a tela, em
   `data-*` do `[data-metas]`: o script troca o valor, e não escreve frase.

   Sem este script a tela funciona igual: salvar, dividir e copiar são POST,
   e a régua e as barras são as da última gravação. */
(function () {
  "use strict";

  var raiz = document.querySelector("[data-metas]");
  if (!raiz) return;
  var form = raiz.querySelector("[data-metas-form]");
  raiz.classList.add("metas-com-script");

  function centavos(texto) {
    var digitos = String(texto || "").replace(/\D/g, "");
    return digitos ? parseInt(digitos, 10) : 0;
  }

  function reais(c) {
    return "R$ " + (c / 100).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  function frase(chave, valores) {
    return (raiz.dataset[chave] || "").replace(/%\((\w+)\)s/g, function (_t, nome) {
      return valores[nome];
    });
  }

  var trocarLoja = raiz.querySelector("[data-trocar-loja]");
  if (trocarLoja) trocarLoja.addEventListener("change", function () { trocarLoja.form.submit(); });

  if (!form) return;
  var salvar = form.querySelector("[data-salvar]");
  var mudadas = form.querySelector("[data-mudadas]");
  if (salvar) salvar.setAttribute("data-limpo", "");

  function ritmo(linha, meta) {
    var barra = linha.querySelector(".metas-barra");
    var estado = linha.querySelector(".metas-estado");
    // Só o mês em andamento muda de ritmo ao digitar: encerrado não se edita,
    // e o futuro ainda não tem venda.
    if (!barra || linha.dataset.mes !== "atual") return;
    var vendido = parseInt(linha.dataset.vendido || "0", 10);
    var esperado = parseFloat(linha.dataset.esperado);
    var tipo = "sem_meta", pct = 0;
    if (meta > 0) {
      pct = vendido * 100 / meta;
      tipo = vendido >= meta ? "bateu" : pct >= esperado * 0.85 ? "no_ritmo" : "atras";
    }
    barra.dataset.ritmo = estado.dataset.ritmo = tipo;
    barra.firstElementChild.style.width = Math.min(pct, 100).toFixed(1) + "%";
    var rotulo = { bateu: raiz.dataset.bateu, no_ritmo: raiz.dataset.noRitmo, atras: raiz.dataset.atras }[tipo];
    estado.textContent = rotulo ? rotulo + " · " + Math.round(pct) + "%" : "—";
  }

  function atualizar() {
    var campoLoja = form.querySelector("[data-campo-loja]");
    var loja = campoLoja ? centavos(campoLoja.value) : 0;
    var soma = 0, alteradas = 0;
    var linhas = form.querySelectorAll(".metas-linha");

    if (campoLoja && campoLoja.value !== campoLoja.defaultValue) alteradas += 1;
    linhas.forEach(function (linha) {
      var campo = linha.querySelector("input[data-valor]");
      var meta = campo ? centavos(campo.value) : 0;
      soma += meta;
      var mudou = campo && !campo.disabled && campo.value !== campo.defaultValue;
      linha.classList.toggle("mudou", !!mudou);
      if (mudou) alteradas += 1;
      ritmo(linha, meta);
    });

    var base = Math.max(soma, loja) || 1;
    linhas.forEach(function (linha) {
      var trecho = form.querySelector('[data-trecho="' + linha.dataset.pessoa + '"]');
      var campo = linha.querySelector("input[data-valor]");
      if (trecho) trecho.style.width = ((campo ? centavos(campo.value) : 0) * 100 / base).toFixed(2) + "%";
    });
    var linhaLoja = form.querySelector("[data-linha-loja]");
    if (linhaLoja) {
      linhaLoja.hidden = !loja;
      linhaLoja.style.left = (loja * 100 / base).toFixed(2) + "%";
      linhaLoja.querySelector("[data-rotulo]").textContent = frase("rotuloLoja", { valor: reais(loja) });
    }
    form.querySelector("[data-soma]").textContent = reais(soma);
    var veredito = form.querySelector("[data-veredito]");
    veredito.classList.remove("ok", "warn");
    if (!loja) veredito.textContent = raiz.dataset.semLoja;
    else if (soma < loja) { veredito.classList.add("warn"); veredito.textContent = frase("falta", { valor: reais(loja - soma) }); }
    else if (soma === loja) { veredito.classList.add("ok"); veredito.textContent = raiz.dataset.exata; }
    else { veredito.classList.add("ok"); veredito.textContent = frase("cobre", { valor: reais(soma - loja) }); }

    if (salvar) {
      salvar.toggleAttribute("data-limpo", alteradas === 0);
      mudadas.textContent = alteradas === 1 ? raiz.dataset.umaMudanca
        : frase("variasMudancas", { n: alteradas });
    }
  }

  form.addEventListener("input", function (e) {
    if (e.target.matches("input[data-valor]")) atualizar();
  });
  // Voltou de um POST com valores que não estão salvos (erro, copiar ou
  // dividir): a barra de salvar aparece, porque há o que gravar.
  if (document.querySelector(".alert") && form.querySelector("input[data-valor]:not(:disabled)")) {
    if (salvar) salvar.removeAttribute("data-limpo");
  }
})();
