/**
 * budget.js - Gestión Integral de Presupuesto (SIGETH)
 * Arquitectura: Vanilla JS + Select2 + SweetAlert2
 * Estándar: Senior Software Architecture (Zero redundancy)
 */

// --- 1. CONFIGURACIÓN GLOBAL Y UTILIDADES ---

const Toast = Swal.mixin({
    toast: true,
    position: 'top-end',
    showConfirmButton: false,
    timer: 3000,
    timerProgressBar: true,
});

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
    if (window.fetchBudgets) window.fetchBudgets();
    const searchInput = document.getElementById('table-search-budget');
    if (searchInput) {
        let timeout;
        searchInput.addEventListener('input', (e) => {
            clearTimeout(timeout);
            timeout = setTimeout(() => window.fetchBudgets({q: e.target.value, page: 1}), 500);
        });
    }
});

// --- 2. GESTIÓN DE TABLA Y FILTROS ---

let currentFilters = {q: '', status: 'all', page: 1};

window.fetchBudgets = function (params = {}) {
    Object.assign(currentFilters, params);
    const url = new URL(window.location.href);
    if (currentFilters.q) url.searchParams.set('q', currentFilters.q);
    if (currentFilters.status) url.searchParams.set('status', currentFilters.status);
    if (currentFilters.page) url.searchParams.set('page', currentFilters.page);

    fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
        .then(res => res.text())
        .then(html => {
            const wrapper = document.getElementById('table-content-wrapper');
            if (wrapper) wrapper.innerHTML = html;
        });
};

function updatePaginationUI() {
    const meta = document.getElementById('pagination-metadata');
    if (!meta) return;
    const pageInfo = document.getElementById('page-info');
    if (pageInfo) pageInfo.textContent = meta.dataset.total == 0 ? "Sin resultados" : `Mostrando ${meta.dataset.start}-${meta.dataset.end} de ${meta.dataset.total}`;

    document.getElementById('btn-prev').disabled = meta.dataset.hasPrev !== 'true';
    document.getElementById('btn-next').disabled = meta.dataset.hasNext !== 'true';
    const display = document.getElementById('current-page-display');
    if (display) display.textContent = meta.dataset.page;
}

// --- 3. ACTUALIZACIÓN DE ESTADÍSTICAS (STATS) ---

window.refreshStatsUI = function (stats) {
    if (!stats) return;
    const keys = ['total', 'libre', 'ocupada', 'concurso', 'litigio', 'inactiva'];
    keys.forEach(key => {
        const element = document.getElementById(`stat-${key}`);
        if (element) {
            if (element.textContent != stats[key]) {
                element.textContent = stats[key];
                // Efecto visual de pulso
                element.style.transform = 'scale(1.2)';
                element.style.color = '#2563eb';
                element.style.transition = 'all 0.3s ease';
                setTimeout(() => {
                    element.style.transform = 'scale(1)';
                    element.style.color = '';
                }, 300);
            }
        }
    });
};

/**
 * Manejador universal de éxito para todas las acciones de presupuesto
 */
window.handleActionSuccess = function (data) {
    if (data.success) {
        window.closeBudgetModal();
        Toast.fire({icon: 'success', title: data.message});
        // Recargar tabla asíncronamente
        window.fetchBudgets();
        // Actualizar contadores asíncronamente
        if (data.new_stats) window.refreshStatsUI(data.new_stats);
    }
};

// --- 4. CASCADA DINÁMICA Y GENERACIÓN DE CÓDIGO (6 NIVELES) ---

