document.addEventListener('DOMContentLoaded', () => {

    // =========================================================
    // 1. VARIABLES Y UTILIDADES
    // =========================================================
    const tableContainer = document.getElementById('table-content-wrapper');
    const searchInput = document.getElementById('table-search-budget');
    let currentFilters = {q: '', status: 'all', page: 1};

    // Configuración Toast (SweetAlert2)
    const Toast = Swal.mixin({
        toast: true,
        position: 'top-end',
        showConfirmButton: false,
        timer: 3000,
        timerProgressBar: true,
        didOpen: (toast) => {
            toast.addEventListener('mouseenter', Swal.stopTimer);
            toast.addEventListener('mouseleave', Swal.resumeTimer);
        }
    });

    // =========================================================
    // 2. LÓGICA DE TABLA (AJAX Fetch)
    // =========================================================
    window.fetchBudgets = function (params = {}) {
        if (params.reset) currentFilters = {q: '', status: 'all', page: 1};
        else Object.assign(currentFilters, params);

        const url = new URL(window.location.href);
        Object.keys(currentFilters).forEach(key => {
            if (currentFilters[key]) url.searchParams.set(key, currentFilters[key]);
        });

        // Llamada AJAX
        fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
            .then(res => res.text())
            .then(html => {
                if (tableContainer) {
                    tableContainer.innerHTML = html;
                    updatePaginationUI();
                }
            })
            .catch(err => console.error("Error cargando tabla:", err));
    };

    function updatePaginationUI() {
        const meta = document.getElementById('pagination-metadata');
        if (!meta) return;

        const total = meta.dataset.total,
            start = meta.dataset.start,
            end = meta.dataset.end,
            page = parseInt(meta.dataset.page);

        const pageInfo = document.getElementById('page-info');
        if (pageInfo) pageInfo.textContent = total == 0 ? "Sin resultados" : `Mostrando ${start}-${end} de ${total}`;

        const pageDisplay = document.getElementById('current-page-display');
        if (pageDisplay) pageDisplay.textContent = page;

        const btnPrev = document.getElementById('btn-prev');
        const btnNext = document.getElementById('btn-next');
        if (btnPrev) btnPrev.disabled = meta.dataset.hasPrev !== 'true';
        if (btnNext) btnNext.disabled = meta.dataset.hasNext !== 'true';
    }

    // Listener para el Buscador
    if (searchInput) {
        let timeout;
        searchInput.addEventListener('input', (e) => {
            clearTimeout(timeout);
            timeout = setTimeout(() => window.fetchBudgets({q: e.target.value, page: 1}), 500);
        });
    }

    // Filtros por Estado (Estadísticas)
    window.filterBudgetByStatus = function (status) {
        // Opacidad visual de tarjetas
        document.querySelectorAll('.stat-card').forEach(c => c.classList.add('opacity-low'));

        let activeId = 'card-filter-all';
        if (status === 'VACANT') activeId = 'card-filter-vacant';
        if (status === 'OCCUPIED') activeId = 'card-filter-occupied';

        const activeCard = document.getElementById(activeId);
        if (activeCard) activeCard.classList.remove('opacity-low');

        // Recargar tabla
        window.fetchBudgets({status: status, page: 1});
    };

    // Listeners de Botones de Paginación y Crear
    const btnP = document.getElementById('btn-prev');
    const btnN = document.getElementById('btn-next');
    const btnAdd = document.getElementById('btn-add-budget'); // ID del botón "Nueva Partida"

    // Delegación de eventos para paginación (porque los botones pueden redibujarse,
    // aunque en este diseño están fuera del partial, así que listener directo funciona)
    if (btnP) btnP.onclick = () => window.fetchBudgets({page: currentFilters.page - 1});
    if (btnN) btnN.onclick = () => window.fetchBudgets({page: currentFilters.page + 1});

    // Botón CREAR
    if (btnAdd) {
        btnAdd.addEventListener('click', () => {
            openCreateBudget();
        });
    }


    // =========================================================
    // 3. LÓGICA DE CASCADA (Hierarchical Selects)
    // =========================================================
    async function loadHierarchyOptions(parentId, targetType, targetSelectId) {
        const targetSelect = document.getElementById(targetSelectId);
        if (!targetSelect) return;

        targetSelect.innerHTML = '<option value="">Cargando...</option>';
        targetSelect.disabled = true;

        try {
            const res = await fetch(`/budget/api/hierarchy/?parent_id=${parentId}&target_type=${targetType}`);
            const data = await res.json();

            targetSelect.innerHTML = '<option value="">---------</option>';

            if (data.results && data.results.length > 0) {
                data.results.forEach(item => {
                    const option = document.createElement('option');
                    option.value = item.id;
                    option.textContent = item.text;
                    targetSelect.appendChild(option);
                });
                targetSelect.disabled = false;
            } else {
                targetSelect.innerHTML = '<option value="">Sin registros</option>';
            }
        } catch (e) {
            console.error("Error cargando jerarquía:", e);
            targetSelect.innerHTML = '<option value="">Error</option>';
        }
    }

    window.setupHierarchyListeners = function () {
        const progSelect = document.getElementById('id_program');
        if (progSelect) {
            progSelect.addEventListener('change', (e) => {
                loadHierarchyOptions(e.target.value, 'subprogram', 'id_subprogram');
                // Limpiar niveles inferiores
                document.getElementById('id_project').innerHTML = '<option value="">---</option>';
                document.getElementById('id_project').disabled = true;
                document.getElementById('id_activity').innerHTML = '<option value="">---</option>';
                document.getElementById('id_activity').disabled = true;
            });
        }

        const subSelect = document.getElementById('id_subprogram');
        if (subSelect) {
            subSelect.addEventListener('change', (e) => {
                loadHierarchyOptions(e.target.value, 'project', 'id_project');
                // Limpiar niveles inferiores
                document.getElementById('id_activity').innerHTML = '<option value="">---</option>';
                document.getElementById('id_activity').disabled = true;
            });
        }

        const projSelect = document.getElementById('id_project');
        if (projSelect) {
            projSelect.addEventListener('change', (e) => {
                loadHierarchyOptions(e.target.value, 'activity', 'id_activity');
            });
        }
    };


    // =========================================================
    // 4. LÓGICA DE MODALES (Apertura y Submit)
    // =========================================================

    // ABRIR CREAR
    window.openCreateBudget = function () {
        const modal = document.getElementById('budget-modal-app');
        const form = document.getElementById('budgetForm');

        if (modal && form) {
            form.reset();
            // Limpiar errores visuales previos
            document.querySelectorAll('.text-error').forEach(el => el.textContent = '');

            // Reiniciar selects de cascada
            const sub = document.getElementById('id_subprogram');
            if (sub) {
                sub.innerHTML = '';
                sub.disabled = true;
            }
            const proj = document.getElementById('id_project');
            if (proj) {
                proj.innerHTML = '';
                proj.disabled = true;
            }
            const act = document.getElementById('id_activity');
            if (act) {
                act.innerHTML = '';
                act.disabled = true;
            }

            // Mostrar modal
            modal.classList.remove('hidden');
            document.body.classList.add('no-scroll');

            // Activar listeners
            setupHierarchyListeners();
        }
    };

    // structure.js

    window.openCreateStructure = function (modelType, parentId) {
        const url = `/budget/structure/create/${modelType}/${parentId}/`;
        fetch(url)
            .then(res => res.text())
            .then(html => {
                const container = document.getElementById('modal-inject-container');
                container.innerHTML = html;
                const modal = container.querySelector('.modal-overlay');
                modal.classList.remove('hidden');
                document.body.classList.add('no-scroll');

                // Si usas Select2 en los modales:
                $(modal).find('select').select2({width: '100%', dropdownParent: $(modal)});
            });
    };

    window.submitStructureForm = async function (e, modelType, parentId) {
        e.preventDefault();
        const form = e.target;
        const formData = new FormData(form);
        const url = `/budget/structure/create/${modelType}/${parentId}/`;

        try {
            const res = await fetch(url, {
                method: 'POST',
                body: formData,
                headers: {'X-Requested-With': 'XMLHttpRequest'}
            });
            const data = await res.json();
            if (data.success) {
                Swal.fire('Guardado', data.message, 'success').then(() => location.reload());
            } else {
                // Mostrar errores en los div err-X
                Toast.fire({icon: 'error', title: 'Revise los campos'});
            }
        } catch (err) {
            console.error(err);
        }
    };

    // ABRIR EDITAR (Fetch HTML)
    window.openEditBudget = async function (pk) {
        try {
            const res = await fetch(`/budget/update/${pk}/`);
            if (!res.ok) throw new Error("Error al obtener formulario");

            const html = await res.text();

            // Inyectar HTML en el contenedor específico
            const container = document.getElementById('modal-inject-container');
            container.innerHTML = html;

            // Buscar el nuevo modal inyectado (asumimos que el HTML viene con id="budget-modal-content" wrapper)
            // Necesitamos envolverlo o mostrar el overlay.
            // En este caso, reutilizamos el overlay general si es posible, o el HTML traído trae su propio overlay.
            // Para mantener consistencia con Unit, el HTML traído debe ser SOLO el contenido,
            // pero Unit usaba Vue. Aquí usamos HTML puro.

            // ESTRATEGIA: El HTML que devuelve BudgetUpdateView (modal_budget_form.html)
            // YA TIENE el div con clase 'modal-overlay' oculto o visible?
            // Recomiendo que modal_budget_form tenga id="budget-modal-app-edit" o similar.

            // Simplificación: Forzamos la clase 'hidden' a false en el elemento inyectado
            const newModal = container.querySelector('.modal-overlay');
            if (newModal) {
                newModal.classList.remove('hidden'); // Mostrar
                newModal.id = "budget-modal-edit-active"; // ID temporal único
            }

            document.body.classList.add('no-scroll');
            setupHierarchyListeners();

        } catch (e) {
            console.error(e);
            Toast.fire({icon: 'error', title: 'Error al cargar formulario'});
        }
    };

    // CERRAR MODAL
    window.closeBudgetModal = function () {
        // Cerrar modal de creación
        const createModal = document.getElementById('budget-modal-app');
        if (createModal) createModal.classList.add('hidden');

        // Cerrar/Eliminar modal de edición inyectado
        const injectContainer = document.getElementById('modal-inject-container');
        if (injectContainer) injectContainer.innerHTML = ''; // Limpiar HTML inyectado

        document.body.classList.remove('no-scroll');
    };

    // SUBMIT FORMULARIO (Vinculado via onsubmit en el HTML)
    window.submitBudgetForm = async function (e, url) {
        e.preventDefault();
        const form = e.target;
        const formData = new FormData(form);

        // Limpiar errores previos
        document.querySelectorAll('.text-error').forEach(el => el.textContent = '');

        try {
            const res = await fetch(url, {
                method: 'POST',
                body: formData,
                headers: {'X-Requested-With': 'XMLHttpRequest'}
            });
            const data = await res.json();

            if (data.success) {
                closeBudgetModal();
                window.fetchBudgets(); // Recargar tabla

                // Actualizar stats si vienen
                if (data.new_stats) {
                    document.getElementById('stat-total').textContent = data.new_stats.total;
                    document.getElementById('stat-vacant').textContent = data.new_stats.vacant;
                    document.getElementById('stat-occupied').textContent = data.new_stats.occupied;
                }

                Toast.fire({
                    icon: 'success',
                    title: 'Guardado',
                    text: data.message
                });
            } else {
                // Mostrar errores de campo
                if (data.errors) {
                    Object.keys(data.errors).forEach(key => {
                        const errDiv = document.getElementById(`err-${key}`);
                        // Intenta buscar el error dentro del form actual
                        const formErrDiv = form.querySelector(`#err-${key}`);
                        if (formErrDiv) formErrDiv.textContent = data.errors[key][0];
                    });
                }
                Toast.fire({icon: 'warning', title: 'Revise el formulario'});
            }
        } catch (error) {
            console.error(error);
            Toast.fire({icon: 'error', title: 'Error del servidor'});
        }
    };

    // Carga inicial de la tabla
    window.fetchBudgets();
});