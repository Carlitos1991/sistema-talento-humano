/* apps/contract/static/js/management_period.js */
const {createApp} = Vue;

/**
 * Helper: Obtiene el token CSRF para peticiones POST
 */
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
        const container = document.getElementById('period-app');
        return {
            // Estados de Control
            loading: false,
            step: 1,
            showWizard: false,
            showDetailModal: false,
            isEdit: false,

            // Paginación y Filtrado Frontend
            currentPage: 1,
            pageSize: 10,
            totalRows: 0,
            searchTerm: '',
            allDOMRows: [], // Cache de los elementos <tr>

            // Búsqueda Avanzada
            isAdvancedSearch: false,
            advancedQuery: '',

            // Datos de Búsqueda y Selección
            searchDoc: '',
            selectedContractType: {id: null, name: ''},
            selectedEmployee: {id: null, full_name: '', photo: '', budget_line: null},
            selectedPeriod: {},

            // Formulario Paso 3
            form: {
                id: null,
                administrative_unit: '',
                budget_line: '',
                schedule: '',
                workplace: '',
                start_date: '',
                end_date: '',
                document_number: '',
                job_functions: '',
                institutional_need_memo: '',
                budget_certification: ''
            },

            // Estadísticas
            stats: {
                total: parseInt(container?.dataset.total) || 0,
                active: parseInt(container?.dataset.active) || 0,
                losep: parseInt(container?.dataset.losep) || 0,
                ct: parseInt(container?.dataset.ct) || 0
            },
            filters: {status: ''}
        }
    },

    mounted() {
        this.fetchTable();
        this.setupFrontendSearch();
    },

    methods: {
        async fetchTable(advanced = false) {
            this.loading = true;
            this.isAdvancedSearch = advanced;

            const params = new URLSearchParams({
                advanced: this.isAdvancedSearch,
                q: this.advancedQuery,
                status: this.filters.status
            }).toString();

            try {
                const response = await fetch(`/contract/periods/partial-table/?${params}`);
                const data = await response.json();

                const container = document.getElementById('table-content-wrapper');
                container.innerHTML = data.table_html;

                if (data.stats) this.stats = data.stats;

                setTimeout(() => {
                    this.indexRows();
                    this.applyFrontendLogic();
                }, 100);

            } catch (e) {
                this.showToast('error', 'Fallo de conexión');
            } finally {
                this.loading = false;
            }
        },

        indexRows() {
            const tbody = document.querySelector('#table-content-wrapper table tbody');
            if (tbody) {
                this.allDOMRows = Array.from(tbody.querySelectorAll('tr.period-row'));
            }
        },

        setupFrontendSearch() {
            const input = document.getElementById('table-search-input');
            if (input) {
                input.addEventListener('input', (e) => {
                    this.searchTerm = e.target.value.toLowerCase().trim();
                    this.currentPage = 1;
                    this.applyFrontendLogic();
                });
            }
        },

        applyFrontendLogic() {
            const matches = this.allDOMRows.filter(row => {
                return row.innerText.toLowerCase().includes(this.searchTerm);
            });

            this.totalRows = matches.length;
            const totalPages = Math.ceil(this.totalRows / this.pageSize) || 1;

            // CONTROL DE MENSAJE VACÍO
            const emptyRow = document.getElementById('frontend-no-results');
            const termDisplay = document.getElementById('search-term-display');
            if (emptyRow) {
                if (this.totalRows === 0 && this.searchTerm !== '') {
                    emptyRow.style.display = '';
                    if (termDisplay) termDisplay.textContent = this.searchTerm;
                } else {
                    emptyRow.style.display = 'none';
                }
            }

            const start = (this.currentPage - 1) * this.pageSize;
            const end = start + this.pageSize;

            // Ocultamos todas las filas reales
            this.allDOMRows.forEach(row => row.style.display = 'none');

            // Mostramos solo las que encajan en la página
            matches.forEach((row, index) => {
                if (index >= start && index < end) {
                    row.style.display = '';
                }
            });

            this.updatePaginationLabels(totalPages);
        },
        clearSearch() {
            this.isAdvancedSearch = false;
            this.advancedQuery = '';
            this.searchTerm = '';
            const input = document.getElementById('table-search-input');
            if (input) input.value = '';
            this.currentPage = 1;
            this.fetchTable(false); // Vuelve a los 50 originales
        },

        updatePaginationLabels(totalPages) {
            const pageInfo = document.getElementById('page-info');
            const pageDisplay = document.getElementById('current-page-display');
            const btnPrev = document.getElementById('btn-prev');
            const btnNext = document.getElementById('btn-next');

            if (pageInfo) {
                const startLabel = this.totalRows > 0 ? (this.currentPage - 1) * this.pageSize + 1 : 0;
                const endLabel = Math.min(this.currentPage * this.pageSize, this.totalRows);
                pageInfo.textContent = `Mostrando ${startLabel}-${endLabel} de ${this.totalRows} registros`;
            }
            if (pageDisplay) pageDisplay.textContent = this.currentPage;

            if (btnPrev) btnPrev.disabled = (this.currentPage === 1);
            if (btnNext) btnNext.disabled = (this.currentPage >= totalPages);
        },

        nextPage() {
            const totalPages = Math.ceil(this.totalRows / this.pageSize);
            if (this.currentPage < totalPages) {
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

        async triggerAdvancedSearch() {
            const {value: query} = await Swal.fire({
                title: 'Búsqueda Avanzada',
                text: 'Buscando en toda la Base de Datos...',
                input: 'text',
                inputPlaceholder: 'Cédula o Nombre...',
                showCancelButton: true,
                confirmButtonText: 'Buscar',
                cancelButtonText: 'Cerrar'
            });

            if (query) {
                this.advancedQuery = query;
                this.searchTerm = '';
                const input = document.getElementById('table-search-input');
                if (input) input.value = '';
                this.fetchTable(true);
            }
        },

        filterByStatus(status) {
            this.filters.status = status;
            this.fetchTable();
        },

        // ==========================================
        // 2. GESTIÓN DEL WIZARD (CREACIÓN)
        // ==========================================
        startWizard() {
            this.step = 1;
            this.isEdit = false;
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
                administrative_unit: '',
                budget_line: '',
                schedule: '',
                workplace: '',
                start_date: '',
                end_date: '',
                document_number: '',
                job_functions: '',
                institutional_need_memo: '',
                budget_certification: ''
            };
        },

        selectContractType(id, name) {
            this.selectedContractType = {id, name};
            this.step = 2;
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
                    this.$nextTick(() => {
                        this.initSelect2();
                    });
                } else {
                    Swal.fire('Validación', data.message, 'info');
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
                $(this).select2({
                    width: '100%',
                    dropdownParent: $('.modal-container-xl')
                }).on('change', function () {
                    vm.form[$(this).attr('name')] = $(this).val();
                });
            });
        },

        async saveManagementPeriod() {
            const f = this.form;
            if (!f.administrative_unit || !f.schedule || !f.start_date || !f.document_number) {
                Swal.fire('Atención', 'Complete los campos obligatorios.', 'warning');
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
                    method: 'POST',
                    body: formData,
                    headers: {'X-CSRFToken': getCookie('csrftoken')}
                });
                const result = await response.json();

                if (response.ok && result.success) {
                    Swal.fire('¡Éxito!', result.message, 'success').then(() => location.reload());
                } else {
                    Swal.fire('Error', result.message || 'Error al guardar', 'error');
                }
            } catch (e) {
                this.showToast('error', 'Error en el servidor');
            } finally {
                this.loading = false;
            }
        },

        // ==========================================
        // 3. EXPEDIENTE, FIRMA Y TERMINACIÓN
        // ==========================================
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
                this.showToast('error', 'No se pudo cargar el expediente');
            } finally {
                this.loading = false;
            }
        },

        closeDetailModal() {
            this.showDetailModal = false;
            document.body.classList.remove('no-scroll');
        },

        async signPeriod(id) {
            const {isConfirmed} = await Swal.fire({
                title: '¿Legalizar Contrato?',
                icon: 'info', showCancelButton: true, confirmButtonText: 'Sí, Firmar'
            });

            if (isConfirmed) {
                try {
                    const response = await fetch(`/contract/periods/sign/${id}/`, {
                        method: 'POST',
                        headers: {'X-CSRFToken': getCookie('csrftoken')}
                    });
                    const data = await response.json();
                    if (data.success) {
                        this.showToast('success', data.message);
                        this.fetchTable();
                    }
                } catch (e) {
                    this.showToast('error', 'Error al firmar');
                }
            }
        },

        async terminatePeriod(id) {
            const {value: reason, isConfirmed} = await Swal.fire({
                title: 'Finalizar Gestión',
                input: 'textarea',
                inputLabel: 'Motivo de salida',
                showCancelButton: true, confirmButtonText: 'Finalizar'
            });

            if (isConfirmed && reason) {
                const formData = new FormData();
                formData.append('reason', reason);
                try {
                    const response = await fetch(`/contract/periods/terminate/${id}/`, {
                        method: 'POST',
                        body: formData,
                        headers: {'X-CSRFToken': getCookie('csrftoken')}
                    });
                    const data = await response.json();
                    if (data.success) {
                        Swal.fire('Éxito', data.message, 'success');
                        this.fetchTable();
                    }
                } catch (e) {
                    this.showToast('error', 'Error al terminar');
                }
            }
        },

        showToast(icon, title) {
            Swal.fire({icon, title, toast: true, position: 'top-end', showConfirmButton: false});
        }
    }
});

// Inicio
window.periodInstance = periodApp.mount('#period-app');