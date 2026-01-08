/* apps/schedule/static/js/observation_module.js */
const { createApp } = Vue;

const observationApp = createApp({
    delimiters: ['[[', ']]'],
    data() {
        return {
            loading: false,
            showModal: false,
            isEdit: false,
            searchTimer: null,
            stats: { total: 0, holiday: 0, special: 0 },
            filters: { name: '', is_holiday: '' },
            form: {
                id: null,
                name: '',
                description: '',
                start_date: '',
                end_date: '',
                is_holiday: true
            }
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
            } catch (error) { this.showToast('error', 'Error al cargar datos'); }
            finally { this.loading = false; }
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
                    headers: { 'X-CSRFToken': getCookie('csrftoken') }
                });
                const result = await response.json();
                if (result.success) {
                    this.showToast('success', result.message);
                    this.closeModal();
                    this.fetchTable();
                }
            } catch (error) { this.showToast('error', 'Error de red'); }
            finally { this.loading = false; }
        },

        async toggleStatus(id) {
            const result = await Swal.fire({
                title: '¿Cambiar estado?',
                icon: 'question',
                showCancelButton: true,
                confirmButtonText: 'Sí, cambiar'
            });

            if (result.isConfirmed) {
                const response = await fetch(`/schedule/observations/toggle-status/${id}/`, {
                    method: 'POST',
                    headers: { 'X-CSRFToken': getCookie('csrftoken') }
                });
                if (response.ok) {
                    this.showToast('success', 'Estado actualizado');
                    this.fetchTable();
                }
            }
        },

        filterByType(val) {
            this.filters.is_holiday = val;
            this.fetchTable();
        },

        async fetchTable() {
            const params = new URLSearchParams(this.filters).toString();
            const response = await fetch(`/schedule/observations/partial-table/?${params}`);
            const data = await response.json();
            document.getElementById('table-content-wrapper').innerHTML = data.table_html;
            if (data.stats) this.stats = data.stats;
        },

        debouncedSearch() {
            clearTimeout(this.searchTimer);
            this.searchTimer = setTimeout(() => this.fetchTable(), 400);
        },

        resetForm() {
            this.form = { id: null, name: '', description: '', start_date: '', end_date: '', is_holiday: true };
        },

        closeModal() {
            this.showModal = false;
            document.body.classList.remove('no-scroll');
        },

        showToast(icon, title) {
            Swal.fire({ icon, title, toast: true, position: 'top-end', showConfirmButton: false, timer: 3000 });
        }
    },
    mounted() {
        this.fetchTable();
    }
});

// Exponemos la instancia para los botones de la tabla AJAX
window.observationInstance = observationApp.mount('#observation-app');