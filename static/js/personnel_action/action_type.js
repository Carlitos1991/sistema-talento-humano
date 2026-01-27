const { createApp } = Vue;

const app = createApp({
    delimiters: ['[[', ']]'],
    data() {
        return {
            showModal: false,
            isEdit: false,
            modalContent: '',
            filters: {
                query: '',
                status: ''
            },
            stats: {
                total: 0,
                active: 0,
                inactive: 0
            },
            loading: false,
            debounceTimeout: null
        }
    },
    mounted() {
        // Leer estadísticas iniciales del DOM
        const el = document.getElementById('action-type-app');
        this.stats.total = el.dataset.total;
        this.stats.active = el.dataset.active;
        this.stats.inactive = el.dataset.inactive;

        // Exponer instancia globalmente para los botones onclick del HTML parcial
        window.ActionTypeInstance = this;
    },
    methods: {
        // --- MODAL LOGIC ---
        async openCreateModal() {
            this.isEdit = false;
            this.showModal = true;
            this.modalContent = ''; // Limpiar previo

            try {
                // URL hardcodeada o pasada por data attribute, asumimos estándar
                const response = await fetch('/personnel-actions/types/create/', {
                    headers: {'X-Requested-With': 'XMLHttpRequest'}
                });
                this.modalContent = await response.text();
                this.$nextTick(() => this.bindFormSubmit());
            } catch (error) {
                console.error('Error cargando modal', error);
            }
        },

        async openEditModal(url) {
            this.isEdit = true;
            this.showModal = true;
            this.modalContent = '';

            try {
                const response = await fetch(url, {
                    headers: {'X-Requested-With': 'XMLHttpRequest'}
                });
                this.modalContent = await response.text();
                this.$nextTick(() => this.bindFormSubmit());
            } catch (error) {
                console.error('Error cargando modal edición', error);
            }
        },

        closeModal() {
            this.showModal = false;
            this.modalContent = '';
        },

        // --- FORM SUBMISSION ---
        bindFormSubmit() {
            const form = document.querySelector('.modal-container form');
            if (!form) return;

            // Re-estilizar botones del form django para que coincidan con el diseño
            // Esto es un truco para usar el form renderizado por Django pero con estilo Vue
            const footer = document.createElement('div');
            footer.className = 'modal-footer-fixed';
            footer.innerHTML = `
                <button type="button" class="btn-cancel" onclick="ActionTypeInstance.closeModal()">CANCELAR</button>
                <button type="submit" class="btn-save">
                    ${this.isEdit ? 'ACTUALIZAR' : 'GUARDAR'}
                </button>
            `;

            // Ocultar botones originales si existen y agregar los nuevos
            const oldFooter = form.querySelector('.modal-footer');
            if(oldFooter) oldFooter.style.display = 'none';
            form.appendChild(footer);

            form.addEventListener('submit', async (e) => {
                e.preventDefault();
                const formData = new FormData(form);

                try {
                    const response = await fetch(form.action, {
                        method: 'POST',
                        body: formData,
                        headers: {'X-Requested-With': 'XMLHttpRequest'}
                    });

                    if (response.ok) {
                        const newTable = await response.text();
                        document.getElementById('table-content-wrapper').innerHTML = newTable;
                        this.closeModal();
                        Swal.fire({
                            icon: 'success',
                            title: 'Éxito',
                            text: 'Registro guardado correctamente',
                            timer: 1500,
                            showConfirmButton: false,
                            toast: true,
                            position: 'top-end'
                        });
                        // Recargar pagina para actualizar stats (opcional, o hacer fetch de stats)
                        setTimeout(() => location.reload(), 1500);
                    } else {
                        // Error de validación: repintar form
                        this.modalContent = await response.text();
                        this.$nextTick(() => this.bindFormSubmit());
                    }
                } catch (error) {
                    Swal.fire('Error', 'Error de conexión', 'error');
                }
            });
        },

        // --- ACCIONES DE TABLA ---
        async toggleStatus(url) {
            try {
                // Necesitamos el token CSRF
                const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';

                const response = await fetch(url, {
                    method: 'POST',
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest',
                        'X-CSRFToken': getCookie('csrftoken') // Función helper estándar de Django
                    }
                });

                if(response.ok) {
                     const newTable = await response.text();
                     document.getElementById('table-content-wrapper').innerHTML = newTable;
                     // Actualizar stats visualmente (simple)
                     location.reload();
                }
            } catch (e) {
                console.error(e);
            }
        },

        // --- BÚSQUEDA Y FILTROS ---
        debouncedSearch() {
            clearTimeout(this.debounceTimeout);
            this.debounceTimeout = setTimeout(() => {
                this.fetchData();
            }, 300);
        },

        filterByStatus(status) {
            this.filters.status = status;
            this.fetchData();
        },

        async fetchData() {
            const params = new URLSearchParams({
                q: this.filters.query,
                status: this.filters.status
            });
            const url = `${window.location.pathname}?${params.toString()}`;

            const response = await fetch(url, {
                headers: {'X-Requested-With': 'XMLHttpRequest'}
            });
            const html = await response.text();
            document.getElementById('table-content-wrapper').innerHTML = html;
        }
    }
});

app.mount('#action-type-app');

// Helper para CSRF Token (Estándar Django)
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