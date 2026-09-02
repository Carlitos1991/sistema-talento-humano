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
// CONFIGURACIÓN GLOBAL DE SWEETALERT2
if (typeof Swal !== 'undefined') {
    window.Swal = Swal.mixin({
        // 1. SOLUCIÓN AL MOVIMIENTO DE LA TABLA:
        scrollbarPadding: false,
        heightAuto: false,

        // 2. SOLUCIÓN AL DISEÑO DE BOTONES:
        buttonsStyling: false, // Desactiva los colores en línea por defecto de Swal
        customClass: {
            // Aplica las hermosas clases que ya tienes en style.css
            confirmButton: 'swal2-confirm btn-swal-success',
            cancelButton: 'swal2-cancel btn-swal-cancel'
        }
    });
}

// 2. MODALES ESTÁTICOS (Para los que ya están en el HTML como el de "Nuevo")
window.openModal = function (id) {
    const modal = document.getElementById(id);
    if (modal) {
        $(modal).find('select').select2({
            width: '100%'
        });
        document.body.classList.add('no-scroll');
        modal.classList.remove('hidden');
    } else {
        console.error("No se encontró el modal con ID: " + id);
    }
};

// 3. MODALES DINÁMICOS
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
                document.body.classList.add('no-scroll');

                // 1. PRIMERO quitamos el hidden para que el navegador asigne el alto real
                modal.classList.remove('hidden');

                // 2. LUEGO inicializamos Select2 dándole tiempo al DOM de pintar (10ms es suficiente)
                setTimeout(() => {
                    $(modal).find('select').select2({
                        width: '100%',
                        // Al estar ya visible, no forzará un recálculo violento en Flexbox
                        dropdownParent: $(modal).find('.modal-body-custom').length ? $(modal).find('.modal-body-custom') : $(modal)
                    });
                }, 10);
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

        // Reemplazamos confirmButtonColor por tus clases CSS
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

        // Wrapper: el .content-table que agrupa controles + tabla
        this.wrapper = this.table.closest('.content-table') || this.table.parentElement;

        // Input de búsqueda: busca dentro del wrapper primero, luego por ID global
        this.searchInput = this.wrapper.querySelector('.table-search-input')
            || document.getElementById('table-search');
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
        if (!this.scrollContainer) {
            return;
        }

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

    // ─── BÚSQUEDA ────────────────────────────────────────────────────────────

    initSearch() {
        if (!this.searchInput) {
            console.warn('TableManager: No se encontró el input de búsqueda.');
            return;
        }
        // FIX: solo debe existir UN listener de 'input' activo por campo de
        // búsqueda, sin importar cuántas veces se recree TableManager (p.ej.
        // tras cada búsqueda AJAX que reemplaza la tabla e instancia una
        // TableManager nueva). Antes, cada instancia agregaba su propio
        // listener sin quitar el anterior; las instancias viejas (con
        // originalRows/tbody obsoletos) seguían disparándose en cada tecleo
        // junto con la nueva, produciendo renders en conflicto y resultados
        // que parecían "resetearse" solos. Guardamos la referencia del
        // handler en el propio DOM del input (no en la instancia) para
        // poder quitar el de la instancia ANTERIOR antes de añadir el de esta.
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

    // ─── FILTROS ──────────────────────────────────────────────────────────────
    applyGlobalFilters() {
        let result = [...this.originalRows];

        // Filtro de columna (tarjetas)
        if (this.filterState.value !== 'all' && this.filterState.column) {
            result = result.filter(row =>
                row.getAttribute(`data-${this.filterState.column}`) === this.filterState.value
            );
        }

        // Búsqueda de texto
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

    /**
     * Filtra las filas por una columna específica y valor.
     * @param {string} columnName - Nombre de la columna a filtrar (se busca en data-{columnName})
     * @param {string} value - Valor a filtrar: 'all' para mostrar todas, o un valor específico
     */
    filterByColumnData(columnName, value) {
        this.filterState.column = columnName;
        this.filterState.value = value;
        this.applyGlobalFilters();
    }

    // ─── SORT ─────────────────────────────────────────────────────────────────

    initSortHeaders() {
        const headers = this.table.querySelectorAll('thead th');
        headers.forEach((th, index) => {
            if (th.classList.contains('no-sort')) return;
            th.classList.add('sortable-header');
            // Añadir el indicador de orden SIN sobrescribir innerHTML (evita romper estructura)
            if (!th.querySelector('.sort-arrow')) {
                const spacer = document.createTextNode(' ');
                const span = document.createElement('span');
                span.className = 'sort-arrow';
                span.textContent = '⇅';
                th.appendChild(spacer);
                th.appendChild(span);
            }

            // Evitar doble-binding si ya fue inicializado
            if (!th.dataset.tmInit) {
                th.addEventListener('click', (e) => {
                    // Si un manejador delegado ya está procesando este click, ignorar
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
                                    const arrow = ths[s.col].querySelector('.sort-arrow');
                                    if (arrow) arrow.innerText = s.asc ? '↑' : '↓';
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

    /**
     * Compara dos strings que pueden ser:
     *  - Enteros puros:          "1", "2", "10"
     *  - Versión jerárquica:     "1.1", "1.2", "2.3.1"  ← caso código de unidades
     *  - Texto:                  "PROCESOS", "Dirección..."
     *
     * Estrategia:
     *  1. Si ambos son versión semántica (segmentos todos numéricos separados por "."),
     *     se compara segmento a segmento como enteros → 1 < 1.1 < 1.2 < 2 < 10
     *  2. Si ambos son número puro, se compara como float.
     *  3. Si no, localeCompare (texto).
     */
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

        // Intento numérico puro (ignora símbolos como $ o %)
        const numA = parseFloat(a.replace(/[^0-9.-]+/g, ''));
        const numB = parseFloat(b.replace(/[^0-9.-]+/g, ''));
        if (!isNaN(numA) && !isNaN(numB) && a !== '' && b !== '') {
            return numA - numB;
        }

        // Texto
        return a.localeCompare(b, undefined, {sensitivity: 'base'});
    }

    sortData() {
        if (this.sortCol === null) return;
        this.currentRows.sort((rowA, rowB) => {
            const cellElA = rowA.children[this.sortCol];
            const cellElB = rowB.children[this.sortCol];
            // Prefer data-sort attribute when present (allows normalized sort keys)
            const cellA = (cellElA && cellElA.dataset && cellElA.dataset.sort) ? String(cellElA.dataset.sort).trim() : (cellElA?.innerText.trim() || '');
            const cellB = (cellElB && cellElB.dataset && cellElB.dataset.sort) ? String(cellElB.dataset.sort).trim() : (cellElB?.innerText.trim() || '');
            const cmp = this.compareValues(cellA, cellB);
            return this.sortAsc ? cmp : -cmp;
        });
    }

    // ─── ESTADÍSTICAS (Levels) ────────────────────────────────────────────────

    updateStats() {
        // Solo aplica en la vista de Niveles (stat-total / stat-active / stat-inactive)
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

    // ─── PAGINACIÓN ───────────────────────────────────────────────────────────

    initPagination() {
        const contentTable = this.table.closest('.content-table');

        // Reutiliza el paginador que ya existe junto a este .content-table
        // en vez de crear uno nuevo cada vez (evita duplicados que "mueven" los botones)
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
        /*
         * FIX #2 — Paginador siempre visible (incluso con 0 resultados):
         * Antes: se ocultaba cuando totalPages <= 1 Y había filas.
         * Ahora: SIEMPRE se muestra el paginador con la info "Mostrando 0 de 0"
         * para que no "suba" al quedarse sin contenido y el layout no salte.
         *
         * Solo se oculta si hay exactamente 1 página CON resultados (no hace
         * falta navegar) — y aun así se muestra el texto informativo.
         */
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

        if (!showControls) return; // No conectar eventos si los controles están ocultos

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

    // ─── RENDER PRINCIPAL ─────────────────────────────────────────────────────

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
            // Construir una fila vacía con tantas celdas como encabezados para
            // preservar el ancho calculado de cada columna cuando no hay datos.
            const headerThs = Array.from(this.table.querySelectorAll('thead th'));
            const emptyRow = document.createElement('tr');
            emptyRow.className = 'empty-results-row';

            if (headerThs.length > 0) {
                // 1) Spacer row: una fila invisible con una celda por columna
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
                    // Hacerla de altura mínima para no afectar layout vertical
                    td.style.padding = '0';
                    td.style.border = 'none';
                    spacerRow.appendChild(td);
                });
                this.tbody.appendChild(spacerRow);

                // 2) Mensaje centrado en una sola fila que abarca todas las columnas
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
                // Fallback: una sola celda que ocupa todo el ancho
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

document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.managed-table').forEach(t => new TableManager(t));
});


document.addEventListener('click', (e) => {
    const th = e.target.closest('.managed-table thead th');
    if (!th) return;
    if (th.classList.contains('no-sort')) return;
    const table = th.closest('.managed-table');
    if (!table) return;

    if (table.dataset.externalPagination === 'true' || table.dataset.externalSearch === 'true') return;

    // Determinar índice de la columna
    const headers = Array.from(table.querySelectorAll('thead th'));
    const colIndex = headers.indexOf(th);
    if (colIndex === -1) return;

    // Obtener o crear TableManager
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

    // Evitar doble ejecución: marcar el th temporalmente
    try {
        th._tm_handling = true;
        mgr.handleSort(colIndex, th, headers);
    } catch (err) {
        console.warn('TableManager: error en handleSort delegado', err);
    } finally {
        setTimeout(() => {
            try {
                delete th._tm_handling;
            } catch (_) {
            }
        }, 60);
    }

}, true);

// Expose constructor on window explicitly in case environments differ
try {
    window.TableManager = TableManager;
} catch (e) { /* ignore */
}
// =====================================================================
// DELEGADO GLOBAL PARA PAGINACIÓN EXTERNA AJAX
// Resuelve la "muerte" de los botones al reemplazar el HTML
// =====================================================================
document.addEventListener('click', (e) => {
    const btn = e.target.closest('.page-btn');
    if (!btn) return;

    // Buscar la tabla administrada principal
    const table = document.querySelector('.managed-table');
    if (!table || table.dataset.externalPagination !== 'true') return;

    // Ignorar si el botón está deshabilitado
    if (btn.hasAttribute('disabled') || btn.classList.contains('disabled')) return;

    // Bloquear scripts viejos/rotos del usuario
    e.preventDefault();
    e.stopImmediatePropagation();

    const page = btn.dataset.page;
    if (!page) return;

    const oldTableContainer = table.closest('.table-container');
    const oldPagination = btn.closest('.pagination-container');

    // Efecto de carga
    if (oldTableContainer) {
        oldTableContainer.style.opacity = '0.4';
        oldTableContainer.style.pointerEvents = 'none';
    }

    // Preparar URL preservando búsqueda y ordenamiento actual
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

    // Petición AJAX idéntica a la del ordenamiento
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

            // Re-inicializar JS para mantener la tabla viva
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
