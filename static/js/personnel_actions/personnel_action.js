document.addEventListener('DOMContentLoaded', function () {
    const tableContainer = document.getElementById('table-content-wrapper');
    const searchInput = document.getElementById('table-search');

    if (!tableContainer || !searchInput) {
        return;
    }

    const table = tableContainer.querySelector('.managed-table');
    const listUrl = table?.dataset.listUrl || window.location.pathname;

    if (!table) {
        return;
    }

    tableContainer.addEventListener('click', function (e) {
        const generateBtn = e.target.closest('.js-generate-action');
        if (generateBtn) {
            e.preventDefault();
            openAjaxModal(
                `/personnel_actions/create/?employee_id=${generateBtn.dataset.employeeId}`,
                () => PersonnelActionModal.init()
            );
            return;
        }

        const historyBtn = e.target.closest('.js-view-history');
        if (historyBtn) {
            e.preventDefault();
            window.location.href = `/personnel_actions/history/${historyBtn.dataset.employeeId}/`;
        }
    });

    let timeout = null;
    searchInput.addEventListener('input', function () {
        clearTimeout(timeout);
        timeout = setTimeout(() => {
            const q = searchInput.value.trim();
            const params = new URLSearchParams(window.location.search);
            params.set('page', '1');
            if (q) params.set('q', q); else params.delete('q');

            fetch(`${listUrl}?${params.toString()}`, {
                headers: {'X-Requested-With': 'XMLHttpRequest'}
            })
                .then(async (response) => {
                    const contentType = response.headers.get('content-type');
                    if (contentType && contentType.includes('application/json')) {
                        const data = await response.json();
                        return data.html || '';
                    }
                    return await response.text();
                })
                .then((html) => {
                    if (!html) return;
                    tableContainer.innerHTML = html;
                    const newTable = tableContainer.querySelector('.managed-table');
                    if (newTable) {
                        new TableManager(newTable);
                    }
                })
                .catch((err) => console.error('Error al buscar empleados:', err));
        }, 300);
    });
});
/**
 * Maneja: Cascadas de Unidades Administrativas, Búsqueda de Partidas Presupuestarias
 */

