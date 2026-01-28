const {createApp} = Vue;

createApp({
    delimiters: ['[[', ']]'],
    data() {
        return {
            stats: {total: 0, registered: 0, pending: 0},

            // UI State
            isLoading: false,
            isModalOpen: false,
            isSearchModalOpen: false,
            modalTitle: '',
            modalHtml: '',

            // Filtros
            currentStatus: 'all',
            filters: {
                q: '',
                date_start: '',
                date_end: ''
            },

            // Paginación
            pagination: {
                page: 1,
                numPages: 1,
                hasNext: false,
                hasPrev: false,
                totalRecords: 0
            }
        }
    },
    mounted() {
        // 1. Cargar Estadísticas Iniciales
        const initialStatsEl = document.getElementById('initial-stats');
        if (initialStatsEl) {
            try {
                this.stats = JSON.parse(initialStatsEl.textContent);
            } catch (e) {
                console.error("Error parseando stats", e);
            }
        }

        // 2. Cargar Paginación Inicial desde Django
        const initialPagEl = document.getElementById('initial-pagination');
        if (initialPagEl) {
            try {
                const pagData = JSON.parse(initialPagEl.textContent);
                this.pagination = pagData;
            } catch (e) {
                console.error("Error parseando paginación inicial", e);
            }
        }
    },
    computed: {
        hasActiveFilters() {
            return this.currentStatus !== 'all' ||
                this.filters.q !== '' ||
                this.filters.date_start !== '';
        }
    },
    methods: {
        async openCreateModal() {
            this.modalTitle = 'Nueva Acción de Personal';
            this.modalHtml = '<div style="text-align:center; padding:20px;"><i class="fas fa-spinner fa-spin fa-2x"></i></div>';
            this.isModalOpen = true;
            // ... resto del fetch ...
            try {
                const response = await fetch('/personnel_actions/create/', {
                    headers: {'X-Requested-With': 'XMLHttpRequest'}
                });
                if (response.ok) {
                    this.modalHtml = await response.text();
                    this.$nextTick(() => {
                        this.initializePluginsInModal();
                        this.bindFormSubmit();
                    });
                } else {
                    this.modalHtml = '<p>Error.</p>';
                }
            } catch (e) {
                this.modalHtml = '<p>Error conexión.</p>';
            }
        },
        closeModal() {
            this.isModalOpen = false;
            this.modalHtml = '';
        },

        openSearchModal() {
            this.isSearchModalOpen = true;
        },
        closeSearchModal() {
            this.isSearchModalOpen = false;
        },

        // --- LÓGICA DE TABLA ---

        applyBackendSearch() {
            this.pagination.page = 1;
            this.fetchTableData();
            this.closeSearchModal();
        },

        clearFilters() {
            this.currentStatus = 'all';
            this.filters.q = '';
            this.filters.date_start = '';
            this.filters.date_end = '';
            this.pagination.page = 1;

            // Limpiar input visual
            const localInput = document.getElementById('local-search-input');
            if (localInput) localInput.value = '';

            this.fetchTableData();
        },

        filterByStatus(status) {
            if (this.currentStatus === status) return;
            this.currentStatus = status;
            this.pagination.page = 1;
            this.fetchTableData();
        },

        changePage(newPage) {
            if (newPage < 1) return;
            this.pagination.page = newPage;
            this.fetchTableData();
        },

        async fetchTableData() {
            // 1. Activamos "Cargando".
            this.isLoading = true;

            const params = new URLSearchParams();
            params.append('page', this.pagination.page);
            if (this.currentStatus !== 'all') params.append('status', this.currentStatus);
            if (this.filters.q) params.append('q', this.filters.q);
            if (this.filters.date_start) params.append('date_start', this.filters.date_start);
            if (this.filters.date_end) params.append('date_end', this.filters.date_end);

            try {
                const response = await fetch(`?${params.toString()}`, {
                    headers: {'X-Requested-With': 'XMLHttpRequest'}
                });
                if (response.ok) {
                    const data = await response.json();

                    // Reemplazo del HTML
                    document.getElementById('table-content-wrapper').innerHTML = data.html;

                    // Actualizar Paginación
                    this.pagination = {
                        page: data.page_number,
                        numPages: data.num_pages,
                        hasNext: data.has_next,
                        hasPrev: data.has_previous,
                        totalRecords: data.total_records
                    };

                    this.$nextTick(() => { this.localSearch(); });
                }
            } catch (error) {
                console.error(error);
            } finally {
                this.isLoading = false;
            }
        },

        // Búsqueda Local
        localSearch() {
            const input = document.getElementById('local-search-input');
            if (!input) return;

            const filter = input.value.toUpperCase();
            // Busca por ID ahora que lo agregamos al partial
            const table = document.getElementById('main-data-table');

            if (!table) return;

            const tr = table.getElementsByTagName('tr');

            // Comenzamos en i=1 para saltar el thead
            for (let i = 1; i < tr.length; i++) {
                // Aseguramos que sea una fila de datos y no el mensaje de "No records"
                if (tr[i].getElementsByTagName('td').length > 1) {
                    let txtValue = tr[i].textContent || tr[i].innerText;
                    tr[i].style.display = txtValue.toUpperCase().indexOf(filter) > -1 ? "" : "none";
                }
            }
        },

        initializePluginsInModal() {
            if (window.jQuery && $.fn.select2) {
                $('.select2').select2({width: '100%', dropdownParent: $('.modal-container')});
            }
        },
        bindFormSubmit() {
            const form = document.querySelector('.modal-container form');
            if (!form) return;
            form.addEventListener('submit', async (e) => {
                e.preventDefault();
                const formData = new FormData(form);
                try {
                    const response = await fetch(form.action, {
                        method: 'POST',
                        body: formData,
                        headers: {'X-Requested-With': 'XMLHttpRequest'}
                    });
                    if (response.ok) {
                        Swal.fire({icon: 'success', title: 'Guardado', timer: 1500, showConfirmButton: false});
                        this.closeModal();
                        this.fetchTableData(); // Recargar tabla
                    } else {
                        this.modalHtml = await response.text();
                        this.$nextTick(() => {
                            this.initializePluginsInModal();
                            this.bindFormSubmit();
                        });
                    }
                } catch (err) {
                    Swal.fire('Error', 'Error inesperado', 'error');
                }
            });
        }
    }
}).mount('#personnelActionApp');