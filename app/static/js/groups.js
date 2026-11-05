(() => {
  "use strict";

  const form = document.getElementById("group-form");
  if (!form) {
    return;
  }

  const list = document.getElementById("block-list");
  const template = document.getElementById("block-template");
  const addButton = document.getElementById("add-block");
  const summary = document.getElementById("block-summary");
  const inicio = document.getElementById("hora-inicio");
  const fin = document.getElementById("hora-fin");

  const minutos = (valor) => {
    if (!valor) return null;
    const partes = valor.split(":");
    if (partes.length !== 2) return null;
    const horas = Number(partes[0]);
    const minutosHora = Number(partes[1]);
    if (!Number.isInteger(horas) || !Number.isInteger(minutosHora)) return null;
    return horas * 60 + minutosHora;
  };

  const filas = () => [...list.querySelectorAll(".block-row")];

  function renumerar() {
    filas().forEach((fila, indice) => {
      const etiqueta = fila.querySelector(".block-row__orden");
      if (etiqueta) etiqueta.textContent = String(indice + 1);
    });
  }

  function resumir() {
    const total = filas().reduce((suma, fila) => {
      const entrada = fila.querySelector('input[name="bloque_duracion"]');
      const valor = Number(entrada ? entrada.value : 0);
      return suma + (Number.isFinite(valor) ? valor : 0);
    }, 0);

    const objetivoInicio = minutos(inicio ? inicio.value : "");
    const objetivoFin = minutos(fin ? fin.value : "");
    const objetivo =
      objetivoInicio !== null && objetivoFin !== null
        ? objetivoFin - objetivoInicio
        : null;

    let mensaje = `Bloques: ${total} min`;
    if (objetivo !== null && objetivo > 0) {
      mensaje += ` · Horario: ${objetivo} min`;
      mensaje += total === objetivo ? " · Correcto" : " · Falta ajustar";
      summary.classList.toggle("block-summary--ok", total === objetivo);
      summary.classList.toggle("block-summary--warn", total !== objetivo);
    } else {
      summary.classList.remove("block-summary--ok", "block-summary--warn");
    }
    summary.textContent = mensaje;
  }

  function agregarFila() {
    const nodo = template.content.firstElementChild.cloneNode(true);
    nodo
      .querySelector(".block-row__remove")
      .addEventListener("click", () => {
        if (filas().length > 1) {
          nodo.remove();
          renumerar();
          resumir();
        }
      });
    nodo
      .querySelector('input[name="bloque_duracion"]')
      .addEventListener("input", resumir);
    list.appendChild(nodo);
    renumerar();
    resumir();
  }

  filas().forEach((fila) => {
    fila
      .querySelector(".block-row__remove")
      .addEventListener("click", () => {
        if (filas().length > 1) {
          fila.remove();
          renumerar();
          resumir();
        }
      });
    fila
      .querySelector('input[name="bloque_duracion"]')
      .addEventListener("input", resumir);
  });

  if (!filas().length) {
    agregarFila();
  }

  addButton.addEventListener("click", agregarFila);
  if (inicio) inicio.addEventListener("input", resumir);
  if (fin) fin.addEventListener("input", resumir);

  renumerar();
  resumir();
})();
