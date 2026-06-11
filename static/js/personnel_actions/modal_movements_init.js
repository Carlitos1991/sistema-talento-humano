/**
 * Personnel Actions Modal - Movements Initialization
 * Maneja: Cascadas de Unidades Administrativas, Búsqueda de Partidas Presupuestarias
 * Sin Bootstrap - Vanilla JavaScript
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
            this.setupFormSubmit();
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
                        select.focus({preventScroll: true});
                        formGroup.scrollIntoView({behavior: 'smooth', block: 'nearest'});
                    };

                    window.setTimeout(focusAndRevealSelect, 0);

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
            const select = document.getElementById('id_new_budget_line');
            if (!select) return;

            // Inicializar Select2 si está disponible
            if (typeof jQuery !== 'undefined' && jQuery.fn.select2) {
                jQuery(select).select2({
                    placeholder: 'Buscar partida por código o cargo...',
                    width: '100%',
                    ajax: {
                        url: '/personnel_actions/api/search-budget-lines/',
                        dataType: 'json',
                        delay: 300,
                        data: (params) => ({
                            term: params.term
                        }),
                        processResults: (data) => {
                            return {
                                results: data.results || []
                            };
                        }
                    },
                    minimumInputLength: 1
                });

                // Event listener para cambio de selección
                jQuery(select).on('change', (e) => {
                    const selectedData = jQuery(select).select2('data')[0];
                    if (selectedData) {
                        this.selectedBudgetLineId = selectedData.id;
                        this.displayBudgetInfo(selectedData);
                    }
                });
            } else {
                // Fallback sin Select2: búsqueda básica
                console.warn('Select2 not available, using basic search');
                this.initBasicBudgetSearch(select);
            }
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

        setupFormSubmit: function () {
            const form = document.getElementById('form-create-action');
            if (!form) return;

            const originalSubmit = form.onsubmit;
            form.addEventListener('submit', (e) => {
                this.onFormSubmit(form);
            });
        },

        onFormSubmit: function (form) {
            // Guardar los valores seleccionados en inputs ocultos

            if (this.selectedUnitId) {
                let input = document.querySelector('input[name="movement_new_unit"]');
                if (!input) {
                    input = document.createElement('input');
                    input.type = 'hidden';
                    input.name = 'movement_new_unit';
                    form.appendChild(input);
                }
                input.value = this.selectedUnitId;
            }

            if (this.selectedBudgetLineId) {
                let input = document.querySelector('input[name="movement_new_budget_line"]');
                if (!input) {
                    input = document.createElement('input');
                    input.type = 'hidden';
                    input.name = 'movement_new_budget_line';
                    form.appendChild(input);
                }
                input.value = this.selectedBudgetLineId;
            }
        }
    };
    $(document).ready(function () {
        // Escuchar el cambio en el Tipo de Acción
        $('#id_action_type').on('change', function () {
            let typeId = $(this).val();

            if (typeId) {
                // Llamar a tu API (Asegúrate de que la URL coincida con tu urls.py)
                $.get('/ruta-a-tu-api/action-types/' + typeId + '/', function (data) {

                    // Función auxiliar para auto-seleccionar en Select2
                    function setSelect2Value(elementId, id, text) {
                        let element = $('#' + elementId);
                        if (id && text) {
                            // Crear la opción y seleccionarla
                            let newOption = new Option(text, id, true, true);
                            element.append(newOption).trigger('change');
                        } else {
                            // Limpiar si no hay firma por defecto
                            element.val(null).trigger('change');
                        }
                    }

                    // Inyectar las firmas obtenidas
                    setSelect2Value('id_authority_1', data.auth1_id, data.auth1_text);
                    setSelect2Value('id_authority_2', data.auth2_id, data.auth2_text);
                    setSelect2Value('id_reviewer', data.reviewer_id, data.reviewer_text);
                    setSelect2Value('id_register', data.register_id, data.register_text);
                });
            }
        });
    });

    // ==========================================
    // INICIALIZACIÓN AL CARGAR EL DOM
    // ==========================================

    document.addEventListener('DOMContentLoaded', () => {
        // Inicializar cuando el modal esté visible
        const modal = document.getElementById('form-create-action');
        if (modal) {
            PersonnelActionModal.init();
        }
    });

})();
