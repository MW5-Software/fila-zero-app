/* O olho da senha do banco.

   O campo nasce vazio e a senha NÃO está no HTML — a lista de empresas
   desenha um modal por linha, e embutir poria a credencial do Oracle de todos
   os clientes no código-fonte de cada carregamento da página. O olho pede a de
   UMA empresa a `/empresa/<pk>/senha`, que confere permissão, confere alcance
   e registra na trilha quem viu.

   Sem script o olho não aparece (é o próprio script que o liga) e o campo
   segue funcionando como sempre: escrever grava, em branco mantém. O que se
   perde é só a conferência.
*/
(function () {
  "use strict";

  function ligar(botao) {
    var campo = botao.parentElement.querySelector('input[name="senha"]');
    if (!campo) return;
    var pk = botao.getAttribute("data-ep-senha");
    var buscando = false;

    botao.setAttribute("aria-pressed", "false");

    function esconder() {
      campo.type = "password";
      botao.setAttribute("aria-pressed", "false");
      botao.title = "Ver a senha gravada";
    }

    function mostrar(senha) {
      // Só preenche se a pessoa não digitou nada: sobrescrever o que ela
      // acabou de escrever com a senha antiga apagaria a troca que ela estava
      // fazendo — e ela só veria o efeito depois de salvar.
      if (!campo.value) campo.value = senha;
      campo.type = "text";
      botao.setAttribute("aria-pressed", "true");
      botao.title = "Esconder";
    }

    botao.addEventListener("click", function () {
      if (campo.type === "text") { esconder(); return; }
      if (campo.value) { mostrar(campo.value); return; }
      if (buscando) return;
      buscando = true;
      botao.disabled = true;
      fetch("/empresa/" + encodeURIComponent(pk) + "/senha", {
        credentials: "same-origin",
        headers: {"X-Requested-With": "fetch"}
      }).then(function (r) {
        if (!r.ok) throw new Error(r.status);
        return r.json();
      }).then(function (dados) {
        mostrar(dados.senha || "");
      }).catch(function () {
        // Silencioso de propósito: quem não pode ver já foi recusado pela
        // rota, e um alerta na tela só diria o que o campo vazio já diz.
        botao.title = "Não foi possível buscar a senha";
      }).then(function () {
        buscando = false;
        botao.disabled = false;
      });
    });
  }

  function preparar() {
    Array.prototype.forEach.call(
      document.querySelectorAll("[data-ep-senha]"), ligar);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", preparar);
  } else {
    preparar();
  }
})();
