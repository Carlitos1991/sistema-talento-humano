document.addEventListener('DOMContentLoaded', () => {
    // 1. Definimos el ID del Wrapper (NO del overlay)
    const MOUNT_ID = '#catalog-create-app';

    if (document.querySelector(MOUNT_ID)) {
        const {createApp} = Vue;

        // Guardamos la instancia en una constante para usarla luego
        const app = createApp({
            delimiters: ['[[', ']]'],
            data() {
                return {
                    isVisible: false, // Controla la visibilidad
                    form: {
                        name: '',
                        code: '',
                        is_active: true
                    },
                    errors: {}
                }
            },
            methods: {
                openModal() {
                    this.isVisible = true; // Quita la clase 'hidden'
                    this.errors = {}; // Limpia errores viejos
                },
                closeModal() {
                    this.isVisible = false; // Pone la clase 'hidden'
                },
                async submitCatalog() {
                    this.errors = {};

                    const formData = new FormData();
                    formData.append('name', this.form.name);
                    formData.append('code', this.form.code);
                    formData.append('is_active', this.form.is_active ? 'True' : 'False');

                    // Obtener Token CSRF
                    const token = document.querySelector('[name=csrfmiddlewaretoken]');
                    if (token) formData.append('csrfmiddlewaretoken', token.value);

                    try {
                        const response = await fetch('/create/', {
                            method: 'POST',
                            body: formData,
                            headers: {'X-Requested-With': 'XMLHttpRequest'}
                        });
                        const data = await response.json();

                        if (data.success) {
                            Swal.fire({
                                icon: 'success',
                                title: '¡Guardado!',
                                text: data.message,
                                timer: 1500,
                                showConfirmButton: false
                            });
                            // Limpiar y cerrar
                            this.form.name = '';
                            this.form.code = '';
                            this.closeModal();

                            // Recargar página para ver cambios
                            setTimeout(() => location.reload(), 1500);
                        } else {
                            this.errors = data.errors;
                            Swal.fire({icon: 'error', title: 'Error', text: 'Revisa el formulario'});
                        }
                    } catch (e) {
                        console.error(e);
                        Swal.fire('Error', 'Error de servidor', 'error');
                    }
                }
            }
        });

        // 2. MONTAMOS LA APP
        const vm = app.mount(MOUNT_ID);

        // 3. PUENTE DE EVENTOS (Vanilla JS -> Vue)
        // Buscamos el botón "Nuevo Catálogo" que está FUERA de esta app de Vue
        const btnOpen = document.getElementById('btn-add-catalog');
        if (btnOpen) {
            btnOpen.addEventListener('click', (e) => {
                e.preventDefault();
                vm.openModal(); // Llamamos al método dentro de Vue
            });
        }
    }
});