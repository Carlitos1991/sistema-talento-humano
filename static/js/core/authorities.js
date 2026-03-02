/* static/js/core/authorities.js */

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

    window.loadAuthorities = async function (searchTerm = '') {
        const params = new URLSearchParams();
        if (searchTerm) params.append('q', searchTerm);

        const url = `/settings/authorities/?${params.toString()}`;

        try {
            const response = await fetch(url, {
                headers: {'X-Requested-With': 'XMLHttpRequest'}
            });

            if (response.ok) {
                const data = await response.json();
                const wrapper = document.getElementById('table-content-wrapper');
                if (wrapper) {
                    wrapper.innerHTML = data.html;
                    // Reinicializar TableManager después de recargar la tabla
                    const table = wrapper.querySelector('.managed-table');
                    if (table && typeof TableManager !== 'undefined') {
                        new TableManager(table);
                    }
                }
            }
        } catch (error) {
            console.error('Error recargando tabla:', error);
        }
    };

    // Event Listener para el buscador
    // NOTA: La búsqueda la maneja TableManager cuando está activo
    // Si quieres búsqueda AJAX, cambia data-external-search="true" en la tabla
    if (searchInput && !searchInput.dataset.tmBound) {
        searchInput.addEventListener('keyup', (e) => {
            // Si TableManager está activo, él maneja la búsqueda
            const table = document.querySelector('.managed-table');
            if (table && table._tableManager) {
                return; // TableManager lo maneja
            }
            
            // Búsqueda AJAX si no hay TableManager
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                const q = e.target.value.trim();
                window.loadAuthorities(q);
            }, 300);
        });
        searchInput.dataset.tmBound = 'true';
    }

    // =========================================================
    // 2. MODAL VUE (Crear/Editar)
    // =========================================================
    const MOUNT_ID = '#authority-app';

    if (document.querySelector(MOUNT_ID)) {
        const {createApp} = Vue;

        const appAuthority = createApp({
            delimiters: ['[[', ']]'],
            data() {
                return {
                    isVisible: false,
                    isEditing: false,
                    currentId: null,
                    form: {
                        name: '',
                        position: '',
                        is_active: true
                    },
                    errors: {}
                }
            },
            computed: {
                modalTitle() {
                    return this.isEditing ? 'Editar Autoridad' : 'Nueva Autoridad';
                }
            },
            methods: {
                openCreate() {
                    this.isEditing = false;
                    this.currentId = null;
                    this.errors = {};
                    this.form = {name: '', position: '', is_active: true};
                    this.isVisible = true;
                },
                closeModal() {
                    this.isVisible = false;
                    this.errors = {};
                },
                async loadAndOpenEdit(id) {
                    this.errors = {};
                    try {
                        const response = await fetch(`/settings/authorities/detail/${id}/`);
                        const result = await response.json();

                        if (result.success) {
                            this.isEditing = true;
                            this.currentId = id;
                            this.form = {
                                name: result.data.name,
                                position: result.data.position,
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

                    const url = this.isEditing
                        ? `/settings/authorities/update/${this.currentId}/`
                        : '/settings/authorities/create/';

                    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;

                    const formData = new FormData();
                    formData.append('name', this.form.name);
                    formData.append('position', this.form.position);
                    formData.append('is_active', this.form.is_active ? 'on' : '');

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
                            window.loadAuthorities(searchInput ? searchInput.value : '');
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

        const vmAuthority = appAuthority.mount(MOUNT_ID);

        // Puentes Globales
        window.openCreateModal = () => vmAuthority.openCreate();
        window.openEditModal = (id) => vmAuthority.loadAndOpenEdit(id);
    }

    // =========================================================
    // 3. TOGGLE STATUS (Con SweetAlert)
    // =========================================================
    window.toggleStatus = async (id) => {
        const result = await Swal.fire({
            title: '¿Cambiar estado?',
            text: "Esta acción activará o desactivará el registro.",
            icon: 'warning',
            showCancelButton: true,
            buttonsStyling: false,
            customClass: {
                confirmButton: 'swal2-confirm btn-swal-warning',
                cancelButton: 'swal2-cancel btn-swal-cancel',
                popup: 'swal2-popup'
            },
            confirmButtonText: 'Sí, cambiar',
            cancelButtonText: 'Cancelar'
        });

        if (result.isConfirmed) {
            try {
                const response = await fetch(`/settings/authorities/toggle/${id}/`, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                });
                const data = await response.json();

                if (data.success) {
                    Toast.fire({icon: 'success', title: '¡Estado Actualizado!', text: data.message});
                    window.loadAuthorities(searchInput ? searchInput.value : '');
                } else {
                    Swal.fire('Error', data.message, 'error');
                }
            } catch (e) {
                Swal.fire('Error', 'Error de conexión', 'error');
            }
        }
    };
    
    // =========================================================
    // 4. INICIALIZAR TABLEMANAGER
    // =========================================================
    const initialTable = document.querySelector('.managed-table');
    if (initialTable && typeof TableManager !== 'undefined') {
        new TableManager(initialTable);
    }
});
