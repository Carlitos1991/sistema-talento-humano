document.addEventListener('DOMContentLoaded', () => {
    // Inicializar buscador en tiempo real
    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
        searchInput.addEventListener('keyup', function() {
            const searchTerm = this.value.toLowerCase();
            const rows = document.querySelectorAll('.table tbody tr');

            rows.forEach(row => {
                const text = row.textContent.toLowerCase();
                row.style.display = text.includes(searchTerm) ? '' : 'none';
            });
        });
    }
});

// Función para abrir el modal (AJAX)
function openPayrollModal(url) {
    let modalContainer = document.getElementById('modal-root');
    // Si no existe el contenedor de modales en el DOM, lo creamos dinámicamente
    if (!modalContainer) {
        modalContainer = document.createElement('div');
        modalContainer.id = 'modal-root';
        document.body.appendChild(modalContainer);
    }

    fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
    .then(response => response.text())
    .then(html => {
        // inyectamos el HTML recibido sin mostrar mensajes previos
        if (modalContainer) modalContainer.innerHTML = html;
        const modalElement = document.getElementById('payrollModal');
        // Si Bootstrap está disponible, usar su modal; si no, mostrar con estilos propios
        if (modalElement) {
            if (typeof bootstrap !== 'undefined' && bootstrap.Modal) {
                const bsModal = new bootstrap.Modal(modalElement);
                bsModal.show();
            } else {
                // Fallback: activar el modal por CSS/ARIA y bloquear scroll
                modalElement.classList.add('show');
                modalElement.style.display = 'block';
                modalElement.setAttribute('aria-hidden', 'false');
                document.body.classList.add('modal-open');

                // Conectar botones con atributo data-bs-dismiss al cierre personalizado
                modalElement.querySelectorAll('[data-bs-dismiss]').forEach(btn => {
                    btn.addEventListener('click', () => {
                        // limpiar contenido del modal-root y quitar clase
                        if (modalContainer) modalContainer.innerHTML = '';
                        document.body.classList.remove('modal-open');
                    });
                });
            }
        } else {
            console.warn('openPayrollModal: modal element #payrollModal no encontrado en el HTML inyectado');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        // Mostrar error simple sin modal de carga previo
        try { Swal.fire('Error', 'No se pudo cargar el formulario.', 'error'); } catch(e) { alert('No se pudo cargar el formulario.'); }
    });
}

// Cerrar modal inyectado (parcialmente compatible con otros modales)
function closePayrollModal() {
    const modalRoot = document.getElementById('modal-root');
    if (modalRoot) modalRoot.innerHTML = '';
    document.body.classList.remove('modal-open');
}

// Enviar formulario (AJAX)
function submitPayrollForm(event) {
    event.preventDefault();
    const form = event.target;
    const formData = new FormData(form);

    // Limpiar validaciones visuales
    form.querySelectorAll('.is-invalid').forEach(el => el.classList.remove('is-invalid'));

    fetch(form.action, {
        method: 'POST',
        body: formData,
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            const modalElement = document.getElementById('payrollModal');
            // Usar bootstrap si está cargado; si no, aplicar fallback seguro
            if (typeof bootstrap !== 'undefined' && bootstrap.Modal && modalElement) {
                const bsModal = bootstrap.Modal.getInstance(modalElement);
                if (bsModal && typeof bsModal.hide === 'function') bsModal.hide();
            } else {
                const modalRoot = document.getElementById('modal-root');
                if (modalRoot) modalRoot.innerHTML = '';
                document.body.classList.remove('modal-open');
            }

            Swal.fire({
                icon: 'success',
                title: '¡Guardado!',
                text: data.message,
                timer: 1500,
                showConfirmButton: false
            }).then(() => {
                // Refresh only the table body via AJAX (no full reload)
                fetch(window.location.pathname + window.location.search, {
                    headers: { 'X-Requested-With': 'XMLHttpRequest' }
                })
                .then(resp => resp.text())
                .then(html => {
                    const tbody = document.querySelector('.managed-table tbody');
                    if (tbody) tbody.innerHTML = html;

                    // Re-initialize table-manager if present
                    const table = document.querySelector('.managed-table');
                    if (table && table._tableManager) {
                        table._tableManager.originalRows = Array.from(tbody.querySelectorAll('tr'));
                        table._tableManager.currentRows = [...table._tableManager.originalRows];
                        if (typeof table._tableManager.render === 'function') {
                            table._tableManager.render();
                        }
                    }
                })
                .catch(err => {
                    console.error('Error refrescando la tabla:', err);
                    // Fallback: recargar la página si algo falla
                    location.reload();
                });
            });
        } else {
            // Manejo de errores de validación
            if (data.errors) {
                let msg = '';
                for (const [key, value] of Object.entries(data.errors)) {
                    msg += `${value}\n`;
                    const input = form.querySelector(`[name="${key}"]`);
                    if(input) input.classList.add('is-invalid');
                }
                Swal.fire('Atención', msg, 'warning');
            }
        }
    })
    .catch(error => {
        console.error('Error:', error);
        Swal.fire('Error', 'Error de comunicación con el servidor.', 'error');
    });
}

// Eliminar constante
function deleteConstant(url, name) {
    Swal.fire({
        title: `¿Eliminar ${name}?`,
        text: "Esto podría afectar cálculos de nómina futuros.",
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#d33',
        cancelButtonColor: '#3085d6',
        confirmButtonText: 'Sí, eliminar',
        cancelButtonText: 'Cancelar'
    }).then((result) => {
        if (result.isConfirmed) {
            const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
            fetch(url, {
                method: 'POST',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': csrfToken
                }
            })
            .then(res => res.json())
            .then(data => {
                if (data.status === 'success') {
                    Swal.fire('Eliminado', data.message, 'success').then(() => location.reload());
                } else {
                    Swal.fire('Error', data.message, 'error');
                }
            });
        }
    })
}

// Toggle: mostrar/ocultar inactivos en la lista de constantes (AJAX)
function toggleInactiveConstants(showInactive) {
    fetch(`?show_inactive=${showInactive}`, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
        .then(response => response.text())
        .then(html => {
            const tbody = document.querySelector('.managed-table tbody');
            if (tbody) tbody.innerHTML = html;

            // Re-inicializar table-manager si existe
            const table = document.querySelector('.managed-table');
            if (table && table._tableManager) {
                table._tableManager.originalRows = Array.from(tbody.querySelectorAll('tr'));
                table._tableManager.currentRows = [...table._tableManager.originalRows];
                if (typeof table._tableManager.render === 'function') table._tableManager.render();
            }
        })
        .catch(err => console.error('Error cargando constantes inactivas:', err));
}