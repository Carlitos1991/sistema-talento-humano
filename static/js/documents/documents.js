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
            stats: { total: 0, regimes: [] },
            isAdvancedSearch: false,
                advancedFilters: { documents: '', q: '' }
            ,
            // Ordenamiento
            sortField: null,
            sortAsc: true
        };
    },
    mounted() {
        this.fetchTable();
        this.initDelegatedListeners();
        // Deshabilitar el botón Nuevo Documento por defecto (visualmente y funcionalmente)
        this.setAddButtonEnabled(false);
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
            // Añadir orden si está definido
            if (this.sortField) {
                paramsObj.sort_field = this.sortField;
                paramsObj.sort_dir = this.sortAsc ? 'asc' : 'desc';
            }
            const params = new URLSearchParams(paramsObj).toString();

            try {
                const url = `${window.location.pathname}?${params}`;
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
                        code: String(r.code)
                    }));
                    this.stats = { total: data.stats.total || 0, regimes };
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
                    
                    const qty = document.getElementById('modal_quantity'); if (qty) qty.value = 1;
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

        async saveDocument() {
            const form = document.getElementById('documentForm');
            if (!form) return;
            const formData = new FormData(form);
            this.loading = true;
            try {
                // Enviamos siempre a create-multiple que maneja quantity y secuencia
                const createUrl = window.location.pathname.replace(/list\/?$/, 'create-multiple/');
                const response = await fetch(createUrl, {
                    method: 'POST',
                    body: formData,
                    headers: {'X-CSRFToken': getCookie('csrftoken')}
                });
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
                    
                    // Refrescar tabla después de corto delay
                    await new Promise(r => setTimeout(r, 500));
                    this.fetchTable();
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

        editDocument(id) {
            // Placeholder: abrir modal de edición vía fetch si existe endpoint
            console.log('Editar documento', id);
        }
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

window.changeDocumentPage = function(page) {
    if (window.documentsInstance && typeof window.documentsInstance.fetchTable === 'function') {
        return window.documentsInstance.fetchTable(window.documentsInstance.isAdvancedSearch, page);
    }
    console.warn('documentsInstance not ready: changeDocumentPage', page);
};