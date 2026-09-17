/* ==========================================================================
   MW5 Admin — comportamento do design system.

   Escrito à mão, sem framework, porque é pouca coisa: abrir e
   fechar sobreposições, posicionar menus. Tudo o que envolve dados passa pelo
   HTMX e é renderizado no servidor.

   Nada aqui exige inicialização por tela. Os componentes marcam a intenção com
   atributos `data-*` e a delegação de eventos no documento cuida do resto — o
   que também faz o conteúdo trazido por HTMX funcionar sozinho, sem precisar
   religar handler nenhum depois da troca.
   ========================================================================== */
(function () {
  "use strict";

  /* ------------------------------ mascaras ------------------------------- */
  /* Visuais: o valor gravado sai com a pontuacao, e nada aqui valida nem
     normaliza. A mascara ajuda quem digita; o formato do dado e decisao de
     quem escreve o back.

     `#` e um digito; qualquer outro caractere e literal e entra sozinho. Um
     padrao por mascara, e a lista de nomes tem teste de contrato contra o
     `MASCARAS` do Python — sem ele, o painel oferece uma mascara que nao
     formata nada. */
  var PADROES = {
    "cpf": ["###.###.###-##"],
    "cnpj": ["##.###.###/####-##"],
    /* Duas formas, escolhidas pelo tamanho: um campo so para pessoa fisica e
       juridica e o caso mais comum aqui. */
    "cpf_cnpj": ["###.###.###-##", "##.###.###/####-##"],
    /* Fixo e celular. Com um padrao so, o quinto digito de um fixo viraria o
       comeco do sufixo e o numero sairia torto enquanto se digita. */
    "telefone": ["(##) ####-####", "(##) #####-####"],
    "cep": ["#####-###"]
  };

  /** O texto formatado. Devolve o que veio quando a mascara nao existe. */
  function aplicarMascara(mascara, valor) {
    var padroes = PADROES[mascara];
    if (!padroes) return valor;

    var digitos = String(valor).replace(/\D/g, "");
    /* O padrao mais curto que ainda cabe; o mais longo quando nao cabe em
       nenhum — assim o corte pelo tamanho vem de graca. */
    var padrao = padroes[padroes.length - 1];
    for (var i = 0; i < padroes.length; i++) {
      var cabe = padroes[i].split("#").length - 1;
      if (digitos.length <= cabe) { padrao = padroes[i]; break; }
    }

    var saida = "";
    var d = 0;
    for (var j = 0; j < padrao.length && d < digitos.length; j++) {
      if (padrao[j] === "#") { saida += digitos[d]; d++; }
      else saida += padrao[j];
    }
    return saida;
  }

  document.addEventListener("input", function (ev) {
    var campo = ev.target.closest && ev.target.closest("[data-mascara]");
    if (!campo) return;
    var antes = campo.value;
    var depois = aplicarMascara(campo.getAttribute("data-mascara"), antes);
    if (depois === antes) return;
    /* O cursor vai para o fim so quando se esta digitando no fim — que e o
       caso normal. Reposiciona-lo sempre jogaria o cursor para o fim de quem
       esta corrigindo um digito no meio. */
    var noFim = campo.selectionStart === antes.length;
    campo.value = depois;
    if (noFim) campo.setSelectionRange(depois.length, depois.length);
  });


  var MENU_KEY = "mw5-menu-recolhido";

  /* --------------------------------- tema -------------------------------- */

  function currentTheme() {
    return "light";
  }

  function setTheme() {
    document.documentElement.setAttribute("data-theme", "light");
  }

  function toggleTheme() {
    setTheme();
  }

  /* ------------------------------ sobreposições --------------------------- */

  function openOverlay(el) {
    if (!el) return;
    el.classList.add("open");
    el.setAttribute("data-open", "true");
    var focusable = el.querySelector("[autofocus], button, a[href], input, select, textarea");
    if (focusable) focusable.focus();
  }

  function closeOverlay(el) {
    if (!el) return;
    el.classList.remove("open");
    el.removeAttribute("data-open");
  }

  function closeAllOverlays() {
    document.querySelectorAll("[data-modal].open, [data-drawer].open").forEach(closeOverlay);
    closeDropdown();
  }

  /* -------------------------------- dropdown ------------------------------ */

  var openDropdownEl = null;
  var openDropdownTrigger = null;

  function closeDropdown() {
    if (openDropdownEl) {
      openDropdownEl.classList.remove("open");
      openDropdownEl = null;
    }
    /* O gatilho anuncia o estado para quem usa leitor de tela. Sem marcar na
       volta, ele fica dizendo "aberto" com o menu já fechado. */
    if (openDropdownTrigger) {
      openDropdownTrigger.setAttribute("aria-expanded", "false");
      openDropdownTrigger = null;
    }
  }

  function openDropdown(menu, trigger) {
    closeDropdown();
    if (trigger.hasAttribute("aria-expanded")) {
      trigger.setAttribute("aria-expanded", "true");
      openDropdownTrigger = trigger;
    }
    menu.classList.add("open"); /* precisa estar visível para ser medido */
    var rect = trigger.getBoundingClientRect();

    /* alinha pela direita do gatilho, mas nunca sai da janela */
    var left = rect.right - menu.offsetWidth;
    if (left < 8) left = 8;
    if (left + menu.offsetWidth > window.innerWidth - 8) {
      left = window.innerWidth - menu.offsetWidth - 8;
    }

    /* abre para baixo; se não couber, vira para cima */
    var top = rect.bottom + 6;
    if (top + menu.offsetHeight > window.innerHeight - 8) {
      top = rect.top - menu.offsetHeight - 6;
    }
    if (top < 8) top = 8;

    menu.style.left = left + "px";
    menu.style.top = top + "px";
    openDropdownEl = menu;
  }

  /* --------------------------------- toasts ------------------------------- */

  function dismissToast(toast) {
    toast.style.opacity = "0";
    toast.style.transform = "translateY(8px)";
    setTimeout(function () {
      toast.remove();
    }, 180);
  }

  function armToast(toast) {
    if (toast.dataset.armed) return;
    toast.dataset.armed = "1";
    var duration = parseInt(toast.dataset.duration || "5000", 10);
    if (duration > 0) setTimeout(function () { dismissToast(toast); }, duration);
  }

  function armToasts(root) {
    (root || document).querySelectorAll(".toast").forEach(armToast);
  }

  /** Cria um toast por código. Útil para respostas de HTMX.
   *  Montado nó a nó, sem innerHTML: `message` e `title` costumam vir do
   *  servidor com dados que o usuário digitou, e aqui eles nunca são
   *  interpretados como marcação. */
  function toast(message, tone, title) {
    var host = document.getElementById("toasts");
    if (!host) return;

    var el = document.createElement("div");
    el.className = "toast " + (tone || "ok");
    el.setAttribute("role", "status");

    var text = document.createElement("div");
    if (title) {
      var titleEl = document.createElement("div");
      titleEl.className = "tt";
      titleEl.textContent = title;
      text.appendChild(titleEl);
    }
    var messageEl = document.createElement("div");
    messageEl.className = "tm";
    messageEl.textContent = message;
    text.appendChild(messageEl);

    var close = document.createElement("button");
    close.className = "close";
    close.type = "button";
    close.setAttribute("aria-label", "Fechar");
    close.setAttribute("data-toast-close", "");
    close.textContent = "×";

    el.appendChild(text);
    el.appendChild(close);
    host.appendChild(el);
    armToast(el);
  }

  /* ------------------------- delegação de eventos ------------------------- */

  document.addEventListener("click", function (event) {
    var target = event.target;

    var themeBtn = target.closest("[data-theme-toggle]");
    if (themeBtn) {
      toggleTheme();
      return;
    }

    var opener = target.closest("[data-open-modal], [data-open-drawer]");
    if (opener) {
      var id = opener.getAttribute("data-open-modal") || opener.getAttribute("data-open-drawer");
      openOverlay(document.getElementById(id));
      return;
    }

    var closer = target.closest("[data-modal-close], [data-drawer-close]");
    if (closer) {
      closeOverlay(closer.closest("[data-modal], [data-drawer]"));
      return;
    }

    /* clique no fundo escuro fecha; clique dentro do diálogo, não */
    if (target.matches("[data-modal].open")) {
      closeOverlay(target);
      return;
    }

    var toastClose = target.closest("[data-toast-close]");
    if (toastClose) {
      dismissToast(toastClose.closest(".toast"));
      return;
    }

    var dropdownTrigger = target.closest("[data-dropdown-open]");
    if (dropdownTrigger) {
      event.stopPropagation();
      var menu = document.getElementById(dropdownTrigger.getAttribute("data-dropdown-open"));
      if (!menu) return;
      if (menu === openDropdownEl) {
        closeDropdown();
        return;
      }
      /* deixa o menu saber a que linha ele se refere */
      var label = dropdownTrigger.getAttribute("data-dropdown-title");
      var titleEl = menu.querySelector("[data-dropdown-title]");
      if (label && titleEl) titleEl.textContent = label;
      var row = dropdownTrigger.closest("tr");
      if (row) selectRow(row);
      openDropdown(menu, dropdownTrigger);
      return;
    }

    var accordionToggle = target.closest("[data-accordion-toggle]");
    if (accordionToggle) {
      var expanded = accordionToggle.getAttribute("aria-expanded") === "true";
      if (!expanded) fecharIrmas(accordionToggle);
      accordionToggle.setAttribute("aria-expanded", String(!expanded));
      var panel = accordionToggle.nextElementSibling;
      if (panel) panel.classList.toggle("open", !expanded);
      return;
    }

    /* Abas com painel. So a barra que tem `data-abas` troca painel: uma barra
       de navegacao continua sendo link, e o clique nela segue o `href`.

       A posicao sai do indice entre os irmaos da barra, e nao de um atributo
       no botao: assim a `Tab` continua servindo aos dois usos sem saber que
       painel existe. */
    var aba = target.closest("[data-abas] button");
    if (aba) {
      var barra = aba.closest("[data-abas]");
      var botoes = [].slice.call(barra.querySelectorAll("button"));
      var i = botoes.indexOf(aba);
      botoes.forEach(function (b, n) { b.classList.toggle("active", n === i); });
      var id = barra.getAttribute("data-abas");
      /* Os paineis sao irmaos da barra, e nao filhos: o CSS de `.tabs` desenha
         a borda de baixo, e um painel dentro dela herdaria essa borda. */
      var pai = barra.parentElement;
      if (pai) {
        botoes.forEach(function (_, n) {
          var painel = pai.querySelector('[id="' + id + "-" + n + '"]');
          if (painel) painel.classList.toggle("open", n === i);
        });
      }
      return;
    }

  var submenuToggle = target.closest("[data-submenu-toggle]");
    if (submenuToggle) {
      /* Com a barra recolhida os filhos estão escondidos, então abrir não
         mostraria nada. Abrir a barra é o que a pessoa queria de fato. */
      if (menuRecolhido()) recolherMenu(false);
      var isOpen = submenuToggle.getAttribute("aria-expanded") === "true";
      submenuToggle.setAttribute("aria-expanded", String(!isOpen));
      var sub = submenuToggle.nextElementSibling;
      if (sub) sub.classList.toggle("open", !isOpen);
      return;
    }

    var menuToggle = target.closest("[data-menu-toggle]");
    if (menuToggle) {
      abrirMenu(!appEl().classList.contains("menu-aberto"));
      return;
    }
    if (target.closest("[data-menu-fechar]")) {
      abrirMenu(false);
      return;
    }
    /* Escolher um módulo fecha a gaveta: em tela estreita ela cobre o conteúdo,
       e deixá-la aberta esconderia justamente a tela que acabou de abrir. */
    if (target.closest(".side a[href]") && appEl().classList.contains("menu-aberto")) {
      abrirMenu(false);
    }

    var sidebarToggle = target.closest("[data-sidebar-toggle]");
    if (sidebarToggle) {
      recolherMenu(!menuRecolhido());
      return;
    }

    if (openDropdownEl && !openDropdownEl.contains(target)) closeDropdown();

    var selectableRow = target.closest("tbody tr");
    if (selectableRow && selectableRow.closest("table")) selectRow(selectableRow);
  });

  /**
   * Fecha as outras secoes do mesmo grupo.
   *
   * O grupo pode atravessar varios acordeoes — no editor cada area e uma lista
   * propria, mas todas se comportam como uma so. Sem grupo declarado, cada
   * secao abre e fecha por conta.
   */
  function fecharIrmas(toggle) {
    var lista = toggle.closest("[data-accordion-group]");
    if (!lista) return;
    var grupo = lista.getAttribute("data-accordion-group");
    var seletor = '[data-accordion-group="' + grupo + '"] [data-accordion-toggle]';
    document.querySelectorAll(seletor).forEach(function (outro) {
      if (outro === toggle || outro.getAttribute("aria-expanded") !== "true") return;
      outro.setAttribute("aria-expanded", "false");
      var painel = outro.nextElementSibling;
      if (painel) painel.classList.remove("open");
    });
  }

  function appEl() {
    return document.querySelector(".app") || document.body;
  }

  /* ---------------------------- barra recolhida --------------------------- */

  function menuRecolhido() {
    return document.documentElement.classList.contains("side-collapsed");
  }

  /**
   * Recolhe a barra até virar uma faixa de ícones, ou traz de volta.
   *
   * A classe fica no <html>, e não no `.app`: assim o estado salvo pode ser
   * aplicado pelo script do <head>, antes da primeira pintura. No `.app` a
   * barra abriria larga e saltaria para estreita em toda navegação.
   */
  function recolherMenu(recolher) {
    document.documentElement.classList.toggle("side-collapsed", recolher);
    try {
      localStorage.setItem(MENU_KEY, recolher ? "1" : "0");
    } catch (e) {
      /* modo privativo: a escolha vale só para esta aba */
    }
    document.querySelectorAll("[data-sidebar-toggle]").forEach(function (b) {
      b.setAttribute("aria-expanded", String(!recolher));
      var rotulo = recolher ? "Expandir menu" : "Recolher menu";
      b.setAttribute("title", rotulo);
      b.setAttribute("aria-label", rotulo);
    });
  }

  /** Abre ou fecha a gaveta do menu (só existe em tela estreita). */
  function abrirMenu(abrir) {
    appEl().classList.toggle("menu-aberto", abrir);
    document.querySelectorAll("[data-menu-toggle]").forEach(function (b) {
      b.setAttribute("aria-expanded", String(abrir));
      b.setAttribute("title", abrir ? "Fechar menu" : "Abrir menu");
    });
  }

  function selectRow(row) {
    var body = row.parentElement;
    if (!body) return;
    body.querySelectorAll("tr.sel").forEach(function (r) { r.classList.remove("sel"); });
    row.classList.add("sel");
    var radio = row.querySelector('input[type="radio"]');
    if (radio) radio.checked = true;
  }

  /* Trocar de contexto no cabeçalho envia na hora: um botão "aplicar" ali seria
     um segundo clique para uma escolha que já foi feita. */
  document.addEventListener("change", function (event) {
    var campo = event.target.closest("[data-auto-enviar]");
    if (campo && campo.form) campo.form.submit();
  });

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") {
      closeAllOverlays();
      abrirMenu(false);
    }
  });

  window.addEventListener("resize", closeDropdown);
  window.addEventListener("scroll", closeDropdown, true);

  /* Conteúdo trocado pelo HTMX pode trazer toasts novos. */
  document.body.addEventListener("htmx:afterSwap", function (event) {
    armToasts(event.target);
  });

  armToasts(document);

  /* ------------------------------ interface ------------------------------- */

  window.MW5 = {
    setTheme: setTheme,
    toggleTheme: toggleTheme,
    currentTheme: currentTheme,
    openOverlay: function (id) { openOverlay(document.getElementById(id)); },
    closeOverlay: function (id) { closeOverlay(document.getElementById(id)); },
    toast: toast,
  };
})();