function initBudgetFormCascades() {
    const $modal = $('#budget-modal-content');
    const $program = $('#id_program'), $subprogram = $('#id_subprogram'), $project = $('#id_project'),
        $activity = $('#id_activity'), $spending = $('#id_spending_type_item'), $regime = $('#id_regime_item');
    const $displayCode = $('#display-budget-code'), $hiddenCode = $('#id_code');

    // Inicializar Select2
    $modal.find('select').select2({width: '100%', dropdownParent: $modal.parent()});

    const getCodePart = ($el) => {
        const selected = $el.find('option:selected')[0];
        if (!selected || !selected.value || selected.text.includes('---------')) return '';
        return selected.dataset.code || selected.text.split(' - ')[0].trim();
    };

    const updateFullCode = () => {
        const parts = [getCodePart($program), getCodePart($subprogram), getCodePart($project),
            getCodePart($activity), getCodePart($spending), getCodePart($regime)].filter(p => p !== '');
        const finalCode = parts.join('.');
        $displayCode.text(finalCode || "00.00.00.00.00.00");
        $hiddenCode.val(finalCode);
    };

    const fetchChildren = async (parentId, type, $targetSelect) => {
        if (!parentId) {
            $targetSelect.empty().append('<option value="">---------</option>').prop('disabled', true).trigger('change.select2');
            return;
        }
        try {
            const res = await fetch(`/budget/api/hierarchy/?parent_id=${parentId}&target_type=${type}`);
            const data = await res.json();
            $targetSelect.empty().append('<option value="">---------</option>');
            data.results.forEach(item => {
                const opt = new Option(item.text, item.id);
                opt.setAttribute('data-code', item.code);
                $targetSelect.append(opt);
            });
            $targetSelect.prop('disabled', false).trigger('change.select2');
        } catch (e) {
            console.error(e);
        }
    };

    // LISTENERS DE CASCADA (Corregidos para no vaciar catálogos independientes)
    $program.on('change', () => {
        fetchChildren($program.val(), 'subprogram', $subprogram);
        [$project, $activity].forEach(s => s.empty().prop('disabled', true).trigger('change.select2'));
        updateFullCode();
    });

    $subprogram.on('change', () => {
        fetchChildren($subprogram.val(), 'project', $project);
        $activity.empty().prop('disabled', true).trigger('change.select2');
        updateFullCode();
    });

    $project.on('change', () => {
        fetchChildren($project.val(), 'activity', $activity);
        updateFullCode();
    });

    $activity.on('change', () => {
        const hasVal = !!$activity.val();
        $spending.prop('disabled', !hasVal).trigger('change.select2');
        updateFullCode();
    });

    $spending.on('change', () => {
        const hasVal = !!$spending.val();
        $regime.prop('disabled', !hasVal).trigger('change.select2');
        updateFullCode();
    });

    $regime.on('change', updateFullCode);
    updateFullCode();
}

window.openCreateBudget = () => {
    const m = document.getElementById('budget-modal-app');
    if (m) {
        m.classList.remove('hidden');
        document.body.classList.add('no-scroll');
        initBudgetFormCascades();
    }
};
window.openEditBudget = async (pk) => {
    const res = await fetch(`/budget/update/${pk}/`);
    document.getElementById('modal-inject-container').innerHTML = await res.text();
    document.querySelector('#modal-inject-container .modal-overlay').classList.remove('hidden');
    document.body.classList.add('no-scroll');
    initBudgetFormCascades();
};

// --- 5. MODALES Y ACCIONES (DISTRIBUTIVO) ---

window.openCreateBudget = function () {
    const modal = document.getElementById('budget-modal-app');
    if (modal) {
        modal.classList.remove('hidden');
        document.body.classList.add('no-scroll');
        initBudgetFormCascades();
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
            initBudgetFormCascades();
        }
    } catch (e) {
        Toast.fire({icon: 'error', title: 'Error al cargar formulario'});
    }
};

window.submitBudgetForm = async (e, url) => {
    e.preventDefault();
    const res = await fetch(url, {
        method: 'POST',
        body: new FormData(e.target),
        headers: {'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': getCookie('csrftoken')}
    });
    const data = await res.json();
    if (data.success) {
        window.closeBudgetModal();
        Toast.fire({icon: 'success', title: data.message});
        window.fetchBudgets();
        if (data.new_stats) window.refreshStatsUI(data.new_stats);
    } else {
        e.target.querySelectorAll('.text-error').forEach(el => el.textContent = '');
        Object.keys(data.errors).forEach(k => {
            const el = document.getElementById(`err-${k}`);
            if (el) el.textContent = data.errors[k][0];
        });
    }
};

// --- 6. ACCIONES ESPECÍFICAS (NÚMERO, EMPLEADO, LIBERACIÓN) ---

