const {createApp} = Vue;

const reportApp = createApp({
        delimiters: ['[[', ']]'],
        data() {
            return {
                backendParams: {
                    name: '',
                    dni: ''
                },
                pagination: {
                    currentPage: 1,
                    pageSize: 10, // Cantidad de filas por página
                    totalItems: 0,
                    totalPages: 0,
                    start: 0,
                    end: 0
                },
                frontendFilter: '',
                noResultsFrontend: false,
                searchQuery: '',
                showMonthlyModal: false,
                showSpecificModal: false,
                selectedEmp: {id: '', name: '', dni: ''},
                monthlyForm: {month: new Date().getMonth() + 1, year: new Date().getFullYear()},
                specificForm: {start: '', end: ''}
            }
        },
        mounted() {
            this.performBackendSearch();
        },
        methods: {
            async performBackendSearch() {
                const params = new URLSearchParams();
                if (this.backendParams.name) params.append('name', this.backendParams.name);
                if (this.backendParams.dni) params.append('dni', this.backendParams.dni);

                try {
                    const response = await fetch(`?${params.toString()}`, {
                        headers: {'X-Requested-With': 'XMLHttpRequest'}
                    });
                    const data = await response.json();

                    // Inyectamos HTML
                    document.getElementById('table-content-wrapper').innerHTML = data.html;

                    // Reset Frontend
                    this.frontendFilter = '';
                    this.pagination.currentPage = 1;

                    // Recalcular paginación con los nuevos datos
                    this.updateTableState();

                } catch (error) {
                    console.error("Error:", error);
                }
            },
            clearBackendSearch() {
                this.backendParams.name = '';
                this.backendParams.dni = '';
                this.frontendFilter = '';
                this.performBackendSearch();
            },
            handleFrontendInput() {
                this.pagination.currentPage = 1; // Volver a pag 1 al filtrar
                this.updateTableState();
            },
            changePage(delta) {
                this.pagination.currentPage += delta;
                this.updateTableState();
            },
            applyFrontendFilter() {
                const term = this.frontendFilter.toLowerCase();
                const rows = document.querySelectorAll('#table-content-wrapper tr');

                rows.forEach(row => {
                    const text = row.textContent.toLowerCase();

                    // Toggle display
                    if (text.indexOf(term) > -1) {
                        row.style.display = ''; // Mostrar
                    } else {
                        row.style.display = 'none'; // Ocultar
                    }
                });
            },
            updateTableState() {
                const term = this.frontendFilter.toLowerCase();
                // IMPORTANTE: Seleccionar solo filas del cuerpo para no borrar encabezados
                const allRows = Array.from(document.querySelectorAll('#table-content-wrapper tbody tr'));

                // 1. Filtrar filas (Búsqueda)
                const visibleRows = allRows.filter(row => {
                    const text = row.textContent.toLowerCase();
                    return text.includes(term);
                });

                // 2. Actualizar estadísticas de paginación
                this.pagination.totalItems = visibleRows.length;
                this.pagination.totalPages = Math.ceil(this.pagination.totalItems / this.pagination.pageSize) || 1;

                // Corrección si filtramos y la pagina actual queda fuera de rango
                if (this.pagination.currentPage > this.pagination.totalPages) {
                    this.pagination.currentPage = 1;
                }

                // 3. Calcular índices de inicio y fin
                this.pagination.start = (this.pagination.currentPage - 1) * this.pagination.pageSize;
                this.pagination.end = this.pagination.start + this.pagination.pageSize;

                // 4. Renderizar: Ocultar todas, mostrar solo el slice actual
                allRows.forEach(row => row.style.display = 'none'); // Ocultar todo primero

                visibleRows.slice(this.pagination.start, this.pagination.end).forEach(row => {
                    row.style.display = ''; // Mostrar solo las de la página
                });
            },

            openMonthly(id, name, dni) {
                this.selectedEmp = {id, name, dni};
                this.showMonthlyModal = true;
            },
            openSpecific(id, name, dni) {
                this.selectedEmp = {id, name, dni};
                this.showSpecificModal = true;
            },
            downloadMonthly() {
                const url = `/biometric/reports/monthly-pdf/?emp_id=${this.selectedEmp.id}&month=${this.monthlyForm.month}&year=${this.monthlyForm.year}`;
                window.open(url, '_blank');
            },
            downloadSpecific() {
                const url = `/biometric/reports/specific-pdf/?emp_id=${this.selectedEmp.id}&start=${this.specificForm.start}&end=${this.specificForm.end}`;
                window.open(url, '_blank');
            }
        }
    })
;

window.reportVM = reportApp.mount('#report-app');