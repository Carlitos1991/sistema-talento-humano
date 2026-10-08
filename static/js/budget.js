/* static/js/budget.js
   Gestión de Partidas Presupuestarias - AJAX estricto sin saltos ni recargas completas
*/

(function () {
    'use strict';

    const budgetState = {
        status: 'all',
        sort: '',
        page: 1
    };

    // Helper para capturar todos los datos del formulario de búsqueda
    function getFilterParams(targetPage = null) {
        const form = document.getElementById('budget-filter-form');
        const params = new URLSearchParams();

        if (form) {
            const formData = new FormData(form);
            for (let [key, val] of formData.entries()) {
                const cleanVal = val ? val.trim() : '';
                if (cleanVal !== '') {
                    params.set(key, cleanVal);
                }
            }
        }

        if (budgetState.status && budgetState.status !== 'all') {
            params.set('status', budgetState.status);
        }

        if (budgetState.sort) {
            params.set('sort', budgetState.sort);
        }

        const pageToApply = targetPage !== null ? targetPage : budgetState.page;
        params.set('page', pageToApply);

        return params;
    }

    // Petición AJAX que preserva la posición del scroll exacta
    function applyBudgetFilters(page = 1) {
        budgetState.page = page;

        const wrapper = document.getElementById('table-content-wrapper');
        if (!wrapper) return;

        const table = wrapper.querySelector('.managed-table');
        const listUrl = table ? table.getAttribute('data-list-url') : window.location.pathname;
        const params = getFilterParams(page);

        // Guardar la posición actual de scroll para evitar cualquier brinco al inicio
        const currentScrollPos = window.scrollY || document.documentElement.scrollTop;

        wrapper.style.opacity = '0.5';
        wrapper.style.pointerEvents = 'none';

        fetch(`${listUrl}?${params.toString()}`, {
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
            .then(async response => {
                const contentType = response.headers.get("content-type");
                if (contentType && contentType.includes("application/json")) {
                    const data = await response.json();
                    return data.html || '';
                }
                return await response.text();
            })
            .then(html => {
                if (!html) return;
                wrapper.innerHTML = html;

                // Mantener exactamente la posición de scroll
                window.scrollTo({top: currentScrollPos, behavior: 'instant'});

                // Actualizar estilo visual en cabeceras ordenadas
                updateSortHeaderStyles();
            })
            .catch(err => {
                console.error("Error al actualizar la tabla de partidas presupuestarias:", err);
            })
            .finally(() => {
                wrapper.style.opacity = '1';
                wrapper.style.pointerEvents = 'auto';
            });
    }

    // Toggle de búsqueda avanzada
    function toggleAdvancedSearch() {
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
            if (window.$ && $.fn.select2) {
                $('#advanced-search-container select.select2').each(function () {
                    $(this).select2({width: '100%'});
                });
            }
        } else {
            container.classList.add('hidden');
            if (icon) {
                icon.classList.remove('fa-chevron-up');
                icon.classList.down?.classList.add('fa-chevron-down');
            }
        }
    }

    // Limpieza de filtros
    function clearFilters() {
        const form = document.getElementById('budget-filter-form');
        if (form) {
            form.reset();
            if (window.$ && $.fn.select2) {
                $(form).find('select.select2').val('').trigger('change');
            }
        }
        filterByStatus('all');
    }

    // Filtrado por Stat Cards (Estado)
    function filterByStatus(status) {
        budgetState.status = status;
        document.querySelectorAll('#budget-stats-row .stat-card').forEach(c => c.classList.add('opacity-low'));

        const activeId = status === 'all' ? 'card-filter-all' : `card-filter-${status.toLowerCase()}`;
        const activeCard = document.getElementById(activeId);
        if (activeCard) activeCard.classList.remove('opacity-low');

        applyBudgetFilters(1);
    }

    // Ordenamiento por columna
    function sortTable(field) {
        if (budgetState.sort === field) {
            budgetState.sort = '-' + field;
        } else if (budgetState.sort === '-' + field) {
            budgetState.sort = '';
        } else {
            budgetState.sort = field;
        }
        applyBudgetFilters(1);
    }

    function updateSortHeaderStyles() {
        const headers = document.querySelectorAll('#table-content-wrapper thead th.sortable-header');
        if (!headers.length) return;

        const currentSort = budgetState.sort || '';
        const isDesc = currentSort.startsWith('-');
        const activeField = currentSort.replace(/^-/, '');

        headers.forEach(th => {
            // 1. Asegurar que exista el elemento de la flecha
            let arrow = th.querySelector('.sort-arrow');
            if (!arrow) {
                arrow = document.createElement('span');
                arrow.className = 'sort-arrow';
                th.appendChild(document.createTextNode(' '));
                th.appendChild(arrow);
            }

            // 2. Comprobar si este th corresponde a la columna ordenada
            const thField = th.dataset.sortField || '';
            const isCurrentColumn = thField !== '' && thField === activeField;

            // 3. Limpiar estados previos
            th.classList.remove('sorted-asc', 'sorted-desc');

            // 4. Aplicar la clase institucional de style.css y el glifo
            if (isCurrentColumn) {
                if (isDesc) {
                    th.classList.add('sorted-desc');
                    arrow.innerText = '↓';
                } else {
                    th.classList.add('sorted-asc');
                    arrow.innerText = '↑';
                }
            } else {
                arrow.innerText = '⇅';
            }
        });
    }

    document.addEventListener('DOMContentLoaded', () => {
        // Inicializar combos Select2
        if (window.$ && $.fn.select2) {
            $('#budget-filter-form select.select2').select2({
                width: '100%'
            });
        }

        // Búsqueda en tiempo real con debounce
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

        // Bloquear submit nativo y enter accidental en el formulario
        const filterForm = document.getElementById('budget-filter-form');
        if (filterForm) {
            filterForm.addEventListener('submit', (e) => {
                e.preventDefault();
                e.stopPropagation();
                applyBudgetFilters(1);
            });

            filterForm.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && e.target.tagName === 'INPUT') {
                    e.preventDefault();
                    applyBudgetFilters(1);
                }
            });
        }

        // Botón toggle de filtros avanzados
        const btnToggle = document.getElementById('btn-toggle-advanced');
        if (btnToggle) {
            btnToggle.addEventListener('click', toggleAdvancedSearch);
        }

        // Botón Limpiar
        const btnClear = document.getElementById('btn-budget-clear');
        if (btnClear) {
            btnClear.addEventListener('click', (e) => {
                e.preventDefault();
                clearFilters();
            });
        }

        // Botón Nueva Partida
        const btnAdd = document.getElementById('btn-add-budget');
        if (btnAdd) {
            btnAdd.addEventListener('click', () => {
                window.openCreateBudgetModal();
            });
        }

        // Clic en Stat Cards (Filtro por estado)
        const statsRow = document.getElementById('budget-stats-row');
        if (statsRow) {
            statsRow.addEventListener('click', (e) => {
                const card = e.target.closest('.stat-card');
                if (card && card.dataset.budgetStatus) {
                    e.preventDefault();
                    filterByStatus(card.dataset.budgetStatus);
                }
            });
        }
    });

    // Delegación de eventos para la tabla y paginación
    document.addEventListener('click', (e) => {
        // 1. Modales en botones de acciones
        const modalBtn = e.target.closest('.btn-ajax-modal');
        if (modalBtn && modalBtn.dataset.modalUrl) {
            e.preventDefault();
            window.openAjaxModal(modalBtn.dataset.modalUrl);
            return;
        }

        // 2. Ordenamiento de cabeceras
        const sortTh = e.target.closest('th.sortable-header[data-sort-field]');
        if (sortTh && sortTh.closest('#table-content-wrapper')) {
            e.preventDefault();
            e.stopPropagation();
            sortTable(sortTh.dataset.sortField);
            return;
        }

        // 3. Paginación AJAX conservando la posición
        const pageBtn = e.target.closest('#js-pagination .page-btn');
        if (pageBtn) {
            if (pageBtn.disabled || pageBtn.classList.contains('disabled')) return;
            const targetPage = parseInt(pageBtn.dataset.page);
            if (!isNaN(targetPage)) {
                e.preventDefault();
                e.stopPropagation();
                e.stopImmediatePropagation();
                applyBudgetFilters(targetPage);
            }
        }
    }, true);

    // Salto directo por input numérico en la paginación
    document.addEventListener('change', (e) => {
        if (e.target && e.target.classList.contains('budget-page-input')) {
            e.preventDefault();
            const page = parseInt(e.target.value) || 1;
            applyBudgetFilters(page);
        }
    });

    document.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && e.target && e.target.classList.contains('budget-page-input')) {
            e.preventDefault();
            const page = parseInt(e.target.value) || 1;
            applyBudgetFilters(page);
        }
    });

    // =========================================================================
    // MODALES Y CASCADAS
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