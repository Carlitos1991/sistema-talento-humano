/* static/js/locations.js */

document.addEventListener('DOMContentLoaded', () => {

    // =========================================================
    // 1. GESTIÓN DE LA TABLA PRINCIPAL
    // =========================================================
    const tableBody = document.getElementById('table-body');
    const searchInput = document.getElementById('table-search');
    const overlay = document.querySelector('.no-results-overlay');
    const searchMsg = document.getElementById('no-results-placeholder');
    const emptyDbMsg = document.querySelector('.empty-db-msg');

    const pageSize = 10;
    let currentPage = 1;
    let allRows = Array.from(document.querySelectorAll('tr.location-row'));
    let filteredRows = allRows;
    let currentSearchTerm = '';

    // Estado global de filtros
    let currentFilters = {
        level: 'all',
        parent_id: null,
        q: '',
        page: 1
    };
    const Toast = Swal.mixin({
        toast: true,
        position: 'top-end',
        showConfirmButton: false,
        timer: 3000,
        timerProgressBar: true,
        didOpen: (toast) => {
            toast.addEventListener('mouseenter', Swal.stopTimer)
            toast.addEventListener('mouseleave', Swal.resumeTimer)
        }
    });

    // Función para iluminar las tarjetas (Stats)
    function updateStatsUI(activeLevel) {
        const cards = {
            '1': document.getElementById('card-filter-1'),
            '2': document.getElementById('card-filter-2'),
            '3': document.getElementById('card-filter-3'),
            '4': document.getElementById('card-filter-4')
        };

        Object.keys(cards).forEach(key => {
            const card = cards[key];
            if (card) {
                // Si el nivel coincide, quitamos la opacidad
                if (String(activeLevel) === String(key)) {
                    card.classList.remove('opacity-low');
                } else {
                    // Si no coincide, lo ponemos tenue
                    card.classList.add('opacity-low');
                }
            }
        });
    }

    // --- FUNCIÓN DE FILTRADO LOCAL (Buscador) ---
    function applyLocalSearch() {
        filteredRows = allRows.filter(row => {
            if (currentSearchTerm && !row.innerText.toLowerCase().includes(currentSearchTerm)) return false;
            return true;
        });
        currentPage = 1;
        renderTable();
    }

    // --- FUNCIÓN DE RENDERIZADO (Paginación) ---
    function renderTable() {
        const totalRows = filteredRows.length;
        const totalPages = Math.ceil(totalRows / pageSize) || 1;

        if (currentPage < 1) currentPage = 1;
        if (currentPage > totalPages) currentPage = totalPages;

        const start = (currentPage - 1) * pageSize;
        const end = start + pageSize;

        allRows.forEach(row => row.style.display = 'none');
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
            const startLabel = totalRows > 0 ? (currentPage - 1) * pageSize + 1 : 0;
            const endLabel = Math.min(currentPage * pageSize, totalRows);
            pageInfo.textContent = `Mostrando ${startLabel}-${endLabel} de ${totalRows}`;
        }
        if (pageDisplay) pageDisplay.textContent = currentPage;

        if (btnPrev) {
            btnPrev.disabled = (currentPage === 1);
            btnPrev.onclick = () => {
                if (currentPage > 1) {
                    currentPage--;
                    renderTable();
                }
            };
        }
        if (btnNext) {
            btnNext.disabled = (currentPage === totalPages);
            btnNext.onclick = () => {
                if (currentPage < totalPages) {
                    currentPage++;
                    renderTable();
                }
            };
        }
    }

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

    // =========================================================
    // 2. LÓGICA DE CARGA BACKEND (AJAX)
    // =========================================================

    async function loadLocations() {
        const params = new URLSearchParams();

        if (currentFilters.parent_id) {
            params.append('parent_id', currentFilters.parent_id);
        } else if (currentFilters.level && currentFilters.level !== 'all') {
            params.append('level', currentFilters.level);
        }

        if (currentFilters.q) params.append('q', currentFilters.q);
        // Siempre pedimos página 1 al backend porque la paginación real la hacemos en frontend (híbrido)
        // o si quisieras paginación backend, aquí iría currentFilters.page

        const url = `/settings/locations/?${params.toString()}`;

        try {
            const response = await fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}});
            if (response.ok) {
                const html = await response.text();
                const wrapper = document.getElementById('table-content-wrapper');
                if (wrapper) {
                    wrapper.innerHTML = html;

                    // REINICIALIZAR FILAS LOCALES
                    allRows = Array.from(document.querySelectorAll('tr.location-row'));
                    filteredRows = allRows;
                    currentPage = 1;
                    renderTable();

                    // ACTUALIZAR CARDS SEGÚN RESPUESTA DEL SERVER
                    const levelIndicator = document.getElementById('server-level-indicator');
                    if (levelIndicator && levelIndicator.value) {
                        updateStatsUI(levelIndicator.value);
                    }
                }
            }
        } catch (error) {
            console.error('Error loading locations:', error);
        }
    }

    // --- FUNCIONES GLOBALES DE FILTRADO ---

    window.filterByParent = function (parentId) {
        currentFilters.level = null;
        currentFilters.parent_id = parentId;
        loadLocations();
    };

    window.filterByLevel = function (level) {
        currentFilters.level = level;
        currentFilters.parent_id = null; // Resetear padre para ver listado completo de ese nivel

        // CORRECCIÓN DEL ERROR AQUÍ: Usamos 'key' consistentemente
        const cards = {
            '1': document.getElementById('card-filter-1'),
            '2': document.getElementById('card-filter-2'),
            '3': document.getElementById('card-filter-3'),
            '4': document.getElementById('card-filter-4')
        };
        Object.keys(cards).forEach(key => {
            const card = cards[key];
            if (card) {
                if (level === 'all' || level === key) { // Ahora 'key' existe
                    card.classList.remove('opacity-low');
                } else {
                    card.classList.add('opacity-low');
                }
            }
        });

        loadLocations();
    };


    // =========================================================
    // 3. MODAL VUE (Crear/Editar)
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
                            this.form = result.data; // {name, level, parent}
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
                            method: 'POST',
                            body: formData,
                            headers: {'X-Requested-With': 'XMLHttpRequest'}
                        });
                        const data = await response.json();
                        if (data.success) {
                            this.closeModal();
                            Swal.fire({
                                icon: 'success',
                                title: '¡Guardado!',
                                text: data.message,
                                showConfirmButton: false,
                                timer: 1500
                            });
                            // Recargar página para asegurar consistencia
                            setTimeout(() => location.reload(), 1500);
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

    // Toggle Status Global (con reload)
    window.toggleLocationStatus = async (btnElement, url, name) => {
        const result = await Swal.fire({
            title: '¿Cambiar estado?',
            text: `Vas a modificar el estado de "${name}"`,
            icon: 'warning',
            showCancelButton: true,
            confirmButtonColor: '#3085d6',
            confirmButtonText: 'Sí, cambiar',
            cancelButtonText: 'Cancelar'
        });

        if (result.isConfirmed) {
            try {
                const formData = new FormData();
                formData.append('csrfmiddlewaretoken', document.querySelector('[name=csrfmiddlewaretoken]').value);

                const response = await fetch(url, {
                    method: 'POST', body: formData, headers: {'X-Requested-With': 'XMLHttpRequest'}
                });
                const data = await response.json();

                if (data.success) {
                    // TOAST DE ÉXITO (AL CAMBIAR ESTADO)
                    Toast.fire({
                        icon: 'success',
                        title: '¡Estado Actualizado!',
                        text: data.message
                    });

                    setTimeout(() => location.reload(), 1500);
                } else {
                    Swal.fire('Error', data.message, 'error');
                }
            } catch (e) {
                console.error(e);
            }
        }
    };

    renderTable();
});