/* A altura do quadro da prévia segue o relatório (05/10/2026).

   O relatório aparece na tela dentro de um <iframe> — é a mesma página do
   PDF, sem a impressão —, e um quadro não cresce sozinho com o conteúdo: sem
   este ajuste ele teria a altura fixa da folha e uma barra de rolagem dentro
   da página, que já rola. A prévia é da mesma origem, e por isso a altura do
   documento de dentro pode ser lida daqui. Sem script, o quadro fica com a
   altura fixa da folha e rola por dentro: o relatório continua inteiro. */
(function () {
  function ajustar(quadro) {
    try {
      var doc = quadro.contentDocument;
      if (doc && doc.documentElement) {
        // Zera antes de medir: a altura do documento de dentro nunca é menor
        // que a do próprio quadro, e sem isto ele só crescia — com o
        // relatório de mídias (~550px), o quadro ficava nos 1100px da folha.
        quadro.style.height = "0px";
        quadro.style.height = doc.documentElement.scrollHeight + "px";
      }
    } catch (erro) {
      /* Outra origem: o quadro fica com a altura da folha. */
    }
  }

  document.querySelectorAll("iframe.relatorio-quadro").forEach(function (quadro) {
    quadro.addEventListener("load", function () { ajustar(quadro); });
    if (quadro.contentDocument && quadro.contentDocument.readyState === "complete") {
      ajustar(quadro);
    }
    window.addEventListener("resize", function () { ajustar(quadro); });
  });
})();
