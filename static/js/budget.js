/**
 * budget.js - Gestión de Presupuesto y Estructura Programática
 * Sistema: SIGETH | Arquitectura: Vanilla JS + Select2 + SweetAlert2
 */

// --- 1. CONFIGURACIÓN GLOBAL ---
const Toast = Swal.mixin({
    toast: true,
    position: 'top-end',
    showConfirmButton: false,
    timer: 3000,
    timerProgressBar: true
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

// --- 2. INICIALIZACIÓN PRINCIPAL ---
document.addEventListener('DOMContentLoaded', () => {
    const searchInput = document.getElementById('table-search-budget');

    // Carga inicial de tablas
    if (window.fetchBudgets) window.fetchBudgets();

    // Buscador con Debounce
    if (searchInput) {
        let timeout;
        searchInput.addEventListener('input', (e) => {
            clearTimeout(timeout);
            timeout = setTimeout(() => window.fetchBudgets({q: e.target.value, page: 1}), 500);
        });
    }

    // Listeners de botones de cabecera
    const btnAddBudget = document.getElementById('btn-add-budget');
    if (btnAddBudget) btnAddBudget.onclick = () => window.openCreateBudget();
});

// --- 3. LÓGICA DE TABLAS Y FILTROS ---
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
            updatePaginationUI();
        });
};

function updatePaginationUI() {
    const meta = document.getElementById('pagination-metadata');
    if (!meta) return;
    const pageInfo = document.getElementById('page-info');
    if (pageInfo) pageInfo.textContent = meta.dataset.total == 0 ? "Sin resultados" : `Mostrando ${meta.dataset.start}-${meta.dataset.end} de ${meta.dataset.total}`;

    document.getElementById('btn-prev').disabled = meta.dataset.hasPrev !== 'true';
    document.getElementById('btn-next').disabled = meta.dataset.hasNext !== 'true';
}

// --- 4. GESTIÓN DE PARTIDAS (CASCADA Y CÓDIGO) ---

function initBudgetFormCascades() {
    const $modal = $('#budget-modal-content');
    // Referencias
    const $program = $('#id_program');
    const $subprogram = $('#id_subprogram');
    const $project = $('#id_project');
    const $activity = $('#id_activity');
    const $spending = $('#id_spending_type_item');
    const $regime = $('#id_regime_item');

    const $displayCode = $('#display-budget-code');
    const $hiddenCode = $('#id_code');

    // 1. Inicializar Select2 con el padre correcto para el z-index
    $modal.find('select').select2({
        width: '100%',
        dropdownParent: $modal.parent()
    });

    // 2. Extracción de Código (Toma lo que está antes del " - ")
    const getCodePart = ($el) => {
        const selectedOption = $el.find('option:selected')[0];
        if (!selectedOption || selectedOption.value === "" || selectedOption.text.includes('---------')) return '';

        // 1. Intentar obtenerlo desde el atributo data-code (inyectado por fetchChildren)
        if (selectedOption.dataset.code) return selectedOption.dataset.code;

        // 2. Intentar parsear el texto si viene como "1.01 - NOMBRE"
        const text = selectedOption.text;
        if (text.includes(' - ')) return text.split(' - ')[0].trim();

        // 3. Si no tiene guion (como los catálogos), es posible que el VALUE sea el ID,
        // pero necesitamos el código. Como Senior fix, si el texto no tiene código,
        // devolveremos un marcador para que sepas que falta configurar ese ítem.
        return text.trim();
    };

    // 3. Actualizar Código Completo (6 niveles)
    const updateFullCode = () => {
        const parts = [
            getCodePart($program),
            getCodePart($subprogram),
            getCodePart($project),
            getCodePart($activity),
            getCodePart($spending),
            getCodePart($regime)
        ].filter(p => p !== '');

        const finalCode = parts.join('.');
        $displayCode.text(finalCode || "00.00.00.00.00.00");
        $hiddenCode.val(finalCode);
    };

    // 4. Carga de datos AJAX (Hierarchy API)
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
                // INYECTAMOS EL CÓDIGO PURO EN EL DATASET
                opt.setAttribute('data-code', item.code);
                $targetSelect.append(opt);
            });

            $targetSelect.prop('disabled', false).trigger('change.select2');
        } catch (e) {
            console.error(e);
        }
    };

    // --- LISTENERS (Usando el evento de Select2) ---

    $program.on('change', () => {
        fetchChildren($program.val(), 'subprogram', $subprogram);
        updateFullCode();
    });

    $subprogram.on('change', () => {
        fetchChildren($subprogram.val(), 'project', $project);
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

window.filterStructureByStatus = function (status) {
    // UI: Manejo visual de opacidad en las tarjetas
    document.querySelectorAll('.stat-card').forEach(c => c.classList.add('opacity-low'));

    // Mapeo de IDs según el HTML que tienes
    const activeId = {
        'all': 'card-struct-all',
        'active': 'card-struct-active',
        'inactive': 'card-struct-inactive'
    }[status] || 'card-struct-all';

    const card = document.getElementById(activeId);
    if (card) card.classList.remove('opacity-low');

    // Lógica: Llamar a la función universal de carga con el nuevo filtro
    if (window.fetchBudgets) {
        window.fetchBudgets({status: status, page: 1});
    }
};
window.filterBudgetByStatus = function (status) {
    // 1. Manejo visual de las tarjetas (Opacidad)
    const allCards = [
        'card-filter-all',
        'card-filter-libre',
        'card-filter-ocupada',
        'card-filter-concurso',
        'card-filter-litigio',
        'card-filter-inactiva'
    ];

    allCards.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.classList.add('opacity-low');
    });

    // 2. Resaltar la tarjeta seleccionada
    const activeId = status === 'all' ? 'card-filter-all' : `card-filter-${status.toLowerCase()}`;
    const activeCard = document.getElementById(activeId);
    if (activeCard) activeCard.classList.remove('opacity-low');

    // 3. Ejecutar la recarga de la tabla vía AJAX con el nuevo estado
    // Asumiendo que fetchBudgets ya maneja el parámetro 'status' en el objeto currentFilters
    window.fetchBudgets({status: status, page: 1});
};
// Vinculación global
window.setupHierarchyListeners = function () {
    initBudgetFormCascades();
};
// --- 5. FUNCIONES GLOBALES DE MODALES ---

