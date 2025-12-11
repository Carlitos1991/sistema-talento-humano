document.addEventListener('DOMContentLoaded', () => {
    const MOUNT_ID = '#catalog-create-app';

    if (document.querySelector(MOUNT_ID)) {
        const {createApp} = Vue;

        const app = createApp({
            delimiters: ['[[', ']]'],
            data() {
                return {
                    isVisible: false,
                    isEditing: false,
                    currentId: null,
                    form: {
                        name: '',
                        code: '',
                        is_active: true
                    },
                    errors: {}
                }
            },
            computed: {
                modalTitle() {
                    return this.isEditing ? 'Editar Catálogo' : 'Nuevo Catálogo';
                }
            },
            methods: {
                openModal() {
                    this.isVisible = true;
                    this.errors = {};
                },
                closeModal() {
                    this.isVisible = false;
                },
                openCreate() {
                    this.isEditing = false;
                    this.currentId = null;
                    this.form = {name: '', code: '', is_active: true};
                    this.errors = {};
                    this.isVisible = true;
                },
                async loadAndOpenEdit(id) {
                    this.isEditing = true;
                    this.currentId = id;
                    this.errors = {};

                    try {
                        const response = await fetch(`/settings/catalogs/detail/${id}/`);
                        const result = await response.json();

                        if (result.success) {
                            this.form = result.data;
                            this.isVisible = true;
                        } else {
                            Swal.fire('Error', 'No se pudieron cargar los datos', 'error');
                        }
                    } catch (error) {
                        console.error(error);
                        Swal.fire('Error', 'Error de conexión al cargar', 'error');
                    }
                },
                // --- AQUÍ ESTABA EL DUPLICADO, DEJÉ SOLO LA VERSIÓN CORRECTA ---
                async submitCatalog() {
                    this.errors = {};
                    const formData = new FormData();
                    formData.append('name', this.form.name);
                    // Enviamos código (el backend decidirá si lo usa o no según si es create/update)
                    formData.append('code', this.form.code);

                    const token = document.querySelector('[name=csrfmiddlewaretoken]');
                    if (token) formData.append('csrfmiddlewaretoken', token.value);

                    // Determinar URL
                    let url = '/settings/catalogs/create/';
                    if (this.isEditing && this.currentId) {
                        url = `/settings/catalogs/update/${this.currentId}/`;
                    }

                    try {
                        const response = await fetch(url, {
                            method: 'POST',
                            body: formData,
                            headers: {'X-Requested-With': 'XMLHttpRequest'}
                        });
                        const contentType = response.headers.get("content-type");
                        if (!contentType || !contentType.includes("application/json")) {
                            throw new Error("El servidor no devolvió JSON. Posible error 404 o 500.");
                        }
                        const data = await response.json();

                        if (data.success) {
                            Swal.fire({
                                icon: 'success',
                                title: '¡Guardado!',
                                text: data.message,
                                timer: 1500,
                                showConfirmButton: false
                            });
                            this.closeModal();
                            setTimeout(() => location.reload(), 1500);
                        } else {
                            this.errors = data.errors;
                            Swal.fire({icon: 'error', title: 'Atención', text: 'Revisa el formulario'});
                        }
                    } catch (e) {
                        console.error(e);
                        Swal.fire('Error', 'Error de servidor', 'error');
                    }
                }
            }
        });

        const vm = app.mount(MOUNT_ID);

        // --- Puentes ---
        const btnNew = document.getElementById('btn-add-catalog');
        if (btnNew) {
            btnNew.addEventListener('click', (e) => {
                e.preventDefault();
                vm.openCreate();
            });
        }

        window.openEditCatalog = (id) => {
            vm.loadAndOpenEdit(id);
        };
    }

});
window.toggleCatalogStatus = async (id, name, isActive) => {
    // 1. Configurar textos según el estado actual
    // Si está activo (True), preguntamos si quiere desactivar
    const actionVerb = isActive ? 'Desactivar' : 'Activar';
    const confirmButtonColor = isActive ? '#dc2626' : '#10b981'; // Rojo para desactivar, Verde para activar

    // 2. Mostrar Alerta de Confirmación
    const result = await Swal.fire({
        title: `¿${actionVerb} catálogo?`,
        text: `Vas a ${actionVerb.toLowerCase()} el catálogo "${name}".`,
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: confirmButtonColor,
        cancelButtonColor: '#64748b',
        confirmButtonText: `Sí, ${actionVerb.toLowerCase()}`,
        cancelButtonText: 'Cancelar'
    });
    // 3. Si el usuario confirma
    if (result.isConfirmed) {
        try {
            const formData = new FormData();
            // CSRF Token es obligatorio para POST
            const token = document.querySelector('[name=csrfmiddlewaretoken]').value;
            formData.append('csrfmiddlewaretoken', token);

            const response = await fetch(`/settings/catalogs/toggle/${id}/`, {
                method: 'POST',
                body: formData,
                headers: {'X-Requested-With': 'XMLHttpRequest'}
            });

            const data = await response.json();

            if (data.success) {
                Swal.fire({
                    icon: 'success',
                    title: '¡Actualizado!',
                    text: data.message,
                    timer: 1500,
                    showConfirmButton: false
                });

                // Recargar página para ver el cambio de icono/color
                setTimeout(() => location.reload(), 1500);
            } else {
                Swal.fire('Error', data.message || 'No se pudo cambiar el estado', 'error');
            }

        } catch (error) {
            console.error(error);
            Swal.fire('Error', 'Ocurrió un error de conexión', 'error');
        }
    }
};