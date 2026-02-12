/* static/js/documents/document_types.js */

document.addEventListener('DOMContentLoaded', () => {

    // =========================================================
    // CONFIGURACIÓN GLOBAL (Toast)
    // =========================================================
    const Toast = Swal.mixin({
        toast: true, position: 'top-end', showConfirmButton: false,
        timer: 3000, timerProgressBar: true,
        didOpen: (toast) => {
            toast.addEventListener('mouseenter', Swal.stopTimer)
            toast.addEventListener('mouseleave', Swal.resumeTimer)
        }
    });

    // Referencias DOM para búsqueda
    const searchInput = document.getElementById('searchInput');
    let searchTimeout;

    // =========================================================
    // 1. LÓGICA DE TABLA Y BÚSQUEDA (AJAX)
    // =========================================================

    window.loadTypes = async function (searchTerm = '') {
        const params = new URLSearchParams();
        if (searchTerm) params.append('q', searchTerm);

        // Mantenemos la paginación del backend o la url actual
        const url = `/documents/types/?${params.toString()}`;

        try {
            const response = await fetch(url, {
                headers: {'X-Requested-With': 'XMLHttpRequest'}
            });

            if (response.ok) {
                const data = await response.json(); // Ahora esperamos JSON con { html: ... }
                const wrapper = document.getElementById('table-content-wrapper');
                if (wrapper) {
                    wrapper.innerHTML = data.html;
                }
            }
        } catch (error) {
            console.error('Error recargando tabla:', error);
        }
    };

    // Event Listener para el buscador
    if (searchInput) {
        searchInput.addEventListener('keyup', (e) => {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                const q = e.target.value.trim();
                window.loadTypes(q);
            }, 300);
        });
    }

    // =========================================================
    // 2. MODAL VUE (Crear/Editar) - SIN RELOAD
    // =========================================================
    const MOUNT_ID = '#document-type-app';

    if (document.querySelector(MOUNT_ID)) {
        const {createApp} = Vue;

        const appType = createApp({
            delimiters: ['[[', ']]'],
            data() {
                return {
                    isVisible: false,
                    isEditing: false,
                    currentId: null,
                    form: {
                        name: '',
                        is_active: true
                    },
                    errors: {}
                }
            },
            computed: {
                modalTitle() {
                    return this.isEditing ? 'Editar Tipo Documento' : 'Nuevo Tipo Documento';
                }
            },
            methods: {
                openCreate() {
                    this.isEditing = false;
                    this.currentId = null;
                    this.errors = {};
                    this.form = {name: '', is_active: true};
                    this.isVisible = true;
                },
                closeModal() {
                    this.isVisible = false;
                    this.errors = {};
                },
                async loadAndOpenEdit(id) {
                    this.errors = {};
                    try {
                        // Consumimos el endpoint de detalle creado en views
                        const response = await fetch(`/documents/types/detail/${id}/`);
                        const result = await response.json();

                        if (result.success) {
                            this.isEditing = true;
                            this.currentId = id;
                            this.form = {
                                name: result.data.name,
                                is_active: result.data.is_active
                            };
                            this.isVisible = true;
                        } else {
                            Swal.fire('Error', result.message || 'No se pudo cargar el registro', 'error');
                        }
                    } catch (e) {
                        console.error(e);
                        Swal.fire('Error', 'Error de conexión', 'error');
                    }
                },
                async submitForm() {
                    this.errors = {};

                    // Preparamos datos. Si usas JSON en backend:
                    const url = this.isEditing
                        ? `/documents/types/update/${this.currentId}/`
                        : '/documents/types/create/';

                    // Necesitamos CSRF Token
                    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;

                    // Si usas ModelForm standard, a veces espera FormData.
                    // Pero Documents usa JSON en el ejemplo anterior?
                    // Vamos a usar FormData para compatibilidad máxima con Django Forms
                    const formData = new FormData();
                    formData.append('name', this.form.name);
                    formData.append('is_active', this.form.is_active ? 'on' : '');
                    // Nota: Checkbox html envía 'on' si está check, nada si no.
                    // Si tu ModelForm espera True/False en JSON, usa JSON.stringify.
                    // Ajustaremos para FormData que es lo que suele usar locations.js

                    try {
                        const response = await fetch(url, {
                            method: 'POST',
                            body: formData,
                            headers: {
                                'X-CSRFToken': csrfToken,
                                'X-Requested-With': 'XMLHttpRequest'
                            }
                        });
                        const data = await response.json();

                        if (data.success) {
                            this.closeModal();
                            Toast.fire({
                                icon: 'success',
                                title: this.isEditing ? '¡Actualizado!' : '¡Creado!',
                                text: data.message
                            });
                            // Recargar tabla
                            window.loadTypes(searchInput ? searchInput.value : '');
                        } else {
                            // Manejo de errores
                            this.errors = data.errors || {};
                            if (!data.errors) {
                                Swal.fire('Error', 'Ocurrió un error inesperado', 'error');
                            }
                        }
                    } catch (e) {
                        console.error(e);
                        Swal.fire('Error', 'Error interno del servidor', 'error');
                    }
                }
            }
        });

        const vmType = appType.mount(MOUNT_ID);

        // Puentes Globales (para llamarlos desde onclick="" en el HTML)
        window.openCreateModal = () => vmType.openCreate();
        window.openEditModal = (id) => vmType.loadAndOpenEdit(id);
    }

    // =========================================================
    // 3. TOGGLE STATUS (Optimizado CSS como Location)
    // =========================================================
    window.toggleStatus = async (id, currentStatusBool) => {
        // currentStatusBool puede venir como string 'True'/'False' o boolean
        // Lo ideal es leer la clase del botón para determinar la acción visual, similar a Locations

        // Simplemente confirmamos la acción inversa al estado actual
        const actionVerb = currentStatusBool ? 'Desactivar' : 'Activar';
        const btnClass = currentStatusBool ? 'btn-swal-danger' : 'btn-swal-success';

        const result = await Swal.fire({
            title: `¿${actionVerb} tipo?`,
            text: "El cambio afectará la visibilidad en los formularios.",
            icon: 'warning',
            showCancelButton: true,
            buttonsStyling: false,
            customClass: {
                confirmButton: `swal2-confirm ${btnClass}`,
                cancelButton: 'swal2-cancel btn-swal-cancel',
                popup: 'swal2-popup'
            },
            confirmButtonText: `Sí, ${actionVerb.toLowerCase()}`,
            cancelButtonText: 'Cancelar'
        });

        if (result.isConfirmed) {
            try {
                const response = await fetch(`/documents/types/status/${id}/`, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                });
                const data = await response.json();

                if (data.success) {
                    Toast.fire({icon: 'success', title: '¡Estado Actualizado!', text: data.message});
                    window.loadTypes(searchInput ? searchInput.value : '');
                } else {
                    Swal.fire('Error', data.message, 'error');
                }
            } catch (e) {
                Swal.fire('Error', 'Error de conexión', 'error');
            }
        }
    };

    // Carga inicial
    // window.loadTypes(); // Opcional, ya que Django renderiza la primera vez
});