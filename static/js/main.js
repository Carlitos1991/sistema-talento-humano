/**
 * SIGETH - GESTOR CENTRALIZADO (MODALES, AJAX, FILTROS Y TABLAS)
 * Archivo motor del sistema.
 */

/* ==========================================================================
   1. SEGURIDAD & CSRF (DJANGO)
   ========================================================================== */

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


/* ==========================================================================
   2. NOTIFICACIONES & ALERTAS (TOASTS Y SWEETALERT2)
   ========================================================================== */

// 2.1 Toast Flotante Universal (Píldora superior derecha con franja lateral)
window.showToast = function (message, type = 'success') {
    const oldToast = document.querySelector('.custom-toast-pill');
    if (oldToast) oldToast.remove();

    // Mapeo de iconos SVG/FontAwesome según el tipo
    const icons = {
        'success': '<i class="fas fa-check-circle"></i>',
        'error': '<i class="fas fa-circle-exclamation"></i>',
        'warning': '<i class="fas fa-triangle-exclamation"></i>',
        'info': '<i class="fas fa-circle-info"></i>'
    };

    const iconHtml = icons[type] || icons['success'];

    const toast = document.createElement('div');
    toast.className = `custom-toast-pill custom-toast-${type}`;
    toast.innerHTML = `
        <div class="toast-indicator-strip"></div>
        <div class="toast-content-body">
            <span class="toast-icon">${iconHtml}</span>
            <span class="toast-message-text">${message}</span>
        </div>
        <div class="toast-progress-bar"></div>
    `;

    document.body.appendChild(toast);

    // Animación fluida de entrada
    requestAnimationFrame(() => toast.classList.add('show'));

    // Tiempo visible y transición de salida
    const duration = 2800;
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 320);
    }, duration);
};

// 2.2 Configuración Global Robusta de SweetAlert2 (Preguntas y Advertencias)
if (typeof Swal !== 'undefined') {
    const nativeSwalFire = Swal.fire.bind(Swal);

    Swal.fire = function (...args) {
        let opts = {};

        if (args.length === 1 && typeof args[0] === 'object' && args[0] !== null) {
            opts = Object.assign({}, args[0]);
        } else if (args.length > 0) {
            opts = {
                title: args[0] || '',
                text: args[1] || '',
                icon: args[2] || undefined
            };
        }

        // Estabilidad visual y prevención de saltos de scroll
        opts.scrollbarPadding = false;
        opts.heightAuto = false;
        opts.buttonsStyling = false;

        // Textos estándar en español
        if (!opts.confirmButtonText) opts.confirmButtonText = 'Entendido';
        if (!opts.cancelButtonText) opts.cancelButtonText = 'Cancelar';

        // Clases CSS institucionales
        if (!opts.customClass) {
            opts.customClass = {
                confirmButton: 'swal2-confirm btn-swal-success',
                cancelButton: 'swal2-cancel btn-swal-cancel'
            };
        }

        // REGLA: Si tiene temporizador, jamás muestra botones
        if (opts.timer && Number(opts.timer) > 0) {
            opts.showConfirmButton = false;
            opts.showCancelButton = false;
            opts.showCloseButton = false;
        } else {
            // Si es aviso/error y no solicitó cancelar explícitamente, ocultar botón Cancel
            if (opts.showCancelButton !== true) {
                opts.showCancelButton = false;
            }
        }

        return nativeSwalFire(opts);
    };

    window.Swal = Swal;
}


/* ==========================================================================
   3. RECARGA DINÁMICA DE TABLAS PARCIALES AJAX
   ========================================================================== */

window.refreshCurrentTable = function (callback = null) {
    const wrapper = document.getElementById('table-content-wrapper')
        || document.querySelector('.table-container')?.parentElement;

    if (!wrapper) {
        location.reload();
        return;
    }

    fetch(window.location.href, {
        headers: {'X-Requested-With': 'XMLHttpRequest'}
    })
        .then(async response => {
            const contentType = response.headers.get("content-type");
            if (contentType && contentType.includes("application/json")) {
                const data = await response.json();
                return data.html || '';
            }
            return await response.text();
        })
        .then(html => {
            if (!html) return;
            wrapper.innerHTML = html;

            // Reinstanciar TableManager sobre la nueva tabla
            if (typeof TableManager !== 'undefined') {
                const table = wrapper.querySelector('.managed-table');
                if (table) new TableManager(table);
            }

            if (typeof callback === 'function') callback();
        })
        .catch(err => {
            console.error("Error al refrescar la tabla parcial:", err);
            location.reload();
        });
};


/* ==========================================================================
   4. GESTOR DE MODALES (ESTÁTICOS Y AJAX)
   ========================================================================== */

let currentScrollY = 0;

// 4.1 Modales estáticos (renderizados en HTML)
window.openModal = function (id) {
    const modal = document.getElementById(id);
    if (modal) {
        $(modal).find('select').select2({width: '100%'});
        document.body.classList.add('no-scroll');
        modal.classList.remove('hidden');
    } else {
        console.error("No se encontró el modal con ID: " + id);
    }
};

