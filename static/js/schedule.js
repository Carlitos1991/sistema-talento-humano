/* apps/schedule/static/js/schedule.js */
const {createApp} = Vue;

const scheduleApp = createApp({
    delimiters: ['[[', ']]'],
    data() {
        return {
            loading: false,
            showModal: false, // Variable necesaria para el v-if del modal
            isEdit: false,
            isSplitShift: false,
            filters: {
                name: '',
                is_active: ''
            },
            days: [
                {key: 'monday', label: 'LUN'}, {key: 'tuesday', label: 'MAR'},
                {key: 'wednesday', label: 'MIÉ'}, {key: 'thursday', label: 'JUE'},
                {key: 'friday', label: 'VIE'}, {key: 'saturday', label: 'SÁB'},
                {key: 'sunday', label: 'DOM'}
            ],
            form: {
                id: null,
                name: '',
                morning_start: '08:00',
                morning_end: '13:00',
                afternoon_start: '14:00',
                afternoon_end: '17:00',
                monday: true, tuesday: true, wednesday: true, thursday: true, friday: true,
                saturday: false, sunday: false
            }
        }
    },
    methods: {
        openCreateModal() {
            this.isEdit = false;
            this.showModal = true;
            this.isSplitShift = false;
            // Reset form to defaults
            this.form = {
                name: '',
                morning_start: '08:00',
                morning_end: '13:00',
                afternoon_start: '14:00',
                afternoon_end: '17:00',
                monday: true,
                tuesday: true,
                wednesday: true,
                thursday: true,
                friday: true,
                saturday: false,
                sunday: false
            };
        },
        closeModal() {
            this.showModal = false;
        },
        async fetchTable() {
            const params = new URLSearchParams(this.filters).toString();
            try {
                const response = await fetch(`/schedule/partial-table/?${params}`);
                const data = await response.json();
                document.getElementById('table-content-wrapper').innerHTML = data.table_html;
            } catch (error) {
                console.error("Error fetching table:", error);
            }
        },
        debouncedSearch() {
            clearTimeout(this.searchTimer);
            this.searchTimer = setTimeout(() => {
                this.fetchTable();
            }, 400);
        },
        async saveSchedule() {
            this.loading = true;
            const formData = new FormData(document.getElementById('scheduleForm'));
            if (!this.isSplitShift) {
                formData.delete('afternoon_start');
                formData.delete('afternoon_end');
            }

            const url = this.isEdit ? `/schedule/update/${this.form.id}/` : '/schedule/create/';

            try {
                const response = await fetch(url, {
                    method: 'POST',
                    body: formData,
                    headers: {'X-CSRFToken': getCookie('csrftoken')}
                });
                const result = await response.json();
                if (result.success) {
                    Swal.fire({
                        icon: 'success',
                        title: 'Operación Exitosa',
                        text: result.message,
                        toast: true,
                        position: 'top-end',
                        showConfirmButton: false,
                        timer: 3000
                    });
                    this.closeModal();
                    this.fetchTable();
                }
            } catch (error) {
                Swal.fire('Error', 'No se pudo procesar la solicitud', 'error');
            } finally {
                this.loading = false;
            }
        }
    }
});

// Función global necesaria para obtener el CSRF de Django
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

scheduleApp.mount('#schedule-app'); // COINCIDE CON EL HTML