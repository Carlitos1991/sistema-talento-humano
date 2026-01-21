const {createApp} = Vue;

createApp({
    delimiters: ['[[', ']]'],
    data() {
        return {
            showModal: false,
            modalTitle: 'Nuevo Biométrico',
            searchQuery: '',
            isSaving: false,
            form: {
                id: null,
                name: '',
                ip_address: '',
                port: 4370,
                location: ''
            }
        }
    },
    methods: {
        async search() {
            try {
                const data = await BiometricService.getTable(this.searchQuery);
                // CAMBIO AQUÍ: Debe coincidir con el ID del HTML
                const container = document.getElementById('table-content-wrapper');
                if (container) {
                    container.innerHTML = data.html;
                }
            } catch (error) {
                console.error(error);
                this.notifyError('No se pudo actualizar la tabla');
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
                    await this.search();
                } else {
                    this.notifyError('Verifique los datos ingresados');
                }
            } catch (error) {
                this.notifyError('Error crítico al guardar');
            } finally {
                this.isSaving = false;
            }
        },

        resetForm() {
            this.form = {id: null, name: '', ip_address: '', port: 4370, location: ''};
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
    }
}).mount('#biometric-app');