// 4.2 Modales dinámicos vía AJAX
window.openAjaxModal = function (url, callback = null) {
    currentScrollY = window.scrollY;
    document.documentElement.classList.add('no-scroll');
    document.body.classList.add('no-scroll');

    fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
        .then(response => {
            if (!response.ok) throw new Error('Error al cargar modal');
            return response.text();
        })
        .then(html => {
            const root = document.getElementById('modal-root');
            if (!root) return;
            root.innerHTML = html;

            const modal = root.querySelector('.modal-overlay');
            if (modal) {
                modal.classList.remove('hidden');

                setTimeout(() => {
                    if (window.$ && $.fn.select2) {
                        $(modal).find('select').each(function () {
                            const $select = $(this);
                            if ($select.hasClass('select2-hidden-accessible')) return;

                            $select.select2({
                                width: '100%',
                                dropdownParent: $(modal).find('.modal-body-custom').length
                                    ? $(modal).find('.modal-body-custom')
                                    : $(modal)
                            });
                        });
                    }
                }, 10);
            }

            if (callback) callback(root);
        })
        .catch(error => {
            document.documentElement.classList.remove('no-scroll');
            document.body.classList.remove('no-scroll');
            window.scrollTo(0, currentScrollY);

            Swal.fire({
                icon: 'error',
                title: 'Error',
                text: 'No se pudo cargar el formulario.'
            });
            console.error(error);
        });
};

// 4.3 Cierre de modales universal
window.closeModal = function (id = null) {
    if (id) {
        const modal = document.getElementById(id);
        if (modal) modal.classList.add('hidden');
    }

    const root = document.getElementById('modal-root');
    if (root) root.innerHTML = '';

    document.documentElement.classList.remove('no-scroll');
    document.body.classList.remove('no-scroll');
    window.scrollTo(0, currentScrollY);
};

window.closeAjaxModal = window.closeModal;


/* ==========================================================================
   5. OPERACIONES AJAX CRUD UNIVERSALES
   ========================================================================== */

// 5.1 Envío de Formularios (Creación y Edición)
window.submitAjaxForm = function (event, successCallback = null) {
    event.preventDefault();
    const form = event.target;
    const formData = new FormData(form);

    // Limpieza de estados de error previos
    form.querySelectorAll('.is-invalid').forEach(el => el.classList.remove('is-invalid'));
    form.querySelectorAll('.invalid-feedback').forEach(el => {
        el.textContent = '';
        el.style.display = 'none';
    });

    fetch(form.action, {
        method: 'POST',
        body: formData,
        headers: {
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRFToken': typeof getCSRF === 'function' ? getCSRF() : ''
        }
    })
        .then(async response => {
            const contentType = response.headers.get('content-type');

            // Caso A: Respuesta HTML con formulario renderizado con errores
            if (contentType && contentType.includes('text/html')) {
                const html = await response.text();
                const root = document.getElementById('modal-root');
                if (root && root.innerHTML !== "") {
                    root.innerHTML = html;
                }
                Swal.fire({
                    icon: 'warning',
                    title: 'Atención',
                    text: 'Corrija los errores en el formulario.'
                });
                return;
            }

            // Caso B: Respuesta JSON
            const data = await response.json();

            // ÉXITO
            if (response.ok && (data.status === 'success' || data.success)) {
                if (typeof window.closeModal === 'function') window.closeModal();

                showToast(data.message || 'Operación realizada correctamente.', 'success');

                if (typeof successCallback === 'function') {
                    successCallback(data);
                } else {
                    refreshCurrentTable();
                }
                return;
            }

            // ERROR DE VALIDACIÓN (HTTP 400 u otro)
            let errorHtml = data.message || 'Existen errores en el formulario.';

            if (data.errors) {
                const errorItems = [];
                const fallbackLabels = {
                    'name': 'Nombre',
                    'code': 'Código / Partida',
                    'level': 'Nivel Jerárquico',
                    'parent': 'Unidad Padre',
                    'boss': 'Jefe / Responsable',
                    'address': 'Dirección / Ubicación',
                    'phone': 'Teléfono / Extensión',
                    'is_active': 'Estado',
                    'description': 'Descripción',
                    'image': 'Imagen'
                };

                Object.keys(data.errors).forEach(field => {
                    const rawMsg = data.errors[field];
                    const msg = Array.isArray(rawMsg) ? rawMsg[0] : rawMsg;
                    const input = form.querySelector(`[name="${field}"]`);
                    let fieldName = null;

                    if (input) {
                        input.classList.add('is-invalid');
                        const container = input.closest('.form-group') || input.parentElement;
                        const feedback = container ? container.querySelector('.invalid-feedback') : null;
                        if (feedback) {
                            feedback.textContent = msg;
                            feedback.style.display = 'block';
                        }
                        const labelInContainer = container ? container.querySelector('label') : null;
                        if (labelInContainer) {
                            fieldName = labelInContainer.textContent.replace(/[*:]/g, '').trim();
                        } else if (input.getAttribute('placeholder')) {
                            fieldName = input.getAttribute('placeholder').replace(/^Ej:\s*/i, '').trim();
                        }
                    }

                    if (!fieldName) {
                        const label = form.querySelector(`label[for="${field}"], label[for="id_${field}"]`);
                        if (label) {
                            fieldName = label.textContent.replace(/[*:]/g, '').trim();
                        }
                    }

                    if (!fieldName || fieldName.toLowerCase() === field.toLowerCase()) {
                        fieldName = fallbackLabels[field] || (field.charAt(0).toUpperCase() + field.slice(1));
                    }

                    errorItems.push(`• <b>${fieldName}:</b> ${msg}`);
                });

                if (errorItems.length > 0) {
                    errorHtml = errorItems.join('<br>');
                }
            }

            Swal.fire({
                icon: 'warning',
                title: 'Atención',
                html: errorHtml,
                confirmButtonText: 'Entendido'
            });
        })
        .catch(err => {
            console.error('Error Ajax Form:', err);
            Swal.fire({
                icon: 'error',
                title: 'Error',
                text: 'Problema de conexión con el servidor.'
            });
        });
};

