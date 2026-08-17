/**
 * MAIN.JS - GESTOR CENTRALIZADO DE AJAX Y MODALES PARA TODO SIGETH
 */

// 1. OBTENCIÓN ROBUSTA DEL TOKEN CSRF
const getCSRF = () => {
    const el = document.querySelector('[name=csrfmiddlewaretoken]');
    if (el) return el.value;
    const name = 'csrftoken=';
    const cookies = document.cookie.split(';');
    for (let c of cookies) {
        c = c.trim();
        if (c.indexOf(name) === 0) return decodeURIComponent(c.substring(name.length));
    }
    return '';
};

// 2. APERTURA DE MODALES DINÁMICOS
window.openAjaxModal = function (url, modalOverlaySelector = '.modal-overlay', callback = null) {
    fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
        .then(response => response.text())
        .then(html => {
            const root = document.getElementById('modal-root');
            if (!root) return;

            root.innerHTML = html;
            document.body.classList.add('modal-open');

            const overlay = document.querySelector(modalOverlaySelector);
            if (overlay) {
                $(overlay).find('select').select2({
                    width: '100%',
                    dropdownParent: $(overlay),
                    allowClear: true
                });
            }

            $(root).find('input[type="text"]').addClass('input-field');
            window.initSharedFormInteractions(root);

            if (callback) {
                if (typeof callback === 'function') {
                    callback(root);
                } else if (typeof window[callback] === 'function') {
                    window[callback](root);
                }
            }
        })
        .catch(error => {
            console.error(error);
            Swal.fire('Error', 'No se pudo cargar la vista.', 'error');
        });
};

// 3. CIERRE DE MODALES DINÁMICOS
window.closeAjaxModal = function () {
    const root = document.getElementById('modal-root');
    if (root) root.innerHTML = '';
    document.body.classList.remove('modal-open');
};

// 4. ENVÍO ESTANDARIZADO DE FORMULARIOS
window.submitAjaxForm = function (event, successCallback = null) {
    event.preventDefault();
    const form = event.target;
    const formData = new FormData(form);

    form.querySelectorAll('.is-invalid').forEach(el => el.classList.remove('is-invalid'));

    fetch(form.action, {
        method: 'POST',
        body: formData,
        headers: {'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': getCSRF()}
    })
        .then(async response => {
            const contentType = response.headers.get('content-type');

            if (contentType && contentType.includes('text/html')) {
                const html = await response.text();
                document.getElementById('modal-root').innerHTML = html;
                window.initSharedFormInteractions(document.getElementById('modal-root'));
                Swal.fire('Atención', 'Revise los campos del formulario.', 'warning');
                return;
            }

            const data = await response.json();
            if (data.status === 'success' || data.success) {
                window.closeAjaxModal();
                Swal.fire({
                    icon: 'success', title: '¡Operación Exitosa!', text: data.message,
                    timer: 1500, showConfirmButton: false
                }).then(() => {
                    if (successCallback) successCallback(); else location.reload();
                });
            } else {
                Swal.fire('Error', data.message || 'Error al procesar la solicitud.', 'error');
            }
        })
        .catch(() => Swal.fire('Error', 'Problema con el servidor.', 'error'));
};

// 5. INTERACCIONES COMPARTIDAS (Mapeos y Select2)
window.initSharedFormInteractions = function (container) {
    const mappingCheckbox = container.querySelector('input[name="has_mapping"]');
    const budgetFieldsBox = container.querySelector('#budgetMappingFields');

    if (mappingCheckbox && budgetFieldsBox) {
        budgetFieldsBox.style.display = mappingCheckbox.checked ? 'block' : 'none';
        mappingCheckbox.addEventListener('change', function () {
            budgetFieldsBox.style.display = this.checked ? 'block' : 'none';
        });
    }

    $(container).find('select').each(function () {
        if (!$(this).hasClass('select2-hidden-accessible')) {
            $(this).select2({width: '100%', dropdownParent: $(container).closest('.modal-overlay')});
        }
    });
};

// 6. RECARGA INTELIGENTE DE TABLAS
window.reloadTableData = function (url, containerSelector) {
    fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
        .then(async response => {
            const text = await response.text();
            try {
                const data = JSON.parse(text);
                return data.html ? data.html : text;
            } catch (e) {
                return text;
            }
        })
        .then(html => {
            const container = document.querySelector(containerSelector);
            if (!container) return location.reload();

            container.innerHTML = html;
            const table = container.querySelector('.managed-table');
            if (table) {
                if (table._tableManager) {
                    table._tableManager.originalRows = Array.from(table.querySelectorAll('tbody tr'));
                    table._tableManager.currentRows = [...table._tableManager.originalRows];
                    if (typeof table._tableManager.render === 'function') table._tableManager.render();
                } else if (typeof TableManager !== 'undefined') {
                    new TableManager(table);
                }
            }
        })
        .catch(() => location.reload());
};

// 7. ELIMINACIÓN GENÉRICA DE REGISTROS (Reemplaza a deleteConstant)
window.deleteRecordAjax = function (url, itemName) {
    Swal.fire({
        title: `¿Eliminar ${itemName}?`,
        text: "Esta acción no se puede deshacer.",
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#d33',
        cancelButtonColor: '#64748b',
        confirmButtonText: 'Sí, eliminar',
        cancelButtonText: 'Cancelar',
        scrollbarPadding: false,
        heightAuto: false
    }).then((result) => {
        if (result.isConfirmed) {
            fetch(url, {
                method: 'POST',
                headers: {'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': getCSRF()}
            })
                .then(res => res.json())
                .then(data => {
                    if (data.status === 'success' || data.success) {
                        Swal.fire('Eliminado', data.message, 'success').then(() => location.reload());
                    } else {
                        Swal.fire('Error', data.message, 'error');
                    }
                })
                .catch(() => Swal.fire('Error', 'Error de comunicación', 'error'));
        }
    });
};