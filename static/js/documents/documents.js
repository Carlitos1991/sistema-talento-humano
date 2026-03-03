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
            searchTerm: '',
            allDOMRows: [],
            // Estadísticas y filtros
            stats: { total: 0, regimes: [] },
            isAdvancedSearch: false,
            advancedFilters: { regime_code: '', q: '' }
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
            const searchInput = document.getElementById('table-search-budget');
            if (searchInput) {
                searchInput.addEventListener('input', (e) => {
                    this.searchTerm = e.target.value.toLowerCase().trim();
                    this.currentPage = 1;
                    this.applyFrontendLogic();
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
            }
        },

        // Habilita / deshabilita visualmente el botón 'Nuevo Documento'
        setAddButtonEnabled(enabled) {
            const btn = document.getElementById('btn-add-budget');
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

        async fetchTable(advanced = false) {
            this.loading = true;
            this.isAdvancedSearch = advanced;

            const params = new URLSearchParams({
                advanced: advanced ? 1 : 0,
                q: this.advancedFilters.q || '',
                regime_code: this.advancedFilters.regime_code || ''
            }).toString();

            try {
                const url = `${window.location.pathname}?${params}`;
                const response = await fetch(url, {
                    headers: {'X-Requested-With': 'XMLHttpRequest'}
                });
                const data = await response.json();

                const container = document.getElementById('table-content-wrapper');
                if (container) container.innerHTML = data.table_html || data.html || container.innerHTML;

                if (data.stats) {
                    // Asegurar que los códigos vienen como strings para comparación en plantilla
                    const regimes = (data.stats.regimes || []).map(r => ({
                        ...r,
                        code: String(r.code)
                    }));
                    this.stats = { total: data.stats.total || 0, regimes };
                }

                this.$nextTick(() => {
                    setTimeout(() => {
                        this.indexRows();
                        this.applyFrontendLogic();
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
            if (this.currentPage < Math.ceil(this.totalRows / this.pageSize)) {
                this.currentPage++;
                this.applyFrontendLogic();
            }
        },
        prevPage() {
            if (this.currentPage > 1) {
                this.currentPage--;
                this.applyFrontendLogic();
            }
        },

        filterByRegime(regimeCode) {
            // Force string comparison to avoid type mismatch between template and JS
            const codeStr = String(regimeCode);
            if (String(this.advancedFilters.regime_code) === codeStr) {
                this.advancedFilters.regime_code = '';
                this.isAdvancedSearch = false;
                this.fetchTable(false);
            } else {
                this.advancedFilters.regime_code = codeStr;
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
                const btn = document.getElementById('btn-add-budget'); if (btn) this.setAddButtonEnabled(this.selectedTypeId !== '');
            }
        },

        clearSearch() {
            this.advancedFilters = {regime_code: '', q: ''};
            this.isAdvancedSearch = false;
            this.searchTerm = '';
            const input = document.getElementById('table-search-budget');
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