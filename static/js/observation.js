const {createApp} = Vue;

const observationApp = createApp({
    delimiters: ['[[', ']]'],
    data() {
        const container = document.getElementById('observation-app');
        return {
            loading: false, showModal: false, isEdit: false, searchTimer: null,
            filters: {name: '', is_holiday: ''},
            currentPage: 1,
            pagination: {
                current_page: 1,
                total_pages: 1,
                has_previous: false,
                has_next: false,
                total_count: 0,
                start_index: 0,
                end_index: 0
            },
            stats: {
                total: parseInt(container?.dataset.total) || 0,
                holiday: parseInt(container?.dataset.holiday) || 0,
                special: parseInt(container?.dataset.special) || 0
            },
            form: {id: null, name: '', description: '', start_date: '', end_date: '', is_holiday: true, is_active: true}
        }
    },
    methods: {
        openCreateModal() {
            this.isEdit = false;
            this.resetForm();
            this.showModal = true;
            document.body.classList.add('no-scroll');
        },
        async openEditModal(id) {
            this.loading = true;
            this.isEdit = true;
            try {
                const response = await fetch(`/schedule/observations/detail/${id}/`);
                const data = await response.json();
                if (data.success) {
                    this.form = data.observation;
                    this.showModal = true;
                    document.body.classList.add('no-scroll');
                }
            } catch (error) {
                this.showToast('error', 'Error al cargar datos');
            } finally {
                this.loading = false;
            }
        },
        async saveObservation() {
            this.loading = true;
            const formData = new FormData();
            Object.keys(this.form).forEach(key => formData.append(key, this.form[key]));
            const url = this.isEdit ? `/schedule/observations/update/${this.form.id}/` : '/schedule/observations/create/';
            try {
                const response = await fetch(url, {
                    method: 'POST',
                    body: formData,
                    headers: {'X-CSRFToken': getCookie('csrftoken')}
                });
                const result = await response.json();
                if (result.success) {
                    this.showToast('success', result.message);
                    this.closeModal();
                    this.fetchTable();
                } else {
                    Swal.fire('Atención', 'Revise los datos ingresados', 'warning');
                }
            } catch (error) {
                this.showToast('error', 'Error de servidor');
            } finally {
                this.loading = false;
            }
        },
        async toggleStatus(id, currentStatus) {
            const status = String(currentStatus) === 'true';
            const {isConfirmed} = await Swal.fire({
                title: '¿Cambiar estado del evento?',
                icon: 'warning', showCancelButton: true, confirmButtonText: 'Sí, confirmar'
            });
            if (isConfirmed) {
                const response = await fetch(`/schedule/observations/toggle-status/${id}/`, {
                    method: 'POST', headers: {'X-CSRFToken': getCookie('csrftoken')}
                });
                if (response.ok) {
                    this.fetchTable();
                    this.showToast('success', 'Estado actualizado');
                }
            }
        },
        filterByStatus(val) {
            this.filters.is_holiday = val;
            this.fetchTable();
        },
        async fetchTable() {
            const params = new URLSearchParams({...this.filters, page: this.currentPage}).toString();
            try {
                const response = await fetch(`/schedule/observations/partial-table/?${params}`);
                const data = await response.json();

                // Actualizamos el HTML de la tabla
                const wrapper = document.getElementById('table-content-wrapper');
                if (wrapper) wrapper.innerHTML = data.table_html;

                // Actualizamos las stats (esto quita el 0 y pone los números reales)
                if (data.stats) {
                    this.stats = data.stats;
                }
                
                // Actualizar información de paginación
                if (data.pagination) {
                    this.pagination = data.pagination;
                    this.updatePaginationUI();
                }
            } catch (error) {
                console.error("Error fetching table:", error);
            }
        },
        debouncedSearch() {
            clearTimeout(this.searchTimer);
            this.currentPage = 1; // Reset a página 1 al buscar
            this.searchTimer = setTimeout(() => this.fetchTable(), 400);
        },
        resetForm() {
            this.form = {
                id: null,
                name: '',
                description: '',
                start_date: '',
                end_date: '',
                is_holiday: true,
                is_active: true
            };
        },
        closeModal() {
            this.showModal = false;
            document.body.classList.remove('no-scroll');
        },
        showToast(icon, title) {
            Swal.fire({icon, title, toast: true, position: 'top-end', showConfirmButton: false, timer: 3000});
        },
        
        updatePaginationUI() {
            const pageInfo = document.getElementById('page-info');
            const currentPageDisplay = document.getElementById('current-page-display');
            const btnPrev = document.getElementById('btn-prev');
            const btnNext = document.getElementById('btn-next');

            if (pageInfo) {
                pageInfo.textContent = `Mostrando ${this.pagination.start_index} a ${this.pagination.end_index} registros de ${this.pagination.total_count} registros`;
            }
            if (currentPageDisplay) {
                currentPageDisplay.textContent = this.pagination.current_page;
            }
            if (btnPrev) {
                btnPrev.disabled = !this.pagination.has_previous;
            }
            if (btnNext) {
                btnNext.disabled = !this.pagination.has_next;
            }
        },
        
        nextPage() {
            if (this.pagination.has_next) {
                this.currentPage++;
                this.fetchTable();
            }
        },
        
        prevPage() {
            if (this.pagination.has_previous) {
                this.currentPage--;
                this.fetchTable();
            }
        }
    },
    mounted() {
        const container = document.getElementById('observation-app');
        if (container) {
            this.stats.total = parseInt(container.dataset.total) || 0;
            this.stats.holiday = parseInt(container.dataset.holiday) || 0;
            this.stats.special = parseInt(container.dataset.special) || 0;
        }
        this.fetchTable();
        
        // Configurar botones de paginación
        const btnPrev = document.getElementById('btn-prev');
        const btnNext = document.getElementById('btn-next');
        
        if (btnPrev) btnPrev.addEventListener('click', () => this.prevPage());
        if (btnNext) btnNext.addEventListener('click', () => this.nextPage());
    }
});

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

window.observationInstance = observationApp.mount('#observation-app');