// O comportamento da página da fila (Fila Zero).
//
// A página funciona inteira sem este arquivo (formulários e links comuns).
// Ele acrescenta três coisas: a consulta de 3 em 3 segundos (D8 do spec), as
// ações sem recarregar a página, e as folhas como diálogo. Tudo que ele
// desenha vem do servidor pronto: não há HTML montado aqui, para a tela não
// mudar de cara depois da primeira consulta.
(function () {
  "use strict";

  var INTERVALO = 3000;          // D8: a cada 3 segundos
  var INTERVALO_SEM_SINAL = 10000;
  // A página mora dentro do shell do sistema: os endereços e a versão vêm do
  // miolo da fila, e não do <body>, que é do shell.
  var corpo = document.getElementById("fila");
  if (!corpo) return;
  var versao = corpo.dataset.versao || "";
  var urlEstado = corpo.dataset.estadoUrl;
  var urlAgir = corpo.dataset.agirUrl;
  var esperando = null;

  function el(id) { return document.getElementById(id); }

  function haQuanto(iso) {
    var minutos = Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
    if (minutos < 1) return "agora";
    if (minutos < 60) return "há " + minutos + " min";
    var resto = minutos % 60;
    return "há " + Math.floor(minutos / 60) + " h " + (resto < 10 ? "0" : "") + resto + " min";
  }

  function atualizarTempos() {
    document.querySelectorAll("time[data-desde]").forEach(function (t) {
      t.textContent = haQuanto(t.dataset.desde);
    });
    // Os cronômetros de quem atende ou pausa: só o número; o "min" é do HTML.
    document.querySelectorAll("[data-minutos]").forEach(function (n) {
      var minutos = Math.max(0, Math.floor((Date.now() - new Date(n.dataset.minutos).getTime()) / 60000));
      var texto = n.firstChild;
      if (texto && texto.nodeType === 3) texto.nodeValue = String(minutos);
    });
  }

  function numeroDaPosicao() {
    var n = document.querySelector("#fila-painel .painel-na-fila .fila-numeral-n");
    return n ? n.textContent.trim() : "";
  }

  // Troca os pedaços e marca os dois únicos momentos com movimento: a vez
  // que chega e a posição que muda.
  function trocar(html, novaVersao) {
    if (!html) return;
    var eraVez = !!document.querySelector("#fila-painel .painel-sua-vez");
    var posicaoAntes = numeroDaPosicao();
    ["painel", "lista", "barra", "lancamentos"].forEach(function (nome) {
      var lugar = el("fila-" + nome);
      if (lugar && typeof html[nome] === "string") lugar.innerHTML = html[nome];
    });
    if (novaVersao) { versao = novaVersao; corpo.dataset.versao = novaVersao; }
    var eVez = !!document.querySelector("#fila-painel .painel-sua-vez");
    corpo.classList.remove("fila-chegou", "fila-mudou");
    void corpo.offsetWidth;   // recomeça a animação
    if (eVez && !eraVez) {
      corpo.classList.add("fila-chegou");
      if (navigator.vibrate) navigator.vibrate([180, 80, 180]);
    } else if (posicaoAntes && numeroDaPosicao() !== posicaoAntes) {
      corpo.classList.add("fila-mudou");
    }
    atualizarTempos();
    rolarTrilha();
  }

  // Na trilha estreita do celular, a pessoa é o último nó: rola até ela.
  function rolarTrilha() {
    var trilha = document.querySelector(".fila-trilha");
    if (trilha) trilha.scrollLeft = trilha.scrollWidth;
  }

  function mostrarRecusa(frase) {
    var caixa = el("fila-recusa");
    if (!caixa) return;
    caixa.textContent = frase || "";
    caixa.hidden = !frase;
  }

  function textoAoVivo(texto) {
    var alvo = document.querySelector("[data-ao-vivo-texto]");
    if (alvo) alvo.textContent = texto;
  }

  function agendar(espera) {
    clearTimeout(esperando);
    esperando = setTimeout(consultar, espera);
  }

  function consultar() {
    if (document.hidden) { agendar(INTERVALO); return; }
    fetch(urlEstado + "?versao=" + encodeURIComponent(versao), {
      credentials: "same-origin", headers: { "X-Fila": "1" }
    }).then(function (r) {
      if (r.redirected || !r.ok) throw new Error("estado " + r.status);
      return r.json();
    }).then(function (dados) {
      corpo.classList.remove("fila-sem-sinal");
      textoAoVivo("Ao vivo");
      if (dados.mudou) trocar(dados.html, dados.versao);
      agendar(INTERVALO);
    }).catch(function () {
      // Celular que perde sinal: avisa e tenta de novo mais devagar, sem
      // derrubar a página nem empilhar pedidos.
      corpo.classList.add("fila-sem-sinal");
      textoAoVivo("Sem conexão");
      agendar(INTERVALO_SEM_SINAL);
    });
  }

  // --- As folhas ---------------------------------------------------------
  // São os modais do design system: abrir é pôr `.open` no `.overlay`, e
  // fechar (o X, o fundo, o Esc) já é trabalho do `mw5.js`.
  function abrirFolha(nome, gatilho) {
    var folha = el("folha-" + nome);
    if (!folha) return false;
    fecharFolhas();
    folha.querySelectorAll("form").forEach(function (f) { f.reset(); });
    var dados = gatilho ? gatilho.dataset : {};
    if (dados.pessoa) {
      folha.querySelectorAll("input[name=pessoa]").forEach(function (c) { c.value = dados.pessoa; });
      // Dentro de "Corrigir", os atalhos para as outras folhas levam a pessoa.
      folha.querySelectorAll("[data-folha]").forEach(function (a) {
        a.dataset.pessoa = dados.pessoa;
        a.dataset.nome = dados.nome || "";
      });
    }
    folha.querySelectorAll("[data-nome]").forEach(function (n) {
      if (n.tagName !== "A") n.textContent = dados.nome || "";
    });
    if (dados.estado) {
      folha.querySelectorAll("[data-para]").forEach(function (bloco) {
        bloco.hidden = bloco.dataset.para.split(" ").indexOf(dados.estado) < 0;
      });
    }
    ajustarResultado(folha);
    somar(folha);
    folha.classList.add("open");
    folha.setAttribute("data-open", "true");
    var primeiro = folha.querySelector("input[type=radio], select, textarea, button[type=submit]");
    if (primeiro) primeiro.focus();
    return true;
  }

  function fecharFolhas() {
    document.querySelectorAll("[data-modal].open").forEach(function (d) {
      d.classList.remove("open");
      d.removeAttribute("data-open");
    });
  }

  function ajustarResultado(folha) {
    var escolhido = folha.querySelector("input[name=resultado]:checked");
    var venda = folha.querySelector(".so-venda");
    var naoVenda = folha.querySelector(".so-nao-venda");
    if (venda) venda.hidden = !escolhido || escolhido.value !== "vendeu";
    if (naoVenda) naoVenda.hidden = !escolhido || escolhido.value !== "nao_vendeu";
  }

  function lerValor(texto) {
    var limpo = (texto || "").replace(/R\$|\s/g, "");
    if (limpo.indexOf(",") >= 0) limpo = limpo.replace(/\./g, "").replace(",", ".");
    else if (/^\d{1,3}(\.\d{3})+$/.test(limpo)) limpo = limpo.replace(/\./g, "");
    var n = Number(limpo);
    return isFinite(n) && n > 0 ? n : 0;
  }

  function somar(escopo) {
    escopo.querySelectorAll(".fila-itens").forEach(function (itens) {
      var total = 0;
      itens.querySelectorAll("input[name=valor]").forEach(function (i) { total += lerValor(i.value); });
      var saida = itens.parentNode.querySelector("output.total");
      if (saida) {
        saida.textContent = "R$ " + total.toLocaleString("pt-BR", {
          minimumFractionDigits: 2, maximumFractionDigits: 2 });
      }
    });
  }

  // --- Ações -------------------------------------------------------------
  function enviar(form) {
    var botao = form.querySelector("button[type=submit]");
    if (botao) botao.disabled = true;
    fetch(urlAgir, {
      method: "POST", credentials: "same-origin",
      headers: { "X-Fila": "1" }, body: new FormData(form)
    }).then(function (r) {
      if (!r.ok) throw new Error("agir " + r.status);
      return r.json();
    }).then(function (dados) {
      mostrarRecusa(dados.frase);
      if (dados.ok) fecharFolhas();
      trocar(dados.html, dados.versao);
    }).catch(function () {
      mostrarRecusa("Sem conexão. Tente de novo.");
    }).then(function () {
      if (botao && document.contains(botao)) botao.disabled = false;
    });
  }

  document.addEventListener("submit", function (e) {
    var form = e.target;
    if (!form.matches("form[data-acao]")) return;
    e.preventDefault();
    enviar(form);
  });

  document.addEventListener("click", function (e) {
    var gatilho = e.target.closest("[data-folha]");
    if (gatilho && abrirFolha(gatilho.dataset.folha, gatilho)) {
      e.preventDefault();
      return;
    }
    var outro = e.target.closest("[data-outro-grupo]");
    if (outro) {
      var itens = outro.parentNode.querySelector(".fila-itens");
      var modelo = itens.querySelector(".item-vendido:last-child");
      var copia = modelo.cloneNode(true);
      copia.querySelector("select").selectedIndex = 0;
      copia.querySelector("input").value = "";
      itens.appendChild(copia);
      copia.querySelector("select").focus();
    }
  });

  document.addEventListener("change", function (e) {
    if (e.target.name === "resultado") ajustarResultado(e.target.closest("[data-modal]"));
  });
  document.addEventListener("input", function (e) {
    if (e.target.name === "valor") somar(e.target.closest("form"));
  });

  // Folha aberta pela URL (o caminho sem JavaScript): acerta a parte que
  // depende do resultado escolhido e o total.
  document.querySelectorAll("[data-modal].open").forEach(function (folha) {
    ajustarResultado(folha);
    somar(folha);
  });

  document.addEventListener("visibilitychange", function () {
    if (!document.hidden) agendar(0);
  });

  rolarTrilha();
  setInterval(atualizarTempos, 30000);
  if (urlEstado) agendar(INTERVALO);
})();
