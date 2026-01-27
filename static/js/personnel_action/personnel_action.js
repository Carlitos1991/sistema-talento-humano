const {createApp} = Vue;

createApp({
    delimiters: ['[[', ']]'],
    data() {
        return {
            showModal: false,
            modalTitle: 'Nueva Acción de Personal',
            modalContent: '<div class="text-center"><i class="fa-solid fa-spinner fa-spin"></i> Cargando...</div>'
        }
    },
    methods: {
        async openCreateModal() {
            this.showModal = true;
            this.modalTitle = 'Registrar Acción';

            // Fetch del formulario
            const response = await fetch("{% url 'personnel_actions:action_create' %}");
            this.modalContent = await response.text();

            // Re-inicializar Select2 después de renderizar HTML
            this.$nextTick(() => {
                $('.select2').select2({dropdownParent: $('.modal-container')});
                this.bindFormSubmit();
            });
        },
        closeModal() {
            this.showModal = false;
            this.modalContent = '';
        },
        bindFormSubmit() {
            const form = document.querySelector('.modal-body form');
            if (!form) return;

            form.addEventListener('submit', async (e) => {
                e.preventDefault();
                const formData = new FormData(form);

                const response = await fetch(form.action, {
                    method: 'POST',
                    body: formData,
                    headers: {'X-Requested-With': 'XMLHttpRequest'}
                });

                if (response.ok) {
                    const newTableHtml = await response.text();
                    document.getElementById('tableContainer').innerHTML = newTableHtml;
                    this.closeModal();
                    Swal.fire('Éxito', 'Acción guardada correctamente', 'success');
                } else {
                    // Manejo de errores (volver a pintar el form con errores)
                    this.modalContent = await response.text();
                    this.$nextTick(() => {
                        $('.select2').select2({dropdownParent: $('.modal-container')});
                        this.bindFormSubmit();
                    });
                }
            });
        }
    }
}).mount('#vue-modals');

// Lógica Vanilla JS para búsqueda
let timeout = null;

function searchTable() {
    clearTimeout(timeout);
    timeout = setTimeout(() => {
        const query = document.getElementById('searchInput').value;
        fetch(`?q=${query}`, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
            .then(r => r.text())
            .then(html => {
                document.getElementById('tableContainer').innerHTML = html;
            });
    }, 300);
}