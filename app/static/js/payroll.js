document.addEventListener("DOMContentLoaded", () => {
  const todos = document.querySelector("[data-seleccionar-todos]");
  const casillas = Array.from(document.querySelectorAll("[data-marca-checkbox]"));
  if (!todos || casillas.length === 0) {
    return;
  }

  const sincronizar = () => {
    const marcadas = casillas.filter((casilla) => casilla.checked).length;
    todos.checked = marcadas === casillas.length;
    todos.indeterminate = marcadas > 0 && marcadas < casillas.length;
  };

  todos.addEventListener("change", () => {
    for (const casilla of casillas) {
      casilla.checked = todos.checked;
    }
  });

  for (const casilla of casillas) {
    casilla.addEventListener("change", sincronizar);
  }

  sincronizar();
});
