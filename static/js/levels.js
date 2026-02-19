/* static/js/levels.js */

document.addEventListener('DOMContentLoaded', () => {
    // --- Variables y referencias ---
    const tableBody = document.getElementById('table-body');
    const searchInput = document.getElementById('table-search');
    const pageSize = 10;
    let currentPage = 1;
    let allRows = Array.from(document.querySelectorAll('tr.level-row'));
    let filteredRows = allRows;
    let currentSearchTerm = '';
    let currentStatusFilter = 'all';

    function applyFilters() {
        allRows = Array.from(document.querySelectorAll('tr.level-row'));
        filteredRows = allRows.filter(row => {
            const rowStatus = row.dataset.status;
            if (currentStatusFilter !== 'all' && rowStatus !== currentStatusFilter) return false;
            if (currentSearchTerm && !row.innerText.toLowerCase().includes(currentSearchTerm)) return false;
            return true;
        });
        currentPage = 1;
        renderTable();
    }

    function renderTable() {
        const totalRows = filteredRows.length;
        const totalPages = Math.ceil(totalRows / pageSize) || 1;
        if (currentPage < 1) currentPage = 1;
        if (currentPage > totalPages) currentPage = totalPages;

        const start = (currentPage - 1) * pageSize;
        const end = start + pageSize;

        allRows.forEach(row => row.style.display = 'none');
        let rowsShown = 0;
        if (totalRows > 0) {
            const rowsToShow = filteredRows.slice(start, end);
            rowsToShow.forEach(row => {
                row.style.display = '';
                row.style.height = '32px'; // Compactar filas con datos
            });
            rowsShown = rowsToShow.length;
        }

        // Fila de 'No se encontraron niveles' dinámica
        let noResultsRow = document.getElementById('no-levels-row');
        if (totalRows === 0) {
            if (!noResultsRow) {
                noResultsRow = document.createElement('tr');
                noResultsRow.id = 'no-levels-row';
                noResultsRow.innerHTML = `<td colspan="4" style="text-align:center; padding: 20px 0; color: #888; font-size: 1.1em; background: #fff; border: none; height: 32px;">
                    <div style=\"display: flex; flex-direction: column; align-items: center; justify-content: center;\">
                        <i class=\"fas fa-inbox\" style=\"font-size: 2.5em; color: #d1d5db;\"></i>
                        <div style=\"margin-top: 10px;\">No se encontraron niveles</div>
                    </div>
                </td>`;
                if (tableBody) tableBody.appendChild(noResultsRow);
            }
        } else {
            if (noResultsRow) noResultsRow.remove();
            // Agregar filas vacías para mantener el alto fijo
            const emptyRowsNeeded = pageSize - rowsShown;
            // Elimina filas vacías previas
            Array.from(document.querySelectorAll('.empty-row')).forEach(r => r.remove());
            for (let i = 0; i < emptyRowsNeeded; i++) {
                const tr = document.createElement('tr');
                tr.className = 'empty-row';
                tr.innerHTML = '<td colspan="4" style="background:#fff; border:none; height:32px;">&nbsp;</td>';
                if (tableBody) tableBody.appendChild(tr);
            }
        }

        updatePaginationUI(totalRows, totalPages);
        updateStatsFrontend();
    }

    function updatePaginationUI(totalRows, totalPages) {
        const pageInfo = document.getElementById('page-info');
        const currentPageDisplay = document.getElementById('current-page-display');
        const btnPrev = document.getElementById('btn-prev');
        const btnNext = document.getElementById('btn-next');

        if (pageInfo) {
            const start = totalRows === 0 ? 0 : (currentPage - 1) * pageSize + 1;
            const end = Math.min(currentPage * pageSize, totalRows);
            pageInfo.innerText = totalRows === 0 ? "Sin resultados" : `Mostrando ${start}-${end} de ${totalRows}`;
        }
        if (currentPageDisplay) {
            currentPageDisplay.innerText = currentPage;
        }
        if (btnPrev) btnPrev.disabled = (currentPage === 1);
        if (btnNext) btnNext.disabled = (currentPage === totalPages || totalPages === 0);
    }

    window.filterByStatus = function(status) {
        currentStatusFilter = status;
        const cards = {
            'all': document.getElementById('card-filter-all'),
            'true': document.getElementById('card-filter-active'),
            'false': document.getElementById('card-filter-inactive')
        };
        Object.values(cards).forEach(card => {
            if (card) card.classList.add('opacity-low');
        });
        const activeCard = cards[status];
        if (activeCard) activeCard.classList.remove('opacity-low');
        applyFilters();
    };

    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            currentSearchTerm = e.target.value.toLowerCase();
            currentPage = 1;
            applyFilters();
        });
    }

    const btnPrev = document.getElementById('btn-prev');
    const btnNext = document.getElementById('btn-next');
    if (btnPrev) btnPrev.addEventListener('click', () => {
        if (currentPage > 1) {
            currentPage--;
            renderTable();
        }
    });
    if (btnNext) btnNext.addEventListener('click', () => {
        const totalRows = filteredRows.length;
        const totalPages = Math.ceil(totalRows / pageSize) || 1;
        if (currentPage < totalPages) {
            currentPage++;
            renderTable();
        }
    });

    function updateStatsFrontend() {
        const elTotal = document.getElementById('stat-total');
        const elActive = document.getElementById('stat-active');
        const elInactive = document.getElementById('stat-inactive');
        const total = allRows.length;
        const active = allRows.filter(r => r.dataset.status === 'true').length;
        const inactive = allRows.filter(r => r.dataset.status === 'false').length;
        if (elTotal) elTotal.textContent = total;
        if (elActive) elActive.textContent = active;
        if (elInactive) elInactive.textContent = inactive;
    }

    window.filterByStatus('all');
    renderTable();

    // --- MODAL VUE PARA FORMULARIO DE NIVELES ---
    const modalApp = document.getElementById('level-modal-app');
    if (modalApp && !modalApp.__vue_app__) {
        const { createApp, ref } = Vue;
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
                    document.getElementById(formEl).reset();
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
                            const d = data.data;
                            formName.value = d.name;
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
                    const url = isEditing.value
                        ? `/institution/levels/update/${currentId.value}/`
                        : `/institution/levels/create/`;

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

    // --- TOGGLE STATUS ---
    window.toggleLevelStatus = async (btnElement, url, name) => {
        const isCurrentlyActive = btnElement.classList.contains('btn-delete-action');
        const actionVerb = isCurrentlyActive ? 'Desactivar' : 'Activar';
        const btnClass = isCurrentlyActive ? 'btn-swal-danger' : 'btn-swal-success';
        const result = await Swal.fire({
            title: `¿${actionVerb} nivel?`,
            text: `Vas a cambiar el estado de "${name}"`,
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
                const formData = new FormData();
                formData.append('csrfmiddlewaretoken', document.querySelector('[name=csrfmiddlewaretoken]').value);
                const res = await fetch(url, {
                    method: 'POST',
                    body: formData,
                    headers: {'X-Requested-With': 'XMLHttpRequest'}
                });
                const data = await res.json();
                if (data.success) {
                    location.reload();
                } else {
                    Swal.fire('Error', data.message, 'error');
                }
            } catch (e) {
                Swal.fire('Error', 'Error de conexión', 'error');
            }
        }
    };

    // Listeners para stats (tarjetas)
    const cardAll = document.getElementById('card-filter-all');
    const cardActive = document.getElementById('card-filter-active');
    const cardInactive = document.getElementById('card-filter-inactive');
    if (cardAll) cardAll.addEventListener('click', () => window.filterByStatus('all'));
    if (cardActive) cardActive.addEventListener('click', () => window.filterByStatus('true'));
    if (cardInactive) cardInactive.addEventListener('click', () => window.filterByStatus('false'));
});