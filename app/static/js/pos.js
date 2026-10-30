(() => {
  "use strict";

  const roster = document.querySelector(".roster[data-sesion-id]");
  if (!roster) {
    return;
  }

  const sesionId = Number(roster.dataset.sesionId);
  if (!Number.isInteger(sesionId) || sesionId <= 0) {
    return;
  }

  const toast = document.getElementById("pos-toast");
  const ticketFrame = document.getElementById("ticket-frame");
  const methodButtons = [...document.querySelectorAll("[data-metodo]")];
  const movimientoReducido = window.matchMedia(
    "(prefers-reduced-motion: reduce)",
  ).matches;

  let metodo = "efectivo";
  let cobrando = false;
  let toastTimer = null;

  const tarjetas = () => [...roster.querySelectorAll(".student-card")];
  const pendientes = () =>
    tarjetas().filter((card) => card.dataset.estado === "pendiente");
  const enfocables = () =>
    tarjetas().filter((card) => card.tabIndex >= 0);

  function nombreMetodo(valor) {
    return valor === "transferencia" ? "Transferencia" : "Efectivo";
  }

  function mostrarToast(mensaje, tipo = "success") {
    if (!toast) {
      return;
    }
    toast.textContent = mensaje;
    toast.className = `toast toast--${tipo}`;
    toast.hidden = false;
    window.clearTimeout(toastTimer);
    toastTimer = window.setTimeout(() => {
      toast.hidden = true;
    }, 3500);
  }

  function actualizarMetodo(nuevoMetodo) {
    metodo = nuevoMetodo;
    for (const button of methodButtons) {
      const activo = button.dataset.metodo === metodo;
      button.classList.toggle("is-active", activo);
      button.setAttribute("aria-pressed", String(activo));
    }
  }

  function enfocar(card, desplazar = true) {
    if (!card) {
      return;
    }
    card.focus({ preventScroll: !desplazar });
    if (desplazar) {
      card.scrollIntoView({
        block: "nearest",
        behavior: movimientoReducido ? "auto" : "smooth",
      });
    }
  }

  function primerPendiente() {
    return pendientes()[0] || null;
  }

  function siguientePendienteDesde(card) {
    const todas = tarjetas();
    const indice = todas.indexOf(card);
    const despues = todas
      .slice(indice + 1)
      .find((item) => item.dataset.estado === "pendiente");
    return despues || primerPendiente();
  }

  function actualizarResumen(resumen) {
    if (!resumen) {
      return;
    }
    const textos = {
      pendientes: `${resumen.pendientes} pendientes`,
      pagados: `${resumen.pagados} pagados`,
      deudas: `${resumen.deudas} deudas`,
      faltas: `${resumen.faltas} faltas`,
    };
    for (const [clave, texto] of Object.entries(textos)) {
      const nodo = document.querySelector(`[data-counter="${clave}"]`);
      if (nodo) {
        nodo.textContent = texto;
      }
    }
  }

  function imprimirTicket(pago) {
    if (!ticketFrame || !pago || !Number.isInteger(pago.id)) {
      return;
    }
    ticketFrame.src = `/pos/tickets/${encodeURIComponent(pago.id)}?auto=1`;
  }

  function marcarPagado(card, alumno, pago) {
    card.dataset.estado = "pagado";
    card.dataset.folio = pago.folio;
    card.removeAttribute("role");
    card.removeAttribute("aria-label");
    card.removeAttribute("aria-busy");
    card.tabIndex = -1;
    card.classList.remove("student-card--cobrando");
    card.classList.add("student-card--pagado");

    const pill = card.querySelector(".pill");
    if (pill) {
      pill.className = "pill pill--pagado";
      pill.textContent = alumno?.etiqueta || "Pagado";
    }

    window.setTimeout(() => {
      card.classList.remove("student-card--pagado");
    }, 1200);
  }

  function mensajeError(data, status) {
    if (typeof data.detail === "string") {
      return data.detail;
    }
    if (Array.isArray(data.detail)) {
      return "Datos de cobro inválidos.";
    }
    return `No se pudo cobrar (${status}).`;
  }

  async function cobrar(card, metodoSolicitado = metodo) {
    if (!card || cobrando) {
      return;
    }
    if (card.dataset.estado !== "pendiente") {
      mostrarToast("Ese alumno no está pendiente de cobro.", "error");
      return;
    }

    const alumnoId = Number(card.dataset.alumnoId);
    if (!Number.isInteger(alumnoId) || alumnoId <= 0) {
      return;
    }

    cobrando = true;
    actualizarMetodo(metodoSolicitado);
    card.classList.add("student-card--cobrando");
    card.setAttribute("aria-busy", "true");

    try {
      const response = await fetch("/pos/cobrar", {
        method: "POST",
        credentials: "same-origin",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          sesion_id: sesionId,
          alumno_id: alumnoId,
          metodo: metodoSolicitado,
        }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(mensajeError(data, response.status));
      }
      if (!data.pago || !data.resumen) {
        throw new Error(
          "El servidor no confirmó el cobro. Revisa la lista.",
        );
      }

      const siguiente = siguientePendienteDesde(card);
      marcarPagado(card, data.alumno, data.pago);
      actualizarResumen(data.resumen);
      mostrarToast(
        `${data.pago.folio} · ${data.pago.alumno} · ${data.pago.monto} · ${nombreMetodo(data.pago.metodo)}`,
        "success",
      );
      imprimirTicket(data.pago);

      if (siguiente && siguiente !== card) {
        enfocar(siguiente);
      } else if (document.activeElement === card) {
        card.blur();
      }
    } catch (error) {
      card.classList.remove("student-card--cobrando");
      card.removeAttribute("aria-busy");
      let mensaje = "No se pudo cobrar.";
      if (error instanceof TypeError) {
        mensaje = "No se pudo conectar con el servidor local.";
      } else if (error instanceof Error) {
        mensaje = error.message;
      }
      mostrarToast(mensaje, "error");
    } finally {
      cobrando = false;
    }
  }

  function mover(direccion) {
    const disponibles = enfocables();
    if (!disponibles.length) {
      return;
    }
    const actual = document.activeElement;
    const indice = disponibles.indexOf(actual);
    let siguiente;
    if (indice === -1) {
      siguiente =
        direccion > 0 ? disponibles[0] : disponibles[disponibles.length - 1];
    } else {
      siguiente =
        disponibles[
          (indice + direccion + disponibles.length) % disponibles.length
        ];
    }
    enfocar(siguiente);
  }

  for (const card of tarjetas()) {
    if (card.dataset.estado === "pendiente") {
      card.tabIndex = 0;
      card.setAttribute("role", "button");
      card.setAttribute(
        "aria-label",
        `Cobrar a ${card.querySelector("h3")?.textContent || "alumno"}`,
      );
    } else {
      card.tabIndex = -1;
    }

    card.addEventListener("click", () => {
      if (card.dataset.estado === "pendiente") {
        cobrar(card);
      }
    });

    card.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        cobrar(card);
      }
    });
  }

  for (const button of methodButtons) {
    button.addEventListener("click", () => {
      actualizarMetodo(button.dataset.metodo);
      mostrarToast(`Método: ${nombreMetodo(metodo)}.`, "info");
    });
  }

  document.addEventListener("keydown", (event) => {
    const activo = document.activeElement;
    const etiqueta = activo?.tagName;
    const enCampo =
      etiqueta === "INPUT" ||
      etiqueta === "TEXTAREA" ||
      etiqueta === "SELECT";
    const esCobro =
      event.key === " " ||
      event.code === "Space" ||
      event.key === "F1" ||
      event.key === "F2";
    if (enCampo || (event.repeat && esCobro)) {
      return;
    }

    const cardActivo =
      activo instanceof HTMLElement
        ? activo.closest(".student-card")
        : null;

    if (event.key === "F1" || event.key === "F2") {
      event.preventDefault();
      const nuevoMetodo =
        event.key === "F1" ? "efectivo" : "transferencia";
      actualizarMetodo(nuevoMetodo);
      const card = cardActivo || primerPendiente();
      if (card) {
        cobrar(card, nuevoMetodo);
      } else {
        mostrarToast("No hay alumnos pendientes.", "info");
      }
      return;
    }

    if (event.key === " " || event.code === "Space") {
      if (etiqueta === "BUTTON" || etiqueta === "A") {
        return;
      }
      event.preventDefault();
      const card = cardActivo || primerPendiente();
      if (card) {
        cobrar(card, metodo);
      } else {
        mostrarToast("No hay alumnos pendientes.", "info");
      }
      return;
    }

    if (event.key === "ArrowRight" || event.key === "ArrowDown") {
      event.preventDefault();
      mover(1);
      return;
    }

    if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
      event.preventDefault();
      mover(-1);
      return;
    }

    if (event.key === "Escape") {
      event.preventDefault();
      actualizarMetodo("efectivo");
      if (activo instanceof HTMLElement) {
        activo.blur();
      }
      mostrarToast("Selección limpia.", "info");
    }
  });

  actualizarMetodo("efectivo");
  const inicial = primerPendiente();
  if (inicial) {
    enfocar(inicial, false);
  }
})();
