document.addEventListener('DOMContentLoaded', () => {

    // ---------------------------------------------------------
    // 1. LÓGICA DE LA TABLA (AJAX)
    // ---------------------------------------------------------
    const tableContainer = document.getElementById('table-content-wrapper');
    const quickSearchInput = document.getElementById('table-search');

    // Función principal de carga
    window.fetchUsers = function (params = {}) {
        const url = new URL(window.location.href);

        if (params.reset) {
            url.search = '';
        }

        Object.keys(params).forEach(key => {
            if (params[key]) {
                url.searchParams.set(key, params[key]);
            } else {
                url.searchParams.delete(key);
            }
        });

        fetch(url, {
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        })
            .then(response => response.text())
            .then(html => {
                if (tableContainer) {
                    tableContainer.innerHTML = html;
                }
            })
            .catch(err => console.error("Error cargando usuarios:", err));
    };

    // Listener Búsqueda Rápida
    if (quickSearchInput) {
        quickSearchInput.addEventListener('input', debounce((e) => {
            window.fetchUsers({q: e.target.value, cedula: '', role: '', first_name: '', last_name: '', status: ''});
        }, 500));
    }

    // Filtro de Tarjetas (Stats)
    window.filterByStatus = function (status) {
        // Gestión visual de opacidad en tarjetas
        const cards = {
            'all': document.getElementById('card-filter-all'),
            'active': document.getElementById('card-filter-active'),
            'inactive': document.getElementById('card-filter-inactive')
        };

        // Reset visual: poner todas opacas
        Object.values(cards).forEach(c => {
            if (c) c.classList.add('opacity-low')
        });

        // Activar la seleccionada
        if (cards[status]) cards[status].classList.remove('opacity-low');

        // Carga AJAX
        window.fetchUsers({status: status === 'all' ? '' : status});
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
    // 2. LÓGICA DEL MODAL DE BÚSQUEDA (VUE 3)
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
                    const params = {};
                    formData.forEach((value, key) => {
                        params[key] = value;
                    });

                    if (quickSearchInput) quickSearchInput.value = '';
                    params['q'] = '';

                    window.fetchUsers(params);
                    closeModal();
                };

                const clearFilters = () => {
                    const form = document.getElementById('advancedSearchForm');
                    const clearFilters = () => {
                        const form = document.getElementById('advancedSearchForm');
                        if (form) form.reset();

                        // --- CORRECCIÓN AQUÍ ---
                        // Resetear el select del filtro por su nuevo ID
                        if (typeof $ !== 'undefined') {
                            $('#id_filter_role').val(null).trigger('change');
                        }

                        window.fetchUsers({reset: true});
                        closeModal();
                    };
                    if (form) form.reset();
                    // Resetear Select2 si existe (requiere jQuery)
                    if (typeof $ !== 'undefined') $('.select2-filter').val(null).trigger('change');

                    window.fetchUsers({reset: true});
                    closeModal();
                };

                window.searchActions = {open};

                return {isVisible, open, closeModal, applySearch, clearFilters};
            }
        }).mount('#advanced-search-app');
    }

    // ---------------------------------------------------------
    // 3. CAMBIO DE ESTADO
    // ---------------------------------------------------------
    window.toggleUserStatus = function (personId, name, currentStatusIsActive) {
        const action = currentStatusIsActive ? "desactivar" : "activar";

        // Seleccionamos la clase CSS basada en el estado (definida en style.css)
        const btnClass = currentStatusIsActive ? 'btn-swal-danger' : 'btn-swal-success';

        Swal.fire({
            title: `¿${action.charAt(0).toUpperCase() + action.slice(1)} acceso?`,
            html: `Estás a punto de <b>${action}</b> el usuario de: <br/><strong>${name}</strong>`,
            icon: 'warning',
            showCancelButton: true,

            // OPTIMIZACIÓN: Delegamos el estilo al CSS
            buttonsStyling: false, // Desactiva estilos inline de SweetAlert
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
                    // Notificación
                    if (window.Toast) window.Toast.fire({icon: 'success', title: data.message});
                    else Swal.fire('Éxito', data.message, 'success');

                    // Actualizar Stats
                    if (data.new_stats) {
                        updateStat('card-filter-all', data.new_stats.total);
                        updateStat('card-filter-active', data.new_stats.active);
                        updateStat('card-filter-inactive', data.new_stats.inactive);
                    }

                    // Recargar Tabla
                    if (typeof window.fetchUsers === 'function') {
                        const currentSearch = document.getElementById('table-search')?.value || '';
                        window.fetchUsers({q: currentSearch});
                    } else {
                        location.reload();
                    }

                } else {
                    Swal.fire('Error', data.message, 'error');
                }
            })
            .catch(error => {
                console.error(error);
                Swal.fire('Error', 'Error de comunicación con el servidor', 'error');
            });
    }

    function updateStat(id, value) {
        const el = document.getElementById(id);
        if (el) {
            const num = el.querySelector('.number');
            if (num) num.textContent = value;
        }
    }
});