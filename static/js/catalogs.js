/* static/js/catalogs.js */

document.addEventListener('DOMContentLoaded', () => {

    // =========================================================
    // 1. GESTIÓN DE LA TABLA PRINCIPAL (Buscador, Paginación y DOM)
    // =========================================================
    const tableBody = document.getElementById('table-body');
    const searchInput = document.getElementById('table-search');
    const overlay = document.querySelector('.no-results-overlay');
    const searchMsg = document.getElementById('no-results-placeholder');
    const emptyDbMsg = document.querySelector('.empty-db-msg');

    const pageSize = 10;
    let currentPage = 1;
    let allRows = Array.from(document.querySelectorAll('tr.catalog-row'));
    let filteredRows = allRows;
    let currentSearchTerm = '';
    let currentStatusFilter = 'all';

    function applyFilters() {
        allRows = Array.from(document.querySelectorAll('tr.catalog-row'));
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
        const isDatabaseReallyEmpty = allRows.length === 0;

        if (totalRows === 0) {
            if (overlay) overlay.classList.remove('hidden');
            if (!isDatabaseReallyEmpty) {
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

    // --- Definición de updatePaginationUI ---
    function updatePaginationUI(totalRows, totalPages) {
        const pageInfo = document.getElementById('page-info');
        const currentPageDisplay = document.getElementById('current-page-display');
        const btnPrev = document.getElementById('btn-prev');
        const btnNext = document.getElementById('btn-next');

        if (pageInfo) {
            const start = totalRows === 0 ? 0 : (currentPage - 1) * pageSize + 1;
            const end = Math.min(currentPage * pageSize, totalRows);
            pageInfo.innerText = `Mostrando ${start} a ${end} registros de ${totalRows} registros`;
        }
        if (currentPageDisplay) {
            currentPageDisplay.innerText = currentPage;
        }

        // Habilitar / Deshabilitar botones
        if (btnPrev) btnPrev.disabled = (currentPage === 1);
        if (btnNext) btnNext.disabled = (currentPage === totalPages || totalPages === 0);
    }

    // --- Definición de filterByStatus ---
    window.filterByStatus = function(status) {
        currentStatusFilter = status;

        // Actualizar UI de tarjetas
        const cards = {
            'all': document.getElementById('card-filter-all'),
            'true': document.getElementById('card-filter-active'),
            'false': document.getElementById('card-filter-inactive')
        };
        
        // Reset opacity
        Object.values(cards).forEach(card => {
            if (card) {
                card.style.opacity = '0.4';
                card.classList.remove('active-card'); // opcional si usas clase
            }
        });

        const activeCard = cards[status];
        if (activeCard) {
            activeCard.style.opacity = '1';
        }

        applyFilters();
    };

    // Event Listeners para Paginación y Búsqueda
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

    if (btnNext) {
        btnNext.addEventListener('click', () => {
            const totalRows = filteredRows.length;
            const totalPages = Math.ceil(totalRows / pageSize) || 1;
            if (currentPage < totalPages) {
                currentPage++;
                renderTable();
            }
        });
    }

    // =========================================================
    // 2. DOM MANIPULATION (Insertar / Actualizar)
    // =========================================================
    window.insertNewRow = function (data) {
        if (!tableBody) return;
        const toggleUrl = `/settings/catalogs/toggle/${data.id}/`;

        // Se inserta con la clase 'btn-delete-action' (Rojo/Activo) por defecto para nuevos items
        const newRowHTML = `
            <tr class="catalog-row" id="row-${data.id}" data-status="true">
                <td><span class="badge-new" style="background:#e0f2fe; color:#0369a1; padding:2px 6px; border-radius:4px; font-size:0.8em;">Nuevo</span></td>
                <td class="catalog-name-cell">${data.name}</td>
                <td><span id="badge-${data.id}" class="status-badge active">Activo</span></td>
                <td>
                    <div class="actions-wrapper">
                        <button type="button" class="btn-icon btn-create-action" 
                                onclick="openCreateItem(${data.id}, '${data.name}')" title="Agregar Item">
                            <i class="fas fa-plus"></i>
                        </button>
                        <button class="btn-icon btn-list-action" title="Listar Items"
                                onclick="openListItems(${data.id}, '${data.name}')">
                            <i class="fas fa-list"></i>
                        </button>
                        <button type="button" class="btn-icon btn-views-action"
                                onclick="openEditCatalog(${data.id})" title="Editar">
                            <i class="fas fa-pencil"></i>
                        </button>
                        
                        <button type="button" class="btn-icon btn-delete-action"
                                onclick="toggleCatalogStatus(this, '${toggleUrl}', '${data.name}', ${data.id})"
                                title="Desactivar">
                            <i class="fas fa-power-off"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `;
        tableBody.insertAdjacentHTML('afterbegin', newRowHTML);
        applyFilters();
    };

    window.updateRowDOM = function (id, newName) {
        const row = document.getElementById(`row-${id}`);
        if (row) {
            const nameCell = row.querySelector('.catalog-name-cell');
            if (nameCell) nameCell.textContent = newName;
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
        // 1. Identificar elementos
        const icon = btnElement.querySelector('i');

        // 2. Detectar estado ACTUAL visualmente
        // Si tiene la clase 'btn-delete-action' (Rojo), es que actualmente está ACTIVO.
        const isCurrentlyActive = btnElement.classList.contains('btn-delete-action');

        // 3. Configurar textos y colores para la ALERTA
        const actionVerb = isCurrentlyActive ? 'Desactivar' : 'Activar';
        // Usamos las clases CSS para la alerta, no colores HEX
        const btnSwalClass = isCurrentlyActive ? 'btn-swal-danger' : 'btn-swal-success';

        const result = await Swal.fire({
            title: `¿${actionVerb} catálogo?`,
            text: `Vas a ${actionVerb.toLowerCase()} "${name}".`,
            icon: 'warning',
            showCancelButton: true,

            // Estilos CSS para SweetAlert
            buttonsStyling: false,
            customClass: {
                confirmButton: `swal2-confirm ${btnSwalClass}`,
                cancelButton: 'swal2-cancel btn-swal-cancel',
                popup: 'swal2-popup'
            },

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
                    // Notificación Toast
                    const Toast = Swal.mixin({
                        toast: true, position: 'top-end', showConfirmButton: false, timer: 3000, timerProgressBar: true
                    });
                    Toast.fire({icon: 'success', title: data.message});

                    // Actualizar Stats Dashboard
                    if (data.new_stats) window.updateDashboardStats(data.new_stats);

                    // Referencias a la fila y badge
                    const row = document.getElementById(`row-${catalogId}`);
                    const badge = document.getElementById(`badge-${catalogId}`);

                    // =====================================================
                    // INTERCAMBIO DE CLASES (ROJO <-> VERDE)
                    // =====================================================
                    if (isCurrentlyActive) {
                        // CASO: Estaba ACTIVO (Rojo), pasó a INACTIVO.
                        // El botón debe volverse VERDE (listo para activar).

                        btnElement.classList.remove('btn-delete-action'); // Quitar Rojo
                        btnElement.classList.add('btn-create-action');    // Poner Verde

                        // Cambiar icono a "Switch On" (indicando que se puede encender)
                        icon.className = 'fas fa-toggle-on';
                        btnElement.title = "Activar";

                        // Actualizar Badge de la tabla
                        if (badge) {
                            badge.className = 'status-badge inactive';
                            badge.textContent = 'Inactivo';
                        }
                        // Actualizar atributo de datos para filtros
                        if (row) row.dataset.status = "false";

                    } else {
                        // CASO: Estaba INACTIVO (Verde), pasó a ACTIVO.
                        // El botón debe volverse ROJO (listo para desactivar).

                        btnElement.classList.remove('btn-create-action'); // Quitar Verde
                        btnElement.classList.add('btn-delete-action');    // Poner Rojo

                        // Cambiar icono a "Power Off" (indicando apagar)
                        icon.className = 'fas fa-power-off';
                        btnElement.title = "Desactivar";

                        if (badge) {
                            badge.className = 'status-badge active';
                            badge.textContent = 'Activo';
                        }
                        if (row) row.dataset.status = "true";
                    }

                    // Reaplicar filtros por si el usuario está filtrando por estado
                    applyFilters();

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
                        Swal.fire('Error', 'Error al cargar datos', 'error');
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
                            this.closeModal();
                            const Toast = Swal.mixin({
                                toast: true,
                                position: 'top-end',
                                showConfirmButton: false,
                                timer: 3000,
                                timerProgressBar: true
                            });
                            Toast.fire({icon: 'success', title: data.message});
                            if (data.data && data.data.new_stats) window.updateDashboardStats(data.data.new_stats);
                            if (this.isEditing) {
                                window.updateRowDOM(this.currentId, this.form.name.toUpperCase());
                            } else {
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
        const btnNew = document.getElementById('btn-add-catalog');
        if (btnNew) btnNew.addEventListener('click', (e) => {
            e.preventDefault();
            vmCatalog.openCreate();
        });
        window.openEditCatalog = (id) => vmCatalog.loadAndOpenEdit(id);
    }


    // =========================================================
    // 5. APP VUE: LISTAR ITEMS (CON BUSCADOR Y PAGINACIÓN)
    // =========================================================
    const ITEM_LIST_MOUNT = '#item-list-app';
    let vmItemList = null;

    if (document.querySelector(ITEM_LIST_MOUNT)) {
        const {createApp} = Vue;
        const appList = createApp({
            delimiters: ['[[', ']]'],
            data() {
                return {
                    isVisible: false,
                    catalogId: null,
                    catalogName: '',
                    items: [],

                    // --- Estado para Paginación y Búsqueda ---
                    searchQuery: '',
                    currentPage: 1,
                    pageSize: 5 // Cantidad de items por página en el modal
                }
            },
            computed: {
                // Filtra items por búsqueda
                filteredItems() {
                    const term = this.searchQuery.toLowerCase().trim();
                    if (!term) return this.items;
                    return this.items.filter(item =>
                        item.name.toLowerCase().includes(term) ||
                        item.code.toLowerCase().includes(term)
                    );
                },
                // Calcula total páginas
                totalPages() {
                    return Math.ceil(this.filteredItems.length / this.pageSize) || 1;
                },
                // Obtiene el slice actual
                paginatedItems() {
                    const start = (this.currentPage - 1) * this.pageSize;
                    const end = start + this.pageSize;
                    return this.filteredItems.slice(start, end);
                },
                // Etiqueta "Mostrando X-Y de Z"
                paginationLabel() {
                    const total = this.filteredItems.length;
                    if (total === 0) return '0 de 0';
                    const start = (this.currentPage - 1) * this.pageSize + 1;
                    const end = Math.min(this.currentPage * this.pageSize, total);
                    return `Mostrando ${start}-${end} de ${total}`;
                }
            },
            methods: {
                async open(id, name) {
                    this.catalogId = id;
                    this.catalogName = name;
                    this.searchQuery = ''; // Resetear búsqueda
                    this.currentPage = 1;  // Resetear página
                    this.isVisible = true;
                    await this.fetchItems();
                },
                closeModal() {
                    this.isVisible = false;
                    this.items = [];
                },
                async fetchItems() {
                    if (!this.catalogId) return;
                    try {
                        const res = await fetch(`/settings/items/list/${this.catalogId}/`);
                        const data = await res.json();
                        if (data.success) {
                            this.items = data.data;
                        }
                    } catch (e) {
                        console.error(e);
                    }
                },
                // --- Paginación ---
                prevPage() {
                    if (this.currentPage > 1) this.currentPage--;
                },
                nextPage() {
                    if (this.currentPage < this.totalPages) this.currentPage++;
                },
                // --- Acciones ---
                openCreateFromList() {
                    if (window.vmItemForm) {
                        window.vmItemForm.openCreate(this.catalogId, this.catalogName, true);
                    }
                },
                editItem(itemId) {
                    if (window.vmItemForm) {
                        window.vmItemForm.openEdit(itemId, true);
                    }
                },
                async toggleItem(item) {
                    try {
                        const formData = new FormData();
                        formData.append('csrfmiddlewaretoken', document.querySelector('[name=csrfmiddlewaretoken]').value);
                        const res = await fetch(`/settings/items/toggle/${item.id}/`, {
                            method: 'POST', body: formData, headers: {'X-Requested-With': 'XMLHttpRequest'}
                        });
                        const data = await res.json();
                        if (data.success) {
                            item.is_active = data.is_active;
                            const Toast = Swal.mixin({
                                toast: true, position: 'top-end', showConfirmButton: false, timer: 2000
                            });
                            Toast.fire({icon: 'success', title: data.message});
                        }
                    } catch (e) {
                        console.error(e);
                    }
                }
            }
        });
        vmItemList = appList.mount(ITEM_LIST_MOUNT);
        window.openListItems = (id, name) => {
            vmItemList.open(id, name);
        };
    }


    // =========================================================
    // 6. APP VUE: FORMULARIO ITEM (CREAR / EDITAR)
    // =========================================================
    const ITEM_FORM_MOUNT = '#item-create-app';

    if (document.querySelector(ITEM_FORM_MOUNT)) {
        const {createApp} = Vue;
        const appItemForm = createApp({
            delimiters: ['[[', ']]'],
            data() {
                return {
                    isVisible: false, isEditing: false, isFromList: false,
                    parentCatalogId: null, parentCatalogName: '', currentId: null,
                    form: {name: '', code: ''}, errors: {}
                }
            },
            computed: {
                modalTitle() {
                    return this.isEditing ? 'Editar Item' : `Nuevo Item para: ${this.parentCatalogName}`;
                }
            },
            methods: {
                openCreate(catalogId, catalogName, fromList = false) {
                    this.isEditing = false;
                    this.currentId = null;
                    this.parentCatalogId = catalogId;
                    this.parentCatalogName = catalogName;
                    this.isFromList = fromList;
                    this.form = {name: '', code: ''};
                    this.errors = {};
                    this.isVisible = true;
                },
                async openEdit(itemId, fromList = false) {
                    this.isEditing = true;
                    this.currentId = itemId;
                    this.isFromList = fromList;
                    this.errors = {};
                    try {
                        const res = await fetch(`/settings/items/detail/${itemId}/`);
                        const result = await res.json();
                        if (result.success) {
                            this.form = result.data;
                            this.parentCatalogId = result.data.catalog_id;
                            this.isVisible = true;
                        }
                    } catch (e) {
                        Swal.fire('Error', 'No se pudieron cargar datos', 'error');
                    }
                },
                closeModal() {
                    this.isVisible = false;
                },
                async submitItem() {
                    this.errors = {};
                    const formData = new FormData();
                    if (!this.isEditing) formData.append('catalog_id', this.parentCatalogId);
                    formData.append('name', this.form.name);
                    formData.append('code', this.form.code);
                    formData.append('csrfmiddlewaretoken', document.querySelector('[name=csrfmiddlewaretoken]').value);

                    let url = '/settings/items/create/';
                    if (this.isEditing) url = `/settings/items/update/${this.currentId}/`;

                    try {
                        const response = await fetch(url, {
                            method: 'POST', body: formData, headers: {'X-Requested-With': 'XMLHttpRequest'}
                        });
                        const data = await response.json();

                        if (data.success) {
                            this.closeModal();
                            const Toast = Swal.mixin({
                                toast: true, position: 'top-end', showConfirmButton: false, timer: 3000
                            });
                            Toast.fire({icon: 'success', title: this.isEditing ? 'Item Actualizado' : 'Item Creado'});

                            if (this.isFromList && vmItemList) {
                                vmItemList.catalogId = this.parentCatalogId;
                                await vmItemList.fetchItems();
                            }
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
        window.vmItemForm = appItemForm.mount(ITEM_FORM_MOUNT);
        window.openCreateItem = (catalogId, catalogName) => {
            window.vmItemForm.openCreate(catalogId, catalogName, false);
        };
    }

    // Inicializar tabla y filtros
    window.filterByStatus('all');
    renderTable();
});