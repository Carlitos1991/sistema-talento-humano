const {createApp} = Vue;

// Guardamos la instancia en una constante
const biometricApp = createApp({
    delimiters: ['[[', ']]'],
    data() {
        return {
            showModal: false,
            modalTitle: 'Nuevo Biométrico',
            searchQuery: '',
            stats: {
                total: 0,
                active: 0,
                inactive: 0
            },
            pagination: {
                label: 'Mostrando 0-0 de 0'
            },
            isSaving: false,
            form: {
                id: null,
                name: '',
                ip_address: '',
                port: 4370,
                location: '',
                is_active: true
            }
        }
    },
    methods: {
        async search() {
            try {
                const data = await BiometricService.getTable(this.searchQuery);

                // 1. Actualizar Tabla
                document.getElementById('table-content-wrapper').innerHTML = data.html;

                // 2. Actualizar Estadísticas dinámicamente
                if (data.stats) {
                    this.stats = data.stats;
                }

                // 3. Actualizar Paginación
                if (data.pagination) {
                    this.pagination.label = data.pagination.label;
                }
            } catch (error) {
                console.error(error);
            }
        },

        async openModalEdit(id) {
            this.modalTitle = 'Editar Biométrico';
            try {
                const response = await fetch(`/biometric/get-data/${id}/`);
                const data = await response.json();
                if (data.success) {
                    // Ahora data.biometric incluye is_active correctamente
                    this.form = {...data.biometric};
                    this.showModal = true;
                }
            } catch (error) {
                this.notifyError('Error al obtener datos');
            }
        },

        openModalCreate() {
            this.modalTitle = 'Registrar Nuevo Biométrico';
            this.resetForm();
            this.showModal = true;
        },

        closeModal() {
            this.showModal = false;
        },

        async saveDevice() {
            this.isSaving = true;
            try {
                const result = await BiometricService.save(this.form);
                if (result.status === 'success') {
                    this.notifySuccess(result.message);
                    this.closeModal();
                    // Refrescamos la tabla
                    await this.search();
                }
            } catch (error) {
                this.notifyError('Error al guardar');
            } finally {
                this.isSaving = false;
            }
        },

        resetForm() {
            this.form = {id: null, name: '', ip_address: '', port: 4370, location: '', is_active: true};
        },

        notifySuccess(msg) {
            Swal.fire({
                icon: 'success',
                title: msg,
                toast: true,
                position: 'top-end',
                showConfirmButton: false,
                timer: 3000
            });
        },

        notifyError(msg) {
            Swal.fire({icon: 'error', title: 'Error', text: msg});
        }
    },
    mounted() {
        // 1. Leer estadísticas iniciales desde los spans ocultos de Django
        const total = parseInt(document.getElementById('val-total')?.innerText || 0);
        const active = parseInt(document.getElementById('val-active')?.innerText || 0);
        const inactive = parseInt(document.getElementById('val-inactive')?.innerText || 0);

        // 2. Asignar al estado de Vue
        this.stats.total = total;
        this.stats.active = active;
        this.stats.inactive = inactive;

        // 3. Leer la etiqueta de paginación inicial
        const initialLabel = document.getElementById('val-pagination-label')?.innerText;
        if (initialLabel) {
            this.pagination.label = initialLabel.trim();
        }
    }
});

// MONTAR Y EXPONER GLOBALMENTE
window.biometricVM = biometricApp.mount('#biometric-app');