// 5.2 Alternar Estado Activo / Inactivo Universal (Toggle)
window.toggleStatusAjax = function (url, itemName, currentStatus, callback = null) {
    const actionText = currentStatus ? 'desactivar' : 'activar';
    const confirmBtnClass = currentStatus ? 'btn-swal-danger' : 'btn-swal-success';

    Swal.fire({
        title: `¿Desea ${actionText} ${itemName}?`,
        icon: 'question',
        showCancelButton: true,
        confirmButtonText: `Sí, ${actionText}`,
        cancelButtonText: 'Cancelar',
        customClass: {
            confirmButton: `swal2-confirm ${confirmBtnClass}`,
            cancelButton: 'swal2-cancel btn-swal-cancel'
        }
    }).then((result) => {
        if (result.isConfirmed) {
            fetch(url, {
                method: 'POST',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': typeof getCSRF === 'function' ? getCSRF() : ''
                }
            })
                .then(res => res.json())
                .then(data => {
                    if (data.success) {
                        showToast(data.message || 'Estado actualizado correctamente.', 'success');

                        if (typeof callback === 'function') {
                            callback(data);
                        } else {
                            refreshCurrentTable();
                        }
                    } else {
                        Swal.fire({
                            icon: 'warning',
                            title: 'Atención',
                            text: data.message || 'No se pudo cambiar el estado.',
                            confirmButtonText: 'Entendido'
                        });
                    }
                })
                .catch(err => {
                    console.error("Error cambiando estado:", err);
                    Swal.fire({
                        icon: 'error',
                        title: 'Error',
                        text: 'Ocurrió un problema de comunicación con el servidor.',
                        confirmButtonText: 'Entendido'
                    });
                });
        }
    });
};

// 5.3 Eliminación Universal
window.deleteRecordAjax = function (url, itemName, callback = null) {
    Swal.fire({
        title: `¿Eliminar ${itemName}?`,
        text: "Esta acción no se puede deshacer.",
        icon: 'warning',
        showCancelButton: true,
        customClass: {
            confirmButton: 'swal2-confirm btn-swal-danger',
            cancelButton: 'swal2-cancel btn-swal-cancel'
        },
        confirmButtonText: 'Sí, eliminar',
        cancelButtonText: 'Cancelar'
    }).then((result) => {
        if (result.isConfirmed) {
            fetch(url, {
                method: 'POST',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': getCSRF()
                }
            })
                .then(res => res.json())
                .then(data => {
                    if (data.success) {
                        showToast(data.message || 'Registro eliminado.', 'success');

                        if (typeof callback === 'function') {
                            callback(data);
                        } else {
                            refreshCurrentTable();
                        }
                    } else {
                        Swal.fire({
                            icon: 'error',
                            title: 'Error',
                            text: data.message || 'No se pudo eliminar el registro.'
                        });
                    }
                })
                .catch(err => {
                    console.error("Error eliminando registro:", err);
                    Swal.fire({
                        icon: 'error',
                        title: 'Error',
                        text: 'Error de comunicación con el servidor.'
                    });
                });
        }
    });
};


/* ==========================================================================
   6. TABLE MANAGER (ORDENAMIENTO, FILTRADO Y PAGINACIÓN)
   ========================================================================== */

class TableManager {
    constructor(tableElement) {
        this.table = tableElement;
        this.tbody = this.table.querySelector('tbody');
        this.originalRows = Array.from(this.tbody.querySelectorAll('tr'));
        this.currentRows = [...this.originalRows];

        this.pageSize = parseInt(this.table.dataset.pageSize) || 10;
        this.currentPage = 1;
        this.sortCol = null;
        this.sortAsc = true;

        if (window._currentTableSort) {
            this.sortCol = window._currentTableSort.col;
            this.sortAsc = window._currentTableSort.asc;
        }

        this.externalPagination = this.table.dataset.externalPagination === 'true';
        this.externalSearch = this.table.dataset.externalSearch === 'true';

        this.filterState = {
            search: '',
            column: null,
            value: 'all'
        };

        this.wrapper = this.table.closest('.content-table') || this.table.parentElement;
        this.searchInput = this.wrapper.querySelector('.table-search-input') || document.getElementById('table-search');

        this.initSortHeaders();

        if (!this.externalSearch) {
            this.initSearch();
        }

        if (!this.externalPagination) {
            this.initPagination();
            this.render();
        }

        this.initHorizontalScrollHelper();
        this.table._tableManager = this;
    }

    initHorizontalScrollHelper() {
        this.scrollContainer = this.table.closest('.table-container');
        if (!this.scrollContainer) return;

        this.scrollContainer.classList.add('table-container-has-scroll-helper');

        let helperGroup = this.scrollContainer.querySelector('.table-scroll-helper-group');
        if (!helperGroup) {
            helperGroup = document.createElement('div');
            helperGroup.className = 'table-scroll-helper-group';

            const startButton = document.createElement('button');
            startButton.type = 'button';
            startButton.className = 'table-scroll-nav-button table-scroll-nav-start';
            startButton.setAttribute('aria-label', 'Ir al inicio de la tabla');
            startButton.title = 'Ir al inicio de la tabla';
            startButton.innerHTML = '<i class="fas fa-angles-left"></i>';

            const endButton = document.createElement('button');
            endButton.type = 'button';
            endButton.className = 'table-scroll-nav-button table-scroll-nav-end';
            endButton.setAttribute('aria-label', 'Ir al final de la tabla');
            endButton.title = 'Ir al final de la tabla';
            endButton.innerHTML = '<i class="fas fa-angles-right"></i>';

            helperGroup.appendChild(startButton);
            helperGroup.appendChild(endButton);
            this.scrollContainer.appendChild(helperGroup);
        }

        const startButton = this.scrollContainer.querySelector('.table-scroll-nav-start');
        const endButton = this.scrollContainer.querySelector('.table-scroll-nav-end');

        if (startButton && !startButton.dataset.bound) {
            startButton.addEventListener('click', () => {
                this.scrollContainer.scrollTo({left: 0, behavior: 'smooth'});
            });
            startButton.dataset.bound = '1';
        }

        if (endButton && !endButton.dataset.bound) {
            endButton.addEventListener('click', () => {
                this.scrollContainer.scrollTo({
                    left: this.scrollContainer.scrollWidth,
                    behavior: 'smooth'
                });
            });
            endButton.dataset.bound = '1';
        }
    }

