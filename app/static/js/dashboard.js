const formatoMoneda = new Intl.NumberFormat("es-MX", {
  style: "currency",
  currency: "MXN",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const COLORES = [
  "#4f46e5",
  "#06b6d4",
  "#10b981",
  "#f59e0b",
  "#f43f5e",
  "#00687a",
];

function mostrarResumen(texto) {
  const resumen = document.getElementById("recaudacion-resumen");
  if (resumen !== null) {
    resumen.textContent = texto;
  }
}

async function cargarRecaudacion() {
  const canvas = document.getElementById("recaudacion-chart");
  if (canvas === null) {
    return;
  }

  try {
    if (typeof Chart === "undefined") {
      throw new Error("Chart.js no está disponible.");
    }

    const respuesta = await fetch("/dashboard/recaudacion", {
      headers: { Accept: "application/json" },
      cache: "no-store",
    });
    if (!respuesta.ok) {
      throw new Error("La recaudación no está disponible.");
    }

    const datos = await respuesta.json();
    const sucursales = Array.isArray(datos.sucursales)
      ? datos.sucursales
      : [];
    const totalCentavos = Number(datos.total_centavos) || 0;

    const etiquetas = sucursales.map((sucursal) => sucursal.nombre);
    const valores = sucursales.map(
      (sucursal) => (Number(sucursal.total_centavos) || 0) / 100,
    );
    const colores = sucursales.map(
      (_sucursal, indice) => COLORES[indice % COLORES.length],
    );

    new Chart(canvas.getContext("2d"), {
      type: "bar",
      data: {
        labels: etiquetas,
        datasets: [
          {
            label: "Recaudación",
            data: valores,
            backgroundColor: colores,
            borderRadius: 8,
            borderSkipped: false,
            maxBarThickness: 64,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 300 },
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (contexto) =>
                formatoMoneda.format(Number(contexto.parsed.y) || 0),
            },
          },
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: {
              color: "#464555",
              font: { family: "Inter", size: 12 },
            },
          },
          y: {
            beginAtZero: true,
            grid: { color: "#e2e8f0" },
            ticks: {
              color: "#464555",
              font: { family: "Inter", size: 12 },
              callback: (valor) => formatoMoneda.format(Number(valor) || 0),
            },
          },
        },
      },
    });

    if (sucursales.length === 0 || totalCentavos === 0) {
      mostrarResumen("Sin cobros registrados en la semana actual.");
      return;
    }

    const detalle = sucursales
      .map(
        (sucursal) =>
          `${sucursal.nombre}: ${formatoMoneda.format(
            (Number(sucursal.total_centavos) || 0) / 100,
          )}`,
      )
      .join(" · ");
    mostrarResumen(
      `Total semanal: ${formatoMoneda.format(totalCentavos / 100)}. ${detalle}`,
    );
  } catch (_error) {
    mostrarResumen(
      "No se pudo cargar la gráfica. Recarga la página para intentarlo de nuevo.",
    );
  }
}

cargarRecaudacion();
