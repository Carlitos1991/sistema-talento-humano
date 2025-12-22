document.addEventListener('DOMContentLoaded', () => {
    // 1. IMPORTANTE: Agregar 'reactive' al destructuring de Vue
    const {createApp, ref, reactive} = Vue;
    const mountEl = document.getElementById('credentials-modal-app');

    if (!mountEl) return;

    createApp({
        delimiters: ['[[', ']]'],
        setup() {
            // --- VARIABLES REACTIVAS ---
            const isVisible = ref(false);
            const isEditing = ref(false);
            const currentPersonId = ref(null);
            const employeeName = ref('');
            const errors = ref({});
            const formElementId = 'credentialsForm';

            // 2. DEFINICIÓN DEL FORMULARIO (Objeto Reactivo)
            const creds_form = reactive({
                username: '',
                role: '',
                password: '',
                confirm_password: '',
                is_active: true,
                is_staff: false
            });

            // --- FUNCIONES AUXILIARES ---

            // Función para obtener datos del servidor (MOVIDA DENTRO DEL SETUP)
            const fetchUserData = async (id) => {
                try {
                    const response = await fetch(`/security/users/create-credentials/${id}/`, {
                        headers: {'X-Requested-With': 'XMLHttpRequest'}
                    });
                    const data = await response.json();

                    if (data.success) {
                        employeeName.value = data.person_name;

                        // Activar modo edición visual
                        isEditing.value = data.has_user;

                        // Mapear datos al formulario reactivo
                        const formData = data.form_data;
                        creds_form.username = formData.username;
                        creds_form.role = formData.role || '';
                        creds_form.is_active = formData.is_active;
                        creds_form.is_staff = formData.is_staff;

                        // Limpiar passwords siempre
                        creds_form.password = '';
                        creds_form.confirm_password = '';

                        // Actualizar Select2 manualmente (si se usa jQuery/Select2)
                        if (typeof $ !== 'undefined') {
                            $('#id_input_role').val(formData.role).trigger('change');
                        }

                    } else {
                        throw new Error(data.message);
                    }
                } catch (error) {
                    console.error(error);
                    Swal.fire({
                        icon: 'error',
                        title: 'Error',
                        text: 'No se pudieron cargar los datos.',
                        buttonsStyling: false,
                        customClass: {confirmButton: 'swal2-confirm btn-swal-danger'}
                    });
                    closeModal();
                }
            };

            // --- ACCIONES ---

            const openModal = async (personId, name) => {
                currentPersonId.value = personId;
                employeeName.value = name;
                errors.value = {};

                // Resetear form visualmente
                document.getElementById(formElementId).reset();

                // Resetear objeto reactivo a defaults
                creds_form.username = '';
                creds_form.role = '';
                creds_form.password = '';
                creds_form.confirm_password = '';
                creds_form.is_active = true;
                creds_form.is_staff = false;

                if (typeof $ !== 'undefined') {
                    $('#id_input_role').val(null).trigger('change');
                }

                isVisible.value = true;
                document.body.classList.add('no-scroll');

                // Cargar datos
                await fetchUserData(personId);
            };

            const closeModal = () => {
                isVisible.value = false;
                errors.value = {};
                document.body.classList.remove('no-scroll');
                const formEl = document.getElementById(formElementId);
                if (formEl) formEl.reset();
            };

            const submitCredentials = async () => {
                const formEl = document.getElementById(formElementId);
                const formData = new FormData(formEl);

                // Como usamos v-model, Vue ya actualizó creds_form, pero para enviar archivos 
                // o asegurar compatibilidad con Django forms, FormData es útil. 
                // Sin embargo, como el input "username" es readonly a veces, asegurémonos de enviarlo.
                // FormData lo captura automáticamente si el input tiene name="username".

                const url = `/security/users/create-credentials/${currentPersonId.value}/`;

                try {
                    const response = await fetch(url, {
                        method: 'POST',
                        body: formData,
                        headers: {'X-CSRFToken': window.getCookie('csrftoken')}
                    });

                    // Verificar tipo de contenido
                    const contentType = response.headers.get('content-type');
                    if (!contentType || !contentType.includes('application/json')) {
                        throw new Error("Respuesta no válida del servidor");
                    }

                    const data = await response.json();

                    if (data.success) {
                        Swal.fire({
                            icon: 'success',
                            title: '¡Éxito!',
                            text: data.message,
                            timer: 2000,
                            showConfirmButton: false
                        });
                        closeModal();

                        // Recargar tabla
                        if (window.fetchUsers) window.fetchUsers();
                        else location.reload();
                    } else {
                        if (data.errors) {
                            errors.value = data.errors;

                            // Si hay error general
                            if (data.errors.__all__) {
                                Swal.fire({
                                    icon: 'error',
                                    title: 'Error',
                                    text: data.errors.__all__[0],
                                    buttonsStyling: false,
                                    customClass: {confirmButton: 'swal2-confirm btn-swal-danger'}
                                });
                            }
                        } else {
                            Swal.fire({
                                icon: 'error',
                                title: 'Error',
                                text: data.message || 'Error al guardar',
                                buttonsStyling: false,
                                customClass: {confirmButton: 'swal2-confirm btn-swal-danger'}
                            });
                        }
                    }
                } catch (e) {
                    console.error(e);
                    Swal.fire({
                        icon: 'error',
                        title: 'Error',
                        text: 'Ocurrió un error al procesar la solicitud.',
                        buttonsStyling: false,
                        customClass: {confirmButton: 'swal2-confirm btn-swal-danger'}
                    });
                }
            };

            // Exponer globalmente para los botones onclick
            window.credentialsActions = {openModal};

            // 3. RETORNAR VARIABLES AL TEMPLATE
            return {
                isVisible,
                isEditing,
                employeeName,
                errors,
                creds_form, // <--- ¡AQUÍ ESTABA EL ERROR! Faltaba retornar esto.
                closeModal,
                submitCredentials
            };
        }
    }).mount('#credentials-modal-app');

    // --- LISTENER GLOBAL ---
    document.body.addEventListener('click', (e) => {
        const btn = e.target.closest('.btn-manage-user');
        if (btn) {
            e.preventDefault();
            const url = btn.dataset.url;
            const parts = url.split('/').filter(Boolean);
            const id = parts[parts.length - 1];
            const name = btn.dataset.name || "Colaborador";

            if (window.credentialsActions) {
                window.credentialsActions.openModal(id, name);
            }
        }
    });
});