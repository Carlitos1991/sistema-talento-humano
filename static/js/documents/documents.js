/* static/js/documents/documents.js */
const { createApp } = Vue;

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

const documentsApp = createApp({
    delimiters: ['[[', ']]'],
    data() {
        return {
            loading: false,
            // Selección actual de tipo para creación
            selectedTypeId: '',
            selectedTypeName: '',
            // Paginación / búsqueda frontend
            currentPage: 1,
            pageSize: 10,
            totalRows: 0,
            totalPages: 1,
            searchTerm: '',
            allDOMRows: [],
            // Estadísticas y filtros
            stats: { total: 0, regimes: [], display_total: 0 },
            canDelete: false,
            statsYear: new Date().getFullYear(),
            dateFrom: null,
            dateTo: null,
            isAdvancedSearch: false,
                advancedFilters: { documents: '', q: '' }
            ,
            // Ordenamiento
            sortField: null,
            sortAsc: true
            ,
            editingId: null
            ,creating: false
        };
    },
    mounted() {
        // Inicializar flags y stats desde HTML renderizado por el servidor (si existe)
        const initialStatsScript = document.getElementById('initial-doc-stats');
        const appEl = document.getElementById('documents-app');
        if (appEl && appEl.dataset && typeof appEl.dataset.canDelete !== 'undefined') {
            this.canDelete = String(appEl.dataset.canDelete) === '1' || String(appEl.dataset.canDelete) === 'true';
        }
        if (initialStatsScript && initialStatsScript.textContent) {
            try {
                const s = JSON.parse(initialStatsScript.textContent);
                const regimes = (s.regimes || []).map(r => ({ ...r, code: String(r.code), display_count: this.canDelete ? (r.count || 0) : (r.user_count || 0) }));
                this.stats = { total: s.total || 0, total_user: s.total_user || 0, regimes };
                this.stats.display_total = this.canDelete ? this.stats.total : this.stats.total_user;
            } catch (e) {
                console.warn('No se pudo parsear initial-doc-stats:', e);
            }
        }
        this.initDelegatedListeners();
        // Deshabilitar el botón Nuevo Documento por defecto (visualmente y funcionalmente)
        this.setAddButtonEnabled(false);
        // Leer atributo del contenedor para saber si el usuario puede ver stats globales
            // Inputs de rango de fechas para estadísticas (Desde / Hasta)
        const dateFromInput = document.getElementById('stats-date-from');
        const dateToInput = document.getElementById('stats-date-to');
        // Inicializar valores desde DOM si existen
        if (dateFromInput) {
            this.dateFrom = dateFromInput.value || null;
        }
        if (dateToInput) {
            this.dateTo = dateToInput.value || null;
        }
        // Añadir listeners (debounced) para recargar tabla cuando cambian
        const bindDateChange = (el) => {
            if (!el) return;
            let t = null;
            el.addEventListener('input', (ev) => {
                clearTimeout(t);
                t = setTimeout(() => {
                    this.dateFrom = dateFromInput ? dateFromInput.value : null;
                    this.dateTo = dateToInput ? dateToInput.value : null;
                    console.debug('date inputs changed ->', {date_from: this.dateFrom, date_to: this.dateTo});
                    this.currentPage = 1;
                    this.fetchTable(this.isAdvancedSearch, 1);
                }, 350);
            });
            el.addEventListener('change', () => {
                this.dateFrom = dateFromInput ? dateFromInput.value : null;
                this.dateTo = dateToInput ? dateToInput.value : null;
                console.debug('date inputs changed (change) ->', {date_from: this.dateFrom, date_to: this.dateTo});
                this.currentPage = 1;
                this.fetchTable(this.isAdvancedSearch, 1);
            });
        };
        bindDateChange(dateFromInput);
        bindDateChange(dateToInput);
        // Finalmente, cargar tabla (después de inicializar statsYear y canDelete)
        this.fetchTable();
    },
    methods: {
        initDelegatedListeners() {
            const searchInput = document.getElementById('table-search-document');
            if (searchInput) {
                // Debounce búsqueda para evitar peticiones en cada tecla
                let to = null;
                searchInput.addEventListener('input', (e) => {
                    clearTimeout(to);
                    const val = e.target.value.trim();
                    to = setTimeout(() => {
                        // Usar búsqueda en backend (tabla con external_search)
                        this.advancedFilters.q = val;
                        this.currentPage = 1;
                        this.fetchTable(this.isAdvancedSearch, 1);
                    }, 350);
                });
            }

            const tableWrapper = document.getElementById('table-content-wrapper');
            if (tableWrapper) {
                tableWrapper.addEventListener('click', (e) => {
                    const btn = e.target.closest('button');
                    if (!btn) return;
                    const action = btn.dataset.action;
                    const id = btn.dataset.id;
                    if (action === 'edit') this.editDocument(id);
                    if (action === 'advanced-search-empty') this.openSearchModal && this.openSearchModal();
                    // Nota: no manejar aquí los botones con id btn-prev/btn-next para
                    // evitar dobles invocaciones (hay listeners específicos añadidos
                    // directamente a esos botones más abajo).
                    // Si el click proviene de una tarjeta stat que tiene data-regime-code
                    const statEl = e.target.closest('.stat-card');
                    if (statEl && statEl.dataset && statEl.dataset.code) {
                        // actualizamos selectedType
                        this.selectedTypeId = String(statEl.dataset.code);
                        this.selectedTypeName = statEl.querySelector('.stat-left h3') ? statEl.querySelector('.stat-left h3').innerText.trim() : '';
                        // habilitar/deshabilitar boton Nuevo Documento (con estilo)
                        this.setAddButtonEnabled(this.selectedTypeId !== '');
                    }
                });

                // Click en encabezados para ordenar (delegado)
                tableWrapper.addEventListener('click', (e) => {
                    const th = e.target.closest('thead th');
                    if (!th) return;
                    // Usar atributo data-sortable o data-field
                    const field = th.dataset.sortable || th.dataset.field || null;
                    if (!field) return;
                    // Alternar dirección si ya estamos ordenando por ese campo
                    if (this.sortField === field) this.sortAsc = !this.sortAsc;
                    else { this.sortField = field; this.sortAsc = true; }
                    // Refrescar desde servidor con nuevo orden
                    this.currentPage = 1;
                    this.fetchTable(this.isAdvancedSearch);
                });

                // Botones de paginación externos al wrapper (hermanos dentro de .content-table)
                const btnPrevGlobal = document.getElementById('btn-prev');
                const btnNextGlobal = document.getElementById('btn-next');
                if (btnPrevGlobal) btnPrevGlobal.addEventListener('click', (ev) => { ev.preventDefault(); this.prevPage(); });
                if (btnNextGlobal) btnNextGlobal.addEventListener('click', (ev) => { ev.preventDefault(); this.nextPage(); });
            }
        },

        // Habilita / deshabilita visualmente el botón 'Nuevo Documento'
        setAddButtonEnabled(enabled) {
            const btn = document.getElementById('btn-add-document');
            if (!btn) return;
            btn.disabled = !enabled;
            if (!enabled) {
                btn.classList.add('btn-disabled');
                btn.style.opacity = '0.6';
                btn.style.pointerEvents = 'none';
                btn.style.cursor = 'not-allowed';
            } else {
                btn.classList.remove('btn-disabled');
                btn.style.opacity = '';
                btn.style.pointerEvents = '';
                btn.style.cursor = '';
            }
        },

        async fetchTable(advanced = false, page = 1) {
            this.loading = true;
            this.isAdvancedSearch = advanced;

            // Asegurar que la página solicitada esté dentro de los límites conocidos
            let requestedPage = Math.max(1, Number(page) || 1);
            if (this.totalPages && requestedPage > this.totalPages) requestedPage = this.totalPages;

            const paramsObj = {
                advanced: advanced ? 1 : 0,
                q: this.advancedFilters.q || '',
                documents: this.advancedFilters.documents || '',
                page: requestedPage
            };
            // Añadir rango de fechas para estadísticas y filtrado (si están definidos)
            if (this.dateFrom) paramsObj.date_from = this.dateFrom;
            if (this.dateTo) paramsObj.date_to = this.dateTo;
            // Añadir orden si está definido
            if (this.sortField) {
                paramsObj.sort_field = this.sortField;
                paramsObj.sort_dir = this.sortAsc ? 'asc' : 'desc';
            }
            const params = new URLSearchParams(paramsObj).toString();
            try {
                const url = `${window.location.pathname}?${params}`;
                console.debug('Fetching documents with URL', url, 'paramsObj', paramsObj);
                const response = await fetch(url, {
                    headers: {'X-Requested-With': 'XMLHttpRequest'}
                });

                if (!response.ok) {
                    const txt = await response.text();
                    console.warn('Página inválida (status):', response.status, url);
                    // Mostrar mensaje amable al usuario
                    try {
                        Swal.fire('Página inválida', `Página inválida (${requestedPage}): Esa página no contiene resultados`, 'warning');
                    } catch (e) {
                        console.warn('Swal no disponible para mostrar aviso de página inválida');
                    }
                    // Recuperar a la última página conocida válida
                    const fallback = (this.totalPages && this.totalPages >= 1) ? this.totalPages : 1;
                    if (fallback !== this.currentPage) {
                        this.currentPage = fallback;
                        // Reintentar cargar la página válida
                        await this.fetchTable(this.isAdvancedSearch, this.currentPage);
                    }
                    this.loading = false;
                    return;
                }

                const data = await response.json();
                console.debug('documents.fetchTable response stats:', data.stats);

                const container = document.getElementById('table-content-wrapper');
                if (container) container.innerHTML = data.table_html || data.html || container.innerHTML;

                // Inicializar TableManager para la nueva tabla (compatibilidad)
                const newTable = container ? container.querySelector('.managed-table') : null;
                if (newTable) {
                    try {
                        new TableManager(newTable);
                    } catch (e) {
                        console.warn('No se pudo inicializar TableManager en documents:', e);
                    }
                    // Exponer orden actual globalmente para compatibilidad con otros módulos
                    window._documentExport = window._documentExport || {};
                    if (this.sortField) window._documentExport.sort = {field: this.sortField, asc: this.sortAsc};
                    // Marcar visualmente la columna ordenada si aplica
                    try {
                        const ths = newTable.querySelectorAll('thead th');
                        ths.forEach((th) => {
                            const fld = th.dataset.sortable || th.dataset.field || null;
                            if (!fld) return;
                            th.classList.add('sortable-header');
                            if (!th.querySelector('.sort-arrow')) {
                                const span = document.createElement('span');
                                span.className = 'sort-arrow';
                                span.textContent = '⇅';
                                th.appendChild(span);
                            }
                            if (this.sortField && fld === this.sortField) {
                                th.classList.remove('sorted-asc', 'sorted-desc');
                                th.classList.add(this.sortAsc ? 'sorted-asc' : 'sorted-desc');
                                const arrow = th.querySelector('.sort-arrow'); if (arrow) arrow.innerText = this.sortAsc ? '↑' : '↓';
                            }
                        });
                    } catch (e) { /* silent */ }
                    }

                if (data.stats) {
                    // Asegurar que los códigos vienen como strings para comparación en plantilla
                    const regimes = (data.stats.regimes || []).map(r => ({
                        ...r,
                        code: String(r.code),
                        display_count: this.canDelete ? (r.count || 0) : (r.user_count || 0)
                    }));
                    this.stats = { total: data.stats.total || 0, total_user: data.stats.total_user || 0, regimes };
                    // display_total será global si puede eliminar, sino el conteo del usuario
                    this.stats.display_total = this.canDelete ? this.stats.total : this.stats.total_user;
                }

                // Si el servidor devuelve info de paginación, sincronizar estado
                let serverTotalPages = null;
                if (data.pagination) {
                    this.totalRows = data.pagination.total_items || 0;
                    this.currentPage = data.pagination.current_page || requestedPage;
                    serverTotalPages = data.pagination.total_pages || null;
                    // Sincronizar totalPages conocido
                    if (serverTotalPages) this.totalPages = serverTotalPages;
                    console.debug('documents pagination from server:', data.pagination);
                }

                this.$nextTick(() => {
                    setTimeout(() => {
                        this.indexRows();
                        // Detectar si la tabla inyectada es manejada por el servidor
                        const injectedTable = container ? container.querySelector('.managed-table') : null;
                        const serverDriven = injectedTable && (injectedTable.dataset.externalPagination === 'true' || injectedTable.dataset.externalSearch === 'true');

                        if (serverDriven) {
                            // Mostrar/ocultar mensaje "no results" según conteo devuelto por servidor
                            const emptyRow = document.getElementById('frontend-no-results');
                            if (emptyRow) {
                                const showMsg = (this.totalRows === 0);
                                showMsg ? emptyRow.classList.remove('hidden') : emptyRow.classList.add('hidden');
                            }
                            // Asegurar que las filas del servidor sean visibles (por si otro código las ocultó)
                            this.allDOMRows.forEach(r => r.style.display = '');
                        } else {
                            // Lógica frontend (filtrado + paginado) cuando no es manejado por servidor
                            this.applyFrontendLogic();
                        }
                        // Preferir totalPages proporcionado por el servidor si existe
                        const totalPagesToUse = serverTotalPages || Math.ceil((this.totalRows || 0) / this.pageSize) || 1;
                        this.updatePaginationUI(totalPagesToUse);
                    }, 50);
                });
            } catch (e) {
                console.error('Fallo al cargar tabla documents:', e);
            } finally {
                this.loading = false;
            }
        },

        indexRows() {
            const container = document.getElementById('table-content-wrapper');
            if (container) {
                this.allDOMRows = Array.from(container.querySelectorAll('tbody tr'));
            }
        },

        applyFrontendLogic() {
            const matches = this.allDOMRows.filter(row => row.innerText.toLowerCase().includes(this.searchTerm));

            this.totalRows = matches.length;
            const totalPages = Math.ceil(this.totalRows / this.pageSize) || 1;

            const emptyRow = document.getElementById('frontend-no-results');
            if (emptyRow) {
                const showMsg = (this.allDOMRows.length > 0 && this.totalRows === 0 && this.searchTerm !== '');
                showMsg ? emptyRow.classList.remove('hidden') : emptyRow.classList.add('hidden');
            }

            this.allDOMRows.forEach(row => row.style.display = 'none');
            const start = (this.currentPage - 1) * this.pageSize;
            const end = start + this.pageSize;

            matches.forEach((row, index) => {
                if (index >= start && index < end) row.style.display = '';
            });

            this.updatePaginationUI(totalPages);
        },

        updatePaginationUI(totalPages) {
            // Buscar paginador dentro de #table-app (estilo TableManager/person)
            const pagContainer = document.querySelector('#table-app .pagination-container') || document.querySelector('.pagination-container#js-pagination') || null;
            if (pagContainer) {
                const info = pagContainer.querySelector('.pagination-info');
                const btnPrev = pagContainer.querySelector('.page-btn[title="Anterior"]') || pagContainer.querySelector('.btn-prev');
                const btnNext = pagContainer.querySelector('.page-btn[title="Siguiente"]') || pagContainer.querySelector('.btn-next');
                const input = pagContainer.querySelector('.page-input');

                if (info) {
                    if (this.totalRows > 0) {
                        const start = (this.currentPage - 1) * this.pageSize + 1;
                        const end = Math.min(this.currentPage * this.pageSize, this.totalRows);
                        info.textContent = `Mostrando ${start}-${end} de ${this.totalRows} registros`;
                    } else {
                        info.textContent = 'Sin registros para mostrar';
                    }
                }
                if (input) {
                    input.value = this.currentPage;
                    input.max = totalPages;
                }
                // Actualizar badge "de N"
                const totalBadge = pagContainer.querySelector('.total-pages-badge');
                if (totalBadge) totalBadge.textContent = `de ${totalPages}`;
                if (btnPrev) {
                    btnPrev.disabled = (this.currentPage === 1);
                    btnPrev.onclick = (ev) => { ev && ev.preventDefault(); changeDocumentPage(Math.max(1, this.currentPage - 1)); };
                }
                if (btnNext) {
                    btnNext.disabled = (this.currentPage >= totalPages || this.totalRows === 0);
                    btnNext.onclick = (ev) => { ev && ev.preventDefault(); changeDocumentPage(Math.min(totalPages, this.currentPage + 1)); };
                }
                // Actualizar botones Primera / Última si existen
                const btnFirst = pagContainer.querySelector('.page-btn[title="Primera"]');
                const btnLast = pagContainer.querySelector('.page-btn[title="Última"]');
                if (btnFirst) btnFirst.onclick = (ev) => { ev && ev.preventDefault(); changeDocumentPage(1); };
                if (btnLast) btnLast.onclick = (ev) => { ev && ev.preventDefault(); changeDocumentPage(totalPages); };
                return;
            }

            // Fallback: ids antiguos
            const pageInfo = document.getElementById('page-info');
            const pageDisplay = document.getElementById('current-page-display');
            const btnPrev = document.getElementById('btn-prev');
            const btnNext = document.getElementById('btn-next');

            if (pageInfo) {
                if (this.totalRows > 0) {
                    const start = (this.currentPage - 1) * this.pageSize + 1;
                    const end = Math.min(this.currentPage * this.pageSize, this.totalRows);
                    pageInfo.textContent = `Mostrando ${start}-${end} de ${this.totalRows} registros`;
                } else {
                    pageInfo.textContent = 'Sin registros para mostrar';
                }
            }
            if (pageDisplay) pageDisplay.textContent = this.currentPage;
            if (btnPrev) btnPrev.disabled = (this.currentPage === 1);
            if (btnNext) btnNext.disabled = (this.currentPage >= totalPages || this.totalRows === 0);
        },

        nextPage() {
            const last = this.totalPages || Math.ceil((this.totalRows || 0) / this.pageSize) || 1;
            if (this.currentPage < last) {
                this.currentPage++;
                // Solicitar siguiente página al servidor
                this.fetchTable(this.isAdvancedSearch, this.currentPage);
            }
        },
        prevPage() {
            if (this.currentPage > 1) {
                this.currentPage--;
                this.fetchTable(this.isAdvancedSearch, this.currentPage);
            }
        },

        filterByRegime(regimeCode) {
            // Force string comparison to avoid type mismatch between template and JS
            const codeStr = String(regimeCode);
            if (String(this.advancedFilters.documents) === codeStr) {
                this.advancedFilters.documents = '';
                this.isAdvancedSearch = false;
                this.fetchTable(false);
            } else {
                this.advancedFilters.documents = codeStr;
                this.isAdvancedSearch = true;
                this.fetchTable(true);
                // asignar selectedTypeId/name si existe en stats
                const stat = this.stats.regimes.find(r => String(r.code) === codeStr);
                if (stat) {
                    this.selectedTypeId = String(stat.code);
                    this.selectedTypeName = stat.name;
                } else {
                    this.selectedTypeId = '';
                    this.selectedTypeName = '';
                }
                const btn = document.getElementById('btn-add-document'); if (btn) this.setAddButtonEnabled(this.selectedTypeId !== '');
            }
        },

        clearSearch() {
            this.advancedFilters = {documents: '', q: ''};
            this.isAdvancedSearch = false;
            this.searchTerm = '';
            const input = document.getElementById('table-search-document');
            if (input) input.value = '';
            this.currentPage = 1;
            this.fetchTable(false);
            this.setAddButtonEnabled(false);
        },

        async openDocumentModal() {
            const modalEl = document.getElementById('documentModal-overlay');
            if (!modalEl) return;
            // Solo permitir si hay un tipo seleccionado (no 'Total')
            if (!this.selectedTypeId) {
                Swal.fire('Atención', 'Seleccione primero un tipo de documento para crear.', 'info');
                return;
            }

            // Pedir al servidor el siguiente código para previsualizar
            try {
                const res = await fetch(`/documents/next-code/${this.selectedTypeId}/`);
                const data = await res.json();
                if (data.success) {
                    const form = document.getElementById('documentForm');
                    if (form) form.reset();
                    document.getElementById('modal_filing_code').value = data.code || '';
                    document.getElementById('modal_category').value = this.selectedTypeId;
                    const nameInput = document.getElementById('modal_category_name');
                    if (nameInput) nameInput.value = this.selectedTypeName;
                    
                    // Llenar el campo "Elaborado Por" con el usuario actual
                    const appDiv = document.getElementById('documents-app');
                    const currentUser = appDiv ? appDiv.getAttribute('data-current-user') : '';
                    const senderInput = document.getElementById('modal_sender_name');
                    if (senderInput && currentUser) senderInput.value = currentUser;
                    
                    const qtyGroup = document.getElementById('modal_quantity_group');
                    if (qtyGroup) {
                        const qty = qtyGroup.querySelector('#modal_quantity');
                        if (qty) qty.value = 1;
                        qtyGroup.style.display = '';
                    }
                    // Reset editing state
                    this.editingId = null;
                        const filePreview = document.getElementById('modal_file_preview'); if (filePreview) filePreview.innerHTML = '';
                        // restaurar grid a dos columnas (cantidad + asunto)
                        const grid = document.getElementById('grid-cantidad-asunto'); if (grid) grid.style.gridTemplateColumns = '1fr 3fr';
                        // mostrar cantidad (el grupo ya fue referenciado arriba)
                        if (qtyGroup) qtyGroup.style.display = '';
                        const deleteBtn = document.getElementById('modal_delete_file_btn'); if (deleteBtn) deleteBtn.style.display = 'none';
                    const title = document.getElementById('modalTitle'); if (title) title.innerText = `NUEVO ${this.selectedTypeName.toUpperCase()}`;

                    // Mostrar modal: usar Bootstrap si está disponible, si no usar fallback
                    if (window.bootstrap && window.bootstrap.Modal) {
                        const modal = new bootstrap.Modal(modalEl);
                        modal.show();
                    } else {
                        modalEl.classList.remove('hidden');
                        document.body.classList.add('no-scroll');
                    }
                } else {
                    Swal.fire('Error', data.message || 'No se pudo obtener código', 'error');
                }
            } catch (e) {
                console.error('Error obteniendo next-code:', e);
                Swal.fire('Error', 'No se pudo obtener el siguiente código', 'error');
            }
        },

        async editDocument(id) {
            // Abrir modal en modo edición: ocultar cantidad y precargar campos
            try {
                const res = await fetch(`/documents/detail/${id}/`);
                const data = await res.json();
                if (!data.success) {
                    Swal.fire('Error', data.message || 'No se pudo obtener el documento', 'error');
                    return;
                }
                const doc = data.data;
                const form = document.getElementById('documentForm');
                if (!form) return;
                form.reset();
                // ocultar el grupo completo de cantidad (input + label)
                const qtyGroup = document.getElementById('modal_quantity_group'); if (qtyGroup) qtyGroup.style.display = 'none';
                // ajustar grid para que Asunto ocupe toda la fila
                const grid = document.getElementById('grid-cantidad-asunto'); if (grid) grid.style.gridTemplateColumns = '1fr';
                // rellenar campos ocultos y visibles
                document.getElementById('modal_filing_code').value = doc.filing_code || '';
                document.getElementById('modal_category').value = doc.category || '';
                const nameInput = document.getElementById('modal_category_name'); if (nameInput) nameInput.value = doc.category_name || this.selectedTypeName || '';
                const senderInput = document.getElementById('modal_sender_name'); if (senderInput) senderInput.value = doc.sender_name || '';
                const subj = form.querySelector('input[name="subject"]'); if (subj) subj.value = doc.subject || '';
                const recip = form.querySelector('input[name="recipient_name"]'); if (recip) recip.value = doc.recipient_name || '';
                const obs = form.querySelector('textarea[name="observation"]'); if (obs) obs.value = doc.observation || '';
                // no mostrar link de archivo actual según spec; sólo mostrar botón eliminar si existe
                const filePreview = document.getElementById('modal_file_preview'); if (filePreview) filePreview.innerHTML = '';

                // marcar estado de edición
                this.editingId = id;
                // Mostrar/ocultar botón Eliminar PDF según exista archivo
                const deleteBtn = document.getElementById('modal_delete_file_btn');
                if (deleteBtn) {
                    if (doc.file_url) {
                        deleteBtn.style.display = '';
                        deleteBtn.onclick = (ev) => { ev && ev.preventDefault(); window.deleteDocumentFile(id); };
                    } else {
                        deleteBtn.style.display = 'none';
                        deleteBtn.onclick = null;
                    }
                }
                const title = document.getElementById('modalTitle'); if (title) title.innerText = `EDITAR ${this.selectedTypeName ? this.selectedTypeName.toUpperCase() : ''}`;

                // mostrar modal
                const modalEl = document.getElementById('documentModal-overlay');
                if (window.bootstrap && window.bootstrap.Modal) {
                    const modal = new bootstrap.Modal(modalEl);
                    modal.show();
                } else {
                    modalEl.classList.remove('hidden');
                    document.body.classList.add('no-scroll');
                }
            } catch (e) {
                console.error('Error cargando documento:', e);
                Swal.fire('Error', 'No se pudo cargar el documento', 'error');
            }
        },

        async saveDocument() {
            const form = document.getElementById('documentForm');
            if (!form) return;
            const formData = new FormData(form);
            this.loading = true;
            try {
                let response;
                if (!this.editingId) {
                    // Prevención doble envío: si ya se creó recientemente, pedir esperar
                    if (this.creating) {
                        try { Swal.fire('Espere', 'Espere 5 segundos antes de crear nuevos registros.', 'info'); } catch(e) { alert('Espere 5 segundos antes de crear nuevos registros.'); }
                        this.loading = false;
                        return;
                    }
                }
                if (this.editingId) {
                    // Update single document
                    const url = `/documents/update/${this.editingId}/`;
                    response = await fetch(url, { method: 'POST', body: formData, headers: {'X-CSRFToken': getCookie('csrftoken')} });
                } else {
                    // Create multiple (existing flow)
                    const createUrl = window.location.pathname.replace(/list\/?$/, 'create-multiple/');
                    response = await fetch(createUrl, { method: 'POST', body: formData, headers: {'X-CSRFToken': getCookie('csrftoken')} });
                }
                const data = await response.json();
                if (data.success || data.status === 'success') {
                    // Cerrar modal
                    const modalEl = document.getElementById('documentModal-overlay');
                    if (modalEl) {
                        modalEl.classList.add('hidden');
                        document.body.classList.remove('no-scroll');
                    }
                    
                    // SweetAlert similar al horario
                    Swal.fire({
                        icon: 'success',
                        title: data.message,
                        toast: true,
                        position: 'top-end',
                        timer: 2500,
                        timerProgressBar: true,
                        showConfirmButton: false
                    });
                    
                    // Si fue una creación, bloquear nuevas creaciones por 5s para evitar doble clic accidental
                    if (!this.editingId) {
                        this.creating = true;
                        // Deshabilitar botón de guardar en modal
                        const saveBtn = document.querySelector('#documentForm button[type="submit"], #documentForm .btn-save');
                        if (saveBtn) saveBtn.disabled = true;
                        setTimeout(() => {
                            this.creating = false;
                            if (saveBtn) saveBtn.disabled = false;
                        }, 5000);
                    }
                    // Refrescar tabla después de corto delay
                    await new Promise(r => setTimeout(r, 500));
                    this.fetchTable();
                    // Reset editingId
                    this.editingId = null;
                } else {
                    Swal.fire('Error', data.message || 'Error al guardar', 'error');
                }
            } catch (e) {
                console.error('Error saveDocument:', e);
                Swal.fire('Error', 'Fallo en la solicitud', 'error');
            } finally {
                this.loading = false;
            }
        },

        
    }
});

