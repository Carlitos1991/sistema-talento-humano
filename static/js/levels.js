/* static/js/levels.js */

document.addEventListener('DOMContentLoaded', () => {

    // --- 1. FILTROS DE TARJETAS (Delegados al TableManager) ---
    const cards = {
        'all': document.getElementById('card-filter-all'),
        'true': document.getElementById('card-filter-active'),
        'false': document.getElementById('card-filter-inactive')
    };

    window.filterByStatus = function (status) {
        // Efecto visual en tarjetas
        Object.values(cards).forEach(card => {
            if (card) card.classList.add('opacity-low');
        });
        const activeCard = cards[status];
        if (activeCard) activeCard.classList.remove('opacity-low');

        // COMUNICACIÓN CON TABLE MANAGER
        const table = document.querySelector('.managed-table');
        if (table && table._tableManager) {
            // Esto aplica el filtro de columna Y mantiene la búsqueda de texto si existe
            table._tableManager.filterByColumnData('status', status);
        }
    };

    // Listeners Tarjetas
    if (cards.all) cards.all.addEventListener('click', () => window.filterByStatus('all'));
    if (cards['true']) cards['true'].addEventListener('click', () => window.filterByStatus('true'));
    if (cards['false']) cards['false'].addEventListener('click', () => window.filterByStatus('false'));

    // Filtro inicial
    const statsRow = document.getElementById('stats-row');
    // Pequeño delay para asegurar que TableManager esté listo
    setTimeout(() => {
        window.filterByStatus('all');
        if (statsRow) statsRow.style.display = 'flex';
    }, 50);


    // --- 2. MODAL VUE (Crear/Editar) ---
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
                            location.reload();
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


    // --- 3. TOGGLE STATUS (Activar/Desactivar) ---
    window.toggleLevelStatus = async (btnElement, url, name) => {
        const isDelete = btnElement.classList.contains('btn-delete-action');
        const result = await Swal.fire({
            title: `¿${isDelete ? 'Desactivar' : 'Activar'} nivel?`,
            text: `Vas a cambiar el estado de "${name}"`,
            icon: 'warning',
            showCancelButton: true,
            confirmButtonText: 'Sí, cambiar',
            cancelButtonText: 'Cancelar'
        });

        if (result.isConfirmed) {
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
                    // Recargar HTML tabla
                    const toggleEl = document.getElementById('toggleInactiveLevels');
                    const showInactive = toggleEl && toggleEl.checked ? 'true' : 'false';
                    const r = await fetch('/institution/levels/partial_table/?show_inactive=' + showInactive);
                    const html = await r.text();
                    document.getElementById('table-content-wrapper').innerHTML = html;

                    // Reiniciar TableManager sobre la nueva tabla
                    const newTable = document.querySelector('.managed-table');
                    if (newTable) new TableManager(newTable);

                    // Reaplicar filtro visual actual
                    // (Nota: al recargar HTML se pierde el input de búsqueda, pero se mantiene el filtro de Cards)
                    const activeCard = document.querySelector('.stat-card:not(.opacity-low)');
                    if (activeCard && activeCard.id === 'card-filter-active') window.filterByStatus('true');
                    else if (activeCard && activeCard.id === 'card-filter-inactive') window.filterByStatus('false');
                    else window.filterByStatus('all');

                    Swal.fire('Éxito', data.message, 'success');
                } else {
                    Swal.fire('Error', data.message, 'error');
                }
            } catch (e) {
                Swal.fire('Error', 'Conexión', 'error');
            }
        }
    };

    // --- 4. TOGGLE INACTIVOS (Mostrar/Ocultar) ---
    window.toggleInactiveLevels = function (showInactive) {
        const val = showInactive ? 'true' : 'false';
        fetch('/institution/levels/partial_table/?show_inactive=' + val)
            .then(res => res.text())
            .then(html => {
                document.getElementById('table-content-wrapper').innerHTML = html;
                const newTable = document.querySelector('.managed-table');
                if (newTable) new TableManager(newTable);

                // Reaplicar filtro visual actual de tarjetas
                const activeCard = document.querySelector('.stat-card:not(.opacity-low)');
                if (activeCard && activeCard.id === 'card-filter-active') window.filterByStatus('true');
                else if (activeCard && activeCard.id === 'card-filter-inactive') window.filterByStatus('false');
                else window.filterByStatus('all');
            })
            .catch(err => console.error('Error cargando niveles:', err));
    };
});