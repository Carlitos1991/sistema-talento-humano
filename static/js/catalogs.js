/* static/js/catalogs.js */

document.addEventListener('DOMContentLoaded', () => {

    // =========================================================
    // 1. GESTIÓN DE LA TABLA (Buscador, Paginación y DOM)
    // =========================================================

    // Referencias globales para la tabla
    const tableBody = document.getElementById('table-body');
    const searchInput = document.getElementById('table-search');
    const overlay = document.querySelector('.no-results-overlay');
    const searchMsg = document.getElementById('no-results-placeholder');
    const emptyDbMsg = document.querySelector('.empty-db-msg');
    // Estado de la tabla
    const pageSize = 10;
    let currentPage = 1;
    let allRows = Array.from(document.querySelectorAll('tr.catalog-row')); // Copia viva de las filas
    let filteredRows = allRows; // Filas filtradas actualmente

    /**
     * Renderiza la tabla (Controla visibilidad y paginación)
     */
    function renderTable() {
        const totalRows = filteredRows.length;
        const totalPages = Math.ceil(totalRows / pageSize) || 1;

        // Validar pagina actual
        if (currentPage < 1) currentPage = 1;
        if (currentPage > totalPages) currentPage = totalPages;

        const start = (currentPage - 1) * pageSize;
        const end = start + pageSize;

        // 1. Ocultar TODAS las filas primero
        allRows.forEach(row => row.style.display = 'none');

        // 2. Lógica de Overlay y Mensajes
        const isSearchActive = searchInput && searchInput.value.trim() !== '';
        const isDatabaseReallyEmpty = allRows.length === 0;

        if (totalRows === 0) {
            // --- ESCENARIO: NO HAY FILAS QUE MOSTRAR ---
            if (overlay) overlay.classList.remove('hidden');

            if (isSearchActive && !isDatabaseReallyEmpty) {
                // Caso A: Hay datos en BD, pero la búsqueda falló -> Mostrar Lupa
                if (emptyDbMsg) emptyDbMsg.classList.add('hidden');
                if (searchMsg) searchMsg.classList.remove('hidden');
            } else {
                // Caso B: La BD está vacía -> Mostrar Inbox
                if (emptyDbMsg) emptyDbMsg.classList.remove('hidden');
                if (searchMsg) searchMsg.classList.add('hidden');
            }

        } else {
            // --- ESCENARIO: HAY FILAS VISIBLES ---
            if (overlay) overlay.classList.add('hidden');

            // Resetear mensajes para la próxima
            if (searchMsg) searchMsg.classList.add('hidden');

            // Mostrar el bloque de filas correspondiente
            filteredRows.slice(start, end).forEach(row => {
                row.style.display = '';
            });
        }

        updatePaginationUI(totalRows, totalPages, start, end);
    }

    function updatePaginationUI(totalRows, totalPages, start, end) {
        const pageInfo = document.getElementById('page-info');
        const pageDisplay = document.getElementById('current-page-display');
        const btnPrev = document.getElementById('btn-prev');
        const btnNext = document.getElementById('btn-next');

        if (pageInfo) {
            const startLabel = totalRows > 0 ? start + 1 : 0;
            pageInfo.textContent = `Mostrando ${startLabel}-${Math.min(end, totalRows)} de ${totalRows}`;
        }
        if (pageDisplay) pageDisplay.textContent = currentPage;

        if (btnPrev) {
            btnPrev.disabled = (currentPage === 1);
            // Clonamos el nodo para limpiar eventos viejos o asignamos onclick directo
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

    /**
     * Filtra la tabla en tiempo real
     */
    function filterTable(query) {
        const term = query.toLowerCase().trim();

        // Volvemos a leer allRows por si se agregó algo nuevo
        allRows = Array.from(document.querySelectorAll('tr.catalog-row'));

        if (!term) {
            filteredRows = allRows;
        } else {
            filteredRows = allRows.filter(row => row.innerText.toLowerCase().includes(term));
        }

        currentPage = 1; // Reset a pag 1
        renderTable();
    }

    // Listener del Buscador
    if (searchInput) {
        let timeout = null;
        searchInput.addEventListener('input', (e) => {
            clearTimeout(timeout);
            timeout = setTimeout(() => filterTable(e.target.value), 100); // 100ms delay
        });
    }

    // =========================================================
    // 2. MANIPULACIÓN DEL DOM (Insertar/Editar filas sin recargar)
    // =========================================================

    /**
     * Construye e inserta una nueva fila al inicio de la tabla
     */
    window.insertNewRow = function (data) {
        if (!tableBody) return;

        // Construir URL dinámicamente para el toggle
        const toggleUrl = `/settings/catalogs/toggle/${data.id}/`;

        const newRowHTML = `
            <tr class="catalog-row" id="row-${data.id}">
                <td><span class="badge-new" style="background:#e0f2fe; color:#0369a1; padding:2px 6px; border-radius:4px; font-size:0.8em;">Nuevo</span></td>
                <td class="catalog-name-cell">${data.name}</td>
                <td>
                    <span id="badge-${data.id}" class="status-badge active">Activo</span>
                </td>
                <td>
                    <div class="actions-wrapper">
                        <button type="button" class="btn-icon btn-create-action" 
                                onclick="openCreateItem(${data.id}, '${data.name}')" title="Agregar Item">
                            <i class="fas fa-plus"></i>
                        </button>
                        <button class="btn-icon btn-list-action" title="Listar Items">
                            <i class="fas fa-list"></i>
                        </button>
                        <button type="button" class="btn-icon btn-views-action"
                                onclick="openEditCatalog(${data.id})" title="Editar">
                            <i class="fas fa-pencil"></i>
                        </button>
                        <button type="button" class="btn-icon"
                                onclick="toggleCatalogStatus(this, '${toggleUrl}', '${data.name}', ${data.id})"
                                title="Desactivar">
                            <i class="fas fa-toggle-on text-success"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `;

        // Insertar al inicio del tbody
        tableBody.insertAdjacentHTML('afterbegin', newRowHTML);

        // Actualizar la lista de filas y re-renderizar
        allRows = Array.from(document.querySelectorAll('tr.catalog-row'));
        filterTable(searchInput ? searchInput.value : '');
    };

    /**
     * Actualiza una fila existente
     */
    window.updateRowDOM = function (id, newName) {
        const row = document.getElementById(`row-${id}`);
        if (row) {
            const nameCell = row.querySelector('.catalog-name-cell');
            if (nameCell) {
                nameCell.textContent = newName;
                // Efecto visual de actualización (parpadeo amarillo suave)
                nameCell.style.transition = 'background-color 0.5s';
                nameCell.style.backgroundColor = '#fef08a';
                setTimeout(() => nameCell.style.backgroundColor = 'transparent', 1000);
            }
        }
    };


    // =========================================================
    // 3. FUNCIONES GLOBALES (Toggle y Stats)
    // =========================================================

    window.updateDashboardStats = function (stats) {
        if (!stats) return;
        const elTotal = document.getElementById('stat-total');
        const elActive = document.getElementById('stat-active');
        const elInactive = document.getElementById('stat-inactive');
        if (elTotal) elTotal.textContent = stats.total;
        if (elActive) elActive.textContent = stats.active;
        if (elInactive) elInactive.textContent = stats.inactive;
    };

    window.toggleCatalogStatus = async (btnElement, url, name, catalogId) => {
        const icon = btnElement.querySelector('i');
        const isCurrentlyActive = icon.classList.contains('fa-toggle-on');
        const actionVerb = isCurrentlyActive ? 'Desactivar' : 'Activar';
        const confirmColor = isCurrentlyActive ? '#dc2626' : '#10b981';

        const result = await Swal.fire({
            title: `¿${actionVerb} catálogo?`,
            text: `Vas a ${actionVerb.toLowerCase()} "${name}".`,
            icon: 'warning',
            showCancelButton: true,
            confirmButtonColor: confirmColor,
            cancelButtonColor: '#64748b',
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
                    // Feedback discreto
                    const Toast = Swal.mixin({
                        toast: true, position: 'top-end', showConfirmButton: false, timer: 3000, timerProgressBar: true
                    });
                    Toast.fire({icon: 'success', title: data.message});

                    if (data.new_stats) window.updateDashboardStats(data.new_stats);

                    // ACTUALIZAR DOM INMEDIATAMENTE
                    const badge = document.getElementById(`badge-${catalogId}`);
                    if (isCurrentlyActive) {
                        icon.className = 'fas fa-toggle-off text-danger';
                        btnElement.title = "Activar";
                        if (badge) {
                            badge.className = 'status-badge inactive';
                            badge.textContent = 'Inactivo';
                        }
                    } else {
                        icon.className = 'fas fa-toggle-on text-success';
                        btnElement.title = "Desactivar";
                        if (badge) {
                            badge.className = 'status-badge active';
                            badge.textContent = 'Activo';
                        }
                    }
                } else {
                    Swal.fire('Error', data.message, 'error');
                }
            } catch (error) {
                console.error(error);
                Swal.fire('Error', 'Error de conexión', 'error');
            }
        }
    };


    // =========================================================
    // 4. MODALES VUE (Crear/Editar Catálogo)
    // =========================================================
    const CATALOG_MOUNT_ID = '#catalog-create-app';

    if (document.querySelector(CATALOG_MOUNT_ID)) {
        const {createApp} = Vue;

        const appCatalog = createApp({
            delimiters: ['[[', ']]'],
            data() {
                return {isVisible: false, isEditing: false, currentId: null, form: {name: '', code: ''}, errors: {}}
            },
            computed: {
                modalTitle() {
                    return this.isEditing ? 'Editar Catálogo' : 'Nuevo Catálogo';
                }
            },
            methods: {
                openCreate() {
                    this.isEditing = false;
                    this.currentId = null;
                    this.form = {name: '', code: ''};
                    this.errors = {};
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
                        const response = await fetch(`/settings/catalogs/detail/${id}/`);
                        const result = await response.json();
                        if (result.success) {
                            this.form = result.data;
                            this.isVisible = true;
                        }
                    } catch (error) {
                        Swal.fire('Error', 'No se cargaron los datos', 'error');
                    }
                },
                async submitCatalog() {
                    this.errors = {};
                    const formData = new FormData();
                    formData.append('name', this.form.name);
                    formData.append('code', this.form.code);
                    formData.append('csrfmiddlewaretoken', document.querySelector('[name=csrfmiddlewaretoken]').value);

                    let url = '/settings/catalogs/create/';
                    if (this.isEditing && this.currentId) url = `/settings/catalogs/update/${this.currentId}/`;

                    try {
                        const response = await fetch(url, {
                            method: 'POST', body: formData, headers: {'X-Requested-With': 'XMLHttpRequest'}
                        });
                        const data = await response.json();

                        if (data.success) {
                            // 1. CERRAR MODAL INMEDIATAMENTE
                            this.closeModal();

                            // 2. MOSTRAR TOAST (No bloqueante)
                            const Toast = Swal.mixin({
                                toast: true,
                                position: 'top-end',
                                showConfirmButton: false,
                                timer: 3000,
                                timerProgressBar: true
                            });
                            Toast.fire({icon: 'success', title: data.message});

                            // 3. ACTUALIZAR STATS
                            if (data.data && data.data.new_stats) window.updateDashboardStats(data.data.new_stats);

                            // 4. ACTUALIZAR TABLA (Sin recargar)
                            if (this.isEditing) {
                                window.updateRowDOM(this.currentId, this.form.name.toUpperCase());
                            } else {
                                // En creación, data.data debe traer {id: 1, name: 'X'}
                                window.insertNewRow(data.data);
                            }
                        } else {
                            this.errors = data.errors;
                        }
                    } catch (e) {
                        console.error(e);
                        Swal.fire('Error', 'Error de servidor', 'error');
                    }
                }
            }
        });
        const vmCatalog = appCatalog.mount(CATALOG_MOUNT_ID);

        // Puentes HTML -> Vue
        const btnNew = document.getElementById('btn-add-catalog');
        if (btnNew) btnNew.addEventListener('click', (e) => {
            e.preventDefault();
            vmCatalog.openCreate();
        });
        window.openEditCatalog = (id) => vmCatalog.loadAndOpenEdit(id);
    }


    // =========================================================
    // 5. MODAL ITEMS (Hijos)
    // =========================================================
    const ITEM_MOUNT_ID = '#item-create-app';
    if (document.querySelector(ITEM_MOUNT_ID)) {
        const {createApp} = Vue;
        const appItem = createApp({
            delimiters: ['[[', ']]'],
            data() {
                return {
                    isVisible: false,
                    parentCatalogId: null,
                    parentCatalogName: '',
                    form: {name: '', code: ''},
                    errors: {}
                }
            },
            computed: {
                modalTitle() {
                    return `Nuevo Item para: ${this.parentCatalogName}`;
                }
            },
            methods: {
                open(catalogId, catalogName) {
                    this.parentCatalogId = catalogId;
                    this.parentCatalogName = catalogName;
                    this.form = {name: '', code: ''};
                    this.errors = {};
                    this.isVisible = true;
                },
                closeModal() {
                    this.isVisible = false;
                },
                async submitItem() {
                    this.errors = {};
                    const formData = new FormData();
                    formData.append('catalog_id', this.parentCatalogId);
                    formData.append('name', this.form.name);
                    formData.append('code', this.form.code);
                    formData.append('csrfmiddlewaretoken', document.querySelector('[name=csrfmiddlewaretoken]').value);

                    try {
                        const response = await fetch('/settings/items/create/', {
                            method: 'POST', body: formData, headers: {'X-Requested-With': 'XMLHttpRequest'}
                        });
                        const data = await response.json();

                        if (data.success) {
                            this.closeModal(); // Cerrar inmediato

                            const Toast = Swal.mixin({
                                toast: true,
                                position: 'top-end',
                                showConfirmButton: false,
                                timer: 3000,
                                timerProgressBar: true
                            });
                            Toast.fire({icon: 'success', title: 'Item creado correctamente'});

                            // Aquí no necesitamos actualizar la tabla principal, ya que los items no se ven en el listado
                        } else {
                            this.errors = data.errors || {};
                            if (data.message && !data.errors) Swal.fire('Error', data.message, 'error');
                        }
                    } catch (e) {
                        Swal.fire('Error', 'Error de conexión', 'error');
                    }
                }
            }
        });
        const vmItem = appItem.mount(ITEM_MOUNT_ID);
        window.openCreateItem = (catalogId, catalogName) => vmItem.open(catalogId, catalogName);
    }

    // Inicializar tabla al cargar la página
    renderTable();
});