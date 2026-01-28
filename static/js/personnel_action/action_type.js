/* static/js/personnel_action/action_type.js */

document.addEventListener('DOMContentLoaded', () => {

    // =========================================================
    // 1. LÓGICA DE TABLA (FILTROS Y PAGINACIÓN LOCAL)
    // =========================================================

    // Estado de la tabla
    let tableState = {
        status: '', // ''=All, 'true'=Active, 'false'=Inactive
        q: '',
        page: 1,
        pageSize: 10
    };

    let allRows = [];      // Todas las filas cargadas
    let filteredRows = []; // Filas después de buscar

    // Inicializar
    initTableLogic();

    // Función principal para cargar/recargar datos
    async function loadTableData() {
        const params = new URLSearchParams();
        if (tableState.status) params.append('status', tableState.status);
        if (tableState.q) params.append('q', tableState.q);

        // Llamada AJAX a la vista ListView
        const url = `${window.location.pathname}?${params.toString()}`;

        try {
            const response = await fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}});
            if (response.ok) {
                const html = await response.text();
                const wrapper = document.getElementById('table-content-wrapper');
                if (wrapper) {
                    wrapper.innerHTML = html;
                    // Una vez inyectado el HTML, reiniciamos la lógica de paginación local
                    initTableLogic();
                }
            }
        } catch (e) {
            console.error('Error cargando tabla:', e);
        }
    }

    // Inicializa la lógica sobre las filas existentes en el DOM
    function initTableLogic() {
        // Seleccionamos las filas dentro del tbody
        const tbody = document.querySelector('#table-content-wrapper table tbody');
        if (!tbody) return;

        allRows = Array.from(tbody.querySelectorAll('tr'));

        // Si la tabla viene vacía o con mensaje "No hay registros"
        if (allRows.length === 1 && allRows[0].innerText.includes('No hay registros')) {
            allRows = [];
        }

        applyLocalFilters();
    }

    // Aplica búsqueda local (si ya cargaste datos) y resetea página
    function applyLocalFilters() {
        // En este caso, como el filtrado fuerte lo hace el servidor (active/inactive),
        // aquí filtramos por texto lo que ya llegó, o simplemente pasamos todo.
        // Si prefieres búsqueda 100% servidor, salta este paso y asigna filteredRows = allRows.

        // Modo Híbrido: El servidor filtra Status, JS pagina.
        filteredRows = allRows;

        tableState.page = 1;
        renderPagination();
        updateStatsUI();
    }

    // Renderiza la página actual (Oculta/Muestra TRs)
    function renderPagination() {
        const totalRows = filteredRows.length;
        const totalPages = Math.ceil(totalRows / tableState.pageSize) || 1;

        // Ajustar página válida
        if (tableState.page < 1) tableState.page = 1;
        if (tableState.page > totalPages) tableState.page = totalPages;

        const start = (tableState.page - 1) * tableState.pageSize;
        const end = start + tableState.pageSize;

        // 1. Ocultar todas
        allRows.forEach(row => row.style.display = 'none');

        // 2. Mostrar solo el slice actual
        if (totalRows > 0) {
            filteredRows.slice(start, end).forEach(row => row.style.display = '');
        } else {
            // Manejo visual de tabla vacía si se desea
        }

        // 3. Actualizar controles UI
        const pageInfo = document.getElementById('page-info');
        const btnPrev = document.getElementById('btn-prev');
        const btnNext = document.getElementById('btn-next');
        const pageDisplay = document.getElementById('current-page-display');

        if (pageInfo) {
            const startLabel = totalRows > 0 ? start + 1 : 0;
            const endLabel = Math.min(end, totalRows);
            pageInfo.textContent = `Mostrando ${startLabel}-${endLabel} de ${totalRows}`;
        }
        if (pageDisplay) pageDisplay.textContent = tableState.page;

        if (btnPrev) {
            btnPrev.disabled = (tableState.page === 1);
            btnPrev.onclick = () => {
                if (tableState.page > 1) {
                    tableState.page--;
                    renderPagination();
                }
            };
        }
        if (btnNext) {
            btnNext.disabled = (tableState.page === totalPages);
            btnNext.onclick = () => {
                if (tableState.page < totalPages) {
                    tableState.page++;
                    renderPagination();
                }
            };
        }
    }

    // Actualiza visualmente las tarjetas de estadísticas
    function updateStatsUI() {
        const cards = {
            '': document.getElementById('card-filter-all'),
            'true': document.getElementById('card-filter-true'),
            'false': document.getElementById('card-filter-false')
        };

        Object.keys(cards).forEach(key => {
            const card = cards[key];
            if (card) {
                if (String(tableState.status) === String(key)) {
                    card.classList.remove('opacity-low');
                    card.classList.add('active-card-shadow'); // Opcional para resaltar más
                } else {
                    card.classList.add('opacity-low');
                    card.classList.remove('active-card-shadow');
                }
            }
        });
    }

    // Evento de búsqueda (Debounce)
    const searchInput = document.getElementById('table-search');
    let debounceTimer;
    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(() => {
                tableState.q = e.target.value;
                loadTableData(); // Recargamos del server para buscar en toda la BD
            }, 300);
        });
    }

    // Exponer función de filtrado al window para los onclick del HTML
    window.filterList = function (status) {
        tableState.status = status;
        loadTableData();
    };


    // =========================================================
    // 2. VUE INSTANCE (SOLO PARA MODALES)
    // =========================================================
    const {createApp} = Vue;

    const modalApp = createApp({
        delimiters: ['[[', ']]'],
        data() {
            return {
                isVisible: false,
                isEdit: false,
                loading: false,
                currentId: null,
                formData: {name: '', code: '', is_active: true},
                errors: {}
            }
        },
        methods: {
            openForCreate() {
                this.resetForm();
                this.isEdit = false;
                this.isVisible = true;
            },
            async openForEdit(id) {
                this.resetForm();
                this.isEdit = true;
                this.currentId = id;
                this.isVisible = true;
                this.loading = true;
                try {
                    const response = await fetch(`/personnel_actions/types/api/detail/${id}/`);
                    if (response.ok) {
                        const data = await response.json();
                        this.formData = {name: data.name, code: data.code, is_active: data.is_active};
                    }
                } catch (e) {
                    console.error(e);
                } finally {
                    this.loading = false;
                }
            },
            closeModal() {
                this.isVisible = false;
                this.resetForm();
            },
            resetForm() {
                this.formData = {name: '', code: '', is_active: true};
                this.errors = {};
                this.currentId = null;
            },
            async saveData() {
                this.loading = true;
                this.errors = {};
                let url = '/personnel_actions/types/api/save/';
                if (this.isEdit) url += `${this.currentId}/`;

                const data = new FormData();
                data.append('name', this.formData.name);
                data.append('code', this.formData.code);
                data.append('is_active', this.formData.is_active ? 'on' : '');
                data.append('csrfmiddlewaretoken', getCookie('csrftoken'));

                try {
                    const response = await fetch(url, {
                        method: 'POST', body: data, headers: {'X-Requested-With': 'XMLHttpRequest'}
                    });
                    const result = await response.json();

                    if (result.success) {
                        this.closeModal();
                        Swal.fire({
                            icon: 'success', title: 'Guardado', toast: true,
                            position: 'top-end', showConfirmButton: false, timer: 1500
                        });
                        // RECARGAR TABLA Y PAGINACIÓN
                        loadTableData();
                    } else {
                        this.errors = result.errors || {};
                    }
                } catch (e) {
                    Swal.fire('Error', 'Error de conexión', 'error');
                } finally {
                    this.loading = false;
                }
            }
        }
    });

    const modalInstance = modalApp.mount('#action-type-modal-app');

    // Puentes Globales para Vue
    window.openActionTypeModal = () => modalInstance.openForCreate();
    window.editActionType = (id) => modalInstance.openForEdit(id);

    window.deleteActionType = async (id) => {
        Swal.fire({
            title: '¿Eliminar?', icon: 'warning', showCancelButton: true, confirmButtonText: 'Sí'
        }).then(async (result) => {
            if (result.isConfirmed) {
                const response = await fetch(`/personnel_actions/types/api/delete/${id}/`, {
                    method: 'POST',
                    headers: {'X-CSRFToken': getCookie('csrftoken'), 'X-Requested-With': 'XMLHttpRequest'}
                });
                const res = await response.json();
                if (res.success) {
                    Swal.fire('Eliminado', '', 'success');
                    loadTableData(); // Recargar tabla
                }
            }
        });
    };
});

// Helper CSRF
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