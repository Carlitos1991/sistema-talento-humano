/* static/js/budget.js
   Gestión de Partidas Presupuestarias - Integrado a main.js
*/

(function () {
    'use strict';

    const budgetState = {
        status: 'all',
        sort: '',
        page: 1
    };

    document.addEventListener('DOMContentLoaded', () => {
        // Inicializar Select2 en los combos de filtro
        if (window.$ && $.fn.select2) {
            $('#budget-filter-form select.select2').select2({
                width: '100%'
            });
        }

        // Búsqueda en tiempo real sobre el input de empleado/cédula/código
        const searchInput = document.getElementById('table-search-budget');
        if (searchInput) {
            let debounceTimer = null;
            searchInput.addEventListener('input', () => {
                clearTimeout(debounceTimer);
                debounceTimer = setTimeout(() => {
                    applyBudgetFilters(1);
                }, 400);
            });
        }
    });

    // Control del acordeón colapsable
    window.toggleBudgetAdvancedSearch = function () {
        const container = document.getElementById('advanced-search-container');
        const icon = document.getElementById('icon-toggle-advanced');
        if (!container) return;

        const isHidden = container.classList.contains('hidden');
        if (isHidden) {
            container.classList.remove('hidden');
            if (icon) {
                icon.classList.remove('fa-chevron-down');
                icon.classList.add('fa-chevron-up');
            }
            // Reajustar anchos de Select2 al desplegar
            if (window.$ && $.fn.select2) {
                $('#advanced-search-container select.select2').each(function () {
                    $(this).select2({width: '100%'});
                });
            }
        } else {
            container.classList.add('hidden');
            if (icon) {
                icon.classList.remove('fa-chevron-up');
                icon.classList.add('fa-chevron-down');
            }
        }
    };

    // Helper para capturar todos los datos del formulario de búsqueda y refrescar la tabla
    function getFilterParams() {
        const form = document.getElementById('budget-filter-form');
        const formData = new FormData(form);
        const params = {};

        for (let [key, val] of formData.entries()) {
            if (val && val.trim() !== '') {
                params[key] = val.trim();
            }
        }

        if (budgetState.status && budgetState.status !== 'all') {
            params.status = budgetState.status;
        }

        if (budgetState.sort) {
            params.sort = budgetState.sort;
        }

        params.page = budgetState.page;
        return params;
    }

    function applyBudgetFilters(page = 1) {
        budgetState.page = page;
        const params = getFilterParams();

        if (typeof window.refreshCurrentTable === 'function') {
            window.refreshCurrentTable(params, updateSortHeaderStyles);
        }
    }

    // 1. Filtrar por Stat Card (Estado)
    window.filterBudgetByStatus = function (status) {
        budgetState.status = status;
        document.querySelectorAll('#budget-stats-row .stat-card').forEach(c => c.classList.add('opacity-low'));

        const activeId = status === 'all' ? 'card-filter-all' : `card-filter-${status.toLowerCase()}`;
        const activeCard = document.getElementById(activeId);
        if (activeCard) activeCard.classList.remove('opacity-low');

        applyBudgetFilters(1);
    };

    // 2. Envío del Formulario de Búsqueda Avanzada
    window.handleBudgetSearchSubmit = function (e) {
        e.preventDefault();
        applyBudgetFilters(1);
    };

    // 3. Limpiar Filtros
    window.clearBudgetFilters = function () {
        const form = document.getElementById('budget-filter-form');
        if (form) {
            form.reset();
            if (window.$ && $.fn.select2) {
                $(form).find('select.select2').val('').trigger('change');
            }
        }
        window.filterBudgetByStatus('all');
    };

    // 4. Paginación
    window.changeBudgetPage = function (page) {
        applyBudgetFilters(page);
    };

    // 5. Ordenamiento de Columnas
    window.sortBudgetTable = function (field) {
        if (budgetState.sort === field) {
            budgetState.sort = '-' + field;
        } else if (budgetState.sort === '-' + field) {
            budgetState.sort = '';
        } else {
            budgetState.sort = field;
        }
        applyBudgetFilters(1);
    };

    function updateSortHeaderStyles() {
        document.querySelectorAll('thead th.sortable-header').forEach(th => {
            th.classList.remove('sorted-asc', 'sorted-desc');
            const arrow = th.querySelector('.sort-arrow');
            if (arrow) arrow.innerText = '⇅';
        });

        if (!budgetState.sort) return;

        const field = budgetState.sort.replace('-', '');
        const isDesc = budgetState.sort.startsWith('-');

        document.querySelectorAll('thead th.sortable-header').forEach(th => {
            if (th.getAttribute('onclick') && th.getAttribute('onclick').includes(`'${field}'`)) {
                th.classList.add(isDesc ? 'sorted-desc' : 'sorted-asc');
                const arrow = th.querySelector('.sort-arrow');
                if (arrow) arrow.innerText = isDesc ? '↓' : '↑';
            }
        });
    }

    // =========================================================================
    // MODAL DE CREACIÓN / EDICIÓN CON CASCADA
    // =========================================================================

    window.initBudgetFormCascades = function () {
        const $modal = $('#modal-root');
        const $program = $modal.find('#id_program'),
            $subprogram = $modal.find('#id_subprogram'),
            $project = $modal.find('#id_project'),
            $activity = $modal.find('#id_activity'),
            $spending = $modal.find('#id_spending_type_item'),
            $regime = $modal.find('#id_regime_item'),
            $displayCode = $modal.find('#display-budget-code'),
            $hiddenCode = $modal.find('#id_code');

        if (!$program.length) return;

        $modal.find('select').select2({
            width: '100%',
            dropdownParent: $modal.find('.modal-body-custom')
        });

        const getCodePart = ($el) => {
            const selected = $el.find('option:selected')[0];
            if (!selected || !selected.value || selected.text.includes('---------')) return '';
            return selected.dataset.code || selected.text.split(' - ')[0].trim();
        };

        const updateFullCode = () => {
            const parts = [
                getCodePart($program), getCodePart($subprogram), getCodePart($project),
                getCodePart($activity), getCodePart($spending), getCodePart($regime)
            ].filter(p => p !== '');
            const finalCode = parts.join('.');
            if ($displayCode.length) $displayCode.text(finalCode || '00.00.00.00.00.00');
            if ($hiddenCode.length) $hiddenCode.val(finalCode);
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
    };

    window.openCreateBudgetModal = function () {
        window.openAjaxModal('/budget/create/', () => {
            window.initBudgetFormCascades();
        });
    };

})();

window.searchEmployee = async function () {
    const cedulaInput = document.getElementById('search-cedula');
    const cedula = cedulaInput ? cedulaInput.value.trim() : '';
    const resultCard = document.getElementById('search-result-card');
    const btnSubmit = document.getElementById('btn-submit-assign');
    const resName = document.getElementById('res-name');
    const resEmail = document.getElementById('res-email');
    const resPhoto = document.getElementById('res-photo');
    const hiddenId = document.getElementById('selected-employee-id');

    if (!cedula || cedula.length < 10) {
        Swal.fire({icon: 'warning', title: 'Cédula inválida', text: 'Ingrese una cédula de 10 dígitos.'});
        return;
    }

    try {
        const res = await fetch(`/employee/api/search/?q=${cedula}`);
        const data = await res.json();
        if (data.success) {
            resName.textContent = data.full_name;
            resEmail.textContent = data.email || 'Sin correo registrado';
            hiddenId.value = data.id;

            resPhoto.innerHTML = data.photo_url
                ? `<img src="${data.photo_url}" class="employee-avatar-img">`
                : `<div class="employee-avatar-placeholder">${data.full_name.charAt(0)}</div>`;

            resultCard.classList.remove('hidden');
            btnSubmit.disabled = false;
        } else {
            resultCard.classList.add('hidden');
            btnSubmit.disabled = true;
            Swal.fire({icon: 'warning', title: 'No disponible', text: data.message});
        }
    } catch (e) {
        console.error(e);
        Swal.fire({icon: 'error', title: 'Error', text: 'Problema al consultar la cédula.'});
    }
};