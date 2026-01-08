/* apps/schedule/static/js/schedule.js */
const {createApp} = Vue;

const scheduleApp = createApp({
    delimiters: ['[[', ']]'],
    data() {
        return {
            loading: false,
            showModal: false,
            isEdit: false,
            filters: {name: '', is_active: ''},
            days: [
                {key: 'monday', label: 'LUN'}, {key: 'tuesday', label: 'MAR'},
                {key: 'wednesday', label: 'MIÉ'}, {key: 'thursday', label: 'JUE'},
                {key: 'friday', label: 'VIE'}, {key: 'saturday', label: 'SÁB'},
                {key: 'sunday', label: 'DOM'}
            ],
            form: {
                id: null,
                name: '',
                late_tolerance_minutes: 15,
                daily_hours: 0,
                morning_start: '08:00',
                morning_end: '13:00',
                morning_crosses_midnight: false,
                afternoon_start: '',
                afternoon_end: '',
                afternoon_crosses_midnight: false,
                monday: true, tuesday: true, wednesday: true, thursday: true, friday: true,
                saturday: false, sunday: false
            }
        }
    },
    methods: {
        openCreateModal() {
            this.isEdit = false;
            this.resetForm();
            this.showModal = true;
            this.autoCalculateHours(); // Calcular iniciales
        },

        async openEditModal(id) {
            this.loading = true;
            this.isEdit = true;
            try {
                const response = await fetch(`/schedule/detail/${id}/`);
                const data = await response.json();

                if (data.success) {
                    // Llenamos el objeto form con los datos que vienen del servidor
                    this.form = data.schedule;
                    this.showModal = true;
                    // Bloqueamos scroll del body
                    document.body.classList.add('no-scroll');
                }
            } catch (error) {
                Swal.fire('Error', 'No se pudo obtener la información del horario', 'error');
            } finally {
                this.loading = false;
            }
        },

        resetForm() {
            this.form = {
                id: null, name: '', late_tolerance_minutes: 15, daily_hours: 0,
                morning_start: '08:00', morning_end: '13:00', morning_crosses_midnight: false,
                afternoon_start: '', afternoon_end: '', afternoon_crosses_midnight: false,
                monday: true, tuesday: true, wednesday: true, thursday: true, friday: true,
                saturday: false, sunday: false
            };
        },

        autoCalculateHours() {
            let totalHours = 0;
            if (this.form.morning_start && this.form.morning_end) {
                totalHours += this.calculateDiff(this.form.morning_start, this.form.morning_end, this.form.morning_crosses_midnight);
            }
            if (this.form.afternoon_start && this.form.afternoon_end) {
                totalHours += this.calculateDiff(this.form.afternoon_start, this.form.afternoon_end, this.form.afternoon_crosses_midnight);
            }
            this.form.daily_hours = parseFloat(totalHours.toFixed(2));
        },

        calculateDiff(start, end, crossesMidnight) {
            const [h1, m1] = start.split(':').map(Number);
            const [h2, m2] = end.split(':').map(Number);
            let startDate = new Date(2000, 0, 1, h1, m1);
            let endDate = new Date(2000, 0, 1, h2, m2);
            if (crossesMidnight) endDate.setDate(endDate.getDate() + 1);
            const diffHours = (endDate - startDate) / (1000 * 60 * 60);
            return diffHours > 0 ? diffHours : 0;
        },

        async saveSchedule() {
            this.loading = true;
            const formData = new FormData();

            // Inyectamos todos los campos del objeto reactivo al FormData
            Object.keys(this.form).forEach(key => {
                if (this.form[key] !== null) formData.append(key, this.form[key]);
            });

            // URL DINÁMICA: Si isEdit es true, apunta a update, sino a create
            const url = this.isEdit ? `/schedule/update/${this.form.id}/` : '/schedule/create/';

            try {
                const response = await fetch(url, {
                    method: 'POST',
                    body: formData,
                    headers: {'X-CSRFToken': getCookie('csrftoken')}
                });
                const result = await response.json();

                if (response.ok && result.success) {
                    this.showToast('success', result.message);
                    this.closeModal();
                    this.fetchTable();
                } else {
                    // Manejo de errores de validación de Django
                    let errorMsg = "Revise los campos obligatorios";
                    if (result.errors) {
                        const firstField = Object.keys(result.errors)[0];
                        errorMsg = `${firstField}: ${result.errors[firstField][0]}`;
                    }
                    Swal.fire('Atención', errorMsg, 'warning');
                }
            } catch (error) {
                Swal.fire('Error', 'Error de comunicación con el servidor', 'error');
            } finally {
                this.loading = false;
            }
        },

        async toggleStatus(id, currentStatus) {
            const action = currentStatus ? 'dar de BAJA' : 'dar de ALTA';
            const color = currentStatus ? '#ef4444' : '#22c55e'; // Rojo o Verde

            const result = await Swal.fire({
                title: `¿Confirma ${action}?`,
                text: currentStatus ? "El horario dejará de estar disponible para nuevos empleados." : "El horario volverá a estar disponible.",
                icon: 'warning',
                showCancelButton: true,
                confirmButtonColor: color,
                confirmButtonText: `Sí, ${action}`,
                cancelButtonText: 'Cancelar'
            });

            if (result.isConfirmed) {
                const url = currentStatus ? `/schedule/deactivate/${id}/` : `/schedule/activate/${id}/`;
                try {
                    const response = await fetch(url, {
                        method: 'POST',
                        headers: {'X-CSRFToken': getCookie('csrftoken')}
                    });
                    const data = await response.json();
                    if (data.success) {
                        this.showToast('success', data.message);
                        this.fetchTable(); // Recarga solo el fragmento de la tabla
                    }
                } catch (error) {
                    this.showToast('error', 'No se pudo cambiar el estado');
                }
            }
        },

        showToast(icon, title) {
            Swal.fire({icon, title, toast: true, position: 'top-end', showConfirmButton: false, timer: 3000});
        },

        closeModal() {
            this.showModal = false;
        },

        async fetchTable() {
            const params = new URLSearchParams(this.filters).toString();
            const response = await fetch(`/schedule/partial-table/?${params}`);
            const data = await response.json();
            document.getElementById('table-content-wrapper').innerHTML = data.table_html;
        },

        debouncedSearch() {
            clearTimeout(this.searchTimer);
            this.searchTimer = setTimeout(() => this.fetchTable(), 400);
        }
    },
    mounted() {
        // Al cargar, calculamos horas si hay datos
        this.autoCalculateHours();
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

scheduleApp.mount('#schedule-app');