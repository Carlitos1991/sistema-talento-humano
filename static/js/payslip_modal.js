/* JS para cargar y controlar el modal usando las clases globales de style.css */

function openPayslipDetail(url) {
    // 1. Buscamos el HTML en el servidor
    fetch(url)
        .then(response => response.text())
        .then(html => {
            // 2. Inyectamos el HTML en el contenedor
            const container = document.getElementById('modal-container');
            container.innerHTML = html;

            // 3. Mostramos el modal quitando la clase 'hidden' global
            const backdrop = document.getElementById('payslipBackdrop');
            if (backdrop) {
                backdrop.classList.remove('hidden');
                document.body.classList.add('modal-open'); // Clase global para evitar scroll

                // 4. Activamos los botones
                initModalEvents(backdrop);
            }
        })
        .catch(error => console.error('Error cargando el modal del rol:', error));
}

function closeDetailModal() {
    const backdrop = document.getElementById('payslipBackdrop');
    if (backdrop) {
        // Volvemos a agregar la clase 'hidden' para ocultarlo
        backdrop.classList.add('hidden');
        document.body.classList.remove('modal-open');

        // Limpiamos el HTML para no dejar basura en el DOM
        setTimeout(() => {
            document.getElementById('modal-container').innerHTML = '';
        }, 300);
    }
}

function initModalEvents(backdrop) {
    // Cerrar al hacer clic fuera del contenedor blanco (en el overlay oscuro)
    backdrop.addEventListener('click', function (ev) {
        if (ev.target === backdrop) closeDetailModal();
    });

    // Delegación para botones de acción (Cerrar e Imprimir)
    const closeBtns = backdrop.querySelectorAll('[data-action="close"]');
    closeBtns.forEach(btn => btn.addEventListener('click', closeDetailModal));

    const printBtn = backdrop.querySelector('[data-action="print"]');
    if (printBtn) {
        printBtn.addEventListener('click', () => {
            // Aquí puedes lanzar un pop-up de impresión
            // Ej: window.open('tu_url_de_pdf', '_blank');
            window.print();
        });
    }
}

// Cerrar con la tecla Escape
document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') closeDetailModal();
});

// Exponer globalmente
window.openPayslipDetail = openPayslipDetail;