// Montar el app en el contenedor padre de `#table-app` (para incluir las tarjetas de stats)
// Preferir montar en `#documents-app` (si existe) para controlar v-cloak y stats
const mountEl = document.getElementById('documents-app') || (document.getElementById('table-app') ? document.getElementById('table-app').parentElement : document.body);
window.documentsInstance = documentsApp.mount(mountEl);

// Exponer funciones globales usadas por atributos `onclick` en las plantillas
window.openDocumentModal = function(...args) {
    if (window.documentsInstance && typeof window.documentsInstance.openDocumentModal === 'function') {
        return window.documentsInstance.openDocumentModal(...args);
    }
    console.warn('documentsInstance not ready: openDocumentModal');
};

window.editDocument = function(id) {
    if (window.documentsInstance && typeof window.documentsInstance.editDocument === 'function') {
        return window.documentsInstance.editDocument(id);
    }
    console.warn('documentsInstance not ready: editDocument', id);
};

window.saveDocument = function(...args) {
    if (window.documentsInstance && typeof window.documentsInstance.saveDocument === 'function') {
        return window.documentsInstance.saveDocument(...args);
    }
    console.warn('documentsInstance not ready: saveDocument');
};

// Subir/actualizar archivo PDF para un documento específico
window.uploadDocumentFile = function(id) {
    if (!id) return console.warn('uploadDocumentFile requires id');
    // Crear input temporal
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'application/pdf';
    input.style.display = 'none';
    document.body.appendChild(input);
    input.addEventListener('change', async (ev) => {
        const file = ev.target.files && ev.target.files[0];
        if (!file) { document.body.removeChild(input); return; }
        const fd = new FormData();
        fd.append('file', file);
        try {
            const res = await fetch(`/documents/upload-file/${id}/`, { method: 'POST', body: fd, headers: {'X-CSRFToken': getCookie('csrftoken')} });
            const data = await res.json();
            if (data.success) {
                Swal.fire({ icon: 'success', title: data.message, toast: true, position: 'top-end', timer: 2000, showConfirmButton: false });
                // refrescar tabla
                if (window.documentsInstance && typeof window.documentsInstance.fetchTable === 'function') window.documentsInstance.fetchTable(window.documentsInstance.isAdvancedSearch, window.documentsInstance.currentPage);
            } else {
                Swal.fire('Error', data.message || 'Error subiendo archivo', 'error');
            }
        } catch (e) {
            console.error('Error uploadDocumentFile:', e);
            Swal.fire('Error', 'Fallo en la subida del archivo', 'error');
        } finally {
            document.body.removeChild(input);
        }
    });
    input.click();
};