    initSearch() {
        if (!this.searchInput) return;

        if (this.searchInput._tmSearchHandler) {
            this.searchInput.removeEventListener('input', this.searchInput._tmSearchHandler);
        }
        const handler = (e) => {
            this.filterState.search = e.target.value.toLowerCase().trim();
            this.applyGlobalFilters();
        };
        this.searchInput._tmSearchHandler = handler;
        this.searchInput.addEventListener('input', handler);
    }

    applyGlobalFilters() {
        let result = [...this.originalRows];

        if (this.filterState.value !== 'all' && this.filterState.column) {
            result = result.filter(row =>
                row.getAttribute(`data-${this.filterState.column}`) === this.filterState.value
            );
        }

        if (this.filterState.search) {
            result = result.filter(row =>
                row.innerText.toLowerCase().includes(this.filterState.search)
            );
        }

        this.currentRows = result;
        this.currentPage = 1;

        if (this.sortCol !== null) this.sortData();
        this.render();
    }

    filterByColumnData(columnName, value) {
        this.filterState.column = columnName;
        this.filterState.value = value;
        this.applyGlobalFilters();
    }

    initSortHeaders() {
        const headers = this.table.querySelectorAll('thead th');
        headers.forEach((th, index) => {
            if (th.classList.contains('no-sort')) return;
            th.classList.add('sortable-header');

            if (!th.querySelector('.sort-arrow')) {
                const spacer = document.createTextNode(' ');
                const span = document.createElement('span');
                span.className = 'sort-arrow';
                span.textContent = '⇅';
                th.appendChild(spacer);
                th.appendChild(span);
            }

            if (!th.dataset.tmInit) {
                th.addEventListener('click', () => {
                    if (th._tm_handling) return;
                    this.handleSort(index, th, headers);
                });
                th.dataset.tmInit = '1';
            }
        });
    }

