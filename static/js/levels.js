/* static/js/levels.js */
document.addEventListener('DOMContentLoaded', () => {
    // 1. Manejo de Cards (Filtros Activo/Inactivo)
    // Usamos el TableManager para filtrar, no lógica manual.
    const cards = {
        'all': document.getElementById('card-filter-all'),
        'true': document.getElementById('card-filter-active'),
        'false': document.getElementById('card-filter-inactive')
    };

    window.filterByStatus = function (status) {
        // Estilos de tarjetas
        Object.values(cards).forEach(card => {
            if (card) card.classList.add('opacity-low');
        });
        const activeCard = cards[status];
        if (activeCard) activeCard.classList.remove('opacity-low');

        // BUSCAR LA TABLA Y PEDIRLE QUE FILTRE
        const table = document.querySelector('.managed-table');
        if (table && table._tableManager) {
            // Usa el método filterByColumnData que agregamos al TableManager
            // Asume que las filas tienen data-status="true"
            table._tableManager.filterByColumnData('status', status);
        }
    };

    // Event listeners para cards
    if (cards.all) cards.all.addEventListener('click', () => window.filterByStatus('all'));
    if (cards['true']) cards['true'].addEventListener('click', () => window.filterByStatus('true'));
    if (cards['false']) cards['false'].addEventListener('click', () => window.filterByStatus('false'));

    // Filtro inicial visual
    const statsRow = document.getElementById('stats-row');
    window.filterByStatus('all');
    setTimeout(() => {
        if (statsRow) statsRow.style.display = 'flex';
    }, 100);

    // --- LOGICA DE MODAL (VUE) ---
    const modalApp = document.getElementById('level-modal-app');
    if (modalApp && !modalApp.__vue_app__) {
        const {createApp, ref} = Vue;
        const app = createApp({
            delimiters: ['[[', ']]'],
            setup() {
                const isVisible = ref(false);
                const isEditing = ref(false);
                const currentId = ref(null);
                const errors = ref({});
                const formName = ref('');
                const formEl = 'levelForm';

                const openCreate = () => {
                    isEditing.value = false;
                    currentId.value = null;
                    errors.value = {};
                    formName.value = '';
                    const f = document.getElementById(formEl);
                    if (f) f.reset();
                    isVisible.value = true;
                    document.body.classList.add('no-scroll');
                };

                const openEdit = async (id) => {
                    isEditing.value = true;
                    currentId.value = id;
                    errors.value = {};
                    try {
                        const res = await fetch(`/institution/levels/detail/${id}/`);
                        const data = await res.json();
                        if (data.success) {
                            formName.value = data.data.name;
                            isVisible.value = true;
                            document.body.classList.add('no-scroll');
                        }
                    } catch (e) {
                        alert('Error al cargar datos');
                    }
                };

                const closeModal = () => {
                    isVisible.value = false;
                    document.body.classList.remove('no-scroll');
                };

                const submitForm = async () => {
                    const formData = new FormData(document.getElementById(formEl));
                    formData.set('name', formName.value);
                    const url = isEditing.value ? `/institution/levels/update/${currentId.value}/` : `/institution/levels/create/`;
                    try {
                        const res = await fetch(url, {
                            method: 'POST', body: formData,
                            headers: {'X-Requested-With': 'XMLHttpRequest'}
                        });
                        const data = await res.json();
                        if (data.success) {
                            closeModal();
                            location.reload(); // Recarga simple para asegurar que todo se sincroniza
                        } else {
                            errors.value = data.errors;
                        }
                    } catch (e) {
                        alert('Error del servidor');
                    }
                };

                window.openEditLevel = openEdit;
                window.openCreateLevel = openCreate;
                return {isVisible, isEditing, errors, closeModal, submitForm, formName};
            }
        });
        modalApp.__vue_app__ = app.mount('#level-modal-app');
        const btnNew = document.getElementById('btn-add-level');
        if (btnNew) btnNew.onclick = () => window.openCreateLevel();
    }

    // --- TOGGLE STATUS (AJAX) ---
    function showLoader() { /* Tu loader existente */
    }

    function hideLoader() { /* Tu loader existente */
    }

    window.toggleLevelStatus = async (btnElement, url, name) => {
        // Lógica de SweetAlert (se mantiene igual)
        const isDelete = btnElement.classList.contains('btn-delete-action');
        const result = await Swal.fire({
            title: `¿${isDelete ? 'Desactivar' : 'Activar'} nivel?`,
            text: `Vas a cambiar el estado de "${name}"`,
            icon: 'warning',
            showCancelButton: true,
            confirmButtonText: 'Sí, cambiar'
        });

        if (result.isConfirmed) {
            // showLoader();
            try {
                const formData = new FormData();
                const token = document.querySelector('[name=csrfmiddlewaretoken]');
                if (token) formData.append('csrfmiddlewaretoken', token.value);

                const res = await fetch(url, {
                    method: 'POST',
                    body: formData,
                    headers: {'X-Requested-With': 'XMLHttpRequest'}
                });
                const data = await res.json();

                if (data.success) {
                    // Recargar tabla PARCIAL
                    const r = await fetch('/institution/levels/partial_table/');
                    const html = await r.text();
                    document.getElementById('table-content-wrapper').innerHTML = html;

                    // IMPORTANTE: RE-INICIALIZAR TABLE MANAGER
                    // Como reemplazamos el HTML, el TableManager viejo murió. Creamos uno nuevo.
                    const newTable = document.querySelector('.managed-table');
                    if (newTable) new TableManager(newTable);

                    // Reaplicar filtro actual (visual)
                    window.filterByStatus(currentStatusFilter || 'all');

                    Swal.fire('Éxito', data.message, 'success');
                } else {
                    Swal.fire('Error', data.message, 'error');
                }
            } catch (e) {
                Swal.fire('Error', 'Conexión', 'error');
            }
            // hideLoader();
        }
    };
});