window.openAssignNumberModal = (pk) => {
    fetch(`/budget/assign-number/${pk}/`).then(res => res.text()).then(html => {
        const container = document.getElementById('modal-inject-container');
        container.innerHTML = html;
        container.querySelector('.modal-overlay').classList.remove('hidden');
        document.body.classList.add('no-scroll');
    });
};

window.submitAssignNumberForm = async (e, pk) => {
    e.preventDefault();
    const res = await fetch(`/budget/assign-number/${pk}/`, {
        method: 'POST',
        body: new FormData(e.target),
        headers: {'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': getCookie('csrftoken')}
    });
    window.handleActionSuccess(await res.json());
};

window.openAssignEmployeeModal = (pk) => {
    fetch(`/budget/assign-employee/${pk}/`).then(res => res.text()).then(html => {
        const container = document.getElementById('modal-inject-container');
        container.innerHTML = html;
        container.querySelector('.modal-overlay').classList.remove('hidden');
        document.body.classList.add('no-scroll');
    });
};

window.searchEmployee = async function () {
    const cedula = document.getElementById('search-cedula').value;
    const resultCard = document.getElementById('search-result-card'),
        btnSubmit = document.getElementById('btn-submit-assign'),
        resName = document.getElementById('res-name'), resEmail = document.getElementById('res-email'),
        resPhoto = document.getElementById('res-photo'), hiddenId = document.getElementById('selected-employee-id');

    if (!cedula || cedula.length < 10) return Toast.fire({icon: 'warning', title: 'Cédula no válida'});

    try {
        const res = await fetch(`/employee/api/search/?q=${cedula}`);
        const data = await res.json();
        if (data.success) {
            resName.textContent = data.full_name;
            resEmail.textContent = data.email;
            hiddenId.value = data.id;
            resPhoto.innerHTML = data.photo_url ? `<img src="${data.photo_url}" class="person-avatar" style="width:50px; height:50px; border-radius:50%; object-fit:cover;">` :
                `<div class="person-avatar-placeholder" style="width:50px; height:50px; border-radius:50%; background:#3b82f6; color:white; display:flex; align-items:center; justify-content:center; font-weight:bold;">${data.full_name.charAt(0)}</div>`;
            resultCard.classList.remove('hidden');
            btnSubmit.disabled = false;
        } else {
            resultCard.classList.add('hidden');
            btnSubmit.disabled = true;
            Swal.fire({title: 'No disponible', text: data.message, icon: 'warning', confirmButtonText: 'Entendido'});
        }
    } catch (e) {
        Toast.fire({icon: 'error', title: 'Error de servidor'});
    }
};

window.submitAssignEmployee = async (e, pk) => {
    e.preventDefault();
    const res = await fetch(`/budget/assign-employee/${pk}/`, {
        method: 'POST',
        body: new FormData(e.target),
        headers: {'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': getCookie('csrftoken')}
    });
    window.handleActionSuccess(await res.json());
};

window.openReleaseModal = (pk) => {
    fetch(`/budget/release/${pk}/`).then(res => res.text()).then(html => {
        const container = document.getElementById('modal-inject-container');
        container.innerHTML = html;
        container.querySelector('.modal-overlay').classList.remove('hidden');
        document.body.classList.add('no-scroll');
    });
};

window.submitReleaseForm = async (e, pk) => {
    e.preventDefault();
    const res = await fetch(`/budget/release/${pk}/`, {
        method: 'POST',
        body: new FormData(e.target),
        headers: {'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': getCookie('csrftoken')}
    });
    window.handleActionSuccess(await res.json());
};

window.openChangeStatusModal = (pk) => {
    fetch(`/budget/change-status/${pk}/`).then(res => res.text()).then(html => {
        const container = document.getElementById('modal-inject-container');
        container.innerHTML = html;
        $(container).find('select').select2({width: '100%', dropdownParent: $(container).find('.modal-overlay')});
        container.querySelector('.modal-overlay').classList.remove('hidden');
        document.body.classList.add('no-scroll');
    });
};