window.openCreateBudget = function () {
    const modal = document.getElementById('budget-modal-app');
    modal.classList.remove('hidden');
    document.body.classList.add('no-scroll');
    initBudgetFormCascades();
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

window.closeBudgetModal = function () {
    // 1. Intentar cerrar el modal estático (usado en creación de partidas)
    const staticModal = document.getElementById('budget-modal-app');
    if (staticModal) {
        staticModal.classList.add('hidden');
    }

    // 2. Limpiar el contenedor de inyección (usado en edición y estructura)
    const injectContainer = document.getElementById('modal-inject-container');
    if (injectContainer) {
        injectContainer.innerHTML = '';
    }
    document.body.classList.remove('no-scroll');
};

window.submitBudgetForm = async function (e, url) {
    e.preventDefault();
    const formData = new FormData(e.target);
    try {
        const res = await fetch(url, {
            method: 'POST',
            body: formData,
            headers: {'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': getCookie('csrftoken')}
        });
        const data = await res.json();
        if (data.success) {
            window.closeBudgetModal();
            Toast.fire({icon: 'success', title: data.message});
            window.fetchBudgets();
        } else {
            Toast.fire({icon: 'error', title: 'Revise los errores'});
            // Lógica de visualización de errores err-X...
        }
    } catch (e) {
        console.error(e);
    }
};

// --- 6. ESTRUCTURA PROGRAMÁTICA (MODALES Y TOGGLE) ---
window.openCreateStructure = (modelType, parentId) => {
    fetch(`/budget/structure/create/${modelType}/${parentId}/`)
        .then(res => res.text())
        .then(html => {
            const container = document.getElementById('modal-inject-container');
            container.innerHTML = html;
            container.querySelector('.modal-overlay').classList.remove('hidden');
            document.body.classList.add('no-scroll');
        });
};

window.openEditStructure = (modelType, pk) => {
    fetch(`/budget/structure/edit/${modelType}/${pk}/`)
        .then(res => res.text())
        .then(html => {
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
    const btn = document.getElementById(`btn-toggle-${pk}`);
    const actionText = isActive ? 'desactivar' : 'activar';
    Swal.fire({
        title: `¿Confirmar ${actionText}?`,
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: 'Sí, cambiar',
        customClass: {
            confirmButton: isActive ? 'btn-swal-danger' : 'btn-swal-success',
            cancelButton: 'swal2-cancel btn-swal-cancel'
        }
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
window.openAssignNumberModal = function (pk) {
    fetch(`/budget/assign-number/${pk}/`)
        .then(res => res.text())
        .then(html => {
            const container = document.getElementById('modal-inject-container');
            container.innerHTML = html;
            container.querySelector('.modal-overlay').classList.remove('hidden');
            document.body.classList.add('no-scroll');
        });
};

window.submitAssignNumberForm = async function (e, pk) {
    e.preventDefault();
    const form = e.target;
    const formData = new FormData(form);

    // Limpiar errores
    form.querySelectorAll('.text-error').forEach(el => el.textContent = '');

    try {
        const res = await fetch(`/budget/assign-number/${pk}/`, {
            method: 'POST',
            body: formData,
            headers: {'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': getCookie('csrftoken')}
        });
        const data = await res.json();

        if (data.success) {
            window.closeBudgetModal();
            Toast.fire({icon: 'success', title: data.message});
            // Recargamos la tabla para que el botón desaparezca y se vea el número
            window.fetchBudgets();
        } else {
            if (data.errors) {
                Object.keys(data.errors).forEach(key => {
                    const errDiv = form.querySelector(`#err-${key}`);
                    if (errDiv) errDiv.textContent = data.errors[key][0];
                });
            } else {
                Toast.fire({icon: 'error', title: data.message});
            }
        }
    } catch (err) {
        Toast.fire({icon: 'error', title: 'Error de servidor'});
    }
};
window.openAssignEmployeeModal = function (pk) {
    fetch(`/budget/assign-employee/${pk}/`)
        .then(res => res.text())
        .then(html => {
            const container = document.getElementById('modal-inject-container');
            container.innerHTML = html;
            container.querySelector('.modal-overlay').classList.remove('hidden');
            document.body.classList.add('no-scroll');
        });
};

window.searchEmployee = async function () {
    // 1. Obtener elementos del DOM
    const cedulaInput = document.getElementById('search-cedula');
    const resultCard = document.getElementById('search-result-card');
    const btnSubmit = document.getElementById('btn-submit-assign');
    const resName = document.getElementById('res-name');
    const resEmail = document.getElementById('res-email');
    const resPhoto = document.getElementById('res-photo');
    const hiddenId = document.getElementById('selected-employee-id');

    if (!cedulaInput.value || cedulaInput.value.length < 10) {
        return Toast.fire({icon: 'warning', title: 'Ingrese una cédula válida'});
    }

    try {
        const response = await fetch(`/employee/api/search/?q=${cedulaInput.value}`);
        const data = await response.json();

        if (data.success) {
            // 2. Poblar datos
            resName.textContent = data.full_name;
            resEmail.textContent = data.email;
            hiddenId.value = data.id;

            // 3. Manejar Foto
            if (data.photo_url) {
                resPhoto.innerHTML = `<img src="${data.photo_url}" class="person-avatar" style="width:50px; height:50px; border-radius:50%; object-fit:cover;">`;
            } else {
                resPhoto.innerHTML = `<div class="person-avatar-placeholder" style="width:50px; height:50px; border-radius:50%; background:#3b82f6; color:white; display:flex; align-items:center; justify-content:center; font-weight:bold;">${data.full_name.charAt(0)}</div>`;
            }

            // 4. Mostrar y Habilitar
            resultCard.classList.remove('hidden');
            btnSubmit.disabled = false;
            Toast.fire({icon: 'success', title: 'Empleado verificado'});

        } else {
            // Si el empleado no existe o ya tiene partida
            resultCard.classList.add('hidden');
            btnSubmit.disabled = true;
            Swal.fire({
                title: 'Atención',
                text: data.message,
                icon: 'warning',
                confirmButtonText: 'Entendido',
                customClass: {confirmButton: 'btn-save'},
                buttonsStyling: false
            });
        }
    } catch (e) {
        console.error("Error en búsqueda:", e);
        Toast.fire({icon: 'error', title: 'Error de comunicación con el servidor'});
    }
};

window.submitAssignEmployee = async function (e, pk) {
    e.preventDefault();
    const formData = new FormData(e.target);

    try {
        const res = await fetch(`/budget/assign-employee/${pk}/`, {
            method: 'POST',
            body: formData,
            headers: {'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': getCookie('csrftoken')}
        });
        const data = await res.json();

        if (data.success) {
            window.closeBudgetModal();
            Toast.fire({icon: 'success', title: data.message});
            window.fetchBudgets(); // Recargar tabla
        } else {
            Swal.fire('Error', data.message, 'error');
        }
    } catch (e) {
        Toast.fire({icon: 'error', title: 'Error de servidor'});
    }
};
// apps/budget/static/js/budget.js

// 1. Corregir configuración de SweetAlert global (Idioma)
const swalConfig = {
    confirmButtonText: 'Aceptar',
    cancelButtonText: 'Cancelar', // Forzamos español
    customClass: {
        confirmButton: 'btn-save',
        cancelButton: 'btn-cancel'
    },
    buttonsStyling: false
};

// 2. Modificar buscador para mostrar la foto
window.searchEmployee = async function () {
    const cedula = document.getElementById('search-cedula').value;
    const resultCard = document.getElementById('search-result-card');
    const btnSubmit = document.getElementById('btn-submit-assign');
    const resPhoto = document.getElementById('res-photo'); // Elemento img

    // ... validación de cédula igual ...

    try {
        const response = await fetch(`/employee/api/search/?q=${cedula}`);
        const data = await response.json();

        if (data.success) {
            document.getElementById('res-name').textContent = data.full_name;
            document.getElementById('res-email').textContent = data.email;
            document.getElementById('selected-employee-id').value = data.id;

            // Lógica de Foto: Si no hay, usar iniciales o placeholder
            if (data.photo_url) {
                resPhoto.innerHTML = `<img src="${data.photo_url}" class="person-avatar" alt="Foto">`;
            } else {
                resPhoto.innerHTML = `<div class="person-avatar-placeholder">${data.full_name.charAt(0)}</div>`;
            }

            resultCard.classList.remove('hidden');
            btnSubmit.disabled = false;
        } else {
            // SweetAlert corregido a español
            Swal.fire({
                title: 'No disponible',
                text: data.message,
                icon: 'warning',
                confirmButtonText: 'Entendido'
            });
            resultCard.classList.add('hidden');
        }
    } catch (e) { /* error */
    }
};

// 3. Acción de Liberar Partida
window.openReleaseModal = function (pk) {
    fetch(`/budget/release/${pk}/`)
        .then(res => res.text())
        .then(html => {
            const container = document.getElementById('modal-inject-container');
            container.innerHTML = html;
            container.querySelector('.modal-overlay').classList.remove('hidden');
            document.body.classList.add('no-scroll');
        });
};

window.submitReleaseForm = async function (e, pk) {
    e.preventDefault();
    const formData = new FormData(e.target);
    try {
        const res = await fetch(`/budget/release/${pk}/`, {
            method: 'POST',
            body: formData,
            headers: {'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': getCookie('csrftoken')}
        });
        const data = await res.json();
        if (data.success) {
            window.closeBudgetModal();
            Toast.fire({icon: 'success', title: data.message});
            window.fetchBudgets();
        }
    } catch (e) { /* error */
    }
};

window.openChangeStatusModal = function (pk) {
    fetch(`/budget/change-status/${pk}/`)
        .then(res => res.text())
        .then(html => {
            const container = document.getElementById('modal-inject-container');
            container.innerHTML = html;
            // Inicializar Select2 en el nuevo modal
            $(container).find('.select2-field').select2({
                width: '100%',
                dropdownParent: $(container).find('.modal-overlay')
            });
            container.querySelector('.modal-overlay').classList.remove('hidden');
            document.body.classList.add('no-scroll');
        });
};

window.submitChangeStatusForm = async function (e, pk) {
    e.preventDefault();
    const form = e.target;
    const formData = new FormData(form);

    form.querySelectorAll('.text-error').forEach(el => el.textContent = '');

    try {
        const res = await fetch(`/budget/change-status/${pk}/`, {
            method: 'POST',
            body: formData,
            headers: {'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': getCookie('csrftoken')}
        });
        const data = await res.json();

        if (data.success) {
            window.closeBudgetModal();
            Toast.fire({icon: 'success', title: data.message});
            window.fetchBudgets();
        } else {
            Object.keys(data.errors).forEach(key => {
                const errDiv = document.getElementById(`err-${key}`);
                if (errDiv) errDiv.textContent = data.errors[key][0];
            });
        }
    } catch (err) {
        Toast.fire({icon: 'error', title: 'Error de servidor'});
    }
};