    handleSort(colIndex, clickedTh, allHeaders) {
        if (this.sortCol === colIndex) {
            this.sortAsc = !this.sortAsc;
        } else {
            this.sortCol = colIndex;
            this.sortAsc = true;
            allHeaders.forEach(h => {
                h.classList.remove('sorted-asc', 'sorted-desc');
                const arrow = h.querySelector('.sort-arrow');
                if (arrow) arrow.innerText = '⇅';
            });
        }
        clickedTh.classList.remove('sorted-asc', 'sorted-desc');
        clickedTh.classList.add(this.sortAsc ? 'sorted-asc' : 'sorted-desc');
        const arrow = clickedTh.querySelector('.sort-arrow');
        if (arrow) arrow.innerText = this.sortAsc ? '↑' : '↓';

        if (this.externalPagination || this.externalSearch) {
            const headerEl = allHeaders[colIndex];
            const field = headerEl?.dataset?.field || null;
            if (!field) return;

            window._currentTableSort = {col: colIndex, asc: this.sortAsc};

            const oldTableContainer = this.table.closest('.table-container');
            if (oldTableContainer) {
                oldTableContainer.style.opacity = '0.4';
                oldTableContainer.style.pointerEvents = 'none';
            }

            const listUrl = this.table.getAttribute('data-list-url') || window.location.pathname;
            const params = new URLSearchParams(window.location.search);
            params.set('page', 1);
            params.set('sort_field', field);
            params.set('sort_dir', this.sortAsc ? 'asc' : 'desc');

            fetch(`${listUrl}?${params.toString()}`, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
                .then(async (response) => {
                    const contentType = response.headers.get("content-type");
                    if (contentType && contentType.includes("application/json")) {
                        const data = await response.json();
                        return data.html || '';
                    }
                    return await response.text();
                })
                .then(html => {
                    if (!html) return;

                    const temp = document.createElement('div');
                    temp.innerHTML = html;

                    const newTableContainer = temp.querySelector('.table-container');
                    const newPagination = temp.querySelector('.pagination-container');
                    const oldPagination = document.getElementById('js-pagination');

                    if (newTableContainer && oldTableContainer) {
                        oldTableContainer.replaceWith(newTableContainer);
                    }
                    if (newPagination && oldPagination) {
                        oldPagination.replaceWith(newPagination);
                    } else if (newPagination && !oldPagination && newTableContainer) {
                        newTableContainer.after(newPagination);
                    }

                    setTimeout(() => {
                        if (newTableContainer) {
                            const newTable = newTableContainer.querySelector('.managed-table');
                            if (newTable) {
                                new TableManager(newTable);
                                const s = window._currentTableSort;
                                const ths = newTable.querySelectorAll('thead th');
                                if (ths[s.col]) {
                                    ths[s.col].classList.add(s.asc ? 'sorted-asc' : 'sorted-desc');
                                    const a = ths[s.col].querySelector('.sort-arrow');
                                    if (a) a.innerText = s.asc ? '↑' : '↓';
                                }
                            }
                        }
                    }, 50);
                })
                .catch(e => {
                    console.error('Error al ordenar la tabla:', e);
                    if (oldTableContainer) {
                        oldTableContainer.style.opacity = '1';
                        oldTableContainer.style.pointerEvents = 'auto';
                    }
                });
            return;
        }

        this.sortData();
        this.render();
    }

    compareValues(a, b) {
        const isVersionStr = (s) => /^\d+(\.\d+)*$/.test(s.trim());

        if (isVersionStr(a) && isVersionStr(b)) {
            const partsA = a.trim().split('.').map(Number);
            const partsB = b.trim().split('.').map(Number);
            const len = Math.max(partsA.length, partsB.length);
            for (let i = 0; i < len; i++) {
                const na = partsA[i] ?? 0;
                const nb = partsB[i] ?? 0;
                if (na !== nb) return na - nb;
            }
            return 0;
        }

        const numA = parseFloat(a.replace(/[^0-9.-]+/g, ''));
        const numB = parseFloat(b.replace(/[^0-9.-]+/g, ''));
        if (!isNaN(numA) && !isNaN(numB) && a !== '' && b !== '') {
            return numA - numB;
        }

        return a.localeCompare(b, undefined, {sensitivity: 'base'});
    }

    sortData() {
        if (this.sortCol === null) return;
        this.currentRows.sort((rowA, rowB) => {
            const cellElA = rowA.children[this.sortCol];
            const cellElB = rowB.children[this.sortCol];
            const cellA = (cellElA && cellElA.dataset && cellElA.dataset.sort) ? String(cellElA.dataset.sort).trim() : (cellElA?.innerText.trim() || '');
            const cellB = (cellElB && cellElB.dataset && cellElB.dataset.sort) ? String(cellElB.dataset.sort).trim() : (cellElB?.innerText.trim() || '');
            const cmp = this.compareValues(cellA, cellB);
            return this.sortAsc ? cmp : -cmp;
        });
    }

    updateStats() {
        const elTotal = document.getElementById('stat-total');
        const elActive = document.getElementById('stat-active');
        const elInactive = document.getElementById('stat-inactive');

        if (elTotal) elTotal.innerText = this.originalRows.length;
        if (elActive || elInactive) {
            const active = this.originalRows.filter(r => r.dataset.status === 'true').length;
            const inactive = this.originalRows.filter(r => r.dataset.status === 'false').length;
            if (elActive) elActive.innerText = active;
            if (elInactive) elInactive.innerText = inactive;
        }
    }

    initPagination() {
        const contentTable = this.table.closest('.content-table');
        let pagContainer = contentTable?.nextElementSibling?.classList.contains('pagination-container')
            ? contentTable.nextElementSibling
            : null;

        if (!pagContainer) {
            pagContainer = document.createElement('div');
            pagContainer.className = 'pagination-container';
            if (contentTable && contentTable.parentNode) {
                contentTable.parentNode.insertBefore(pagContainer, contentTable.nextSibling);
            } else {
                this.table.parentNode.insertBefore(pagContainer, this.table.nextSibling);
            }
        }
        this.pagContainer = pagContainer;
    }

    renderPaginationControls(totalPages) {
        const totalRows = this.currentRows.length;
        const start = totalRows === 0 ? 0 : (this.currentPage - 1) * this.pageSize + 1;
        const end = Math.min(this.currentPage * this.pageSize, totalRows);

        if (!this.pagContainer) return;
        this.pagContainer.style.display = 'flex';

        const prevDisabled = this.currentPage === 1;
        const nextDisabled = this.currentPage === totalPages || totalRows === 0;
        const showControls = totalPages > 1 && totalRows > 0;

        this.pagContainer.innerHTML = `
            <div class="pagination-info">
                Mostrando ${start}-${end} de ${totalRows}
            </div>
            <div class="pagination-controls" style="${!showControls ? 'visibility:hidden;' : ''}">
                <button class="page-btn page-first" title="Primera" ${prevDisabled ? 'disabled' : ''}>
                    <i class="fas fa-angle-double-left"></i>
                </button>
                <button class="page-btn page-prev" title="Anterior" ${prevDisabled ? 'disabled' : ''}>
                    <i class="fas fa-angle-left"></i>
                </button>
                <div class="page-input-wrapper">
                    <input type="number" class="page-input" value="${this.currentPage}" min="1" max="${totalPages}">
                    <span class="total-pages-badge">de ${totalPages}</span>
                </div>
                <button class="page-btn page-next" title="Siguiente" ${nextDisabled ? 'disabled' : ''}>
                    <i class="fas fa-angle-right"></i>
                </button>
                <button class="page-btn page-last" title="Última" ${nextDisabled ? 'disabled' : ''}>
                    <i class="fas fa-angle-double-right"></i>
                </button>
            </div>
        `;

        if (!showControls) return;

        const input = this.pagContainer.querySelector('.page-input');
        const go = (page) => {
            if (page < 1) page = 1;
            if (page > totalPages) page = totalPages;
            this.currentPage = page;
            this.render();
        };

        this.pagContainer.querySelector('.page-first').onclick = () => go(1);
        this.pagContainer.querySelector('.page-prev').onclick = () => go(this.currentPage - 1);
        this.pagContainer.querySelector('.page-next').onclick = () => go(this.currentPage + 1);
        this.pagContainer.querySelector('.page-last').onclick = () => go(totalPages);

        input.addEventListener('change', () => go(parseInt(input.value) || 1));
        input.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') go(parseInt(input.value) || 1);
        });
    }

    render() {
        this.updateStats();

        const totalRows = this.currentRows.length;
        const totalPages = Math.max(Math.ceil(totalRows / this.pageSize), 1);

        if (this.currentPage > totalPages) this.currentPage = totalPages;
        if (this.currentPage < 1) this.currentPage = 1;

        const start = (this.currentPage - 1) * this.pageSize;
        const end = start + this.pageSize;

        this.tbody.innerHTML = '';

        if (totalRows > 0) {
            this.currentRows.slice(start, end).forEach(row => {
                row.style.display = '';
                this.tbody.appendChild(row);
            });
        } else {
            const headerThs = Array.from(this.table.querySelectorAll('thead th'));
            if (headerThs.length > 0) {
                const spacerRow = document.createElement('tr');
                spacerRow.className = 'spacer-row';
                headerThs.forEach((th) => {
                    const td = document.createElement('td');
                    td.innerHTML = '&nbsp;';
                    try {
                        const w = th.offsetWidth;
                        if (w && w > 0) td.style.minWidth = w + 'px';
                    } catch (e) {
                    }
                    td.style.padding = '0';
                    td.style.border = 'none';
                    spacerRow.appendChild(td);
                });
                this.tbody.appendChild(spacerRow);

                const msgRow = document.createElement('tr');
                msgRow.className = 'empty-results-row';
                const msgTd = document.createElement('td');
                msgTd.colSpan = headerThs.length;
                msgTd.style.textAlign = 'center';
                msgTd.innerHTML = `
                    <div style="display:flex;flex-direction:column;align-items:center;padding:40px 0;color:#94a3b8;">
                        <i class="fas fa-search" style="font-size:1.6em;margin-bottom:10px;"></i>
                        <span>Sin resultados</span>
                    </div>`;
                msgRow.appendChild(msgTd);
                this.tbody.appendChild(msgRow);
            } else {
                const emptyRow = document.createElement('tr');
                emptyRow.className = 'empty-results-row';
                const td = document.createElement('td');
                td.colSpan = 100;
                td.innerHTML = `
                    <div style="display:flex;flex-direction:column;align-items:center;padding:40px 0;color:#94a3b8;">
                        <i class="fas fa-search" style="font-size:1.6em;margin-bottom:10px;"></i>
                        <span>Sin resultados</span>
                    </div>`;
                emptyRow.appendChild(td);
                this.tbody.appendChild(emptyRow);
            }
        }

        this.renderPaginationControls(totalPages);
    }
}

