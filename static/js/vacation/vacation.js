/* apps/vacation/static/js/vacation/vacation.js */

function open_modal(url) {
    const modalContainer = document.getElementById('popupPeriod');

    fetch(url)
        .then(response => {
            if (!response.ok) throw new Error('Error de red');
            return response.text();
        })
        .then(html => {
            // 1. Inyectamos el HTML del formulario
            modalContainer.innerHTML = html;

            // 2. Mostramos el modal agregando la clase CSS
            modalContainer.classList.add('open');

            // 3. Reactivar funcionalidad del botón "Cerrar" (X y Cancelar)
            // Buscamos todos los botones con data-dismiss="modal"
            const closeButtons = modalContainer.querySelectorAll('[data-dismiss="modal"]');
            closeButtons.forEach(btn => {
                btn.onclick = function () {
                    close_modal(); // Llamamos a nuestra función de cerrar
                };
            });

            // Opcional: Cerrar si clickean fuera del modal (en el fondo oscuro)
            modalContainer.onclick = function (event) {
                if (event.target === modalContainer) {
                    close_modal();
                }
            }
        })
        .catch(error => console.error('Error cargando modal:', error));
}

function close_modal() {
    const modalContainer = document.getElementById('popupPeriod');
    modalContainer.classList.remove('open');
    modalContainer.innerHTML = ''; // Limpiamos el contenido
}