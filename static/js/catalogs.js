/* static/js/catalogs.js */

// ==========================================
// 1. FUNCIONES GLOBALES (Accesibles desde HTML)
// ==========================================

/**
 * Cambia el estado (Activo/Inactivo) usando SweetAlert y AJAX
 */
window.toggleCatalogStatus = async (id, name, isActive) => {
    const actionVerb = isActive ? 'Desactivar' : 'Activar';
    const confirmColor = isActive ? '#dc2626' : '#10b981'; // Rojo o Verde

    // 1. Confirmación con SweetAlert2
    const result = await Swal.fire({
        title: `¿${actionVerb} catálogo?`,
        text: `Vas a ${actionVerb.toLowerCase()} el catálogo "${name}".`,
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: confirmColor,
        cancelButtonColor: '#64748b',
        confirmButtonText: `Sí, ${actionVerb.toLowerCase()}`,
        cancelButtonText: 'Cancelar'
    });

    if (result.isConfirmed) {
        try {
            // Preparar datos para el POST
            const formData = new FormData();
            const token = document.querySelector('[name=csrfmiddlewaretoken]').value;
            formData.append('csrfmiddlewaretoken', token);

            // 2. Petición AJAX
            const response = await fetch(`/settings/catalogs/toggle/${id}/`, {
                method: 'POST',
                body: formData,
                headers: {'X-Requested-With': 'XMLHttpRequest'}
            });

            const data = await response.json();

            if (data.success) {
                // Notificación de éxito
                Swal.fire({
                    icon: 'success',
                    title: '¡Actualizado!',
                    text: data.message,
                    timer: 1500,
                    showConfirmButton: false
                });

                // Recargar la página para reflejar los cambios
                setTimeout(() => location.reload(), 1500);
            } else {
                Swal.fire('Error', data.message || 'No se pudo cambiar el estado', 'error');
            }
        } catch (error) {
            console.error(error);
            Swal.fire('Error', 'Ocurrió un error de conexión', 'error');
        }
    }
};


