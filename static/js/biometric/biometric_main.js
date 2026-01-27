const {createApp} = Vue;

// Guardamos la instancia en una constante
const biometricApp = createApp({
    delimiters: ['[[', ']]'],
    data() {
        return {
            showModal: false,
            modalTitle: 'Nuevo Biométrico',
            searchQuery: '',
            showUploadModal: false,
            isUploading: false,
            selectedDeviceId: null,
            selectedDeviceName: '',
            uploadForm: {file: null},
            showTimeModal: false,
            isSavingTime: false,
            timeData: {name: '', server_time: '', device_time: ''},
            timeForm: {id: null, mode: 'server', custom_time: ''},
            currentStatus: 'all',
            stats: {total: 0, active: 0, inactive: 0},
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
        openModalUpload(id, name) {
            this.selectedDeviceId = id;
            this.selectedDeviceName = name;
            this.uploadForm.file = null;
            this.showUploadModal = true;
        },

        onFileSelected(event) {
            this.uploadForm.file = event.target.files[0];
        },

        async processUpload() {
            this.isUploading = true;
            const fd = new FormData();
            fd.append('file', this.uploadForm.file);

            try {
                const response = await fetch(`/biometric/upload-file/${this.selectedDeviceId}/`, {
                    method: 'POST',
                    body: fd
                });
                const result = await response.json();

                if (result.status === 'success') {
                    Swal.fire({
                        title: 'Carga Completada',
                        text: result.message,
                        icon: 'success',
                        confirmButtonText: 'Entendido',
                        customClass: {confirmButton: 'btn-swal-confirm-green-centered'},
                        buttonsStyling: false
                    });
                    this.showUploadModal = false;
                    await this.search(); // Actualizar estadísticas
                } else {
                    this.notifyError(result.message);
                }
            } catch (e) {
                this.notifyError('Error técnico al subir el archivo');
            } finally {
                this.isUploading = false;
            }
        },
        closeUploadModal() {
            this.showUploadModal = false;
        },
        async search() {
            try {
                const data = await BiometricService.getTable(this.searchQuery, this.currentStatus);

                // 1. Actualizar Tabla
                document.getElementById('table-content-wrapper').innerHTML = data.html;

                // 2. Actualizar Estadísticas dinámicamente
                if (data.stats) this.stats = data.stats;

                // 3. Actualizar Paginación
                if (data.pagination) this.pagination.label = data.pagination.label;
            } catch (error) {
                console.error(error);
            }
        },
        async filterByStatus(status) {
            this.currentStatus = status;
            await this.search();
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
        async openModalTime(id) {
            // Mostrar loading sin botones
            Swal.fire({
                title: 'Consultando tiempos...',
                text: 'Conectando con el dispositivo...',
                allowOutsideClick: false,
                showConfirmButton: false,
                showCancelButton: false,
                didOpen: () => {
                    Swal.showLoading();
                }
            });

            try {
                const response = await fetch(`/biometric/get-device-time/${id}/`);

                console.log('Response status:', response.status);

                const data = await response.json();
                console.log('Data recibida:', data);

                // Si la respuesta no es exitosa, mostrar error
                if (!response.ok || !data.success) {
                    Swal.fire({
                        icon: 'error',
                        title: 'Error de Conexión',
                        text: data.message || 'No se pudo comunicar con el servidor.',
                        confirmButtonText: 'Aceptar',
                        showCancelButton: false,
                        buttonsStyling: false,
                        customClass: {
                            confirmButton: 'btn-swal-confirm-red-centered',
                            actions: 'swal-actions-centered'
                        }
                    });
                    return;
                }

                // Verificar si hubo error de conexión con el dispositivo
                if (data.device_time && data.device_time.includes('Error')) {
                    // Cerrar el loading
                    Swal.close();

                    // Mostrar advertencia
                    await Swal.fire({
                        icon: 'warning',
                        title: 'Sin Conexión al Dispositivo',
                        text: 'No se pudo leer la hora del dispositivo. Verifique que esté encendido y accesible en la red.',
                        confirmButtonText: 'Aceptar',
                        showCancelButton: false,
                        buttonsStyling: false,
                        customClass: {
                            confirmButton: 'btn-swal-confirm-red-centered',
                            actions: 'swal-actions-centered'
                        }
                    });
                    return; // No abrir el modal si no hay conexión
                }

                // Si todo está bien, cerrar loading y abrir modal
                Swal.close();

                // Preparar datos del formulario
                this.timeData = {
                    name: data.device_name,
                    server_time: data.server_time,
                    device_time: data.device_time
                };
                this.timeForm = {
                    id: id,
                    mode: 'server',
                    custom_time: data.server_time.replace(' ', 'T').substring(0, 16)
                };

                // Abrir el modal
                console.log('Abriendo modal, showTimeModal:', this.showTimeModal);
                this.showTimeModal = true;
                console.log('Modal abierto, showTimeModal:', this.showTimeModal);

            } catch (e) {
                console.error('Error en openModalTime:', e);
                Swal.fire({
                    icon: 'error',
                    title: 'Error de Conexión',
                    text: 'No se pudo comunicar con el servidor. Verifique la conexión de red.',
                    confirmButtonText: 'Aceptar',
                    showCancelButton: false,
                    buttonsStyling: false,
                    customClass: {
                        confirmButton: 'btn-swal-confirm-red-centered',
                        actions: 'swal-actions-centered'
                    }
                });
            }
        },

        async saveTime() {
            this.isSavingTime = true;
            const fd = new FormData();
            fd.append('mode', this.timeForm.mode);
            fd.append('new_time', this.timeForm.custom_time);

            console.log('Enviando actualización de hora:', {
                id: this.timeForm.id,
                mode: this.timeForm.mode,
                custom_time: this.timeForm.custom_time
            });

            try {
                const response = await fetch(`/biometric/update-device-time/${this.timeForm.id}/`, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': this.getCsrfToken()
                    },
                    body: fd
                });

                console.log('Response status:', response.status);
                const result = await response.json();
                console.log('Response data:', result);

                if (response.ok && result.status === 'success') {
                    Swal.fire({
                        icon: 'success',
                        title: 'Éxito',
                        text: result.message,
                        confirmButtonText: 'Aceptar'
                    });
                    this.showTimeModal = false;
                    // Recargar la tabla para reflejar cambios
                    await this.search();
                } else {
                    // Mostrar mensaje de error del servidor
                    Swal.fire({
                        icon: 'error',
                        title: 'Error',
                        text: result.message || 'Error al actualizar la hora',
                        confirmButtonText: 'Aceptar'
                    });
                }
            } catch (e) {
                console.error('Error en saveTime:', e);
                Swal.fire({
                    icon: 'error',
                    title: 'Error de Conexión',
                    text: 'No se pudo comunicar con el servidor. Verifique la conexión.',
                    confirmButtonText: 'Aceptar'
                });
            } finally {
                this.isSavingTime = false;
            }
        },

        closeTimeModal() {
            this.showTimeModal = false;
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
        async handleTestConnection(id) {
            // 1. ESTADO DE CARGA: Limpio, sin botones, solo spinner
            Swal.fire({
                title: 'Probando comunicación',
                text: 'Intentando conectar con el dispositivo...',
                allowOutsideClick: false,
                showConfirmButton: false, // <--- DESACTIVA BOTÓN OK
                showCancelButton: false,  // <--- DESACTIVA BOTÓN CANCEL
                didOpen: () => {
                    Swal.showLoading(); // Muestra el spinner
                }
            });

            try {
                const res = await BiometricService.testConnection(id);

                if (res.success) {
                    // 2. ESTADO DE ÉXITO: Solo un botón "Cerrar" centrado
                    Swal.fire({
                        title: '<span style="color: #334155; font-weight: 800; font-size: 1.6rem;">¡Conexión Exitosa!</span>',
                        icon: 'success',
                        iconColor: '#10b981',
                        html: `
                    <div class="swal-connection-box">
                        <div class="swal-connection-header">
                            <i class="fa-solid fa-circle-check"></i>
                            <span>Conexión establecida con éxito</span>
                        </div>
                        <div class="swal-connection-details">
                            <div class="swal-connection-item"><strong>Dispositivo:</strong> ${res.device_info.deviceName || '---'}</div>
                            <div class="swal-connection-item"><strong>Plataforma:</strong> ${res.device_info.platform || '---'}</div>
                            <div class="swal-connection-item"><strong>Número de Serie:</strong> ${res.device_info.serialNumber || '---'}</div>
                            <div class="swal-connection-item"><strong>Versión Firmware:</strong> ${res.device_info.firmware || '---'}</div>
                            <div class="swal-connection-item"><strong>Usuarios Registrados:</strong> ${res.device_info.userCount || '0'}</div>
                        </div>
                    </div>
                `,
                        showConfirmButton: true,
                        confirmButtonText: 'Cerrar',
                        showCancelButton: false,
                        showDenyButton: false,
                        showCloseButton: false,
                        allowOutsideClick: true,
                        buttonsStyling: false,
                        customClass: {
                            confirmButton: 'btn-swal-confirm-green-centered',
                            actions: 'swal-actions-centered'
                        }
                    });
                    await this.search();
                } else {
                    // 3. ESTADO DE ERROR: Solo un botón "Aceptar" centrado
                    Swal.fire({
                        title: '<span style="color: #334155; font-weight: 800;">Fallo de Conexión</span>',
                        icon: 'error',
                        text: res.error_details || res.message,
                        showConfirmButton: true,
                        confirmButtonText: 'Aceptar',
                        showCancelButton: false,
                        showDenyButton: false,
                        showCloseButton: false,
                        allowOutsideClick: true,
                        buttonsStyling: false,
                        customClass: {
                            confirmButton: 'btn-swal-confirm-red-centered',
                            actions: 'swal-actions-centered'
                        }
                    });
                }
            } catch (error) {
                this.notifyError('Error de red al intentar la conexión');
            }
        },
        async handleLoadAttendance(id, name) {
            // 1. MODAL DE CONFIRMACIÓN (Estilo púrpura solicitado)
            const result = await Swal.fire({
                title: '¿Cargar marcaciones?',
                html: `
            <p style="color: #64748b; font-size: 0.95rem; margin-bottom: 10px;">Se cargarán todas las marcaciones del dispositivo:</p>
            <p style="font-weight: 800; color: #1e293b; text-transform: uppercase;">${name}</p>
            <p style="color: #64748b; font-size: 0.95rem; margin-top: 15px;">Solo se guardarán las marcaciones de empleados con identificador biométrico registrado.</p>
        `,
                icon: 'question',
                iconColor: '#7e22ce',
                showCancelButton: true,
                confirmButtonText: '<i class="fa-solid fa-download"></i> Cargar Marcaciones',
                cancelButtonText: 'Cancelar',
                buttonsStyling: false,
                customClass: {
                    confirmButton: 'btn-swal-confirm-purple-centered', // Clase para botón púrpura
                    cancelButton: 'btn-swal-cancel-gray'
                }
            });

            if (result.isConfirmed) {
                // 2. MOSTRAR LOADING SIN BOTONES
                Swal.fire({
                    title: 'Sincronizando...',
                    text: 'Conectando y descargando datos, espere por favor.',
                    allowOutsideClick: false,
                    showConfirmButton: false,
                    showCancelButton: false,
                    didOpen: () => {
                        Swal.showLoading();
                    }
                });

                try {
                    // Llamada al endpoint de Python que creamos en views.py
                    const response = await fetch(`/biometric/load-attendance/${id}/`, {
                        method: 'POST',
                        headers: {
                            'X-CSRFToken': BiometricService.getCsrfToken()
                        }
                    });

                    const data = await response.json();

                    if (response.ok && data.status === 'success') {
                        // 3. ÉXITO
                        Swal.fire({
                            icon: 'success',
                            title: '¡Sincronización Exitosa!',
                            text: data.message,
                            confirmButtonText: 'Aceptar',
                            customClass: {
                                confirmButton: 'btn-swal-confirm-green-centered'
                            },
                            buttonsStyling: false
                        });
                        await this.search(); // Refrescar tabla y contadores
                    } else {
                        // 4. ERROR O INFO (No hay registros)
                        Swal.fire({
                            icon: data.status === 'info' ? 'info' : 'error',
                            title: data.status === 'info' ? 'Sin registros' : 'Error',
                            text: data.message,
                            confirmButtonText: 'Cerrar',
                            customClass: {
                                confirmButton: 'btn-swal-confirm-red-centered'
                            },
                            buttonsStyling: false
                        });
                    }
                } catch (error) {
                    console.error(error);
                    this.notifyError('Error de red al intentar sincronizar marcaciones');
                }
            }
        },

        resetForm() {
            this.form = {id: null, name: '', ip_address: '', port: 4370, location: '', is_active: true};
        },

        getCsrfToken() {
            return document.cookie.split('; ')
                .find(row => row.startsWith('csrftoken='))
                ?.split('=')[1];
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
