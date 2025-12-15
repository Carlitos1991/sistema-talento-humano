/* static/js/locations.js */

document.addEventListener('DOMContentLoaded', () => {

    // =========================================================
    // CONFIGURACIÓN GLOBAL (Toast y Estado)
    // =========================================================
    const Toast = Swal.mixin({
        toast: true, position: 'top-end', showConfirmButton: false,
        timer: 3000, timerProgressBar: true,
        didOpen: (toast) => {
            toast.addEventListener('mouseenter', Swal.stopTimer)
            toast.addEventListener('mouseleave', Swal.resumeTimer)
        }
    });

    // Referencias DOM
    const tableBody = document.getElementById('table-body');
    const searchInput = document.getElementById('table-search');

    // Estado global de filtros (Memoria de la tabla)
    let currentFilters = {
        level: 'all',
        parent_id: null,
        q: '',
        page: 1
    };

    // =========================================================
    // 1. ACTUALIZACIÓN VISUAL (UI)
    // =========================================================

    // A. Actualiza qué tarjeta está "activa/iluminada"
    function updateStatsHighlight(activeLevel) {
        const cards = {
            '1': document.getElementById('card-filter-1'),
            '2': document.getElementById('card-filter-2'),
            '3': document.getElementById('card-filter-3'),
            '4': document.getElementById('card-filter-4')
        };

        Object.keys(cards).forEach(key => {
            const card = cards[key];
            if (card) {
                // Si el nivel coincide (o es 'all'), quitamos opacidad
                if (String(activeLevel) === String(key)) {
                    card.classList.remove('opacity-low');
                } else {
                    card.classList.add('opacity-low');
                }
            }
        });
    }

    // B. Actualiza los NÚMEROS de las tarjetas (Nuevo)
    window.updateDashboardCounters = function (stats) {
        if (!stats) return;
        const elCountry = document.getElementById('stat-country');
        const elProvince = document.getElementById('stat-province');
        const elCity = document.getElementById('stat-city');
        const elParish = document.getElementById('stat-parish');

        // Animación simple o asignación directa
        if (elCountry) elCountry.textContent = stats.country;
        if (elProvince) elProvince.textContent = stats.province;
        if (elCity) elCity.textContent = stats.city;
        if (elParish) elParish.textContent = stats.parish;
    };

    // =========================================================
    // 2. LÓGICA DE CARGA DE DATOS (AJAX)
    // =========================================================

    // Función Maestra: Recarga la tabla manteniendo el contexto actual
    window.loadLocations = async function () {
        const params = new URLSearchParams();

        if (currentFilters.parent_id) {
            params.append('parent_id', currentFilters.parent_id);
        } else if (currentFilters.level && currentFilters.level !== 'all') {
            params.append('level', currentFilters.level);
        }

        if (currentFilters.q) params.append('q', currentFilters.q);
        // Enviamos la página actual para mantener la posición si fuera paginación backend
        // Como es híbrido (backend filtra todo, frontend pagina), pedimos todo el set filtrado.
        // Si usas paginación Django completa, descomenta: params.append('page', currentFilters.page);

        const url = `/settings/locations/?${params.toString()}`;

        try {
            const response = await fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}});
            if (response.ok) {
                const html = await response.text();
                const wrapper = document.getElementById('table-content-wrapper');

                if (wrapper) {
                    wrapper.innerHTML = html;

                    // Reinicializar lógica local de tabla
                    rebindTableLogic();

                    // Leer el nivel que devolvió el backend para iluminar la tarjeta correcta
                    const levelIndicator = document.getElementById('server-level-indicator');
                    if (levelIndicator && levelIndicator.value) {
                        updateStatsHighlight(levelIndicator.value);
                    }
                }
            }
        } catch (error) {
            console.error('Error recargando tabla:', error);
        }
    };

    // --- LÓGICA LOCAL DE TABLA (Paginación JS y Buscador JS) ---
    // Esta función se llama cada vez que el HTML de la tabla cambia
    let allRows = [];
    let filteredRows = [];
    const pageSize = 10;

    function rebindTableLogic() {
        allRows = Array.from(document.querySelectorAll('tr.location-row'));
        filteredRows = allRows;
        // Al recargar datos, volvemos a aplicar el buscador local si había texto
        if (currentSearchTerm) {
            applyLocalSearch();
        } else {
            // Si no hay búsqueda, mostramos la página que estaba (o la 1 si cambió el contexto drásticamente)
            // Para simplificar tras editar, mantenemos página 1, o podrías guardar page en currentFilters
            currentFilters.page = 1;
            renderTable();
        }
    }

    let currentSearchTerm = '';

    function applyLocalSearch() {
        filteredRows = allRows.filter(row => {
            if (currentSearchTerm && !row.innerText.toLowerCase().includes(currentSearchTerm)) return false;
            return true;
        });
        currentFilters.page = 1;
        renderTable();
    }

    function renderTable() {
        const totalRows = filteredRows.length;
        const totalPages = Math.ceil(totalRows / pageSize) || 1;
        let page = currentFilters.page;

        if (page < 1) page = 1;
        if (page > totalPages) page = totalPages;
        currentFilters.page = page;

        const start = (page - 1) * pageSize;
        const end = start + pageSize;

        // Ocultar todo
        allRows.forEach(row => row.style.display = 'none');

        // Mensajes UI
        const overlay = document.querySelector('.no-results-overlay');
        const searchMsg = document.getElementById('no-results-placeholder');
        const emptyDbMsg = document.querySelector('.empty-db-msg');
        const isListEmpty = allRows.length === 0;

        if (totalRows === 0) {
            if (overlay) overlay.classList.remove('hidden');
            if (!isListEmpty) {
                if (emptyDbMsg) emptyDbMsg.classList.add('hidden');
                if (searchMsg) searchMsg.classList.remove('hidden');
            } else {
                if (emptyDbMsg) emptyDbMsg.classList.remove('hidden');
                if (searchMsg) searchMsg.classList.add('hidden');
            }
        } else {
            if (overlay) overlay.classList.add('hidden');
            filteredRows.slice(start, end).forEach(row => row.style.display = '');
        }

        updatePaginationUI(totalRows, totalPages);
    }

    function updatePaginationUI(totalRows, totalPages) {
        const pageInfo = document.getElementById('page-info');
        const pageDisplay = document.getElementById('current-page-display');
        const btnPrev = document.getElementById('btn-prev');
        const btnNext = document.getElementById('btn-next');

        if (pageInfo) {
            const startLabel = totalRows > 0 ? (currentFilters.page - 1) * pageSize + 1 : 0;
            const endLabel = Math.min(currentFilters.page * pageSize, totalRows);
            pageInfo.textContent = `Mostrando ${startLabel}-${endLabel} de ${totalRows}`;
        }
        if (pageDisplay) pageDisplay.textContent = currentFilters.page;

        if (btnPrev) {
            btnPrev.disabled = (currentFilters.page === 1);
            btnPrev.onclick = () => {
                if (currentFilters.page > 1) {
                    currentFilters.page--;
                    renderTable();
                }
            };
        }
        if (btnNext) {
            btnNext.disabled = (currentFilters.page === totalPages);
            btnNext.onclick = () => {
                if (currentFilters.page < totalPages) {
                    currentFilters.page++;
                    renderTable();
                }
            };
        }
    }

    // Buscador Input
    if (searchInput) {
        let timeout;
        searchInput.addEventListener('input', (e) => {
            clearTimeout(timeout);
            timeout = setTimeout(() => {
                currentSearchTerm = e.target.value.toLowerCase().trim();
                applyLocalSearch();
            }, 100);
        });
    }

    // --- ACCIONES DE FILTRO (Stats y Links) ---

    window.filterByParent = function (parentId) {
        currentFilters.level = null;
        currentFilters.parent_id = parentId;
        currentFilters.page = 1;

        // Reset visual de cards (opaco todo)
        const cards = document.querySelectorAll('.stat-card');
        cards.forEach(c => c.classList.add('opacity-low'));

        loadLocations();
    };

    window.filterByLevel = function (level) {
        currentFilters.level = level;
        currentFilters.parent_id = null;
        currentFilters.page = 1;
        updateStatsHighlight(level); // Iluminar tarjeta inmediatamente
        loadLocations();
    };


    // =========================================================
    // 3. MODAL VUE (Crear/Editar) - SIN RELOAD
    // =========================================================
    const LOCATION_MOUNT_ID = '#location-create-app';

    if (document.querySelector(LOCATION_MOUNT_ID)) {
        const {createApp} = Vue;

        const appLocation = createApp({
            delimiters: ['[[', ']]'],
            data() {
                return {
                    isVisible: false, isEditing: false, currentId: null,
                    parentNameDisplay: '',
                    form: {name: '', level: 1, parent: ''},
                    errors: {}
                }
            },
            computed: {
                modalTitle() {
                    if (this.isEditing) return 'Editar Ubicación';
                    if (this.form.level === 1) return `Nuevo PAÍS`;
                    return `Nueva ${this.levelLabel} de ${this.parentNameDisplay}`;
                },
                levelLabel() {
                    const map = {1: 'PAÍS', 2: 'PROVINCIA', 3: 'CIUDAD', 4: 'PARROQUIA'};
                    return map[this.form.level] || 'UBICACIÓN';
                }
            },
            methods: {
                openCreate(parentData = null) {
                    this.isEditing = false;
                    this.currentId = null;
                    this.errors = {};
                    if (parentData) {
                        let nextLevel = parseInt(parentData.level) + 1;
                        if (nextLevel > 4) nextLevel = 4;
                        this.form = {name: '', level: nextLevel, parent: parentData.id};
                        this.parentNameDisplay = parentData.name;
                    } else {
                        this.form = {name: '', level: 1, parent: ''};
                        this.parentNameDisplay = '- Raíz -';
                    }
                    this.isVisible = true;
                },
                closeModal() {
                    this.isVisible = false;
                },
                async loadAndOpenEdit(id) {
                    this.isEditing = true;
                    this.currentId = id;
                    this.errors = {};
                    try {
                        const response = await fetch(`/settings/locations/detail/${id}/`);
                        const result = await response.json();
                        if (result.success) {
                            this.form = result.data;
                            this.parentNameDisplay = result.data.parent_name || 'Sin Padre';
                            this.isVisible = true;
                        }
                    } catch (e) {
                        Swal.fire('Error', 'Error de conexión', 'error');
                    }
                },
                async submitLocation() {
                    this.errors = {};
                    const formData = new FormData();
                    formData.append('name', this.form.name);
                    formData.append('level', this.form.level);
                    if (this.form.parent) formData.append('parent', this.form.parent);
                    formData.append('csrfmiddlewaretoken', document.querySelector('[name=csrfmiddlewaretoken]').value);

                    let url = '/settings/locations/create/';
                    if (this.isEditing) url = `/settings/locations/update/${this.currentId}/`;

                    try {
                        const response = await fetch(url, {
                            method: 'POST', body: formData, headers: {'X-Requested-With': 'XMLHttpRequest'}
                        });
                        const data = await response.json();

                        if (data.success) {
                            this.closeModal();

                            // 1. Mostrar Toast
                            Toast.fire({
                                icon: 'success',
                                title: this.isEditing ? '¡Actualizado!' : '¡Creado!',
                                text: data.message
                            });

                            // 2. Actualizar contadores si vienen en la respuesta
                            if (data.data && data.data.new_stats) {
                                window.updateDashboardCounters(data.data.new_stats);
                            }

                            // 3. Recargar SOLO la tabla (mantiene contexto)
                            window.loadLocations();

                        } else {
                            this.errors = data.errors;
                        }
                    } catch (e) {
                        Swal.fire('Error', 'Error interno', 'error');
                    }
                }
            }
        });

        const vmLocation = appLocation.mount(LOCATION_MOUNT_ID);

        // Puentes Globales
        const btnNew = document.getElementById('btn-add-location');
        if (btnNew) btnNew.addEventListener('click', (e) => {
            e.preventDefault();
            vmLocation.openCreate();
        });

        window.openCreateChildLocation = async (parentId) => {
            try {
                const response = await fetch(`/settings/locations/detail/${parentId}/`);
                const result = await response.json();
                if (result.success) vmLocation.openCreate(result.data);
            } catch (error) {
                Swal.fire('Error', 'Error al validar padre', 'error');
            }
        };

        window.openEditLocation = (id) => vmLocation.loadAndOpenEdit(id);
    }

    // Toggle Status Global (SIN RELOAD)
    window.toggleLocationStatus = async (btnElement, url, name) => {
        const result = await Swal.fire({
            title: '¿Cambiar estado?',
            text: `Vas a modificar el estado de "${name}"`,
            icon: 'warning',
            showCancelButton: true,
            confirmButtonColor: '#3085d6',
            confirmButtonText: 'Sí'
        });

        if (result.isConfirmed) {
            try {
                const formData = new FormData();
                formData.append('csrfmiddlewaretoken', document.querySelector('[name=csrfmiddlewaretoken]').value);
                const response = await fetch(url, {
                    method: 'POST',
                    body: formData,
                    headers: {'X-Requested-With': 'XMLHttpRequest'}
                });
                const data = await response.json();

                if (data.success) {
                    // 1. Toast
                    Toast.fire({icon: 'success', title: '¡Estado Actualizado!', text: data.message});

                    // 2. Stats
                    if (data.new_stats) {
                        window.updateDashboardCounters(data.new_stats);
                    }

                    // 3. Tabla (Mantiene contexto)
                    window.loadLocations();
                } else {
                    Swal.fire('Error', data.message, 'error');
                }
            } catch (e) {
                console.error(e);
            }
        }
    };

    // Carga inicial
    loadLocations();
});