document.addEventListener('DOMContentLoaded', function () {

    // --- REFERENCIAS ---
    const tableContainer = document.getElementById('table-content-wrapper');
    const searchInput = document.getElementById('table-search');
    const btnAdd = document.getElementById('btn-add-type');
    const csrfToken = document.getElementById('csrf-token').value;
    const urlList = document.getElementById('url-list').value;

    // Referencias Modal
    const modalOverlay = document.getElementById('customModal');
    const modalContentContainer = document.getElementById('modal-dynamic-content');

    // Referencias de paginación
    const pageInfo = document.getElementById('page-info');
    const btnPrev = document.getElementById('btn-prev');
    const btnNext = document.getElementById('btn-next');
    const currentPageDisplay = document.getElementById('current-page-display');

    // Estado de paginación
    let currentPage = 1;
    let totalPages = 1;

    // =========================================================
    // MODAL VUE: LISTAR SUB-TIPOS (INICIALIZAR PRIMERO)
    // =========================================================
    const SUBTYPE_LIST_MOUNT = '#subtype-list-app';

    if (document.querySelector(SUBTYPE_LIST_MOUNT)) {
        const {createApp} = Vue;
        const appSubtypes = createApp({
            delimiters: ['[[', ']]'],
            data() {
                return {
                    isVisible: false,
                    parentId: null,
                    parentName: '',
                    items: [],
                    searchQuery: '',
                    currentPage: 1,
                    pageSize: 5,
                    csrfToken: csrfToken // Usar el token del scope padre
                }
            },
            computed: {
                filteredItems() {
                    const term = this.searchQuery.toLowerCase().trim();
                    if (!term) return this.items;
                    return this.items.filter(item =>
                        item.name.toLowerCase().includes(term)
                    );
                },
                totalPages() {
                    return Math.ceil(this.filteredItems.length / this.pageSize) || 1;
                },
                paginatedItems() {
                    const start = (this.currentPage - 1) * this.pageSize;
                    const end = start + this.pageSize;
                    return this.filteredItems.slice(start, end);
                },
                startIndex() {
                    return this.filteredItems.length === 0 ? 0 : (this.currentPage - 1) * this.pageSize + 1;
                },
                endIndex() {
                    return Math.min(this.currentPage * this.pageSize, this.filteredItems.length);
                }
            },
            methods: {
                async open(parentId) {
                    this.parentId = parentId;
                    this.searchQuery = '';
                    this.currentPage = 1;
                    await this.fetchSubtypes();
                    this.isVisible = true;
                },
                closeModal() {
                    this.isVisible = false;
                    this.items = [];
                },
                async fetchSubtypes() {
                    if (!this.parentId) return;
                    try {
                        const url = `/permitrequest/types/${this.parentId}/subitems/`;
                        const res = await fetch(url);
                        
                        if (!res.ok) {
                            throw new Error(`HTTP error! status: ${res.status}`);
                        }
                        
                        const data = await res.json();
                        if (data.success) {
                            this.parentName = data.parent_name;
                            this.items = data.items;
                        } else {
                            Swal.fire('Error', data.message || 'No se pudieron cargar los sub-tipos', 'error');
                        }
                    } catch (e) {
                        console.error('Error al cargar sub-tipos:', e);
                        Swal.fire('Error', 'No se pudieron cargar los sub-tipos. Verifique sus permisos.', 'error');
                    }
                },
                openCreateSubtype() {
                    if (this.parentId && window.openPermissionModal) {
                        window.openPermissionModal(`/permitrequest/types/create/?parent=${this.parentId}`);
                        this.closeModal();
                    }
                },
                editSubtype(subtypeId) {
                    if (window.openPermissionModal) {
                        window.openPermissionModal(`/permitrequest/types/update/${subtypeId}/`);
                        this.closeModal();
                    }
                },
                async toggleStatus(subtypeId) {
                    const result = await Swal.fire({
                        title: '¿Cambiar estado?',
                        text: 'Se alternará entre activo e inactivo',
                        icon: 'question',
                        showCancelButton: true,
                        confirmButtonText: 'Sí, cambiar',
                        cancelButtonText: 'Cancelar'
                    });

                    if (result.isConfirmed) {
                        try {
                            const url = `/permitrequest/types/toggle/${subtypeId}/`;
                            const res = await fetch(url, {
                                method: 'POST',
                                headers: {
                                    'X-Requested-With': 'XMLHttpRequest',
                                    'X-CSRFToken': this.csrfToken
                                }
                            });
                            const data = await res.json();
                            if (data.success) {
                                Swal.fire({
                                    icon: 'success',
                                    title: 'Éxito',
                                    text: data.message,
                                    timer: 2000,
                                    showConfirmButton: false
                                });
                                await this.fetchSubtypes();
                                if (window.fetchPermissionTableData) {
                                    window.fetchPermissionTableData('/permitrequest/types/');
                                }
                            }
                        } catch (e) {
                            console.error(e);
                            Swal.fire('Error', 'No se pudo cambiar el estado', 'error');
                        }
                    }
                }
            }
        });

        window.vmSubtypeList = appSubtypes.mount(SUBTYPE_LIST_MOUNT);
    }

    // --- EVENTOS ---

    // 1. Buscador
    let timeout = null;
    if (searchInput) {
        searchInput.addEventListener('keyup', (e) => {
            clearTimeout(timeout);
            timeout = setTimeout(() => {
                currentPage = 1; // Reset a página 1 al buscar
                fetchTableData(urlList + `?q=${e.target.value}&page=1`);
            }, 300);
        });
    }

    // 2. Abrir Modal (Botón Principal)
    if (btnAdd) {
        btnAdd.addEventListener('click', function () {
            openModal(this.dataset.url);
        });
    }

    // 3. Botones de paginación
    if (btnPrev) {
        btnPrev.addEventListener('click', () => {
            if (currentPage > 1) {
                const searchQuery = searchInput ? searchInput.value : '';
                const url = urlList + `?page=${currentPage - 1}${searchQuery ? '&q=' + searchQuery : ''}`;
                fetchTableData(url);
            }
        });
    }

    if (btnNext) {
        btnNext.addEventListener('click', () => {
            if (currentPage < totalPages) {
                const searchQuery = searchInput ? searchInput.value : '';
                const url = urlList + `?page=${currentPage + 1}${searchQuery ? '&q=' + searchQuery : ''}`;
                fetchTableData(url);
            }
        });
    }

    // 4. Cargar tabla inicial con paginación
    fetchTableData(urlList + '?page=1');

    // 5. Cerrar Modal desde overlay o botón cerrar
    if (modalOverlay) {
        modalOverlay.addEventListener('click', (e) => {
            if (e.target === modalOverlay || e.target.closest('.btn-close-modal') || e.target.closest('.js-close-modal')) {
                closeModal();
            }
        });
    }

    // 6. DELEGACIÓN DE ACCIONES EN LA TABLA (CRÍTICO)
    if (tableContainer) {
        tableContainer.addEventListener('click', function (e) {

            // A. EDITAR y CREAR SUB-ITEM (Abren el mismo modal)
            const modalBtn = e.target.closest('.js-edit') || e.target.closest('.js-add-sub');
            if (modalBtn) {
                e.preventDefault();
                openModal(modalBtn.dataset.url);
                return;
            }

            // B. TOGGLE STATUS (Baja/Alta)
            const toggleBtn = e.target.closest('.js-toggle');
            if (toggleBtn) {
                e.preventDefault();
                toggleStatus(toggleBtn.dataset.url);
                return;
            }

            // C. VER SUB-ITEMS EN MODAL (Nuevo)
            const viewSubsModalBtn = e.target.closest('.js-view-subs-modal');
            if (viewSubsModalBtn) {
                e.preventDefault();
                const parentId = viewSubsModalBtn.dataset.parentId;
                
                if (window.vmSubtypeList && parentId) {
                    window.vmSubtypeList.open(parentId);
                } else if (!window.vmSubtypeList) {
                    console.error('window.vmSubtypeList no está definido');
                } else if (!parentId) {
                    console.error('parentId no está definido');
                }
                return;
            }

            // D. VER SUB-ITEMS (Recarga tabla con filtro) - Para navegación desde header
            const viewSubsBtn = e.target.closest('.js-view-subs') || e.target.closest('.js-load-parent');
            if (viewSubsBtn) {
                e.preventDefault();
                fetchTableData(viewSubsBtn.dataset.url);
                return;
            }
        });
    }

    // --- FUNCIONES ---

    function openModal(url) {
        fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
            .then(res => res.text())
            .then(html => {
                modalContentContainer.innerHTML = html;
                modalOverlay.classList.remove('hidden');

                initModalPlugins();

                const form = modalContentContainer.querySelector('form');
                if (form) form.addEventListener('submit', handleFormSubmit);
            })
            .catch(err => {
                console.error('Error al abrir modal:', err);
                Swal.fire('Error', 'No se pudo cargar el formulario', 'error');
            });
    }

    // Hacer openModal global para que Vue pueda accederlo
    window.openPermissionModal = openModal;

    function closeModal() {
        modalOverlay.classList.add('hidden');
        modalContentContainer.innerHTML = '';
    }

    function initModalPlugins() {
        if (typeof $ !== 'undefined' && $.fn.select2) {
            $('.select2').select2({
                width: '100%',
                dropdownParent: modalOverlay
            });
        }
    }

    function handleFormSubmit(e) {
        e.preventDefault();
        const form = e.target;
        const formData = new FormData(form);

        // Limpiar errores previos
        form.querySelectorAll('.is-invalid').forEach(el => el.classList.remove('is-invalid'));
        form.querySelectorAll('.invalid-feedback').forEach(el => el.textContent = '');

        fetch(form.action, {
            method: 'POST',
            body: formData,
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        })
            .then(async res => {
                // Verificar si la respuesta es JSON
                const contentType = res.headers.get('content-type');
                if (!contentType || !contentType.includes('application/json')) {
                    throw new Error('Respuesta no válida del servidor');
                }
                
                const data = await res.json();
                
                if (res.ok) {
                    closeModal();
                    Swal.fire({
                        icon: 'success',
                        title: 'Guardado',
                        text: data.message || 'Operación exitosa',
                        timer: 2000,
                        showConfirmButton: false
                    });
                    // Recargar en la página actual
                    const searchQuery = searchInput ? searchInput.value : '';
                    fetchTableData(urlList + `?page=${currentPage}${searchQuery ? '&q=' + searchQuery : ''}`);
                } else {
                    // Manejar errores HTTP
                    if (res.status === 403) {
                        Swal.fire('Acceso denegado', data.message || 'No tiene permisos para realizar esta acción', 'error');
                    } else if (data.errors) {
                        showErrors(form, data.errors);
                    } else {
                        Swal.fire('Error', data.message || 'Ocurrió un error al guardar', 'error');
                    }
                }
            })
            .catch(err => {
                console.error(err);
                Swal.fire('Error', 'Error de comunicación con el servidor', 'error');
            });
    }

    function toggleStatus(url) {
        Swal.fire({
            title: '¿Cambiar estado?',
            text: 'Se alternará entre activo e inactivo',
            icon: 'question',
            showCancelButton: true,
            confirmButtonText: 'Sí, cambiar',
            cancelButtonText: 'Cancelar',
            confirmButtonColor: '#3085d6',
            cancelButtonColor: '#d33'
        }).then((result) => {
            if (result.isConfirmed) {
                fetch(url, {
                    method: 'POST',
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest',
                        'X-CSRFToken': csrfToken
                    }
                })
                    .then(res => res.json())
                    .then(data => {
                        if (data.success) {
                            const Toast = Swal.mixin({
                                toast: true, position: 'top-end', showConfirmButton: false, timer: 3000
                            });
                            Toast.fire({icon: 'success', title: data.message});
                            // Recargar en la página actual
                            const searchQuery = searchInput ? searchInput.value : '';
                            fetchTableData(urlList + `?page=${currentPage}${searchQuery ? '&q=' + searchQuery : ''}`);
                        }
                    })
                    .catch(err => {
                        console.error(err);
                        Swal.fire('Error', 'No se pudo cambiar el estado', 'error');
                    });
            }
        });
    }

    function fetchTableData(url) {
        fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
            .then(res => res.json())
            .then(data => {
                tableContainer.innerHTML = data.html;
                
                // Actualizar información de paginación
                if (data.pagination) {
                    updatePagination(data.pagination);
                }
            })
            .catch(err => {
                console.error('Error al cargar datos:', err);
            });
    }

    // Hacer fetchTableData global para que Vue pueda accederlo
    window.fetchPermissionTableData = fetchTableData;

    function updatePagination(paginationData) {
        currentPage = paginationData.current_page;
        totalPages = paginationData.total_pages;

        // Actualizar texto de información
        if (pageInfo) {
            pageInfo.textContent = `Mostrando ${paginationData.start_index} a ${paginationData.end_index} registros de ${paginationData.total_count} registros`;
        }

        // Actualizar página actual
        if (currentPageDisplay) {
            currentPageDisplay.textContent = currentPage;
        }

        // Habilitar/deshabilitar botones
        if (btnPrev) {
            btnPrev.disabled = !paginationData.has_previous;
        }
        if (btnNext) {
            btnNext.disabled = !paginationData.has_next;
        }
    }

    function showErrors(form, errors) {
        for (const [field, msgs] of Object.entries(errors)) {
            const input = form.querySelector(`[name="${field}"]`);
            if (input) {
                input.classList.add('is-invalid');
                const feedback = input.parentNode.querySelector('.invalid-feedback');
                if (feedback) feedback.textContent = Array.isArray(msgs) ? msgs.join(', ') : msgs;
            }
        }
    }
});