(function () {
    'use strict';

    // ==========================================
    // FUNCIÓN GLOBAL PARA ACORDEONES
    // ==========================================
    window.toggleAccordion = function (accordionId, buttonElement) {
        const accordionItem = buttonElement.closest('.accordion-item');
        const content = accordionItem.querySelector('.accordion-content');

        // Toggle clases
        buttonElement.classList.toggle('active');
        content.classList.toggle('show');
    };

    // ==========================================
    // OBJETO PERSONALACTL IONMODAL
    // ==========================================

    window.PersonnelActionModal = {
        selectedUnitId: null,
        selectedBudgetLineId: null,

        init: function () {
            this.initReubicarCascade();
            this.initBudgetLineSearch();
            this.initSignatureSelects();
        },

        // ==========================================
        // CASCADA DE UNIDADES ADMINISTRATIVAS
        // ==========================================

        initReubicarCascade: function () {
            const wrapper = document.getElementById('reubicar-combos-wrapper');
            if (!wrapper) return;

            // Limpiar contenido anterior
            const existingSelects = wrapper.querySelectorAll('.form-group');
            existingSelects.forEach(el => el.remove());

            // Cargar el primer nivel de unidades administrativas
            this.loadUnitLevel(null, wrapper);
        },

        clearDescendantGroups: function (groupElement) {
            if (!groupElement) return;

            let nextSibling = groupElement.nextElementSibling;
            while (nextSibling) {
                const toRemove = nextSibling;
                nextSibling = nextSibling.nextElementSibling;
                toRemove.remove();
            }
        },

        loadUnitLevel: function (parentId, wrapper, insertAfterGroup = null) {
            const self = this;
            const url = '/personnel_actions/api/unit-children/' + (parentId ? '?parent_id=' + parentId : '');

            fetch(url, {
                headers: {'X-Requested-With': 'XMLHttpRequest'}
            })
                .then(res => res.json())
                .then(data => {
                    if (!data.success || !data.units || data.units.length === 0) {
                        console.warn('No units found for parent:', parentId);
                        return;
                    }

                    // Crear wrapper del select
                    const formGroup = document.createElement('div');
                    formGroup.className = 'form-group';

                    const label = document.createElement('label');
                    label.className = 'form-label';
                    label.textContent = 'Seleccione Unidad:';

                    const select = document.createElement('select');
                    select.className = 'input-field form-control';
                    select.style.width = '100%';

                    // Opción por defecto
                    const defaultOption = document.createElement('option');
                    defaultOption.value = '';
                    defaultOption.textContent = '-- Seleccione --';
                    select.appendChild(defaultOption);

                    // Agregar opciones de unidades
                    data.units.forEach(unit => {
                        const option = document.createElement('option');
                        option.value = unit.id;
                        option.textContent = unit.name;
                        option.setAttribute('data-has-children', unit.has_children);
                        select.appendChild(option);
                    });

                    formGroup.appendChild(label);
                    formGroup.appendChild(select);

                    if (insertAfterGroup) {
                        insertAfterGroup.insertAdjacentElement('afterend', formGroup);
                    } else {
                        wrapper.appendChild(formGroup);
                    }

                    const focusAndRevealSelect = function () {
                        if (!parentId) {
                            select.focus({preventScroll: true});
                        } else {
                            select.focus({preventScroll: true});
                            formGroup.scrollIntoView({behavior: 'smooth', block: 'nearest'});
                        }
                    };

                    window.setTimeout(focusAndRevealSelect, 100);

                    // Event listener para cambio de selección
                    select.addEventListener('change', (e) => {
                        const val = e.target.value;
                        const hasChildren = e.target.selectedOptions[0]?.getAttribute('data-has-children') === 'true';

                        self.selectedUnitId = val || null;

                        // Siempre borrar los niveles dependientes del combo actual
                        self.clearDescendantGroups(formGroup);

                        // Si tiene hijos, cargar el siguiente nivel justo debajo del actual
                        if (val && hasChildren) {
                            self.loadUnitLevel(val, wrapper, formGroup);
                        }
                    });
                })
                .catch(err => {
                    console.error('Error loading units:', err);
                });
        },

        // ==========================================
        // BÚSQUEDA DE PARTIDAS PRESUPUESTARIAS
        // ==========================================

        initBudgetLineSearch: function () {
            const selectElement = document.getElementById('id_new_budget_line');
            if (!selectElement) return;

            const $select = $(selectElement);
            const $modal = $select.closest('.modal-container-medium');

            if (typeof jQuery !== 'undefined' && jQuery.fn.select2) {
                if ($select.hasClass('select2-hidden-accessible')) {
                    $select.select2('destroy');
                }

                $select.select2({
                    placeholder: '-- Busque por código o cargo --',
                    allowClear: true,
                    width: '100%',
                    dropdownParent: $modal.length ? $modal : $(document.body),
                    minimumInputLength: 0,
                    ajax: {
                        url: '/personnel_actions/api/search-budget-lines/',
                        dataType: 'json',
                        delay: 250,
                        data: function (params) {
                            return {term: params.term || ''};
                        },
                        processResults: function (data) {
                            console.log('Partidas recibidas:', data.results); // Verifica la respuesta aquí
                            return {results: data.results || []};
                        },
                        error: function (xhr, status, error) {
                            console.error('Error al consultar partidas:', error, xhr.responseText);
                        },
                        cache: true
                    }
                });

                $select.on('select2:select', (e) => {
                    const data = e.params.data;
                    if (data) {
                        this.selectedBudgetLineId = data.id;
                        this.displayBudgetInfo(data);
                    }
                });

                $select.on('select2:clear', () => {
                    this.selectedBudgetLineId = null;
                    const infoBox = document.getElementById('budget-info');
                    if (infoBox) infoBox.classList.remove('show');
                });
            }
        },
        initSignatureSelects: function () {
            if (typeof jQuery === 'undefined' || !jQuery.fn.select2) return;

            jQuery('.action-signature-select').each(function () {
                const $select = jQuery(this);

                if ($select.hasClass('select2-hidden-accessible')) {
                    return;
                }

                $select.select2({
                    width: '100%',
                    placeholder: 'Seleccione una firma',
                    allowClear: true
                });
            });
        },

        initBasicBudgetSearch: function (select) {
            // Búsqueda simple sin Select2
            const input = document.createElement('input');
            input.type = 'text';
            input.placeholder = 'Buscar partida...';
            input.className = 'input-field form-control';
            input.style.marginBottom = '10px';

            select.parentNode.insertBefore(input, select);
            select.style.display = 'none';

            let searchTimeout;
            input.addEventListener('input', (e) => {
                clearTimeout(searchTimeout);
                const term = e.target.value.trim();

                if (term.length < 1) {
                    select.innerHTML = '<option value="">-- Seleccione una partida --</option>';
                    return;
                }

                searchTimeout = setTimeout(() => {
                    fetch('/personnel_actions/api/search-budget-lines/?term=' + encodeURIComponent(term), {
                        headers: {'X-Requested-With': 'XMLHttpRequest'}
                    })
                        .then(res => res.json())
                        .then(data => {
                            select.innerHTML = '<option value="">-- Resultados --</option>';
                            (data.results || []).forEach(item => {
                                const option = document.createElement('option');
                                option.value = item.id;
                                option.textContent = item.text;
                                option.setAttribute('data-code', item.code);
                                option.setAttribute('data-position', item.position);
                                option.setAttribute('data-remuneration', item.remuneration);
                                option.setAttribute('data-program', item.program);
                                select.appendChild(option);
                            });
                            select.style.display = 'block';
                        });
                }, 300);
            });

            select.addEventListener('change', (e) => {
                const option = e.target.selectedOptions[0];
                if (option && option.value) {
                    this.selectedBudgetLineId = option.value;
                    const data = {
                        id: option.value,
                        code: option.getAttribute('data-code'),
                        position: option.getAttribute('data-position'),
                        remuneration: option.getAttribute('data-remuneration'),
                        program: option.getAttribute('data-program')
                    };
                    this.displayBudgetInfo(data);
                    input.value = option.textContent;
                    select.style.display = 'none';
                }
            });
        },

        displayBudgetInfo: function (budgetData) {
            // Mostrar información de la partida seleccionada
            const infoBox = document.getElementById('budget-info');
            if (!infoBox) return;

            document.getElementById('budget-code').textContent = budgetData.code || '-';
            document.getElementById('budget-position').textContent = budgetData.position || '-';
            document.getElementById('budget-remuneration').textContent = '$' + (budgetData.remuneration || '0.00');
            document.getElementById('budget-program').textContent = budgetData.program || '-';

            infoBox.classList.add('show');
        },

        // ==========================================
        // CONFIGURACIÓN DEL FORMULARIO
        // ==========================================

        onFormSubmit: function (form) {
            if (this.selectedUnitId) {
                let input = form.querySelector('input[name="movement_new_unit"]');
                if (!input) {
                    input = document.createElement('input');
                    input.type = 'hidden';
                    input.name = 'movement_new_unit';
                    form.appendChild(input);
                }
                input.value = this.selectedUnitId;
            }
        }
    };
    $(document).on('change', '#id_action_type', function () {
        const form = document.getElementById('form-create-action');
        const isCreateMode = !form || form.dataset.formMode !== 'edit';
        const alertBox = document.getElementById('acting-action-alert');

        let typeId = $(this).val();

        if (!typeId) {
            if (alertBox) alertBox.classList.add('hidden');
            return;
        }

        $.get('/personnel_actions/types/api/detail/' + typeId + '/', function (data) {
            if (!data || !data.success) return;

            const unitSection = document.getElementById('section-unit-movement');
            const budgetSection = document.getElementById('section-budget-movement');

            // Visibilidad dinámica de Reubicación de Unidad
            if (unitSection) {
                if (data.requires_unit) {
                    unitSection.classList.remove('hidden');
                } else {
                    unitSection.classList.add('hidden');
                    // Limpiar selección de unidad si ya no aplica
                    window.PersonnelActionModal.selectedUnitId = null;
                }
            }

            // Visibilidad dinámica de Cambio / Asignación de Partida
            if (budgetSection) {
                if (data.requires_budget) {
                    budgetSection.classList.remove('hidden');
                } else {
                    budgetSection.classList.add('hidden');
                    // Limpiar selección de Select2 si ya no aplica
                    $('#id_new_budget_line').val(null).trigger('change');
                    const infoBox = document.getElementById('budget-info');
                    if (infoBox) infoBox.classList.remove('show');
                }
            }
        });
    });
})();