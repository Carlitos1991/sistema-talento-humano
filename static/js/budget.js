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
        if (e.target.closest('[data-action="close-modal"]')) {
            e.preventDefault();
            window.closeModal();
        }
        if (e.target && e.target.id === 'budget-item-form') {
            window.submitAjaxForm(e, () => {
                applyBudgetFilters(budgetState.page);
            });
        }
        // 1. Modales en botones de acciones
        const modalBtn = e.target.closest('.btn-ajax-modal');
        if (modalBtn && modalBtn.dataset.modalUrl) {
            e.preventDefault();
            const url = modalBtn.dataset.modalUrl;

            window.openAjaxModal(url, () => {
                if (document.getElementById('display-budget-code')) {
                    window.initBudgetFormCascades();
                }
            });
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
    // MODAL DE CREACIÓN / EDICIÓN CON CASCADA Y CÓDIGO GENERADO
    // =========================================================================
    window.initBudgetFormCascades = function () {
        const modal = document.querySelector('#modal-root .modal-overlay');
        if (!modal) return;

        // Referencias a los campos
        const $program = $('#id_program', modal);
        const $subprogram = $('#id_subprogram', modal);
        const $project = $('#id_project', modal);
        const $activity = $('#id_activity', modal);
        const $spending = $('#id_spending_type_item', modal);
        const $regime = $('#id_regime_item', modal);
        const displayCode = document.getElementById('display-budget-code');
        const hiddenCode = document.getElementById('id_code');

        if (!$program.length) return;

        // 1. Inicialización limpia de Select2
        $(modal).find('select').each(function () {
            const $this = $(this);
            if ($this.hasClass('select2-hidden-accessible')) {
                $this.select2('destroy');
            }
            $this.select2({
                width: '100%',
                dropdownParent: $(modal).find('.modal-body-custom')
            });
        });

        // 2. Extractor de código robusto (soporta data-code o split por guion)
        const getCodePart = ($el) => {
            if (!$el || !$el.length) return '';
            return '';
            const val = $el.val();
            if (!val) return '';

            const opt = $el.find('option:selected')[0];
            if (!opt) return '';

            if (opt.dataset && opt.dataset.code) {
                return opt.dataset.code.trim();
            }

            const rawText = (opt.textContent || opt.innerText || '').trim();
            if (rawText.includes('---------') || rawText === '') return '';

            // Limpieza de texto (soporta " - ", " – ", o solo el primer bloque)
            if (rawText.includes('-')) {
                return rawText.split('-')[0].trim();
            }

            return rawText;
        };

        // 3. Función unificada para pintar el código
        const updateFullCode = () => {
            const parts = [
                getCodePart($program),
                getCodePart($subprogram),
                getCodePart($project),
                getCodePart($activity),
                getCodePart($spending),
                getCodePart($regime)
            ].filter(p => p !== '');

            const finalCode = parts.length > 0 ? parts.join('.') : '00.00.00.00.00.00';

            if (displayCode) {
                displayCode.textContent = finalCode;
            }
            if (hiddenCode) {
                hiddenCode.value = finalCode;
            }
        };

        // 4. Carga AJAX jerárquica de combos dependientes
        const fetchChildren = (parentId, type, $targetSelect) => {
            if (!parentId) {
                $targetSelect.empty().append(new Option('---------', '')).prop('disabled', true).trigger('change');
                return Promise.resolve();
            }

            return fetch(`/budget/api/hierarchy/?parent_id=${parentId}&target_type=${type}`, {
                headers: {'X-Requested-With': 'XMLHttpRequest'}
            })
                .then(res => res.json())
                .then(data => {
                    $targetSelect.empty().append(new Option('---------', ''));
                    const list = data.results || data || [];

                    list.forEach(item => {
                        const opt = new Option(item.text, item.id);
                        const code = item.code || (item.text.includes('-') ? item.text.split('-')[0].trim() : item.text);
                        opt.setAttribute('data-code', code);
                        $targetSelect.append(opt);
                    });

                    $targetSelect.prop('disabled', false).trigger('change');
                })
                .catch(err => {
                    console.error(`Error consultando niveles para ${type}:`, err);
                });
        };

        // 5. Enlace directo a eventos nativos y de Select2
        // Al cambiar PROGRAMA -> actualiza SUBPROGRAMA y vacía PROYECTO y ACTIVIDAD
        $program.off('select2:select change').on('select2:select change', function (e) {
            if (e.originalEvent || e.type === 'select2:select') {
                const parentVal = $(this).val();
                $project.empty().append(new Option('---------', '')).prop('disabled', true).trigger('change');
                $activity.empty().append(new Option('---------', '')).prop('disabled', true).trigger('change');
                fetchChildren(parentVal, 'subprogram', $subprogram).then(updateFullCode);
            } else {
                updateFullCode();
            }
        });

        // Al cambiar SUBPROGRAMA -> actualiza PROYECTO y vacía ACTIVIDAD
        $subprogram.off('select2:select change').on('select2:select change', function (e) {
            if (e.originalEvent || e.type === 'select2:select') {
                const parentVal = $(this).val();
                $activity.empty().append(new Option('---------', '')).prop('disabled', true).trigger('change');
                fetchChildren(parentVal, 'project', $project).then(updateFullCode);
            } else {
                updateFullCode();
            }
        });

        // Al cambiar PROYECTO -> actualiza ACTIVIDAD
        $project.off('select2:select change').on('select2:select change', function (e) {
            if (e.originalEvent || e.type === 'select2:select') {
                const parentVal = $(this).val();
                fetchChildren(parentVal, 'activity', $activity).then(updateFullCode);
            } else {
                updateFullCode();
            }
        });

        // Al cambiar ACTIVIDAD, TIPO DE GASTO o RÉGIMEN -> recalcula código
        $activity.off('select2:select change').on('select2:select change', function () {
            const hasVal = !!$(this).val();
            $spending.prop('disabled', !hasVal).trigger('change');
            updateFullCode();
        });

        $spending.off('select2:select change').on('select2:select change', function () {
            const hasVal = !!$(this).val();
            $regime.prop('disabled', !hasVal).trigger('change');
            updateFullCode();
        });

        $regime.off('select2:select change').on('select2:select change', function () {
            updateFullCode();
        });

        // Habilitar según valores existentes en caso de edición
        if ($activity.val()) $spending.prop('disabled', false);
        if ($spending.val()) $regime.prop('disabled', false);

        // Disparo inicial
        updateFullCode();
    };
    window.openCreateBudgetModal = function () {
        window.openAjaxModal('/budget/create/', () => {
            window.initBudgetFormCascades();
        });
    };

    window.openEditBudgetModal = function (url) {
        window.openAjaxModal(url, () => {
            window.initBudgetFormCascades();
        });
    };
})();
// Detecta automáticamente cuando el modal de partidas presupuestarias se inyecta en el DOM
const modalObserver = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
        if (mutation.addedNodes.length) {
            const form = document.getElementById('budget-item-form') || document.getElementById('display-budget-code');
            if (form) {
                setTimeout(() => {
                    window.initBudgetFormCascades();
                }, 50);
            }
        }
    });
});

document.addEventListener('DOMContentLoaded', () => {
    const modalRoot = document.getElementById('modal-root');
    if (modalRoot) {
        modalObserver.observe(modalRoot, {childList: true, subtree: true});
    }
});