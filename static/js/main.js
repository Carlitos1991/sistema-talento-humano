/**
 * SIGETH - GESTOR CENTRALIZADO (MODALES, AJAX, FILTROS)
 * Este archivo es el motor del sistema.
 */

// 1. SEGURIDAD: OBTENCIÓN DEL TOKEN CSRF (Indispensable para Django)
const getCSRF = () => {
    const el = document.querySelector('[name=csrfmiddlewaretoken]');
    if (el) return el.value;
    const cookies = document.cookie.split(';');
    for (let c of cookies) {
        c = c.trim();
        if (c.indexOf('csrftoken=') === 0) return decodeURIComponent(c.substring(10));
    }
    return '';
};

// 2. MODALES ESTÁTICOS (Para los que ya están en el HTML como el de "Nuevo")
window.openModal = function (id) {
    const modal = document.getElementById(id);
    if (modal) {
        modal.classList.remove('hidden');
        document.body.classList.add('no-scroll');
        // Inicializar Select2 si hay dentro
        $(modal).find('select').select2({
            width: '100%',
            dropdownParent: $(modal)
        });
    } else {
        console.error("No se encontró el modal con ID: " + id);
    }
};

// 3. MODALES DINÁMICOS (Para los que cargan datos del servidor como "Editar")
window.openAjaxModal = function (url, callback = null) {
    fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
        .then(response => {
            if (!response.ok) throw new Error('Error al cargar modal');
            return response.text();
        })
        .then(html => {
            const root = document.getElementById('modal-root');
            root.innerHTML = html;

            const modal = root.querySelector('.modal-overlay');
            if (modal) {
                modal.classList.remove('hidden');
                document.body.classList.add('no-scroll');

                // Auto-inicializar Select2 en el contenido inyectado
                $(modal).find('select').select2({
                    width: '100%',
                    dropdownParent: $(modal)
                });
            }
            if (callback) callback(root);
        })
        .catch(error => {
            Swal.fire('Error', 'No se pudo cargar el formulario.', 'error');
        });
};

// 4. CIERRE DE MODALES (Universal)
window.closeModal = function (id = null) {
    if (id) {
        const modal = document.getElementById(id);
        if (modal) modal.classList.add('hidden');
    }
    // Si se cargó por Ajax, limpiamos el root
    const root = document.getElementById('modal-root');
    if (root) root.innerHTML = '';

    document.body.classList.remove('no-scroll');
};

// Alias para compatibilidad con botones que digan "closeAjaxModal"
window.closeAjaxModal = window.closeModal;

// 5. ENVÍO DE FORMULARIOS (Maneja validaciones de Django y éxito con SweetAlert)
window.submitAjaxForm = function (event, successCallback = null) {
    event.preventDefault();
    const form = event.target;
    const formData = new FormData(form);

    // Limpiar errores visuales previos
    form.querySelectorAll('.is-invalid').forEach(el => el.classList.remove('is-invalid'));

    fetch(form.action, {
        method: 'POST',
        body: formData,
        headers: {'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': getCSRF()}
    })
        .then(async response => {
            const contentType = response.headers.get('content-type');

            // Si Django devuelve HTML, es porque el formulario falló (errores de validación)
            if (contentType && contentType.includes('text/html')) {
                const html = await response.text();
                // Si el form es de un modal-root, lo actualizamos
                const root = document.getElementById('modal-root');
                if (root && root.innerHTML !== "") {
                    root.innerHTML = html;
                } else {
                    // Si es un modal estático, podrías necesitar otra lógica o recargar el div
                    console.warn("Validación fallida en modal estático.");
                }
                Swal.fire('Atención', 'Corrija los errores en el formulario.', 'warning');
                return;
            }

            // Si devuelve JSON, la operación fue exitosa
            const data = await response.json();
            if (data.status === 'success' || data.success) {
                window.closeModal();
                Swal.fire({
                    icon: 'success',
                    title: '¡Operación Exitosa!',
                    text: data.message,
                    timer: 1500,
                    showConfirmButton: false
                }).then(() => {
                    if (successCallback) successCallback(); else location.reload();
                });
            } else {
                Swal.fire('Error', data.message || 'Error al procesar la solicitud.', 'error');
            }
        })
        .catch(() => Swal.fire('Error', 'Problema de conexión con el servidor.', 'error'));
};

// 6. ELIMINACIÓN GENÉRICA
window.deleteRecordAjax = function (url, itemName) {
    Swal.fire({
        title: `¿Eliminar ${itemName}?`,
        text: "Esta acción no se puede deshacer.",
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#d33',
        confirmButtonText: 'Sí, eliminar',
        cancelButtonText: 'Cancelar'
    }).then((result) => {
        if (result.isConfirmed) {
            fetch(url, {
                method: 'POST',
                headers: {'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': getCSRF()}
            })
                .then(res => res.json())
                .then(data => {
                    if (data.success) {
                        Swal.fire('Eliminado', data.message, 'success').then(() => location.reload());
                    } else {
                        Swal.fire('Error', data.message, 'error');
                    }
                });
        }
    });
};

// 7. FILTROS DE TABLA (Busca automáticamente en las filas de la tabla)
window.initGlobalTableFilters = function (root) {
    const container = typeof root === 'string' ? document.querySelector(root) : root;
    if (!container || container.dataset.filterBound === '1') return;

    const searchInput = container.querySelector('[data-filter-search]');
    const rowSelector = '[data-filter-row]'; // Asegúrate de que tus <tr> tengan este atributo

    if (searchInput) {
        searchInput.addEventListener('input', function () {
            const term = this.value.toLowerCase();
            const rows = container.querySelectorAll(rowSelector);

            rows.forEach(row => {
                const text = row.innerText.toLowerCase();
                row.style.display = text.includes(term) ? '' : 'none';
            });
        });
    }
    container.dataset.filterBound = '1';
};

// Ejecutar filtros al cargar la página
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-global-table-filter]').forEach(container => {
        window.initGlobalTableFilters(container);
    });
});