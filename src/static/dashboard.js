function toggleRoof(button) {
    const row = button.closest(".field-row");
    const status = row.querySelector(".field-status");

    button.disabled = true;
    button.classList.add("disabled");

    if (status.classList.contains("status-open")) {
        status.className = "field-status status-closing";
        status.textContent = "Cerrando...";
        button.textContent = "Cierre manual";

        setTimeout(() => {
            status.className = "field-status status-closed";
            status.textContent = "Cerrado";
            button.textContent = "Apertura manual";
            button.disabled = false;
            button.classList.remove("disabled");
        }, 3000);

    } else if (status.classList.contains("status-closed")) {
        status.className = "field-status status-opening";
        status.textContent = "Abriendo...";
        button.textContent = "Apertura manual";

        setTimeout(() => {
            status.className = "field-status status-open";
            status.textContent = "Abierto";
            button.textContent = "Cierre manual";
            button.disabled = false;
            button.classList.remove("disabled");
        }, 3000);
    }
}
