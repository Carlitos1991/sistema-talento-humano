/**
 * budget.js - Gestión de Presupuesto y Estructura Programática
 * Sistema: SIGETH
 */

// --- 1. CONFIGURACIÓN GLOBAL Y UTILIDADES ---

// Configuración Toast (SweetAlert2) - ÚNICA DECLARACIÓN
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

// Helper para obtener CSRF Token de las cookies
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

document.addEventListener('DOMContentLoaded', () => {
    const tableContainer = document.getElementById('table-content-wrapper');
    const searchInput = document.getElementById('table-search-budget');
    let currentFilters = {q: '', status: 'all', page: 1};

    // --- 2. LÓGICA DE TABLA ASÍNCRONA (Común para Distributivo y Estructura) ---

    window.fetchBudgets = function (params = {}) {
        if (params.reset) currentFilters = {q: '', status: 'all', page: 1};
        else Object.assign(currentFilters, params);

        const url = new URL(window.location.href);
        if (currentFilters.q) url.searchParams.set('q', currentFilters.q);
        if (currentFilters.status) url.searchParams.set('status', currentFilters.status);
        if (currentFilters.page) url.searchParams.set('page', currentFilters.page);

        fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
            .then(res => res.text())
            .then(html => {
                const wrapper = document.getElementById('table-content-wrapper');
                if (wrapper) {
                    wrapper.innerHTML = html;
                    updatePaginationUI();
                }
            })
            .catch(err => console.error("Error en fetch:", err));
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

    // Buscador con Debounce
    if (searchInput) {
        let timeout;
        searchInput.addEventListener('input', (e) => {
            clearTimeout(timeout);
            timeout = setTimeout(() => {
                window.fetchBudgets({q: e.target.value, page: 1});
            }, 500);
        });
    }

    // --- 3. LÓGICA DE FILTRADO POR ESTADÍSTICAS ---

    // Filtro para Distributivo (Presupuesto)
    window.filterBudgetByStatus = function (status) {
        document.querySelectorAll('.stat-card').forEach(c => c.classList.add('opacity-low'));
        const activeId = {
            'all': 'card-filter-all',
            'VACANT': 'card-filter-vacant',
            'OCCUPIED': 'card-filter-occupied'
        }[status] || 'card-filter-all';
        const card = document.getElementById(activeId);
        if (card) card.classList.remove('opacity-low');
        window.fetchBudgets({status: status, page: 1});
    };

    // Filtro para Estructura (Programas/Sub/etc)
    window.filterStructureByStatus = function (status) {
        document.querySelectorAll('.stat-card').forEach(c => c.classList.add('opacity-low'));
        const activeId = {
            'all': 'card-struct-all',
            'active': 'card-struct-active',
            'inactive': 'card-struct-inactive'
        }[status] || 'card-struct-all';
        const card = document.getElementById(activeId);
        if (card) card.classList.remove('opacity-low');
        window.fetchBudgets({status: status, page: 1});
    };

    // --- 4. GESTIÓN DE MODALES (PARTIDAS PRESUPUESTARIAS) ---

    window.openCreateBudget = function () {
        const modal = document.getElementById('budget-modal-app');
        if (modal) {
            const form = document.getElementById('budgetForm');
            if (form) form.reset();
            document.querySelectorAll('.text-error').forEach(el => el.textContent = '');
            modal.classList.remove('hidden');
            document.body.classList.add('no-scroll');
            setupHierarchyListeners();
        }
    };

    window.openEditBudget = async function (pk) {
        try {
            const res = await fetch(`/budget/update/${pk}/`);
            const html = await res.text();
            const container = document.getElementById('modal-inject-container');
            container.innerHTML = html;
            const modal = container.querySelector('.modal-overlay');
            if (modal) {
                modal.classList.remove('hidden');
                document.body.classList.add('no-scroll');
                setupHierarchyListeners();
            }
        } catch (e) {
            Toast.fire({icon: 'error', title: 'Error al cargar formulario'});
        }
    };

    window.closeBudgetModal = function () {
        const createModal = document.getElementById('budget-modal-app');
        if (createModal) createModal.classList.add('hidden');
        document.getElementById('modal-inject-container').innerHTML = '';
        document.body.classList.remove('no-scroll');
    };

    // --- 5. GESTIÓN DE MODALES (ESTRUCTURA PROGRAMÁTICA) ---

    window.openCreateStructure = function (modelType, parentId) {
        fetch(`/budget/structure/create/${modelType}/${parentId}/`)
            .then(res => res.text())
            .then(html => {
                const container = document.getElementById('modal-inject-container');
                container.innerHTML = html;
                container.querySelector('.modal-overlay').classList.remove('hidden');
                document.body.classList.add('no-scroll');
            });
    };

    window.openEditStructure = function (modelType, pk) {
        fetch(`/budget/structure/edit/${modelType}/${pk}/`)
            .then(res => res.text())
            .then(html => {
                const container = document.getElementById('modal-inject-container');
                container.innerHTML = html;
                const modal = container.querySelector('.modal-overlay');
                if (modal) {
                    modal.classList.remove('hidden');
                    document.body.classList.add('no-scroll');
                }
            })
            .catch(() => Toast.fire({icon: 'error', title: 'Error al cargar formulario'}));
    };

    window.submitStructureForm = async function (e, modelType, id, isEditing = false) {
        e.preventDefault();
        const form = e.target;
        const formData = new FormData(form);
        const url = isEditing ? `/budget/structure/edit/${modelType}/${id}/` : `/budget/structure/create/${modelType}/${id}/`;
        form.querySelectorAll('.text-error').forEach(el => el.textContent = '');
        try {
            const res = await fetch(url, {
                method: 'POST',
                body: formData,
                headers: {'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': getCookie('csrftoken')}
            });
            const data = await res.json();

            if (data.success) {
                window.closeBudgetModal();
                // Toast de éxito inmediato
                Toast.fire({icon: 'success', title: data.message});
                // Recargar para actualizar tabla y stats
                setTimeout(() => location.reload(), 800);
            } else {
                Object.keys(data.errors).forEach(key => {
                    const errDiv = form.querySelector(`#err-${key}`);
                    if (errDiv) errDiv.textContent = data.errors[key][0];
                });
                Toast.fire({icon: 'error', title: 'Revise los campos del formulario'});
            }
        } catch (err) {
            Toast.fire({icon: 'error', title: 'Error de servidor'});
        }
    };

    window.toggleStructureActive = function (modelType, pk, isActive) {
        const btn = document.getElementById(`btn-toggle-${pk}`);
        const icon = btn.querySelector('i');
        const actionText = isActive ? 'desactivar' : 'activar';
        const confirmBtnClass = isActive ? 'btn-swal-danger' : 'btn-swal-success';
        Swal.fire({
            title: `¿${actionText.charAt(0).toUpperCase() + actionText.slice(1)} registro?`,
            text: `Vas a cambiar el estado de este registro.`,
            icon: 'warning',
            showCancelButton: true,
            buttonsStyling: false,
            customClass: {
                confirmButton: `swal2-confirm ${confirmBtnClass}`,
                cancelButton: 'swal2-cancel btn-swal-cancel',
                popup: 'swal2-popup'
            },
            confirmButtonText: 'Sí, cambiar',
            cancelButtonText: 'Cancelar'
        }).then((result) => {
            if (result.isConfirmed) {
                fetch(`/budget/structure/toggle/${modelType}/${pk}/`, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': getCookie('csrftoken'),
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                })
                    .then(res => res.json())
                    .then(data => {
                        if (data.success) {
                            Toast.fire({icon: 'success', title: data.message});

                            // --- LÓGICA DE INTERCAMBIO VISUAL (SIN RELOAD) ---
                            const isNowActive = !isActive;

                            // Actualizar Botón
                            if (isActive) { // Pasó de Activo a Inactivo
                                btn.classList.replace('btn-delete-action', 'btn-create-action');
                                icon.className = 'fas fa-toggle-on';
                                btn.title = "Activar";
                            } else { // Pasó de Inactivo a Activo
                                btn.classList.replace('btn-create-action', 'btn-delete-action');
                                icon.className = 'fas fa-power-off';
                                btn.title = "Desactivar";
                            }

                            // Actualizar el onclick para la siguiente interacción
                            btn.setAttribute('onclick', `toggleStructureActive('${modelType}', ${pk}, ${isNowActive})`);

                            // Actualizar Badge de Estado en la fila
                            const row = btn.closest('tr');
                            const badge = row.querySelector('.status-badge');
                            if (badge) {
                                badge.className = `status-badge ${isNowActive ? 'active' : 'inactive'}`;
                                badge.textContent = isNowActive ? 'Activo' : 'Inactivo';
                            }

                            // Opcional: Si quieres actualizar los números de las tarjetas arriba
                            // puedes llamar a fetchBudgets() o actualizar los contadores vía JS
                            // location.reload(); // Solo si el orden o los contadores deben ser estrictos
                        }
                    })
                    .catch(err => console.error("Error:", err));
            }
        });
    };

    // --- 6. AUXILIARES: CASCADA Y PAGINACIÓN ---

    // Inicialización
    window.fetchBudgets();

    const btnP = document.getElementById('btn-prev');
    const btnN = document.getElementById('btn-next');
    if (btnP) btnP.onclick = () => window.fetchBudgets({page: currentFilters.page - 1});
    if (btnN) btnN.onclick = () => window.fetchBudgets({page: currentFilters.page + 1});

    const btnAdd = document.getElementById('btn-add-budget');
    if (btnAdd) btnAdd.onclick = () => window.openCreateBudget();
});

// Función de cascada fuera del DOMContentLoaded si es necesario o dentro, 
//  asegurando visibilidad para Select2 si se usa.
function setupHierarchyListeners() {
    // Implementación de lógica de cambio de selects...
}