/* ==========================================================================
   MW5 Admin — recorte de imagem.

   A cola entre o Cropper.js e o formulário. Marcação esperada:

     <input type="file" data-recorte="foto" accept="image/*">
     <div data-recorte-palco="foto" hidden><img data-recorte-alvo="foto"></div>
     <input type="hidden" name="recorte" id="foto">

   Por delegação no documento, como o resto do mw5.js: nada aqui exige
   inicialização por tela, e o que vier por HTMX funciona sozinho.

   O recorte sai em WebP a 512×512 — tamanho de sobra para um avatar, e o
   servidor confere os bytes de novo. O que sai daqui é dado de entrada como
   qualquer outro.
   ========================================================================== */
(function () {
  "use strict";

  var LADO = 512;
  var recortadores = {};

  function palco(id) {
    return document.querySelector('[data-recorte-palco="' + id + '"]');
  }

  function alvo(id) {
    return document.querySelector('[data-recorte-alvo="' + id + '"]');
  }

  function abrir(id, arquivo) {
    var imagem = alvo(id);
    var caixa = palco(id);
    if (!imagem || !caixa || !window.Cropper) return;

    var leitor = new FileReader();
    leitor.onload = function (evento) {
      imagem.src = evento.target.result;
      caixa.hidden = false;
      if (recortadores[id]) recortadores[id].destroy();
      recortadores[id] = new window.Cropper(imagem, {
        aspectRatio: 1,
        viewMode: 1,
        autoCropArea: 1,
        dragMode: "move",
        background: false
      });
    };
    leitor.readAsDataURL(arquivo);
  }

  function gravar(id) {
    var destino = document.getElementById(id);
    var recortador = recortadores[id];
    if (!destino || !recortador) return;
    var tela = recortador.getCroppedCanvas({ width: LADO, height: LADO });
    if (!tela) return;
    destino.value = tela.toDataURL("image/webp", 0.9);
  }

  document.addEventListener("change", function (evento) {
    var campo = evento.target.closest
      ? evento.target.closest("[data-recorte]")
      : null;
    if (!campo || !campo.files || !campo.files.length) return;
    abrir(campo.getAttribute("data-recorte"), campo.files[0]);
  });

  /* Grava no envio, e nao a cada arrastada: o `canvas` custa caro e a pessoa
     ainda esta enquadrando. */
  document.addEventListener("submit", function (evento) {
    var form = evento.target;
    var campo = form.querySelector ? form.querySelector("[data-recorte]") : null;
    if (campo) gravar(campo.getAttribute("data-recorte"));
  });
})();