/* ==========================================================================
   Campo de arquivo: mostrar o nome escolhido e a miniatura da imagem.

   O input nativo fica invisivel, entao sem isto a pessoa nao teria retorno
   nenhum de que o arquivo entrou.
   ========================================================================== */
(function () {
  "use strict";

  document.addEventListener("change", function (event) {
    var input = event.target;
    if (!input.classList || !input.classList.contains("filefield-input")) return;

    var caixa = input.closest("[data-filefield]");
    if (!caixa) return;
    var saida = caixa.querySelector("[data-filefield-name]");
    var miniatura = caixa.querySelector("[data-filefield-thumb]");
    var arquivo = input.files && input.files[0];

    if (!arquivo) {
      saida.textContent = saida.getAttribute("data-vazio");
      saida.removeAttribute("data-escolhido");
      limparMiniatura(miniatura);
      return;
    }

    saida.textContent = arquivo.name;
    saida.setAttribute("data-escolhido", "");

    if (input.hasAttribute("data-filefield-preview") && /^image\//.test(arquivo.type)) {
      var url = URL.createObjectURL(arquivo);
      var img = document.createElement("img");
      img.alt = "";
      /* solta a URL depois que o navegador ja decodificou a imagem */
      img.addEventListener("load", function () { URL.revokeObjectURL(url); });
      img.src = url;
      limparMiniatura(miniatura);
      miniatura.appendChild(img);
    }
  });

  function limparMiniatura(miniatura) {
    if (!miniatura) return;
    var antiga = miniatura.querySelector("img");
    if (antiga) antiga.remove();
    var icone = miniatura.querySelector("svg");
    if (icone) icone.style.display = "";
  }
})();
