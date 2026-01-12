/* apps/contract/static/js/management_period.js */
const {createApp} = Vue;

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

const periodApp = createApp({
    delimiters: ['[[', ']]'],
    data() {
        return {
            loading: false,
            step: 1,
            showWizard: false,
            showDetailModal: false,

            // Paginación y Filtrado Frontend
            currentPage: 1,
            pageSize: 10,
            totalRows: 0,
            searchTerm: '',
            allDOMRows: [],

            isAdvancedSearch: false,
            advancedQuery: '',

            // Selección
            searchDoc: '',
            selectedContractType: {id: null, name: ''},
            selectedEmployee: {id: null, full_name: '', photo: '', budget_line: null},
            selectedPeriod: {},

            form: {
                id: null, administrative_unit: '', budget_line: '', schedule: '',
                workplace: '', start_date: '', end_date: '', document_number: '',
                job_functions: '', institutional_need_memo: '', budget_certification: ''
            },

            stats: {total: 0, active: 0, losep: 0, ct: 0},
            filters: {status: ''}
        }
    },

    mounted() {
        this.fetchTable();
        this.initDelegatedListeners();
    },

    methods: {
        initDelegatedListeners() {
            // Buscador Frontend
            const searchInput = document.getElementById('table-search-input');
            if (searchInput) {
                searchInput.addEventListener('input', (e) => {
                    this.searchTerm = e.target.value.toLowerCase().trim();
                    this.currentPage = 1;
                    this.applyFrontendLogic();
                });
            }

            // Delegación de Eventos (Cero onclick inline)
            const tableWrapper = document.getElementById('table-content-wrapper');
            if (tableWrapper) {
                tableWrapper.addEventListener('click', (e) => {
                    const btn = e.target.closest('button');
                    if (!btn) return;

                    const action = btn.dataset.action;
                    const id = btn.dataset.id;

                    if (action === 'sign') this.signPeriod(id);
                    if (action === 'view') this.viewPeriodDetails(id);
                    if (action === 'terminate') this.terminatePeriod(id);
                    if (action === 'advanced-search-empty') this.triggerAdvancedSearch();
                });
            }
        },

        async fetchTable(advanced = false) {
            this.loading = true;
            this.isAdvancedSearch = advanced;
            const params = new URLSearchParams({
                advanced: advanced,
                q: this.advancedQuery,
                status: this.filters.status
            }).toString();

            try {
                const response = await fetch(`/contract/periods/partial-table/?${params}`);
                const data = await response.json();

                const container = document.getElementById('table-content-wrapper');
                if (container) container.innerHTML = data.table_html;

                if (data.stats) this.stats = data.stats;

                // RE-INDEXAR FILAS (Crucial para el filtrado frontend)
                this.$nextTick(() => {
                    setTimeout(() => {
                        this.indexRows();
                        this.applyFrontendLogic();
                    }, 100); // Aumentamos a 100ms para mayor seguridad en el DOM
                });

            } catch (e) {
                this.showToast('error', 'Fallo al cargar tabla');
            } finally {
                this.loading = false;
            }
        },

        indexRows() {
            // Buscamos todas las filas con la clase específica dentro del wrapper
            const container = document.getElementById('table-content-wrapper');
            if (container) {
                const rows = container.querySelectorAll('tr.period-row');
                this.allDOMRows = Array.from(rows);
            }
        },

        applyFrontendLogic() {
            const matches = this.allDOMRows.filter(row => {
                return row.innerText.toLowerCase().includes(this.searchTerm);
            });

            this.totalRows = matches.length;
            const totalPages = Math.ceil(this.totalRows / this.pageSize) || 1;

            // 1. IDs de los mensajes
            const emptyFrontend = document.getElementById('frontend-no-results');
            const emptyServer = document.querySelector('.server-empty-state');

            if (emptyFrontend) {
                // Solo mostramos el "vacío del buscador" si:
                // El servidor TRAJO datos (allDOMRows > 0) pero el filtro los OCULTÓ (totalRows === 0)
                const showFrontendMsg = (this.allDOMRows.length > 0 && this.totalRows === 0 && this.searchTerm !== '');

                if (showFrontendMsg) {
                    emptyFrontend.classList.remove('hidden');
                } else {
                    emptyFrontend.classList.add('hidden');
                }
            }

            // 2. Visibilidad de filas de datos
            this.allDOMRows.forEach(row => row.style.display = 'none');

            const start = (this.currentPage - 1) * this.pageSize;
            const end = start + this.pageSize;

            matches.forEach((row, index) => {
                if (index >= start && index < end) {
                    row.style.display = '';
                }
            });

            // 3. Forzar actualización de etiquetas (Resuelve el "Calculando...")
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
                    pageInfo.textContent = "Sin registros para mostrar";
                }
            }

            if (pageDisplay) pageDisplay.textContent = this.currentPage;
            if (btnPrev) btnPrev.disabled = (this.currentPage === 1);
            if (btnNext) btnNext.disabled = (this.currentPage >= totalPages || this.totalRows === 0);
        },

        updatePaginationLabels(totalPages) {
            const pageInfo = document.getElementById('page-info');
            const pageDisplay = document.getElementById('current-page-display');
            const btnPrev = document.getElementById('btn-prev');
            const btnNext = document.getElementById('btn-next');

            if (pageInfo) {
                const start = this.totalRows > 0 ? (this.currentPage - 1) * this.pageSize + 1 : 0;
                const end = Math.min(this.currentPage * this.pageSize, this.totalRows);
                pageInfo.textContent = `Mostrando ${start}-${end} de ${this.totalRows} registros`;
            }
            if (pageDisplay) pageDisplay.textContent = this.currentPage;

            if (btnPrev) btnPrev.disabled = (this.currentPage === 1);
            if (btnNext) btnNext.disabled = (this.currentPage >= totalPages || this.totalRows === 0);
        },

        clearSearch() {
            this.isAdvancedSearch = false;
            this.advancedQuery = '';
            this.searchTerm = '';
            const input = document.getElementById('table-search-input');
            if (input) input.value = '';
            this.currentPage = 1;
            this.fetchTable(false);
            this.showToast('success', 'Búsqueda restablecida');
        },

        async triggerAdvancedSearch() {
            const {value: query} = await Swal.fire({
                title: 'Búsqueda Avanzada',
                text: 'Consultando en toda la Base de Datos...',
                input: 'text',
                showCancelButton: true,
                confirmButtonText: 'Buscar',
                cancelButtonText: 'Cerrar',
                customClass: {confirmButton: 'btn-save', cancelButton: 'btn-cancel'}
            });

            if (query) {
                this.advancedQuery = query;
                this.searchTerm = '';
                const input = document.getElementById('table-search-input');
                if (input) input.value = '';
                this.fetchTable(true);
            }
        },

        // Métodos Wizard y Gestión
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
        startWizard() {
            this.step = 1;
            this.resetWizard();
            this.showWizard = true;
            document.body.classList.add('no-scroll');
        },
        closeWizard() {
            this.showWizard = false;
            document.body.classList.remove('no-scroll');
        },
        resetWizard() {
            this.searchDoc = '';
            this.selectedContractType = {id: null, name: ''};
            this.selectedEmployee = {id: null, full_name: '', photo: '', budget_line: null};
            this.form = {
                administrative_unit: '', budget_line: '', schedule: '', workplace: '',
                start_date: '', end_date: '', document_number: '', job_functions: '',
                institutional_need_memo: '', budget_certification: ''
            };
        },
        async validateEmployee() {
            if (!this.searchDoc) return;
            this.loading = true;
            try {
                const response = await fetch(`/contract/api/validate-employee/${this.searchDoc}/`);
                const data = await response.json();
                if (data.success) {
                    this.selectedEmployee = data.employee;
                    this.form.budget_line = data.employee.budget_line.id;
                    this.step = 3;
                    this.$nextTick(() => this.initSelect2());
                } else {
                    Swal.fire('Atención', data.message, 'info');
                }
            } catch (e) {
                this.showToast('error', 'Fallo de conexión');
            } finally {
                this.loading = false;
            }
        },
        initSelect2() {
            const vm = this;
            $('.select2-vue').each(function () {
                $(this).select2({width: '100%', dropdownParent: $('.modal-container-xl')})
                    .on('change', function () {
                        vm.form[$(this).attr('name')] = $(this).val();
                    });
            });
        },
        async saveManagementPeriod() {
            const f = this.form;
            if (!f.administrative_unit || !f.schedule || !f.start_date || !f.document_number) {
                Swal.fire('Validación', 'Campos obligatorios incompletos.', 'warning');
                return;
            }
            this.loading = true;
            const formData = new FormData();
            formData.append('employee', this.selectedEmployee.id);
            formData.append('contract_type', this.selectedContractType.id);
            formData.append('budget_line', this.selectedEmployee.budget_line.id);
            Object.keys(this.form).forEach(key => {
                if (this.form[key]) formData.append(key, this.form[key]);
            });
            try {
                const response = await fetch('/contract/periods/create/', {
                    method: 'POST', body: formData, headers: {'X-CSRFToken': getCookie('csrftoken')}
                });
                const result = await response.json();
                if (response.ok && result.success) {
                    Swal.fire('¡Éxito!', result.message, 'success').then(() => location.reload());
                } else {
                    Swal.fire('Error', result.message || 'Error al guardar.', 'error');
                }
            } catch (e) {
                this.showToast('error', 'Error en servidor');
            } finally {
                this.loading = false;
            }
        },
        async viewPeriodDetails(id) {
            this.loading = true;
            try {
                const response = await fetch(`/contract/periods/detail/${id}/`);
                const data = await response.json();
                if (data.success) {
                    this.selectedPeriod = data.period;
                    this.showDetailModal = true;
                    document.body.classList.add('no-scroll');
                }
            } catch (e) {
                this.showToast('error', 'Error al cargar expediente');
            } finally {
                this.loading = false;
            }
        },
        async signPeriod(id) {
            const {isConfirmed} = await Swal.fire({
                title: '¿Legalizar Contrato?', text: 'El estado cambiará a FIRMADO.',
                icon: 'info', showCancelButton: true, confirmButtonText: 'Sí, Firmar'
            });
            if (isConfirmed) {
                try {
                    const response = await fetch(`/contract/periods/sign/${id}/`, {
                        method: 'POST', headers: {'X-CSRFToken': getCookie('csrftoken')}
                    });
                    const data = await response.json();
                    if (data.success) {
                        this.showToast('success', data.message);
                        this.fetchTable();
                    }
                } catch (e) {
                    this.showToast('error', 'Fallo al firmar');
                }
            }
        },
        async terminatePeriod(id) {
            const {value: reason, isConfirmed} = await Swal.fire({
                title: 'Finalizar Gestión', input: 'textarea', inputLabel: 'Motivo de salida',
                showCancelButton: true, confirmButtonText: 'Finalizar'
            });
            if (isConfirmed && reason) {
                const formData = new FormData();
                formData.append('reason', reason);
                try {
                    const response = await fetch(`/contract/periods/terminate/${id}/`, {
                        method: 'POST', body: formData, headers: {'X-CSRFToken': getCookie('csrftoken')}
                    });
                    const data = await response.json();
                    if (data.success) {
                        Swal.fire('Éxito', data.message, 'success');
                        this.fetchTable();
                    }
                } catch (e) {
                    this.showToast('error', 'Fallo al terminar');
                }
            }
        },
        showToast(icon, title) {
            Swal.fire({icon, title, toast: true, position: 'top-end', showConfirmButton: false, timer: 3000});
        }
    }
});

window.periodInstance = periodApp.mount('#period-app');