window.changeDocumentPage = function(page) {
    if (window.documentsInstance && typeof window.documentsInstance.fetchTable === 'function') {
        return window.documentsInstance.fetchTable(window.documentsInstance.isAdvancedSearch, page);
    }
    console.warn('documentsInstance not ready: changeDocumentPage', page);
};

// Eliminar archivo PDF asociado a un documento
window.deleteDocumentFile = async function(id) {
    if (!id) return console.warn('deleteDocumentFile requires id');
    if (typeof Swal === 'undefined') {
        const ok = confirm('¿Eliminar el archivo PDF actual? Esta acción no se puede deshacer.');
        if (!ok) return;
    } else {
        const result = await Swal.fire({
            title: '¿Eliminar el archivo PDF actual?',
            text: 'Esta acción no se puede deshacer.',
            icon: 'warning',
            showCancelButton: true,
            confirmButtonColor: '#d33',
            cancelButtonColor: '#3085d6',
            confirmButtonText: 'Sí, eliminar',
            cancelButtonText: 'Cancelar'
        });
        if (!result || !result.isConfirmed) return;
    }
    try {
        const res = await fetch(`/documents/delete-file/${id}/`, { method: 'POST', headers: {'X-CSRFToken': getCookie('csrftoken')} });
        const data = await res.json();
        if (data.success) {
            Swal.fire({ icon: 'success', title: data.message, toast: true, position: 'top-end', timer: 2000, showConfirmButton: false });
            // actualizar vista del modal
            const filePreview = document.getElementById('modal_file_preview'); if (filePreview) filePreview.innerHTML = '';
            const deleteBtn = document.getElementById('modal_delete_file_btn'); if (deleteBtn) deleteBtn.style.display = 'none';
            // refrescar tabla
            if (window.documentsInstance && typeof window.documentsInstance.fetchTable === 'function') window.documentsInstance.fetchTable(window.documentsInstance.isAdvancedSearch, window.documentsInstance.currentPage);
        } else {
            Swal.fire('Error', data.message || 'No se pudo eliminar', 'error');
        }
    } catch (e) {
        console.error('Error deleteDocumentFile:', e);
        Swal.fire('Error', 'Fallo al eliminar archivo', 'error');
    }
};