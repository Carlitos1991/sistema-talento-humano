/* static/js/apps/credentials.js */

document.addEventListener('DOMContentLoaded', () => {
    const { createApp, ref } = Vue;
    const mountEl = document.getElementById('credentials-modal-app');

    if (!mountEl) return;

    createApp({
        delimiters: ['[[', ']]'],
        setup() {
            const isVisible = ref(false);
            const isEditing = ref(false);
            const currentPersonId = ref(null);
            const employeeName = ref('');
            const errors = ref({});
            const formElementId = 'credentialsForm';

            // --- ABRIR MODAL ---
            const openModal = async (personId, name) => {
                currentPersonId.value = personId;
                employeeName.value = name; // Nombre para mostrar en el header
                errors.value = {};

                // Limpiar form visualmente
                document.getElementById(formElementId).reset();

                // Cargar datos si el usuario ya existe (GET)
                // Nota: Necesitarás una vista que devuelva los datos del usuario dado el person_id
                // Por ahora, asumimos creación limpia o implementación futura de carga.
                // Si es edición, marcar isEditing = true.
                isEditing.value = false; // Por defecto

                // Buscar datos actuales del usuario (implementaremos esta vista luego si la necesitas)
                // await fetchUserData(personId);

                isVisible.value = true;
                document.body.classList.add('no-scroll');
            };

            const closeModal = () => {
                isVisible.value = false;
                errors.value = {}; // Limpiar errores al cerrar
                document.body.classList.remove('no-scroll');
                
                // Resetear formulario
                const formEl = document.getElementById(formElementId);
                if (formEl) formEl.reset();
            };

            // --- GUARDAR ---
            const submitCredentials = async () => {
                const formEl = document.getElementById(formElementId);
                const formData = new FormData(formEl);

                // URL: /security/users/create-credentials/ID/
                const url = `/security/users/create-credentials/${currentPersonId.value}/`;

                try {
                    const response = await fetch(url, {
                        method: 'POST',
                        body: formData,
                        headers: { 'X-CSRFToken': window.getCookie('csrftoken') }
                    });

                    // Verificar si la respuesta es JSON
                    const contentType = response.headers.get('content-type');
                    if (!contentType || !contentType.includes('application/json')) {
                        const htmlError = await response.text();
                        console.error('Respuesta HTML del servidor:', htmlError);
                        window.Toast.fire({ 
                            icon: 'error', 
                            title: 'Error del servidor. Revise la consola del navegador.' 
                        });
                        return;
                    }

                    const data = await response.json();

                    // Manejar respuesta exitosa
                    if (response.ok && data.success) {
                        window.Toast.fire({ icon: 'success', title: data.message });
                        closeModal();
                        errors.value = {};
                        // Recargar tabla de usuarios
                        if(window.fetchUsers) window.fetchUsers();
                        else location.reload();
                    } 
                    // Manejar errores de validación (400) o errores del servidor (500)
                    else {
                        if (data.errors) {
                            errors.value = data.errors;
                            
                            // Mostrar mensaje de error general si existe
                            if (data.errors.__all__) {
                                window.Toast.fire({ 
                                    icon: 'error', 
                                    title: data.errors.__all__[0] || 'Error al procesar' 
                                });
                            } else {
                                window.Toast.fire({ 
                                    icon: 'warning', 
                                    title: 'Por favor revise los campos marcados' 
                                });
                            }
                            
                            // Log para debugging
                            console.error('Errores de validación:', data.errors);
                        } else {
                            window.Toast.fire({ 
                                icon: 'error', 
                                title: data.message || 'Error al guardar' 
                            });
                        }
                    }
                } catch (e) {
                    console.error('Error completo:', e);
                    window.Toast.fire({ icon: 'error', title: 'Error al guardar las credenciales' });
                }
            };

            // Exponer globalmente
            window.credentialsActions = { openModal };

            return {
                isVisible, isEditing, employeeName, errors,
                closeModal, submitCredentials
            };
        }
    }).mount('#credentials-modal-app');

    // --- LISTENER GLOBAL PARA BOTONES ---
    // Delegamos en el documento o tabla para capturar clics en botones generados dinámicamente
    document.body.addEventListener('click', (e) => {
        // Buscar botón con clase .btn-manage-user
        const btn = e.target.closest('.btn-manage-user');
        if (btn) {
            e.preventDefault();
            // Extraer ID y Nombre desde atributos data
            // Asegúrate de agregar data-name="{{ person.full_name }}" en tu tabla
            const url = btn.dataset.url; // /security/users/create-credentials/5/

            // Extraer ID de la URL
            const parts = url.split('/').filter(Boolean);
            const id = parts[parts.length - 1];

            // Nombre (pasarlo desde el HTML es más fácil que hacer fetch extra)
            const name = btn.dataset.name || "Colaborador";

            if(window.credentialsActions) {
                window.credentialsActions.openModal(id, name);
            }
        }
    });
});