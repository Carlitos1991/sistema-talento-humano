// Estado global de sort (necesario para table-sort.js)
window.currentSortCol = null;
window.currentSortAsc = true;

/* static/js/levels.js */
document.addEventListener('DOMContentLoaded', () => {
    // --- Variables y referencias ---
    const tableBody = document.getElementById('table-body');
    const searchInput = document.getElementById('table-search');

    // Referencias a las tarjetas de filtro (Stats)
    const cardAll = document.getElementById('card-filter-all');
    const cardActive = document.getElementById('card-filter-active');
    const cardInactive = document.getElementById('card-filter-inactive');

    const pageSize = 10;

    let currentPage = 1;
    let allRows = Array.from(document.querySelectorAll('tr.level-row'));
    let filteredRows = allRows;
    window.filteredRows = filteredRows; // Referencia global

    let currentSearchTerm = '';
    let currentStatusFilter = 'all';

    // --- FUNCIÓN AUXILIAR DE ORDENAMIENTO ---
    function sortRowsData(rows) {
        if (window.currentSortCol === null) return rows;

        return rows.sort(function (a, b) {
            let cellA = a.children[window.currentSortCol] ? a.children[window.currentSortCol].innerText.trim() : '';
            let cellB = b.children[window.currentSortCol] ? b.children[window.currentSortCol].innerText.trim() : '';

            // Detectar si son números para ordenar correctamente
            let numA = parseFloat(cellA);
            let numB = parseFloat(cellB);

            if (!isNaN(numA) && !isNaN(numB) && cellA !== '' && cellB !== '') {
                cellA = numA;
                cellB = numB;
            } else {
                cellA = cellA.toString().toLowerCase();
                cellB = cellB.toString().toLowerCase();
            }

            if (window.currentSortAsc) {
                return cellA > cellB ? 1 : cellA < cellB ? -1 : 0;
            } else {
                return cellA < cellB ? 1 : cellA > cellB ? -1 : 0;
            }
        });
    }

    // --- FILTRADO PRINCIPAL ---
    function applyFilters() {
        // Refrescar lista completa (por si hubo cambios en DOM tras editar/crear)
        allRows = Array.from(document.querySelectorAll('tr.level-row'));

        // 1. Filtrar
        filteredRows = allRows.filter(row => {
            const rowStatus = row.dataset.status; // 'true' o 'false'

            // Filtro de estado
            if (currentStatusFilter !== 'all' && rowStatus !== currentStatusFilter) return false;

            // Filtro de búsqueda texto
            if (currentSearchTerm && !row.innerText.toLowerCase().includes(currentSearchTerm)) return false;

            return true;
        });

        // 2. Ordenar (si hay columna seleccionada)
        if (window.currentSortCol !== null) {
            filteredRows = sortRowsData(filteredRows);
        }

        // 3. Actualizar globales y reiniciar página
        window.filteredRows = filteredRows;
        window.allRows = allRows;
        currentPage = 1;

        renderTable();
    }

    // --- RENDERIZADO DE TABLA ---
    window.renderTable = function renderTable() {
        let rows = window.filteredRows || [];

        // Asegurar que el ordenamiento esté aplicado
        if (window.currentSortCol !== null) {
            rows = sortRowsData(rows); // Ordenamos el array en memoria
            window.filteredRows = rows;
        }


        const totalRows = rows.length;
        const totalPages = Math.ceil(totalRows / pageSize) || 1;

        // Validar página actual
        if (currentPage < 1) currentPage = 1;
        if (currentPage > totalPages) currentPage = totalPages;

        const start = (currentPage - 1) * pageSize;
        const end = start + pageSize;

        // 1. Ocultar todas las filas primero
        allRows.forEach(row => row.style.display = 'none');

        // 2. Mostrar y REORDENAR filas de la página actual en el DOM
        if (totalRows > 0) {
            const rowsToShow = rows.slice(start, end);

            rowsToShow.forEach(row => {
                row.style.display = '';
                row.style.height = '32px';
                // Esto es vital para que el orden visual coincida con el array ordenado
                tableBody.appendChild(row);
            });
        }

        // 3. Manejo de "No resultados"
        let noResultsRow = document.getElementById('no-levels-row');
        if (totalRows === 0) {
            if (!noResultsRow) {
                noResultsRow = document.createElement('tr');
                noResultsRow.id = 'no-levels-row';
                noResultsRow.innerHTML = `<td colspan="4" style="text-align:center; padding: 20px 0; color: #888; font-size: 1.1em; background: #fff; border: none; height: 32px;">
                    <div style="display: flex; flex-direction: column; align-items: center; justify-content: center;">
                        <i class="fas fa-inbox" style="font-size: 2.5em; color: #d1d5db;"></i>
                        <div style="margin-top: 10px;">No se encontraron niveles</div>
                    </div>
                </td>`;
                if (tableBody) tableBody.appendChild(noResultsRow);
            }
        } else {
            if (noResultsRow) noResultsRow.remove();
        }

        updatePaginationUI(totalRows, totalPages);
        updateStatsFrontend();
    };

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

    // --- LISTENERS DE INTERFAZ ---

    // 1. Función Filtros de Estado (Tarjetas)
    window.filterByStatus = function (status) {
        currentStatusFilter = status;

        const cards = {
            'all': cardAll,
            'true': cardActive,
            'false': cardInactive
        };

        // Actualizar UI de tarjetas (opacidad)
        Object.values(cards).forEach(card => {
            if (card) card.classList.add('opacity-low');
        });
        const activeCard = cards[status];
        if (activeCard) activeCard.classList.remove('opacity-low');

        applyFilters();
    };

    // 2. Eventos Click en Tarjetas (CORREGIDO: Las variables ya existen)
    if (cardAll) cardAll.addEventListener('click', () => window.filterByStatus('all'));
    if (cardActive) cardActive.addEventListener('click', () => window.filterByStatus('true'));
    if (cardInactive) cardInactive.addEventListener('click', () => window.filterByStatus('false'));

    // 3. Búsqueda
    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            currentSearchTerm = e.target.value.toLowerCase();
            currentPage = 1;
            applyFilters();
        });
    }

    // 4. Paginación
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

    // 5. Actualizar contadores
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

    // Inicialización de vista
    const statsRow = document.getElementById('stats-row');
    window.filterByStatus('true'); // Filtro por defecto: Activos

    setTimeout(() => {
        if (statsRow) statsRow.style.display = 'flex';
    }, 120);

    // Render inicial
    renderTable();


    // --- MODAL VUE PARA FORMULARIO DE NIVELES ---
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

    // --- TOGGLE STATUS (AJAX) ---
    function showTableLoader() {
        let loader = document.getElementById('table-loader');
        if (!loader) {
            loader = document.createElement('div');
            loader.id = 'table-loader';
            loader.style.cssText = 'position:absolute; top:0; left:0; width:100%; height:100%; background:rgba(255,255,255,0.7); display:flex; align-items:center; justify-content:center; z-index:10;';
            loader.innerHTML = '<div class="loader-spinner"></div>';
            const container = document.querySelector('.table-container');
            if (container) container.appendChild(loader);
        }
        loader.style.display = 'flex';
    }

    function hideTableLoader() {
        const loader = document.getElementById('table-loader');
        if (loader) loader.style.display = 'none';
    }

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
            showTableLoader();
            try {
                const formData = new FormData();
                const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]');
                if (csrfToken) formData.append('csrfmiddlewaretoken', csrfToken.value);

                const res = await fetch(url, {
                    method: 'POST',
                    body: formData,
                    headers: {'X-Requested-With': 'XMLHttpRequest'}
                });
                const data = await res.json();

                if (data.success) {
                    // Recargar solo HTML de la tabla
                    const r = await fetch('/institution/levels/partial_table/');
                    const html = await r.text();

                    document.getElementById('table-content-wrapper').innerHTML = html;
                    hideTableLoader();

                    // RE-INICIALIZAR REFERENCIAS
                    allRows = Array.from(document.querySelectorAll('tr.level-row'));

                    // IMPORTANTE: Volver a aplicar el filtro actual para mantener la vista consistente
                    applyFilters();

                    Swal.fire({
                        title: '¡Éxito!',
                        text: data.message,
                        icon: 'success',
                        timer: 1500,
                        showConfirmButton: false
                    });
                } else {
                    hideTableLoader();
                    Swal.fire('Error', data.message, 'error');
                }
            } catch (e) {
                hideTableLoader();
                Swal.fire('Error', 'Error de conexión', 'error');
            }
        }
    };
});