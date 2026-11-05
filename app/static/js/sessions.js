document.addEventListener("submit", (event) => {
  const form = event.target;
  if (!(form instanceof HTMLFormElement)) {
    return;
  }

  const mensaje = form.dataset.confirmar;
  if (mensaje && !window.confirm(mensaje)) {
    event.preventDefault();
  }
});
