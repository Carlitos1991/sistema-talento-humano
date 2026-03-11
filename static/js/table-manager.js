/* static/js/table-manager.js */

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

        // data-external-pagination="true" → paginación manejada por backend/Vue
        // data-external-search="true"     → búsqueda manejada por backend/Vue
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

        // Evitar inicializar manejadores de ordenamiento en tablas que delegan
        // paginación/búsqueda al backend (evita conflicto con código específico)
        if (!this.externalPagination && !this.externalSearch) this.initSortHeaders();
        if (!this.externalSearch) this.initSearch();
        if (!this.externalPagination) this.initPagination();
        if (!this.externalPagination) this.render();

        this.table._tableManager = this;
    }

    // ─── BÚSQUEDA ────────────────────────────────────────────────────────────

    initSearch() {
        if (!this.searchInput) {
            console.warn('TableManager: No se encontró el input de búsqueda.');
            return;
        }
        this.searchInput.addEventListener('input', (e) => {
            this.filterState.search = e.target.value.toLowerCase().trim();
            this.applyGlobalFilters();
        });
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

        // Si la tabla usa paginación/filtrado externo, delegar el ordenamiento al servidor
        if (this.externalPagination || this.externalSearch) {
            // Determinar campo de orden desde el encabezado (data-field)
            const headerEl = allHeaders[colIndex];
            const field = headerEl?.dataset?.field || null;
            // Guardar estado globalmente para que el cliente que reciba el HTML lo reaplique
            window._personExport = window._personExport || {};
            window._personExport.sort = {col: colIndex, asc: this.sortAsc, field: field};
            // Intentar invocar fetchPeople; si no existe todavía (Vue no montado), hacer fallback directo
            if (typeof window.fetchPeople === 'function') {
                window.fetchPeople(1);
                return;
            }

            // Fallback: si conocemos la URL del listado, realizar fetch directo al endpoint
            if (!window._personExport) window._personExport = {};
            // Intentar recuperar la URL desde el DOM si aún no la expuso person.js
            if (!window._personExport.listUrl) {
                const appEl = document.getElementById('personApp');
                if (appEl && appEl.dataset && appEl.dataset.urls) {
                    try {
                        // dataset.urls contiene JSON con saltos de línea en template; limpiarlos
                        const raw = appEl.dataset.urls.replace(/\n/g, '');
                        const parsed = JSON.parse(raw);
                        if (parsed && parsed.list) window._personExport.listUrl = parsed.list;
                    } catch (e) {
                        console.warn('TableManager: no se pudo parsear data-urls de #personApp', e);
                    }
                }
            }
            if (window._personExport && window._personExport.listUrl) {
                try {
                    const params = new URLSearchParams();
                    params.append('page', 1);
                    if (window._personExport.sort && window._personExport.sort.field) {
                        params.append('sort_field', window._personExport.sort.field);
                        params.append('sort_dir', window._personExport.sort.asc ? 'asc' : 'desc');
                    }
                    const url = `${window._personExport.listUrl}?${params.toString()}`;
                    fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
                        .then(r => r.json())
                        .then(data => {
                            if (data.success && data.html) {
                                const container = document.getElementById('tableContainer') || document.getElementById('table-app') || document.querySelector('.table-container');
                                if (container) {
                                    container.innerHTML = data.html;
                                    // Inicializar nueva tabla y reaplicar sort
                                    const newTable = container.querySelector('.managed-table');
                                    if (newTable) {
                                        try {
                                            new TableManager(newTable);
                                        } catch (e) {
                                            console.error('Error inicializando TableManager en fallback:', e);
                                        }
                                        // Reaplicar clase de sort
                                        if (window._personExport && window._personExport.sort) {
                                            const s = window._personExport.sort;
                                            const ths = newTable.querySelectorAll('thead th');
                                            const th = ths[s.col];
                                            if (th) {
                                                th.classList.remove('sorted-asc', 'sorted-desc');
                                                th.classList.add(s.asc ? 'sorted-asc' : 'sorted-desc');
                                                const arrow = th.querySelector('.sort-arrow');
                                                if (arrow) arrow.innerText = s.asc ? '↑' : '↓';
                                            }
                                        }
                                    }
                                }
                            }
                        })
                        .catch(e => console.warn('TableManager fallback fetch error:', e));
                    return;
                } catch (e) {
                    console.warn('TableManager: error during fallback fetch', e);
                }
            }

            // Si no hay URL conocida, reintentar corto (compatibilidad)
            let attempts = 0;
            const maxAttempts = 20; // hasta ~2s
            const retryInterval = 100;
            const interval = setInterval(() => {
                attempts += 1;
                if (typeof window.fetchPeople === 'function') {
                    clearInterval(interval);
                    try {
                        window.fetchPeople(1);
                    } catch (e) {
                        console.warn('TableManager: error calling fetchPeople after it became available', e);
                    }
                } else if (attempts >= maxAttempts) {
                    clearInterval(interval);
                    console.warn('TableManager: fetchPeople not available after retries.');
                }
            }, retryInterval);
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
            const cellA = rowA.children[this.sortCol]?.innerText.trim() || '';
            const cellB = rowB.children[this.sortCol]?.innerText.trim() || '';
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
        /*
         * FIX #1 — Posición del paginador:
         * El paginador debe vivir FUERA de .content-table (igual que en levels),
         * pero DENTRO de #table-app, para que herede el fondo correcto y quede
         * siempre pegado al borde inferior del card.
         *
         * Jerarquía esperada:
         *   #table-app
         *     .content-table        ← wrapper (tabla + controles)
         *     .pagination-container ← paginador (hermano de .content-table)
         *
         * Si ya existe un .pagination-container hermano, lo reutilizamos.
         * Si no, lo creamos justo después de .content-table.
         */
        const tableApp = this.table.closest('#table-app');
        const contentTable = this.table.closest('.content-table');

        // Ensure table has an id for pagination association
        if (!this.table.dataset.tmId) this.table.dataset.tmId = 'tm-' + Math.random().toString(36).slice(2,8);

        // Try to reuse an existing pagination container already associated to this table
        let pagContainer = document.querySelector('.pagination-container[data-tm-for="' + this.table.dataset.tmId + '"]');

        if (!pagContainer) {
            // Search within #table-app for a pagination container that is not inside a content-table
            if (tableApp) {
                const candidates = Array.from(tableApp.querySelectorAll('.pagination-container'));
                pagContainer = candidates.find(el => !el.closest('.content-table')) || null;
            }
        }

        if (!pagContainer) {
            // Fallback: search near the contentTable parent for any pagination-container not inside the contentTable
            const parent = (contentTable && contentTable.parentNode) ? contentTable.parentNode : this.table.parentNode;
            const candidates = Array.from(parent.querySelectorAll('.pagination-container'));
            pagContainer = candidates.find(el => !el.closest('.content-table')) || null;
        }

        if (!pagContainer) {
            // Create and place as sibling of .content-table (outside it)
            pagContainer = document.createElement('div');
            pagContainer.className = 'pagination-container';

            if (contentTable && contentTable.parentNode) {
                contentTable.parentNode.insertBefore(pagContainer, contentTable.nextSibling);
            } else {
                this.table.parentNode.insertBefore(pagContainer, this.table.nextSibling);
            }
        }

        // Associate this pagContainer explicitly to this table to avoid other managers reusing it
        try { pagContainer.dataset.tmFor = this.table.dataset.tmId; } catch(e) {}
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
                <button class="page-btn btn-first" title="Primera" ${prevDisabled ? 'disabled' : ''}>
                    <i class="fas fa-angle-double-left"></i>
                </button>
                <button class="page-btn btn-prev" title="Anterior" ${prevDisabled ? 'disabled' : ''}>
                    <i class="fas fa-angle-left"></i>
                </button>
                <div class="page-input-wrapper">
                    <input type="number" class="page-input" value="${this.currentPage}" min="1" max="${totalPages}">
                    <span class="total-pages-badge">de ${totalPages}</span>
                </div>
                <button class="page-btn btn-next" title="Siguiente" ${nextDisabled ? 'disabled' : ''}>
                    <i class="fas fa-angle-right"></i>
                </button>
                <button class="page-btn btn-last" title="Última" ${nextDisabled ? 'disabled' : ''}>
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

        this.pagContainer.querySelector('.btn-first').onclick = () => go(1);
        this.pagContainer.querySelector('.btn-prev').onclick = () => go(this.currentPage - 1);
        this.pagContainer.querySelector('.btn-next').onclick = () => go(this.currentPage + 1);
        this.pagContainer.querySelector('.btn-last').onclick = () => go(totalPages);

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
                    } catch (e) {}
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

// Auto-inicializar todas las tablas con clase .managed-table al cargar el DOM
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.managed-table').forEach(t => new TableManager(t));
});

// Delegado global: asegurar que clicks en th de tablas manejadas siempre invoquen el orden
document.addEventListener('click', (e) => {
    const th = e.target.closest('.managed-table thead th');
    if (!th) return;

    const table = th.closest('.managed-table');
    if (!table) return;

    // Evitar que el delegado global gestione ordenamiento para tablas que
    // usan paginación/búsqueda externa (servidor/Vue) — esas vistas gestionan
    // su propio comportamiento y evitar esto previene conflictos.
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
        setTimeout(() => { try { delete th._tm_handling; } catch(_){} }, 60);
    }

}, true);

// Expose constructor on window explicitly in case environments differ
try { window.TableManager = TableManager; } catch (e) { /* ignore */ }