window.submitChangeStatusForm = async (e, pk) => {
    e.preventDefault();
    const res = await fetch(`/budget/change-status/${pk}/`, {
        method: 'POST',
        body: new FormData(e.target),
        headers: {'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': getCookie('csrftoken')}
    });
    window.handleActionSuccess(await res.json());
};

// --- 7. CIERRE DE MODALES Y FILTROS ---

window.closeBudgetModal = () => {
    const m = document.getElementById('budget-modal-app');
    if (m) m.classList.add('hidden');
    document.getElementById('modal-inject-container').innerHTML = '';
    document.body.classList.remove('no-scroll');
};

window.filterBudgetByStatus = function (status) {
    document.querySelectorAll('.stat-card').forEach(c => c.classList.add('opacity-low'));
    const activeId = status === 'all' ? 'card-filter-all' : `card-filter-${status.toLowerCase()}`;
    const el = document.getElementById(activeId);
    if (el) el.classList.remove('opacity-low');
    window.fetchBudgets({status: status, page: 1});
};

window.filterStructureByStatus = function (status) {
    document.querySelectorAll('.stat-card').forEach(c => c.classList.add('opacity-low'));
    const activeId = status === 'all' ? 'card-struct-all' : `card-struct-${status}`;
    const el = document.getElementById(activeId);
    if (el) el.classList.remove('opacity-low');
    window.fetchBudgets({status: status, page: 1});
};

// --- 8. ESTRUCTURA PROGRAMÁTICA (MODALES Y TOGGLE) ---

window.openCreateStructure = (modelType, parentId) => {
    fetch(`/budget/structure/create/${modelType}/${parentId}/`).then(res => res.text()).then(html => {
        const container = document.getElementById('modal-inject-container');
        container.innerHTML = html;
        container.querySelector('.modal-overlay').classList.remove('hidden');
        document.body.classList.add('no-scroll');
    });
};

window.openEditStructure = (modelType, pk) => {
    fetch(`/budget/structure/edit/${modelType}/${pk}/`).then(res => res.text()).then(html => {
        const container = document.getElementById('modal-inject-container');
        container.innerHTML = html;
        container.querySelector('.modal-overlay').classList.remove('hidden');
        document.body.classList.add('no-scroll');
    });
};

window.submitStructureForm = async (e, modelType, id, isEditing) => {
    e.preventDefault();
    const url = isEditing ? `/budget/structure/edit/${modelType}/${id}/` : `/budget/structure/create/${modelType}/${id}/`;
    const res = await fetch(url, {
        method: 'POST',
        body: new FormData(e.target),
        headers: {'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': getCookie('csrftoken')}
    });
    const data = await res.json();
    if (data.success) {
        Toast.fire({icon: 'success', title: data.message});
        setTimeout(() => location.reload(), 800);
    }
};

window.toggleStructureActive = function (modelType, pk, isActive) {
    const actionText = isActive ? 'desactivar' : 'activar';
    Swal.fire({
        title: `¿Confirmar ${actionText}?`, icon: 'warning', showCancelButton: true, confirmButtonText: 'Aceptar',
        customClass: {
            confirmButton: isActive ? 'btn-swal-danger' : 'btn-swal-success',
            cancelButton: 'btn-swal-cancel'
        },
        buttonsStyling: false
    }).then((result) => {
        if (result.isConfirmed) {
            fetch(`/budget/structure/toggle/${modelType}/${pk}/`, {
                method: 'POST',
                headers: {'X-CSRFToken': getCookie('csrftoken'), 'X-Requested-With': 'XMLHttpRequest'}
            }).then(res => res.json()).then(data => {
                if (data.success) {
                    Toast.fire({icon: 'success', title: data.message});
                    setTimeout(() => location.reload(), 800);
                }
            });
        }
    });
};

// Listeners de paginación finales
document.addEventListener('click', (e) => {
    if (e.target.id === 'btn-prev') window.fetchBudgets({page: currentFilters.page - 1});
    if (e.target.id === 'btn-next') window.fetchBudgets({page: currentFilters.page + 1});
});

// Inicialización de cascadas si es necesario (para modales inyectados se llama al abrir)
window.setupHierarchyListeners = function () {
    initBudgetFormCascades();
};