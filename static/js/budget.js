/* static/js/budget.js
   Gestión de Partidas Presupuestarias - AJAX estricto, sin recargas y cascadas estables
*/

(function () {
    'use strict';

    const budgetState = {
        status: 'all',
        sort: '',
        page: 1
    };

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

    function applyBudgetFilters(page = 1) {
        budgetState.page = page;

        const wrapper = document.getElementById('table-content-wrapper');
        if (!wrapper) return;

        const table = wrapper.querySelector('.managed-table');
        const listUrl = table ? table.getAttribute('data-list-url') : window.location.pathname;
        const params = getFilterParams(page);

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
                window.scrollTo({top: currentScrollPos, behavior: 'instant'});
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
                icon.classList.add('fa-chevron-down');
            }
        }
    }

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

    function filterByStatus(status) {
        budgetState.status = status;
        document.querySelectorAll('#budget-stats-row .stat-card').forEach(c => c.classList.add('opacity-low'));

        const activeId = status === 'all' ? 'card-filter-all' : `card-filter-${status.toLowerCase()}`;
        const activeCard = document.getElementById(activeId);
        if (activeCard) activeCard.classList.remove('opacity-low');

        applyBudgetFilters(1);
    }

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
            let arrow = th.querySelector('.sort-arrow');
            if (!arrow) {
                arrow = document.createElement('span');
                arrow.className = 'sort-arrow';
                th.appendChild(document.createTextNode(' '));
                th.appendChild(arrow);
            }

            const thField = th.dataset.sortField || '';
            const isCurrentColumn = thField !== '' && thField === activeField;

            th.classList.remove('sorted-asc', 'sorted-desc');

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
        if (window.$ && $.fn.select2) {
            $('#budget-filter-form select.select2').select2({width: '100%'});
        }

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

        const btnToggle = document.getElementById('btn-toggle-advanced');
        if (btnToggle) {
            btnToggle.addEventListener('click', toggleAdvancedSearch);
        }

        const btnClear = document.getElementById('btn-budget-clear');
        if (btnClear) {
            btnClear.addEventListener('click', (e) => {
                e.preventDefault();
                clearFilters();
            });
        }

        const btnAdd = document.getElementById('btn-add-budget');
        if (btnAdd) {
            btnAdd.addEventListener('click', () => {
                window.openCreateBudgetModal();
            });
        }

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
            return;
        }

        const modalBtn = e.target.closest('.btn-ajax-modal');
        if (modalBtn && modalBtn.dataset.modalUrl) {
            e.preventDefault();
            const url = modalBtn.dataset.modalUrl;
            window.openAjaxModal(url, () => {
                window.initBudgetFormCascades();
            });
            return;
        }

        const sortTh = e.target.closest('th.sortable-header[data-sort-field]');
        if (sortTh && sortTh.closest('#table-content-wrapper')) {
            e.preventDefault();
            e.stopPropagation();
            sortTable(sortTh.dataset.sortField);
            return;
        }

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

    // Interceptar envío del formulario modal para que NUNCA navegue a la URL del JSON
    // Interceptar envío del formulario modal para que guarde por AJAX y refresque según la vista
    document.addEventListener('submit', (e) => {
        const form = e.target;
        if (form && form.id === 'budget-item-form') {
            e.preventDefault();
            e.stopPropagation();

            const formData = new FormData(form);
            const csrfToken = form.querySelector('[name=csrfmiddlewaretoken]')?.value || '';

            fetch(form.action, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': csrfToken
                }
            })
                .then(async response => {
                    const data = await response.json();
                    if (response.ok && (data.success || data.status === 'success')) {
                        window.closeModal();
                        if (typeof window.showToast === 'function') {
                            window.showToast(data.message || 'Partida guardada exitosamente.', 'success');
                        }

                        // Si estamos en la vista de DETALLE, recargamos la página para ver los cambios
                        const isDetailPage = !document.getElementById('table-content-wrapper');
                        if (isDetailPage) {
                            setTimeout(() => {
                                window.location.reload();
                            }, 500);
                        } else {
                            // Si estamos en el listado, refrescamos la tabla AJAX
                            applyBudgetFilters(budgetState.page);
                        }
                    } else {
                        let msg = data.message || 'Error al guardar la partida.';
                        if (data.errors) {
                            const errorList = Object.entries(data.errors).map(([k, v]) => `• <b>${k}:</b> ${Array.isArray(v) ? v[0] : v}`);
                            msg = errorList.join('<br>');
                        }
                        if (typeof Swal !== 'undefined') {
                            Swal.fire({icon: 'warning', title: 'Atención', html: msg});
                        }
                    }
                })
                .catch(err => {
                    console.error("Error al procesar formulario de partida:", err);
                    if (typeof Swal !== 'undefined') {
                        Swal.fire({icon: 'error', title: 'Error', text: 'Problema de conexión con el servidor.'});
                    }
                });
        }
    });
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
    // MODAL DE CASCADA Y CÓDIGO GENERADO (COMPLETO Y ESTABLE)
    // =========================================================================
    window.initBudgetFormCascades = function () {
        const modal = document.querySelector('#modal-root .modal-overlay');
        if (!modal) return;

        const form = modal.querySelector('#budget-item-form');
        if (!form) return;

        // Evitar inicializaciones dobles de Select2 y de eventos
        if (form.dataset.cascadesInitialized === 'true') return;
        form.dataset.cascadesInitialized = 'true';

        const $modal = $(modal);
        const $program = $('#id_program', form);
        const $subprogram = $('#id_subprogram', form);
        const $project = $('#id_project', form);
        const $activity = $('#id_activity', form);
        const $spending = $('#id_spending_type_item', form);
        const $regime = $('#id_regime_item', form);
        const displayCode = document.getElementById('display-budget-code');
        const hiddenCode = document.getElementById('id_code');

        if (!$program.length) return;

        // 1. Inicialización limpia y única de Select2
        $modal.find('select').each(function () {
            const $this = $(this);
            if (!$this.hasClass('select2-hidden-accessible')) {
                $this.select2({
                    width: '100%',
                    dropdownParent: $modal
                });
            }
        });

        // 2. Extractor de código (LIMPIO: sin return '' previo)
        const getCodePart = ($el) => {
            if (!$el || !$el.length) return '';
            const val = $el.val();
            if (!val) return '';

            const opt = $el.find('option:selected')[0];
            if (!opt) return '';

            // 1. data-code asignado
            if (opt.dataset && opt.dataset.code) {
                return opt.dataset.code.trim();
            }

            // 2. Extraer del texto (ej. "1.06 - PROCURADURIA SINDICA" -> "1.06")
            const rawText = (opt.textContent || opt.innerText || '').trim();
            if (rawText.includes('---------') || rawText === '') return '';

            const match = rawText.match(/^([0-9.]+)/);
            if (match) {
                return match[1].trim();
            }

            if (rawText.includes('-')) {
                return rawText.split('-')[0].trim();
            }

            return rawText;
        };

        // 3. Recalcular y pintar el código compuesto
        const updateFullCode = () => {
            const parts = [
                getCodePart($program),
                getCodePart($subprogram),
                getCodePart($project),
                getCodePart($activity),
                getCodePart($spending),
                getCodePart($regime)
            ].filter(p => p !== '');

            if (parts.length > 0) {
                const finalCode = parts.join('.');
                if (displayCode) displayCode.textContent = finalCode;
                if (hiddenCode) hiddenCode.value = finalCode;
            } else {
                const existingVal = hiddenCode && hiddenCode.value ? hiddenCode.value.trim() : '';
                if (existingVal && existingVal !== '00.00.00.00.00.00') {
                    if (displayCode) displayCode.textContent = existingVal;
                } else {
                    if (displayCode) displayCode.textContent = '00.00.00.00.00.00';
                }
            }
        };

        // 4. Carga AJAX jerárquica de combos dependientes
        const fetchChildren = (parentId, type, $targetSelect) => {
            if (!parentId) {
                $targetSelect.empty().append(new Option('---------', '')).prop('disabled', true).trigger('change.select2');
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

                    $targetSelect.prop('disabled', false).trigger('change.select2');
                })
                .catch(err => {
                    console.error(`Error consultando niveles para ${type}:`, err);
                });
        };

        // 5. Escuchar solo 'change' (evita doble ejecución con select2:select)
        $program.off('change.budgetCascades').on('change.budgetCascades', function (e) {
            const parentVal = $(this).val();
            $project.empty().append(new Option('---------', '')).prop('disabled', true).trigger('change.select2');
            $activity.empty().append(new Option('---------', '')).prop('disabled', true).trigger('change.select2');
            fetchChildren(parentVal, 'subprogram', $subprogram).then(updateFullCode);
        });

        $subprogram.off('change.budgetCascades').on('change.budgetCascades', function (e) {
            const parentVal = $(this).val();
            $activity.empty().append(new Option('---------', '')).prop('disabled', true).trigger('change.select2');
            fetchChildren(parentVal, 'project', $project).then(updateFullCode);
        });

        $project.off('change.budgetCascades').on('change.budgetCascades', function (e) {
            const parentVal = $(this).val();
            fetchChildren(parentVal, 'activity', $activity).then(updateFullCode);
        });

        $activity.off('change.budgetCascades').on('change.budgetCascades', function () {
            const hasVal = !!$(this).val();
            $spending.prop('disabled', !hasVal).trigger('change.select2');
            updateFullCode();
        });

        $spending.off('change.budgetCascades').on('change.budgetCascades', function () {
            const hasVal = !!$(this).val();
            $regime.prop('disabled', !hasVal).trigger('change.select2');
            updateFullCode();
        });

        $regime.off('change.budgetCascades').on('change.budgetCascades', function () {
            updateFullCode();
        });

        // Habilitar según valores existentes en edición
        if ($activity.val()) $spending.prop('disabled', false).trigger('change.select2');
        if ($spending.val()) $regime.prop('disabled', false).trigger('change.select2');

        // Cálculo inicial para reflejar la partida actual
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

// Observador único sin re-ejecuciones múltiples
const modalObserver = new MutationObserver((mutations) => {
    for (let mutation of mutations) {
        if (mutation.addedNodes.length) {
            const form = document.getElementById('budget-item-form');
            if (form && form.dataset.cascadesInitialized !== 'true') {
                window.initBudgetFormCascades();
                break;
            }
        }
    }
});

document.addEventListener('DOMContentLoaded', () => {
    const modalRoot = document.getElementById('modal-root');
    if (modalRoot) {
        modalObserver.observe(modalRoot, {childList: true, subtree: true});
    }
});