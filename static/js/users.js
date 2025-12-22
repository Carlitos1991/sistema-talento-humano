/* static/js/users.js */

document.addEventListener('DOMContentLoaded', () => {

    // ---------------------------------------------------------
    // 1. VARIABLES Y ESTADO GLOBAL
    // ---------------------------------------------------------
    const tableContainer = document.getElementById('table-content-wrapper');
    const quickSearchInput = document.getElementById('table-search');

    // Referencias de Paginación
    const pageInfo = document.getElementById('page-info');
    const pageDisplay = document.getElementById('current-page-display');
    const btnPrev = document.getElementById('btn-prev');
    const btnNext = document.getElementById('btn-next');

    // Estado actual de filtros (Para mantener la memoria al paginar)
    let currentFilters = {
        q: '',
        page: 1,
        status: '',
        cedula: '',
        first_name: '',
        last_name: '',
        role: ''
    };

    // ---------------------------------------------------------
    // 2. LÓGICA DE CARGA (AJAX)
    // ---------------------------------------------------------

    // Función Maestra: Actualiza filtros y recarga tabla
    window.fetchUsers = function (newParams = {}) {

        // 1. Si es reset, limpiar todo
        if (newParams.reset) {
            currentFilters = {
                q: '', page: 1, status: '', cedula: '', first_name: '', last_name: '', role: ''
            };
            if (quickSearchInput) quickSearchInput.value = '';
        } else {
            // 2. Mezclar nuevos parámetros con los actuales
            Object.assign(currentFilters, newParams);
        }

        // 3. Construir URL con todos los filtros actuales
        const url = new URL(window.location.href);
        Object.keys(currentFilters).forEach(key => {
            if (currentFilters[key]) {
                url.searchParams.set(key, currentFilters[key]);
            } else {
                url.searchParams.delete(key);
            }
        });

        // 4. Petición AJAX
        fetch(url, {
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        })
            .then(response => response.text())
            .then(html => {
                if (tableContainer) {
                    tableContainer.innerHTML = html;
                    // Al insertar el HTML nuevo, leemos los datos para actualizar el paginador
                    updatePaginationUI();
                }
            })
            .catch(err => console.error("Error cargando usuarios:", err));
    };

    // ---------------------------------------------------------
    // 3. ACTUALIZAR INTERFAZ DE PAGINACIÓN
    // ---------------------------------------------------------
    function updatePaginationUI() {
        // Buscar el div oculto que viene en el HTML parcial
        const meta = document.getElementById('pagination-metadata');
        if (!meta) return;

        // Leer datos del HTML
        const total = parseInt(meta.dataset.total) || 0;
        const start = parseInt(meta.dataset.start) || 0;
        const end = parseInt(meta.dataset.end) || 0;
        const page = parseInt(meta.dataset.page) || 1;
        const hasNext = meta.dataset.hasNext === 'true';
        const hasPrev = meta.dataset.hasPrev === 'true';

        // Sincronizar estado local
        currentFilters.page = page;

        // 1. Actualizar Texto "Mostrando X-Y de Z"
        if (pageInfo) {
            if (total === 0) {
                pageInfo.textContent = "Sin resultados";
            } else {
                pageInfo.textContent = `Mostrando ${start}-${end} de ${total}`;
            }
        }

        // 2. Actualizar número central
        if (pageDisplay) {
            pageDisplay.textContent = page;
        }

        // 3. Estado de botones
        if (btnPrev) btnPrev.disabled = !hasPrev;
        if (btnNext) btnNext.disabled = !hasNext;
    }

    // ---------------------------------------------------------
    // 4. LISTENERS DE PAGINACIÓN
    // ---------------------------------------------------------
    if (btnPrev) {
        btnPrev.addEventListener('click', () => {
            if (!btnPrev.disabled) {
                window.fetchUsers({page: currentFilters.page - 1});
            }
        });
    }

    if (btnNext) {
        btnNext.addEventListener('click', () => {
            if (!btnNext.disabled) {
                window.fetchUsers({page: currentFilters.page + 1});
            }
        });
    }

    // ---------------------------------------------------------
    // 5. BÚSQUEDA RÁPIDA
    // ---------------------------------------------------------
    if (quickSearchInput) {
        quickSearchInput.addEventListener('input', debounce((e) => {
            // Al buscar, reseteamos filtros avanzados y volvemos a pág 1
            window.fetchUsers({
                q: e.target.value,
                page: 1,
                cedula: '', role: '', first_name: '', last_name: '', status: ''
            });
        }, 500));
    }

    // Filtro por Estado (Tarjetas)
    window.filterByStatus = function (status) {
        // Efecto Visual
        const cards = {
            'all': document.getElementById('card-filter-all'),
            'active': document.getElementById('card-filter-active'),
            'inactive': document.getElementById('card-filter-inactive')
        };
        Object.values(cards).forEach(c => {
            if (c) c.classList.add('opacity-low')
        });
        if (cards[status]) cards[status].classList.remove('opacity-low');

        // Lógica: Filtramos y volvemos a página 1
        window.fetchUsers({status: status === 'all' ? '' : status, page: 1});
    };

    function debounce(func, timeout = 300) {
        let timer;
        return (...args) => {
            clearTimeout(timer);
            timer = setTimeout(() => {
                func.apply(this, args);
            }, timeout);
        };
    }

    // ---------------------------------------------------------
    // 6. MODAL BÚSQUEDA AVANZADA (VUE)
    // ---------------------------------------------------------
    const searchMountEl = document.getElementById('advanced-search-app');
    if (searchMountEl) {
        const {createApp, ref} = Vue;

        createApp({
            delimiters: ['[[', ']]'],
            setup() {
                const isVisible = ref(false);
                const open = () => {
                    isVisible.value = true;
                };
                const closeModal = () => {
                    isVisible.value = false;
                };

                const applySearch = () => {
                    const form = document.getElementById('advancedSearchForm');
                    const formData = new FormData(form);

                    // Resetear página y búsqueda rápida al aplicar filtro avanzado
                    const params = {page: 1, q: ''};

                    formData.forEach((value, key) => {
                        params[key] = value;
                    });

                    if (quickSearchInput) quickSearchInput.value = '';

                    window.fetchUsers(params);
                    closeModal();
                };

                const clearFilters = () => {
                    const form = document.getElementById('advancedSearchForm');
                    if (form) form.reset();

                    // Resetear Select2 si existe
                    if (typeof $ !== 'undefined') {
                        $('#id_filter_role').val(null).trigger('change');
                    }

                    window.fetchUsers({reset: true});
                    closeModal();
                };

                window.searchActions = {open};
                return {isVisible, open, closeModal, applySearch, clearFilters};
            }
        }).mount('#advanced-search-app');
    }

    // ---------------------------------------------------------
    // 7. TOGGLE USER STATUS (Activar/Desactivar)
    // ---------------------------------------------------------
    window.toggleUserStatus = function (personId, name, currentStatusIsActive) {
        const action = currentStatusIsActive ? "desactivar" : "activar";

        // Clases CSS para el botón de SweetAlert (sin estilos inline)
        const btnClass = currentStatusIsActive ? 'btn-swal-danger' : 'btn-swal-success';

        Swal.fire({
            title: `¿${action.charAt(0).toUpperCase() + action.slice(1)} acceso?`,
            html: `Estás a punto de <b>${action}</b> el usuario de: <br/><strong>${name}</strong>`,
            icon: 'warning',
            showCancelButton: true,

            // Configuración de estilos limpios
            buttonsStyling: false,
            customClass: {
                confirmButton: `swal2-confirm ${btnClass}`,
                cancelButton: 'swal2-cancel btn-swal-cancel',
                popup: 'swal2-popup'
            },

            confirmButtonText: `Sí, ${action}`,
            cancelButtonText: 'Cancelar'
        }).then((result) => {
            if (result.isConfirmed) {
                performToggleRequest(personId);
            }
        });
    };

    function performToggleRequest(id) {
        const url = `/security/users/toggle/${id}/`;
        const csrfToken = window.getCookie('csrftoken');

        fetch(url, {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrfToken,
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    if (window.Toast) window.Toast.fire({icon: 'success', title: data.message});
                    else Swal.fire('Éxito', data.message, 'success');

                    // Actualizar contadores visuales (Stats)
                    if (data.new_stats) {
                        updateStat('card-filter-all', data.new_stats.total);
                        updateStat('card-filter-active', data.new_stats.active);
                        updateStat('card-filter-inactive', data.new_stats.inactive);
                    }

                    // Recargar tabla manteniendo filtros
                    window.fetchUsers();
                } else {
                    Swal.fire('Error', data.message, 'error');
                }
            })
            .catch(error => {
                console.error(error);
                Swal.fire('Error', 'Error de comunicación con el servidor', 'error');
            });
    }

    // Helper para actualizar el número en las tarjetas
    function updateStat(id, value) {
        const el = document.getElementById(id);
        if (el) {
            const num = el.querySelector('.number');
            if (num) num.textContent = value;
        }
    }

    // =========================================================
    // 8. INICIALIZACIÓN
    // =========================================================
    // Ejecutar esto al cargar la página para leer el estado inicial del paginador
    updatePaginationUI();
});