// 6.1 Inicialización automática de tablas al cargar el DOM
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.managed-table').forEach(t => new TableManager(t));
});

// 6.2 Delegación de clic para ordenamiento
document.addEventListener('click', (e) => {
    const th = e.target.closest('.managed-table thead th');
    if (!th || th.classList.contains('no-sort')) return;
    const table = th.closest('.managed-table');
    if (!table || table.dataset.externalPagination === 'true' || table.dataset.externalSearch === 'true') return;

    const headers = Array.from(table.querySelectorAll('thead th'));
    const colIndex = headers.indexOf(th);
    if (colIndex === -1) return;

    let mgr = table._tableManager;
    if (!mgr) {
        try {
            new TableManager(table);
            mgr = table._tableManager;
        } catch (err) {
            console.warn('TableManager: no se pudo crear instancia al click delegado', err);
            return;
        }
    }

    try {
        th._tm_handling = true;
        mgr.handleSort(colIndex, th, headers);
    } catch (err) {
        console.warn('TableManager: error en handleSort delegado', err);
    } finally {
        setTimeout(() => {
            delete th._tm_handling;
        }, 60);
    }
}, true);

// 6.3 Delegación global para paginación AJAX externa
document.addEventListener('click', (e) => {
    const btn = e.target.closest('.page-btn');
    if (!btn) return;

    const table = document.querySelector('.managed-table');
    if (!table || table.dataset.externalPagination !== 'true') return;
    if (btn.hasAttribute('disabled') || btn.classList.contains('disabled')) return;

    e.preventDefault();
    e.stopImmediatePropagation();

    const page = btn.dataset.page;
    if (!page) return;

    const oldTableContainer = table.closest('.table-container');
    const oldPagination = btn.closest('.pagination-container');

    if (oldTableContainer) {
        oldTableContainer.style.opacity = '0.4';
        oldTableContainer.style.pointerEvents = 'none';
    }

    const listUrl = table.getAttribute('data-list-url') || window.location.pathname;
    const params = new URLSearchParams(window.location.search);
    params.set('page', page);

    if (window._currentTableSort) {
        const ths = table.querySelectorAll('thead th');
        const th = ths[window._currentTableSort.col];
        if (th && th.dataset.field) {
            params.set('sort_field', th.dataset.field);
            params.set('sort_dir', window._currentTableSort.asc ? 'asc' : 'desc');
        }
    }

    fetch(`${listUrl}?${params.toString()}`, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
        .then(async (response) => {
            const contentType = response.headers.get("content-type");
            if (contentType && contentType.includes("application/json")) {
                const data = await response.json();
                return data.html || '';
            }
            return await response.text();
        })
        .then(html => {
            if (!html) return;

            const temp = document.createElement('div');
            temp.innerHTML = html;

            const newTableContainer = temp.querySelector('.table-container');
            const newPagination = temp.querySelector('.pagination-container');

            if (newTableContainer && oldTableContainer) {
                oldTableContainer.replaceWith(newTableContainer);
            }
            if (newPagination && oldPagination) {
                oldPagination.replaceWith(newPagination);
            }

            setTimeout(() => {
                const newTable = document.querySelector('.managed-table');
                if (newTable) {
                    new TableManager(newTable);
                    if (window._currentTableSort) {
                        const s = window._currentTableSort;
                        const newThs = newTable.querySelectorAll('thead th');
                        if (newThs[s.col]) {
                            newThs[s.col].classList.add(s.asc ? 'sorted-asc' : 'sorted-desc');
                            const arrow = newThs[s.col].querySelector('.sort-arrow');
                            if (arrow) arrow.innerText = s.asc ? '↑' : '↓';
                        }
                    }
                }
            }, 50);
        })
        .catch(err => {
            console.error('Error al cambiar de página AJAX:', err);
            if (oldTableContainer) {
                oldTableContainer.style.opacity = '1';
                oldTableContainer.style.pointerEvents = 'auto';
            }
        });
}, true);

window.TableManager = TableManager;


/* ==========================================================================
   7. UI HELPERS & COMPONENTES DEL SISTEMA
   ========================================================================== */

// 7.1 Previsualización de fotos en modales
window.handleModalPhotoPreview = function (input) {
    if (input.files && input.files[0]) {
        const reader = new FileReader();
        reader.onload = function (e) {
            const img = document.getElementById('photo-preview-img');
            const placeholder = document.getElementById('photo-placeholder');
            if (img) {
                img.src = e.target.result;
                img.style.display = 'block';
            }
            if (placeholder) {
                placeholder.style.display = 'none';
            }
        };
        reader.readAsDataURL(input.files[0]);
    }
};

// 7.2 Toggles y acordeones de visualización
window.syncToggleView = function (checkbox, targetContentId) {
    const target = document.getElementById(targetContentId);
    const header = checkbox.closest('.toggle-header');
    const labelText = checkbox.parentElement.querySelector('.switch-text');

    if (checkbox.checked) {
        if (target) target.classList.remove('hidden');
        if (header) header.classList.add('active-header');
        if (labelText) labelText.textContent = 'Sí';
    } else {
        if (target) target.classList.add('hidden');
        if (header) header.classList.remove('active-header');
        if (labelText) labelText.textContent = 'No';
    }
};

window.toggleAccordionSection = function (targetContentId) {
    const target = document.getElementById(targetContentId);
    if (!target) return;
    const header = target.previousElementSibling;
    const checkbox = header ? header.querySelector('.switch-input') : null;

    if (checkbox) {
        checkbox.checked = !checkbox.checked;
        syncToggleView(checkbox, targetContentId);
    }
};

// 7.3 Cascadas dinámicas de ubicación geográfica (DPA)
window.handleLocationCascade = function (selectElement, targetSelectId, targetLevel) {
    const parentId = selectElement.value;
    const targetSelect = $(`#${targetSelectId}`);

    targetSelect.empty().append('<option value="">Cargando...</option>').trigger('change');

    if (!parentId) {
        targetSelect.empty().append('<option value="">-- Seleccione --</option>').trigger('change');
        return;
    }

    fetch(`/core/locations/children/?parent_id=${parentId}`, {
        headers: {'X-Requested-With': 'XMLHttpRequest'}
    })
        .then(res => res.json())
        .then(data => {
            targetSelect.empty().append('<option value="">-- Seleccione --</option>');
            data.forEach(item => {
                targetSelect.append(new Option(item.name, item.id));
            });
            targetSelect.trigger('change');
        })
        .catch(() => {
            targetSelect.empty().append('<option value="">-- Error al cargar --</option>').trigger('change');
        });
};

// 7.4 Actualizador global de estadísticas de Hoja de Vida
window.refreshCvStats = function (personId) {
    if (!personId) return;
    fetch(`/employee/api/cv/stats/${personId}/`, {
        headers: {'X-Requested-With': 'XMLHttpRequest'}
    })
        .then(res => res.json())
        .then(data => {
            if (!data.success) return;
            const elTitles = document.getElementById('cv-stat-titles') || document.getElementById('stat-titles');
            const elExp = document.getElementById('cv-stat-experience') || document.getElementById('stat-experience');
            const elCourses = document.getElementById('cv-stat-courses') || document.getElementById('stat-courses');

            if (elTitles) elTitles.textContent = data.titles_count;
            if (elExp) elExp.textContent = data.experience_text;
            if (elCourses) elCourses.textContent = data.courses_count;
        })
        .catch(err => console.error("Error actualizando estadísticas de CV:", err));
};

// 7.5 Ocultar fecha fin al marcar "Trabajo actualmente aquí"
document.addEventListener('change', function (e) {
    if (e.target && (e.target.id === 'id_is_current' || e.target.name === 'is_current')) {
        const endWrap = document.getElementById('endDateWrapper');
        if (!endWrap) return;

        if (e.target.checked) {
            endWrap.classList.add('hidden');
            const input = endWrap.querySelector('input');
            if (input) input.value = '';
        } else {
            endWrap.classList.remove('hidden');
        }
    }
});


/* ==========================================================================
   8. MÓDULO DE TELETRABAJO
   ========================================================================== */

window.loadTeleworkData = function (personId) {
    if (!personId) {
        const pane = document.querySelector('.tab-pane-telework');
        if (pane) personId = pane.getAttribute('data-person-id');
    }
    if (!personId) return;

    fetch(`/employee/person/${personId}/telework/data/`, {
        headers: {'X-Requested-With': 'XMLHttpRequest'}
    })
        .then(res => res.json())
        .then(data => {
            if (!data.success) return;

            const readOnlyAlert = document.getElementById('teleworkReadOnlyAlert');
            const punchGroup = document.getElementById('teleworkAttendanceGroup');
            const actionContainer = document.getElementById('teleworkActivityActionContainer');

            if (!data.is_own_profile) {
                if (readOnlyAlert) readOnlyAlert.style.display = 'flex';
                if (punchGroup) punchGroup.style.display = 'none';
                if (actionContainer) {
                    actionContainer.innerHTML = `
                        <div class="telework-readonly-indicator">
                            <i class="fa-solid fa-eye"></i>
                            <span>Vista de solo lectura</span>
                        </div>`;
                }
            } else {
                if (readOnlyAlert) readOnlyAlert.style.display = 'none';
                if (punchGroup) punchGroup.style.display = 'flex';

                const btnIncome = document.getElementById('btnPunchIncome');
                const btnExit = document.getElementById('btnPunchExit');
                if (btnIncome) btnIncome.disabled = (data.last_punch_type === 'INCOME');
                if (btnExit) btnExit.disabled = (data.last_punch_type !== 'INCOME');

                if (actionContainer) {
                    if (data.last_punch_type === 'EXIT') {
                        actionContainer.innerHTML = `
                            <div class="text-center p-2 bg-light border rounded">
                                <i class="fa-solid fa-lock text-red me-1"></i>
                                <span class="small fw-bold text-muted">Salida registrada</span>
                            </div>`;
                    } else if (!data.has_income) {
                        actionContainer.innerHTML = `
                            <div class="text-center p-2 bg-light border rounded">
                                <i class="fa-solid fa-circle-exclamation text-warning me-1"></i>
                                <span class="small fw-bold text-muted">Debe marcar entrada</span>
                            </div>`;
                    } else {
                        actionContainer.innerHTML = `
                            <button type="button" class="btn-telework-square green"
                                    onclick="openAjaxModal('/employee/person/${personId}/telework/activity/modal/')">
                                <i class="fa-solid fa-plus"></i>
                                <span>Nueva<br>Actividad</span>
                            </button>`;
                    }
                }
            }

            // Marcaciones
            const punchesContainer = document.getElementById('teleworkPunchesContainer');
            if (punchesContainer) {
                if (!data.punches || data.punches.length === 0) {
                    punchesContainer.innerHTML = `
                        <div class="text-center py-4 opacity-50">
                            <i class="fa-solid fa-clock-rotate-left fa-2x mb-2 text-secondary"></i>
                            <p class="small text-muted mb-0">No hay marcaciones registradas hoy.</p>
                        </div>`;
                } else {
                    punchesContainer.innerHTML = data.punches.map(p => {
                        const isIncome = p.type_code === 'INCOME';
                        return `
                            <div class="day-card-compact">
                                <div class="day-col">
                                    <span class="day-label">EVENTO</span>
                                    <span class="${isIncome ? 'text-green' : 'text-red'} fw-bold small">
                                        ${p.type.toUpperCase()}
                                    </span>
                                </div>
                                <div class="day-col-center">
                                    <span class="day-label">HORA</span>
                                    <span class="day-time">${p.time}</span>
                                </div>
                                <div class="day-col-right">
                                    <span class="day-label">UBICACIÓN</span>
                                    <span class="badge-gps">
                                        <i class="fa-solid fa-location-dot text-red me-1"></i> GPS VÁLIDO
                                    </span>
                                </div>
                            </div>`;
                    }).join('');
                }
            }

            // Actividades
            const activitiesContainer = document.getElementById('teleworkActivitiesContainer');
            if (activitiesContainer) {
                if (!data.activities || data.activities.length === 0) {
                    activitiesContainer.innerHTML = `
                        <div class="text-center py-4 opacity-50">
                            <i class="fa-solid fa-folder-open fa-2x mb-2 text-secondary"></i>
                            <p class="small text-muted mb-0">No hay actividades reportadas hoy.</p>
                        </div>`;
                } else {
                    activitiesContainer.innerHTML = data.activities.map(a => `
                        <div class="telework-activity-card">
                            <div>
                                <div class="fw-bold small text-dark">${a.title}</div>
                                ${a.detail ? `<div class="telework-badge-sub">${a.detail}</div>` : ''}
                            </div>
                            <div class="telework-progress-group">
                                <span class="fw-bold small text-dark">${a.time}</span>
                                <div class="progress-track" title="${a.percentage}%">
                                    <div class="progress-fill" style="width: ${a.percentage}%"></div>
                                </div>
                            </div>
                        </div>
                    `).join('');
                }
            }
        })
        .catch(err => console.error("Error cargando datos de teletrabajo:", err));
};

document.addEventListener('click', function (e) {
    const btn = e.target.closest('.employee-detail-button');
    if (btn) {
        const label = btn.querySelector('.employee-detail-button-label')?.textContent?.trim().toLowerCase();
        if (label && label.includes('teletrabajo')) {
            const wizardRoot = document.getElementById('employeeWizardApp');
            const personId = wizardRoot ? wizardRoot.getAttribute('data-person-id') : null;
            setTimeout(() => {
                window.loadTeleworkData(personId);
            }, 120);
        }
    }
});

document.addEventListener('DOMContentLoaded', function () {
    const pane = document.querySelector('.tab-pane-telework');
    if (pane) {
        window.loadTeleworkData(pane.getAttribute('data-person-id'));
    }
});

window.markTeleworkAttendance = function (punchType, personId) {
    const doSubmit = (lat = 0, lng = 0) => {
        const formData = new FormData();
        formData.append('punch_type', punchType);
        formData.append('latitude', lat);
        formData.append('longitude', lng);

        const csrf = document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';

        fetch(`/employee/person/${personId}/telework/attendance/mark/`, {
            method: 'POST',
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': csrf
            },
            body: formData
        })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    showToast(data.message || 'Marcación registrada con éxito.', 'success');
                    loadTeleworkData(personId);
                } else {
                    Swal.fire({
                        icon: 'warning',
                        title: 'Atención',
                        text: data.message || 'No se pudo registrar la marcación.',
                        confirmButtonText: 'Entendido'
                    });
                }
            })
            .catch(err => {
                console.error(err);
                Swal.fire({
                    icon: 'error',
                    title: 'Error',
                    text: 'Error de comunicación al registrar marcación.',
                    confirmButtonText: 'Entendido'
                });
            });
    };

    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            pos => doSubmit(pos.coords.latitude, pos.coords.longitude),
            () => doSubmit(0, 0),
            {timeout: 6000}
        );
    } else {
        doSubmit(0, 0);
    }
};