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

// 7. FILTROS GENERICOS PARA TABLAS EN CLIENTE
window.initGlobalTableFilters = function (root) {
    const container = typeof root === 'string' ? document.querySelector(root) : root;
    if (!container || container.dataset.filterBound === '1') return;

    const searchInput = container.querySelector('[data-filter-search]');
    const selectFields = Array.from(container.querySelectorAll('[data-filter-select]'));
    const applyButton = container.querySelector('[data-filter-apply]');
    const clearButton = container.querySelector('[data-filter-clear]');
    const rowSelector = container.dataset.rowSelector || '[data-filter-row]';
    const noResultsRow = container.querySelector('[data-filter-no-results]');
    const tableScope = container.closest('.content-table') || document;

    if (window.$ && $.fn.select2) {
        selectFields.forEach((select) => {
            const $select = $(select);
            try {
                if ($select.hasClass('select2-hidden-accessible')) {
                    $select.select2('destroy');
                }
            } catch (error) {
                console.warn('No se pudo reinicializar Select2', error);
            }

            $select.select2({
                width: '100%',
                allowClear: true,
                minimumResultsForSearch: Infinity,
                dropdownAutoWidth: true
            });
        });
    }

    const normalize = (value) => (value || '').toString().trim().toLowerCase();

    const getRowAttribute = (row, attrName) => {
        const value = row.getAttribute(`data-${attrName}`) ?? row.dataset?.[attrName] ?? '';
        return normalize(value);
    };

    const applyFilters = () => {
        const searchTerm = normalize(searchInput ? searchInput.value : '');
        const hasActiveFilters = !!searchTerm || selectFields.some((select) => normalize(select.value));
        let visibleCount = 0;

        tableScope.querySelectorAll(rowSelector).forEach((row) => {
            const rowSearchText = normalize(row.dataset.searchText || row.innerText);
            const matchesSearch = !searchTerm || rowSearchText.includes(searchTerm);

            const matchesSelects = selectFields.every((select) => {
                const selectedValue = normalize(select.value);
                if (!selectedValue) return true;

                const attrName = select.dataset.filterAttr;
                if (!attrName) return true;

                return getRowAttribute(row, attrName) === selectedValue;
            });

            const visible = matchesSearch && matchesSelects;
            row.style.display = visible ? '' : 'none';
            if (visible) visibleCount += 1;
        });

        if (noResultsRow) {
            noResultsRow.style.display = hasActiveFilters && visibleCount === 0 ? '' : 'none';
        }
    };

    if (searchInput) {
        searchInput.addEventListener('input', applyFilters);
        searchInput.addEventListener('keydown', (event) => {
            if (event.key === 'Enter') {
                event.preventDefault();
                applyFilters();
            }
        });
    }

    selectFields.forEach((select) => {
        select.addEventListener('change', applyFilters);
        if (window.$ && $.fn.select2) {
            $(select).on('select2:select', applyFilters);
            $(select).on('select2:clear', applyFilters);
        }
    });

    if (applyButton) {
        applyButton.addEventListener('click', applyFilters);
    }

    if (clearButton) {
        clearButton.addEventListener('click', () => {
            if (searchInput) searchInput.value = '';
            selectFields.forEach((select) => {
                select.value = '';
            });
            applyFilters();
            if (searchInput) searchInput.focus();
        });
    }

    container.dataset.filterBound = '1';
    applyFilters();
};

document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-global-table-filter]').forEach((container) => {
        window.initGlobalTableFilters(container);
    });
});

// 8. ELIMINACIÓN GENÉRICA DE REGISTROS (Reemplaza a deleteConstant)
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