// ==========================================
// 2. INICIALIZACIÓN DEL DOM
// ==========================================
document.addEventListener('DOMContentLoaded', () => {

    // ---------------------------------------------------------
    // A. APP VUE PARA EL MODAL (Crear / Editar)
    // ---------------------------------------------------------
    const MOUNT_ID = '#catalog-create-app';

    if (document.querySelector(MOUNT_ID)) {
        const {createApp} = Vue;

        const app = createApp({
            delimiters: ['[[', ']]'],
            data() {
                return {
                    isVisible: false,
                    isEditing: false,
                    currentId: null,
                    form: {name: '', code: ''}, // No necesitamos is_active aquí
                    errors: {}
                }
            },
            computed: {
                modalTitle() {
                    return this.isEditing ? 'Editar Catálogo' : 'Nuevo Catálogo';
                }
            },
            methods: {
                openModal() {
                    this.isVisible = true;
                    this.errors = {};
                },
                closeModal() {
                    this.isVisible = false;
                },
                openCreate() {
                    this.isEditing = false;
                    this.currentId = null;
                    this.form = {name: '', code: ''};
                    this.errors = {};
                    this.isVisible = true;
                },
                async loadAndOpenEdit(id) {
                    this.isEditing = true;
                    this.currentId = id;
                    this.errors = {};

                    try {
                        const response = await fetch(`/settings/catalogs/detail/${id}/`);
                        if (!response.ok) throw new Error('Error en la petición');

                        const result = await response.json();

                        if (result.success) {
                            this.form = result.data;
                            this.isVisible = true;
                        } else {
                            Swal.fire('Error', 'No se pudieron cargar los datos', 'error');
                        }
                    } catch (error) {
                        console.error(error);
                        Swal.fire('Error', 'Error al cargar datos', 'error');
                    }
                },
                async submitCatalog() {
                    this.errors = {};
                    const formData = new FormData();
                    formData.append('name', this.form.name);
                    formData.append('code', this.form.code);

                    const token = document.querySelector('[name=csrfmiddlewaretoken]');
                    if (token) formData.append('csrfmiddlewaretoken', token.value);

                    let url = '/settings/catalogs/create/';
                    if (this.isEditing && this.currentId) {
                        url = `/settings/catalogs/update/${this.currentId}/`;
                    }

                    try {
                        const response = await fetch(url, {
                            method: 'POST',
                            body: formData,
                            headers: {'X-Requested-With': 'XMLHttpRequest'}
                        });

                        // Verificar que sea JSON
                        const contentType = response.headers.get("content-type");
                        if (!contentType || !contentType.includes("application/json")) {
                            throw new Error("Respuesta no válida del servidor");
                        }

                        const data = await response.json();

                        if (data.success) {
                            Swal.fire({
                                icon: 'success',
                                title: '¡Guardado!',
                                text: data.message,
                                timer: 1500,
                                showConfirmButton: false
                            });
                            this.closeModal();
                            setTimeout(() => location.reload(), 1500);
                        } else {
                            this.errors = data.errors;
                            Swal.fire({icon: 'error', title: 'Atención', text: 'Revisa el formulario'});
                        }
                    } catch (e) {
                        console.error(e);
                        Swal.fire('Error', 'Error de servidor', 'error');
                    }
                }
            }
        });

        const vm = app.mount(MOUNT_ID);

        // Puentes para botones externos
        const btnNew = document.getElementById('btn-add-catalog');
        if (btnNew) {
            btnNew.addEventListener('click', (e) => {
                e.preventDefault();
                vm.openCreate();
            });
        }

        window.openEditCatalog = (id) => {
            vm.loadAndOpenEdit(id);
        };
    }

    // ---------------------------------------------------------
    // B. LÓGICA DE TABLA (Paginación y Buscador Vanilla JS)
    // ---------------------------------------------------------
    const tableBody = document.getElementById('table-body');

    // Solo ejecutamos si existe la tabla en el HTML
    if (tableBody) {
        // Obtenemos todas las filas generadas por Django
        // IMPORTANTE: Tus <tr> deben tener la clase "catalog-row"
        const rows = Array.from(document.getElementsByClassName('catalog-row'));
        const noResultsRow = document.getElementById('no-results-row'); // Fila oculta de "no hay datos"

        const pageSize = 10;
        let currentPage = 1;
        let visibleRows = rows; // Inicialmente todas son visibles

        // Elementos UI
        const btnPrev = document.getElementById('btn-prev');
        const btnNext = document.getElementById('btn-next');
        const pageInfo = document.getElementById('page-info');
        const pageDisplay = document.getElementById('current-page-display');
        const searchInput = document.getElementById('table-search');

        // Función principal de renderizado
        function renderTable() {
            const totalRows = visibleRows.length;
            const totalPages = Math.ceil(totalRows / pageSize) || 1;

            if (currentPage < 1) currentPage = 1;
            if (currentPage > totalPages) currentPage = totalPages;

            const start = (currentPage - 1) * pageSize;
            const end = start + pageSize;

            // 1. Ocultar TODAS las filas
            rows.forEach(row => {
                row.style.display = 'none';
            });
            if (noResultsRow) noResultsRow.style.display = 'none';

            // 2. Mostrar las visibles de la página actual
            if (totalRows > 0) {
                visibleRows.slice(start, end).forEach(row => {
                    row.classList.remove('row-hidden');
                    row.style.display = '';
                });
            } else {
                // Si no hay resultados tras filtrar
                if (noResultsRow) {
                    noResultsRow.classList.remove('row-hidden');
                    noResultsRow.style.display = '';
                }
            }

            // 3. Actualizar Paginador UI
            if (pageDisplay) pageDisplay.textContent = currentPage;
            if (pageInfo) {
                const startLabel = totalRows > 0 ? start + 1 : 0;
                const endLabel = Math.min(end, totalRows);
                pageInfo.textContent = `Mostrando ${startLabel}-${endLabel} de ${totalRows}`;
            }

            if (btnPrev) btnPrev.disabled = currentPage === 1;
            if (btnNext) btnNext.disabled = currentPage === totalPages;
        }

        // Evento Buscador
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                const term = e.target.value.toLowerCase().trim();

                // Filtramos las filas
                visibleRows = rows.filter(row => {
                    const text = row.innerText.toLowerCase();
                    return text.includes(term);
                });

                currentPage = 1; // Resetear a pag 1 al buscar
                renderTable();
            });
        }

        // Eventos Botones Paginación
        if (btnPrev) {
            btnPrev.addEventListener('click', () => {
                const totalPages = Math.ceil(visibleRows.length / pageSize) || 1;
                if (currentPage > 1) {
                    currentPage--;
                    renderTable();
                }
            });
        }

        if (btnNext) {
            btnNext.addEventListener('click', () => {
                const totalPages = Math.ceil(visibleRows.length / pageSize) || 1;
                if (currentPage < totalPages) {
                    currentPage++;
                    renderTable();
                }
            });
        }

        // Arrancar
        renderTable();
    }

    // Search / No-results helper (se ejecuta al cargar la app ya existente)
    function initTableSearch() {
        const searchInput = document.getElementById('table-search');
        const tableBody = document.getElementById('table-body');
        const overlay = document.querySelector('.no-results-overlay');
        const placeholder = document.getElementById('no-results-placeholder');

        if (!searchInput || !tableBody || !overlay) {
            console.log('catalogs.js: search init - elementos no encontrados (searchInput/tableBody/overlay)');
            return;
        }

        const rows = Array.from(tableBody.querySelectorAll('tr.catalog-row'));
        const pageSize = 10;
        let currentPage = 1;
        let filteredRows = [...rows]; // Copia de todas las filas

        function showNoResults() {
            if (placeholder) placeholder.classList.remove('hidden');
            overlay.classList.remove('hidden');
            overlay.setAttribute('aria-hidden', 'false');
        }

        function hideNoResults() {
            if (placeholder) placeholder.classList.add('hidden');
            overlay.classList.add('hidden');
            overlay.setAttribute('aria-hidden', 'true');
        }

        function renderPage() {
            const totalRows = filteredRows.length;
            const totalPages = Math.ceil(totalRows / pageSize) || 1;

            if (currentPage < 1) currentPage = 1;
            if (currentPage > totalPages) currentPage = totalPages;

            const start = (currentPage - 1) * pageSize;
            const end = start + pageSize;

            // Ocultar todas las filas primero
            rows.forEach(r => r.style.display = 'none');

            // Mostrar solo las de la página actual
            if (totalRows > 0) {
                filteredRows.slice(start, end).forEach(r => {
                    r.style.display = 'table-row';
                });
                hideNoResults();
            } else {
                showNoResults();
            }
        }

        function filterTable(q) {
            const term = (q || '').trim().toLowerCase();
            currentPage = 1; // Resetear a la primera página al filtrar

            if (!term) {
                // Si no hay término, mostrar todas las filas
                filteredRows = [...rows];
            } else {
                // Filtrar filas por el término de búsqueda
                filteredRows = rows.filter(r => {
                    const nameTd = r.children[1];
                    const text = nameTd ? nameTd.textContent.trim().toLowerCase() : '';
                    return text.indexOf(term) !== -1;
                });
            }

            renderPage();
        }

        // debounce
        let timeout = null;
        searchInput.addEventListener('input', function (e) {
            clearTimeout(timeout);
            timeout = setTimeout(() => filterTable(e.target.value), 200);
        });

        // permitir buscar con Enter
        searchInput.addEventListener('keydown', function (e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                filterTable(e.target.value);
            }
        });

        // Renderizar la primera página al iniciar
        renderPage();

        console.log('catalogs.js: table search initialized');
    }

    // Esperar a que la app principal se inicialice y luego inicializar búsqueda
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => setTimeout(initTableSearch, 50));
    } else {
        setTimeout(initTableSearch, 50);
    }
});

/**
 * Función Global para actualizar los contadores del Dashboard
 * Recibe un objeto: { total: int, active: int, inactive: int }
 */
window.updateDashboardStats = function (stats) {
    if (!stats) return;

    const elTotal = document.getElementById('stat-total');
    const elActive = document.getElementById('stat-active');
    const elInactive = document.getElementById('stat-inactive');

    // Animación simple de actualización (opcional)
    if (elTotal) elTotal.textContent = stats.total;
    if (elActive) elActive.textContent = stats.active;
    if (elInactive) elInactive.textContent = stats.inactive;
};
