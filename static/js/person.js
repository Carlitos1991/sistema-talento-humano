/* static/js/apps/person.js */

let vueApp = null;

// --- FUNCIONES GLOBALES (Accesibles desde HTML) ---
window.toggleSearchModal = () => {};

window.applyAdvancedSearch = () => {
    if (vueApp && typeof vueApp.submitPersonFilters === 'function') {
        vueApp.submitPersonFilters();
    }
};

window.resetAdvancedSearch = () => {
    if (vueApp && typeof vueApp.resetFilters === 'function') {
        vueApp.resetFilters();
    }
};

window.closeModalOnOutsideClick = () => {};

window.initializeSelect2 = () => {
    const init = () => {
        if (!window.$ || !$.fn.select2) return;
        const areaSelect = $('#filter_area');
        areaSelect.each(function () {
            try {
                if ($(this).hasClass('select2-hidden-accessible')) {
                    $(this).select2('destroy');
                }
            } catch (error) {
                console.warn('No se pudo reinicializar Select2', error);
            }
        });

        if (!areaSelect.length) return;

        areaSelect.select2({
            width: '100%',
            allowClear: true,
            placeholder: areaSelect.data('placeholder') || 'Dependencia',
            minimumInputLength: parseInt(areaSelect.data('minimum-input-length') || '1', 10) || 1,
            language: {
                inputTooShort: function (args) {
                    const remaining = args.minimum - args.input.length;
                    return `Por favor ingrese ${remaining} carácter${remaining !== 1 ? 'es' : ''} más`;
                },
                noResults: function () {
                    return 'No se encontraron resultados';
                },
                searching: function () {
                    return 'Buscando...';
                }
            },
            ajax: {
                url: areaSelect.data('ajax-url'),
                dataType: 'json',
                delay: 250,
                data: function (params) {
                    return {term: params.term};
                },
                processResults: function (data) {
                    if (Array.isArray(data.results)) {
                        return {results: data.results};
                    }
                    if (Array.isArray(data.units)) {
                        return {
                            results: data.units.map(function (unit) {
                                return {id: String(unit.id), text: unit.name};
                            })
                        };
                    }
                    return {results: []};
                },
                cache: true
            }
        });

        const arrow = document.querySelector('#filter_area + .select2 .select2-selection__arrow b');
        if (arrow) {
            arrow.style.borderColor = '#111827 transparent transparent transparent';
        }
    };

    init();
    setTimeout(init, 0);
};

window.changePage = (page) => {
    if (vueApp) vueApp.fetchPeople(page);
};

window.quickFilterStatus = (statusId) => {
    const statusSelect = document.querySelector('select[name="status"]');
    if (statusSelect) {
        statusSelect.value = statusId;
        $(statusSelect).trigger('change');
    }
    if (vueApp) vueApp.applyQuickFilter(statusId);
};

/**
 * Inicializa el scroll horizontal con flecha en la tabla
 * Detecta si hay scroll y muestra/oculta una flecha para desplazarse al final
 * La flecha se mantiene visible al inicio de la tabla para no depender de ver el final.
 */
window.initTableHorizontalScroll = () => {
    const tableContainer = document.querySelector('.table-container');
    if (!tableContainer) return;

    const table = tableContainer.querySelector('table');
    if (!table) return;

    // Usar el helper nativo de TableManager cuando exista y adaptarlo al listado de personas
    tableContainer.classList.add('table-container-has-scroll-helper');

    let helperGroup = tableContainer.querySelector('.table-scroll-helper-group');
    if (!helperGroup) {
        helperGroup = document.createElement('div');
        helperGroup.className = 'table-scroll-helper-group';

        const startButton = document.createElement('button');
        startButton.type = 'button';
        startButton.className = 'table-scroll-nav-button table-scroll-nav-start';
        startButton.setAttribute('aria-label', 'Ir al inicio de la tabla');
        startButton.title = 'Ir al inicio de la tabla';
        startButton.innerHTML = '<i class="fas fa-angles-left"></i>';

        const endButton = document.createElement('button');
        endButton.type = 'button';
        endButton.className = 'table-scroll-nav-button table-scroll-nav-end';
        endButton.setAttribute('aria-label', 'Ir al final de la tabla');
        endButton.title = 'Ir al final de la tabla';
        endButton.innerHTML = '<i class="fas fa-angles-right"></i>';

        helperGroup.appendChild(startButton);
        helperGroup.appendChild(endButton);
        tableContainer.appendChild(helperGroup);
    }

    // Función para verificar y actualizar el estado del scroll
    const updateScrollIndicator = () => {
        const hasHorizontalScroll = tableContainer.scrollWidth > tableContainer.clientWidth;
        const atStart = tableContainer.scrollLeft <= 4;
        const atEnd = tableContainer.scrollLeft + tableContainer.clientWidth >= tableContainer.scrollWidth - 4;

        const startButton = tableContainer.querySelector('.table-scroll-nav-start');
        const endButton = tableContainer.querySelector('.table-scroll-nav-end');

        tableContainer.classList.toggle('table-scroll-helper-force-visible', hasHorizontalScroll);
        tableContainer.classList.toggle('table-scroll-helper-at-end', hasHorizontalScroll && atEnd && !atStart);

        if (helperGroup) {
            helperGroup.style.left = 'auto';
            helperGroup.style.right = '0.65rem';
            helperGroup.style.top = '0.55rem';
            helperGroup.style.flexDirection = 'row';
            helperGroup.style.gap = '0.35rem';
            helperGroup.style.alignItems = 'center';
            helperGroup.style.padding = '0.2rem 0.35rem';
            helperGroup.style.borderRadius = '999px';
            helperGroup.style.background = 'rgba(15, 23, 42, 0.18)';
            helperGroup.style.backdropFilter = 'blur(2px)';
            helperGroup.style.boxShadow = '0 4px 12px rgba(15, 23, 42, 0.08)';
        }

        if (startButton) {
            startButton.style.display = hasHorizontalScroll && atEnd ? 'inline-flex' : 'none';
            startButton.title = 'Regresar al inicio de la tabla';
            startButton.setAttribute('aria-label', 'Regresar al inicio de la tabla');
            if (!startButton.dataset.bound) {
                startButton.addEventListener('click', () => {
                    tableContainer.scrollTo({left: 0, behavior: 'smooth'});
                });
                startButton.dataset.bound = '1';
            }
        }

        if (endButton) {
            endButton.style.display = hasHorizontalScroll && !atEnd ? 'inline-flex' : 'none';
            endButton.title = 'Ir al final de la tabla';
            endButton.setAttribute('aria-label', 'Ir al final de la tabla');
            endButton.style.width = '28px';
            endButton.style.height = '28px';
            endButton.style.background = 'rgba(14, 165, 233, 0.78)';
            endButton.style.boxShadow = '0 8px 16px rgba(37, 99, 235, 0.16)';
            endButton.style.color = '#ffffff';
            if (!endButton.dataset.bound) {
                endButton.addEventListener('click', () => {
                    tableContainer.scrollTo({
                        left: tableContainer.scrollWidth,
                        behavior: 'smooth'
                    });
                });
                endButton.dataset.bound = '1';
            }
        }
    };
    
    // Actualizar al cargar y cuando se redimensiona
    updateScrollIndicator();
    window.addEventListener('resize', updateScrollIndicator);
    
    // Actualizar cuando el usuario hace scroll
    tableContainer.addEventListener('scroll', updateScrollIndicator);
};

window.sortPersonTable = (thElement) => {
    // Inicializar si no existe
    if (!window._personExport) window._personExport = {};
    
    // Obtener el campo del header
    const field = thElement.getAttribute('data-field');
    if (!field) return;
    
    // Obtener todos los headers (th)
    const allHeaders = document.querySelectorAll('thead tr th');
    let colIndex = -1;
    
    // Buscar el índice del header clickeado
    for (let i = 0; i < allHeaders.length; i++) {
        if (allHeaders[i] === thElement) {
            colIndex = i;
            break;
        }
    }
    
    if (colIndex === -1) return;
    
    const currentSort = window._personExport.sort;
    const isAscending = currentSort && currentSort.col === colIndex && currentSort.asc;
    
    // Actualizar estado del sort
    window._personExport.sort = {
        col: colIndex,
        field: field,
        asc: !isAscending
    };
    
    // Recargar tabla (página 1)
    if (vueApp) vueApp.fetchPeople(1);
};


document.addEventListener('DOMContentLoaded', () => {
    const appElement = document.getElementById('personApp');
    if (!appElement) return;

    const {createApp, ref, onMounted, nextTick} = Vue;
    window._personExport = {
        listUrl: null,
        getFilters: () => ({})
    };
    let urls = {};
    try {
        urls = JSON.parse(appElement.dataset.urls);
        if (window._personExport) window._personExport.listUrl = urls.list;
    } catch (e) {
        console.error(e);
    }
    // Delegación de eventos para el submit del formulario de reubicación
    $(document).on('submit', '#form-relocate-employee', async function (e) {
        e.preventDefault();
        // Buscar el último valor seleccionado
        let finalUnitId = null;
        let finalUnitText = '';
        $('#relocate-combos-wrapper select').each(function () {
            const val = $(this).val();
            if (val) {
                finalUnitId = val;
                finalUnitText = $(this).find('option:selected').text();
            }
        });
        if (!finalUnitId) {
            Swal.fire({
                toast: true,
                position: 'top-end',
                icon: 'warning',
                title: 'Por favor seleccione una unidad administrativa final.',
                showConfirmButton: false,
                timer: 2500
            });
            return;
        }
        const btn = $(this).find('button[type="submit"]');
        const originalText = btn.html();
        btn.prop('disabled', true).html('Guardando...');
        // Usar el área previa guardada globalmente
        let prevUnitText = window.selectedRelocatePersonArea || '';
        // Usar el nombre guardado globalmente
        let personName = window.selectedRelocatePersonName || '';
        $.ajax({
            url: '/person/relocate/',
            method: 'POST',
            headers: {'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]')?.value || window.getCookie('csrftoken')},
            data: {
                person_id: window.selectedRelocatePersonId,
                unit_id: finalUnitId
            },
            success: function (resp) {
                if (resp.success) {
                    // Mensaje HTML personalizado
                    const htmlMsg = `<b>Reubicación exitosa:</b> <span style='font-size:0.95em;font-weight:normal;'>${personName}</span><br><b>pasó de</b> <b>"${prevUnitText}"</b> a <b>"${finalUnitText}"</b>`;
                    Swal.fire({
                        toast: true,
                        position: 'top-end',
                        icon: 'success',
                        html: htmlMsg,
                        showConfirmButton: false,
                        timer: 3500
                    });
                    window.closeRelocateModal();
                    setTimeout(function () {
                        location.reload();
                    }, 1800);
                } else {
                    Swal.fire({
                        toast: true,
                        position: 'top-end',
                        icon: 'error',
                        title: resp.message,
                        showConfirmButton: false,
                        timer: 2500
                    });
                }
            },
            error: function () {
                Swal.fire({
                    toast: true,
                    position: 'top-end',
                    icon: 'error',
                    title: 'Error de conexión con el servidor.',
                    showConfirmButton: false,
                    timer: 2500
                });
            },
            complete: function () {
                btn.prop('disabled', false).html(originalText);
            }
        });
    });
    const app = createApp({
        setup() {
            // --- 1. DEFINICIÓN DE VARIABLES REACTIVAS ---

            // Filtros y Búsqueda
            const activeFilters = ref({});

            // Exponer filtros y URL para exportación completa desde table-export.js
            window._personExport.getFilters = () => activeFilters.value;

            // Vista Rápida
            const loadingQuickView = ref(false);
            const quickViewHtml = ref('');
            const currentDetailUrl = ref('#');

            // Formularios (Crear/Editar)
            const isEditing = ref(false);
            const form = ref({});
            const errors = ref({});
            const photoPreview = ref(null);
            const currentId = ref(null);

            // Credenciales
            const credsForm = ref({username: '', password: '', role: ''});
            const credsErrors = ref({});

            // ----------------------------------------------------
            // 2. BÚSQUEDA RÁPIDA EN BACKEND (como usuarios)
            // ----------------------------------------------------
            const initQuickSearch = () => {
                const form = document.getElementById('personFiltersForm');
                if (!form) return;

                const searchInput = form.querySelector('input[name="q"]');
                const areaSelect = form.querySelector('select[name="area"]');
                const statusSelect = form.querySelector('select[name="is_active"]');
                const clearButton = document.getElementById('personFiltersClear');

                const readFiltersFromForm = () => {
                    const nextFilters = {};
                    const q = (searchInput?.value || '').trim();
                    const area = areaSelect?.value || '';
                    const isActive = statusSelect?.value || '';

                    if (q) nextFilters.q = q;
                    if (area) nextFilters.area = area;
                    if (isActive) nextFilters.is_active = isActive;

                    return nextFilters;
                };

                const submitFilters = () => {
                    activeFilters.value = readFiltersFromForm();
                    fetchPeople(1);
                };

                window.applyPersonFilters = submitFilters;

                form.addEventListener('submit', (event) => {
                    event.preventDefault();
                    submitFilters();
                });

                clearButton?.addEventListener('click', () => {
                    form.reset();
                    const areaSelect = $('#filter_area');
                    if (areaSelect.length) {
                        areaSelect.val(null).trigger('change');
                    }
                    activeFilters.value = {};
                    fetchPeople(1);
                });

                activeFilters.value = readFiltersFromForm();
            };

            // ----------------------------------------------------
            // 3. BÚSQUEDA AVANZADA & PAGINACIÓN (BACKEND)
            // ----------------------------------------------------
            const fetchPeople = async (page = 1) => {
                const params = new URLSearchParams();
                params.append('page', page);

                for (const [key, value] of Object.entries(activeFilters.value)) {
                    if (value) params.append(key, value);
                }
                // Capturar la query usada en esta petición para evitar sobrescribir
                // el input si el usuario ya escribió algo distinto mientras se cargaba
                const requestQuery = activeFilters.value && activeFilters.value.q ? String(activeFilters.value.q) : '';
                // Añadir parámetros de ordenamiento si existen
                if (window._personExport && window._personExport.sort && window._personExport.sort.field) {
                    params.append('sort_field', window._personExport.sort.field);
                    params.append('sort_dir', window._personExport.sort.asc ? 'asc' : 'desc');
                }

                try {
                    const response = await fetch(`${urls.list}?${params.toString()}`, {
                        headers: {'X-Requested-With': 'XMLHttpRequest'}
                    });
                    const data = await response.json();

                    if (data.success) {
                        const container = document.getElementById('tableContainer');
                        if (container) {
                            container.innerHTML = data.html;
                            if (data.stats_html) {
                                const statsRow = document.getElementById('statsRow');
                                if (statsRow) {
                                    statsRow.innerHTML = data.stats_html;
                                }
                            }
                            // Mantener el valor del input si hay búsqueda activa
                            if (typeof addExportButtonsToTables === 'function') {
                                addExportButtonsToTables();
                            }
                            // Inicializar TableManager para la nueva tabla y reaplicar sort si existe
                            const newTable = container.querySelector('.managed-table');
                            if (newTable) {
                                // Crear instancia TableManager para manejar paginación cliente cuando aplique
                                let mgr = null;
                                try {
                                    new TableManager(newTable);
                                    mgr = newTable._tableManager;
                                } catch (e) {
                                    console.error('Error inicializando TableManager:', e);
                                }
                                // Reaplicar clase de sort guardada globalmente y sincronizar el estado interno
                                if (window._personExport && window._personExport.sort) {
                                    const s = window._personExport.sort;
                                    // Sincronizar estado interno del TableManager para que el siguiente
                                    // click alterne correctamente entre asc/desc.
                                    if (mgr) {
                                        try {
                                            mgr.sortCol = parseInt(s.col, 10);
                                            mgr.sortAsc = !!s.asc;
                                        } catch (err) {
                                            console.warn('No se pudo sincronizar estado de orden en TableManager', err);
                                        }
                                    }
                                    const ths = newTable.querySelectorAll('thead th');
                                    const th = ths[s.col];
                                    if (th) {
                                        th.classList.remove('sorted-asc', 'sorted-desc');
                                        th.classList.add(s.asc ? 'sorted-asc' : 'sorted-desc');
                                        const arrow = th.querySelector('.sort-arrow');
                                        if (arrow) arrow.innerText = s.asc ? '↑' : '↓';
                                    }
                                }
                            }
                            // Reinsertar botones Excel/PDF sobre la nueva tabla
                            if (typeof addExportButtonsToTables === 'function') {
                                addExportButtonsToTables();
                            }

                            if (typeof window.applyPersonClientSearchFilter === 'function') {
                                window.applyPersonClientSearchFilter();
                            }

                            // Inicializar scroll horizontal con flecha
                            if (typeof window.initTableHorizontalScroll === 'function') {
                                window.initTableHorizontalScroll();
                            }
                        }
                    }
                } catch (error) {
                    console.error("Error fetching data:", error);
                }
            };

            const handleAdvancedSearch = () => {
                if (typeof window.applyPersonFilters === 'function') {
                    window.applyPersonFilters();
                }
            };

            const resetFilters = () => {
                activeFilters.value = {};
                const form = document.getElementById('personFiltersForm');
                if (form) form.reset();
                fetchPeople(1);
            };

            const applyQuickFilter = (statusId) => {
                const nextFilters = Object.assign({}, activeFilters.value || {});
                if (statusId) {
                    nextFilters.status = String(statusId);
                } else {
                    delete nextFilters.status;
                }
                activeFilters.value = nextFilters;
                fetchPeople(1);
            };

            // ----------------------------------------------------
            // 4. VISTA RÁPIDA (DELEGACIÓN DE EVENTOS)
            // ----------------------------------------------------
            const initTableListeners = () => {
                const container = document.getElementById('tableContainer');
                if (!container) return;

                container.addEventListener('click', (e) => {
                    const btn = e.target.closest('.btn-quick-view, .btn-views-action');
                    if (btn) {
                        e.preventDefault();
                        const personId = btn.dataset.id;
                        if (personId) {
                            openQuickView(personId);
                        }
                    }
                });
            };

            const openQuickView = async (id) => {
                loadingQuickView.value = true;
                quickViewHtml.value = '<div class="p-4 text-center text-gray-500">Cargando información...</div>';
                currentDetailUrl.value = `/employee/detail/${id}/`;

                const modal = document.getElementById('modalQuickViewOverlay');
                showModal(modal);

                try {
                    const res = await fetch(`/person/quick-view/${id}/`);
                    if (res.ok) {
                        quickViewHtml.value = await res.text();
                    } else {
                        const errorText = await res.text();
                        console.error('Error al cargar vista rápida:', res.status, errorText);
                        quickViewHtml.value = '<p class="text-error p-4">No se pudo cargar la información.</p>';
                    }
                } catch (e) {
                    console.error('Error de conexión:', e);
                    quickViewHtml.value = '<p class="text-error p-4">Error de conexión.</p>';
                } finally {
                    loadingQuickView.value = false;
                }
            };

            const closeQuickView = () => {
                const el = document.getElementById('modalQuickViewOverlay');
                hideModal(el);
                // Fallback: asegurar eliminación de no-scroll si no hay overlays visibles
                setTimeout(() => {
                    const overlays = Array.from(document.querySelectorAll('.modal-overlay'));
                    const anyVisible = overlays.some(o => {
                        if (o.classList.contains('hidden')) return false;
                        const cs = window.getComputedStyle(o);
                        return cs.display !== 'none' && cs.visibility !== 'hidden' && cs.opacity !== '0';
                    });
                    if (!anyVisible) document.body.classList.remove('no-scroll');
                }, 80);
            };

            // ----------------------------------------------------
            // 5. MODALES Y FORMULARIOS
            // ----------------------------------------------------
            const showModal = (el) => {
                if (el) {
                    el.classList.remove('hidden');
                    document.body.classList.add('no-scroll');
                }
            };
            const hideModal = (el) => {
                if (el) {
                    el.classList.add('hidden');
                    // Dar un pequeño retardo para asegurar que otros modales reaccionen
                    setTimeout(() => {
                        // Comprobar si existe algún overlay que esté realmente visible
                        const overlays = Array.from(document.querySelectorAll('.modal-overlay'));
                        const anyVisible = overlays.some(o => {
                            if (o.classList.contains('hidden')) return false;
                            const cs = window.getComputedStyle(o);
                            return cs.display !== 'none' && cs.visibility !== 'hidden' && cs.opacity !== '0';
                        });
                        if (!anyVisible) {
                            document.body.classList.remove('no-scroll');
                        }
                    }, 50);
                }
            };

            const getFirstErrorMessage = (value) => {
                if (Array.isArray(value)) return value[0] || '';
                if (typeof value === 'string') return value;
                return 'Campo inválido.';
            };

            const clearPersonFormValidationUI = () => {
                const formEl = document.getElementById('personFormHtml');
                if (!formEl) return;

                formEl.querySelectorAll('input.is-invalid, select.is-invalid, textarea.is-invalid').forEach((el) => {
                    el.classList.remove('is-invalid');
                });

                formEl.querySelectorAll('.field-error-msg').forEach((msgEl) => {
                    msgEl.textContent = '';
                    msgEl.classList.remove('has-message');
                });

                formEl.querySelectorAll('.form-group').forEach((group) => {
                    group.classList.remove('has-error');
                });

                formEl.querySelectorAll('.select2-container .select2-selection.is-invalid').forEach((el) => {
                    el.classList.remove('is-invalid');
                });
            };

            const applyPersonFormErrors = (errorMap) => {
                clearPersonFormValidationUI();

                const formEl = document.getElementById('personFormHtml');
                if (!formEl || !errorMap || typeof errorMap !== 'object') return;

                Object.entries(errorMap).forEach(([fieldName, fieldErrors]) => {
                    if (fieldName === '__all__') return;

                    const field = formEl.querySelector(`[name="${fieldName}"]`);
                    if (!field) return;

                    const message = getFirstErrorMessage(fieldErrors);
                    const group = field.closest('.form-group');

                    field.classList.add('is-invalid');

                    // Si es Select2, marcar también el control visual renderizado.
                    if (field.classList.contains('select2-hidden-accessible')) {
                        const select2Selection = field.nextElementSibling?.querySelector('.select2-selection');
                        if (select2Selection) {
                            select2Selection.classList.add('is-invalid');
                        }
                    }

                    if (group) {
                        group.classList.add('has-error');
                        let errorEl = group.querySelector('.field-error-msg');
                        if (!errorEl) {
                            errorEl = document.createElement('div');
                            errorEl.className = 'field-error-msg';
                            group.appendChild(errorEl);
                        }
                        errorEl.textContent = message;
                        errorEl.classList.add('has-message');
                    }
                });
            };

            const bindPersonFormValidationListeners = () => {
                const formEl = document.getElementById('personFormHtml');
                if (!formEl || formEl.dataset.validationBound === '1') return;

                formEl.dataset.validationBound = '1';

                const clearFieldError = (target) => {
                    if (!target || !target.name) return;

                    target.classList.remove('is-invalid');

                    if (target.classList.contains('select2-hidden-accessible')) {
                        const select2Selection = target.nextElementSibling?.querySelector('.select2-selection');
                        if (select2Selection) {
                            select2Selection.classList.remove('is-invalid');
                        }
                    }

                    const group = target.closest('.form-group');
                    if (group) {
                        const errorEl = group.querySelector('.field-error-msg');
                        if (errorEl) {
                            errorEl.textContent = '';
                            errorEl.classList.remove('has-message');
                        }
                        group.classList.remove('has-error');
                    }

                    if (errors.value && Object.prototype.hasOwnProperty.call(errors.value, target.name)) {
                        delete errors.value[target.name];
                    }
                };

                formEl.addEventListener('input', (event) => {
                    clearFieldError(event.target);
                });

                formEl.addEventListener('change', (event) => {
                    clearFieldError(event.target);
                });
            };

            const submitPersonForm = async () => {
                errors.value = {};
                clearPersonFormValidationUI();
                const formData = new FormData(document.getElementById('personFormHtml'));
                const url = isEditing.value ? urls.update.replace('0', currentId.value) : urls.create;

                try {
                    const res = await fetch(url, {
                        method: 'POST',
                        body: formData,
                        headers: {'X-CSRFToken': window.getCookie('csrftoken')}
                    });
                    const data = await res.json();

                    if (data.success) {
                        if (window.Toast) window.Toast.fire({icon: 'success', title: data.message});
                        hideModal(document.getElementById('modalPersonOverlay'));
                        fetchPeople(1);
                    } else {
                        errors.value = data.errors;
                        applyPersonFormErrors(data.errors);
                        if (window.Toast) window.Toast.fire({icon: 'warning', title: 'Revise el formulario'});
                    }
                } catch (e) {
                    console.error(e);
                    if (window.Toast) window.Toast.fire({icon: 'error', title: 'Error servidor'});
                }
            };

            // Credenciales
            const openCredsModal = (id) => {
                currentId.value = id;
                credsForm.value = {username: '', password: '', role: ''};
                credsErrors.value = {};
                showModal(document.getElementById('modalCredentialsOverlay'));
            };

            const submitCredsForm = async () => {
                credsErrors.value = {};
                const formData = new FormData();
                formData.append('username', credsForm.value.username);
                formData.append('password', credsForm.value.password);
                formData.append('role', credsForm.value.role);

                try {
                    const res = await fetch(urls.createCredentials.replace('0', currentId.value), {
                        method: 'POST',
                        body: formData,
                        headers: {'X-CSRFToken': window.getCookie('csrftoken')}
                    });
                    const data = await res.json();

                    if (data.success) {
                        if (window.Toast) window.Toast.fire({icon: 'success', title: data.message});
                        hideModal(document.getElementById('modalCredentialsOverlay'));
                        fetchPeople(1);
                    } else {
                        credsErrors.value = data.errors;
                    }
                } catch (e) {
                    if (window.Toast) window.Toast.fire({icon: 'error', title: 'Error creando credenciales'});
                }
            };

            const closeModal = () => {
                hideModal(document.getElementById('modalPersonOverlay'));
                hideModal(document.getElementById('modalCredentialsOverlay'));
            };

            // ----------------------------------------------------
            // 6. MANEJO DE SELECT2 Y CASCADA (CORREGIDO)
            // ----------------------------------------------------
            const initModalSelect2 = () => {
                const $selects = $('#modalPersonOverlay select.select2-field');

                // 1. Destruir instancias previas
                $selects.each(function () {
                    if ($(this).hasClass("select2-hidden-accessible")) {
                        $(this).select2('destroy');
                    }
                });

                // 2. Inicializar Select2
                $selects.select2({
                    dropdownParent: $('#modalPersonOverlay'),
                    width: '100%',
                    placeholder: "-- Seleccione --",
                    allowClear: true
                }).on('change', function () {
                    // A. Sincronizar con Vue
                    const fieldName = $(this).attr('name');
                    const newVal = $(this).val();

                    if (form.value && fieldName) {
                        form.value[fieldName] = newVal;
                    }

                    // B. Manejo de Cascada (DIRECTO, SIN DISPATCHEVENT)
                    // Esto evita el bucle infinito "RangeError"
                    const map = {
                        'id_country': 'id_province',
                        'id_province': 'id_canton',
                        'id_canton': 'id_parish'
                    };

                    // Si el select que cambió está en el mapa, cargar hijos
                    if (map[this.id]) {
                        loadLocationChildren(newVal, map[this.id]);
                    }
                });
            };

            // Función auxiliar cascada (Llamada directamente, no por evento)
            const loadLocationChildren = async (parentId, targetSelectId, selectedValue = null) => {
                const target = document.getElementById(targetSelectId);
                if (!target) return;

                // Limpiar visualmente mientras carga
                target.innerHTML = '<option value="">Cargando...</option>';
                if ($(target).hasClass("select2-hidden-accessible")) {
                    $(target).trigger('change.select2'); // Actualizar visual Select2
                }

                if (!parentId) {
                    target.innerHTML = '<option value="">-- Seleccione --</option>';
                    if ($(target).hasClass("select2-hidden-accessible")) $(target).trigger('change.select2');
                    return;
                }

                try {
                    const response = await fetch(`${urls.locations}?parent_id=${parentId}&format=json`, {
                        headers: {'X-Requested-With': 'XMLHttpRequest'}
                    });
                    const data = await response.json();

                    let options = '<option value="">-- Seleccione --</option>';
                    (Array.isArray(data) ? data : data.data || []).forEach(item => {
                        const isSelected = selectedValue == item.id ? 'selected' : '';
                        options += `<option value="${item.id}" ${isSelected}>${item.name}</option>`;
                    });

                    target.innerHTML = options;

                    // Notificar a Select2 que las opciones cambiaron
                    if ($(target).hasClass("select2-hidden-accessible")) {
                        $(target).trigger('change.select2');
                    }

                } catch (error) {
                    console.error("Error ubicaciones:", error);
                    target.innerHTML = '<option value="">Error</option>';
                }
            };

            // ----------------------------------------------------
            // 7. FUNCIONES DEL MODAL (CREAR/EDITAR)
            // ----------------------------------------------------

            const openCreateModal = async () => {
                isEditing.value = false;
                currentId.value = null;
                form.value = {
                    has_disability: false,
                    has_catastrophic_illness: false,
                    is_substitute: false
                };
                errors.value = {};
                photoPreview.value = null;

                const formEl = document.getElementById('personFormHtml');
                if (formEl) formEl.reset();

                clearPersonFormValidationUI();

                showModal(document.getElementById('modalPersonOverlay'));

                await nextTick();

                // Limpiar selects dependientes
                $('#id_province').empty().append('<option value="">-- Seleccione --</option>');
                $('#id_canton').empty().append('<option value="">-- Seleccione --</option>');
                $('#id_parish').empty().append('<option value="">-- Seleccione --</option>');

                initModalSelect2();

                // Asegurar valor por defecto en creación: Tipo de documento = CEDULA
                const documentTypeSelect = document.getElementById('id_document_type');
                if (documentTypeSelect) {
                    const cedulaOption = Array.from(documentTypeSelect.options || []).find((opt) => {
                        const label = (opt.text || '').trim().toUpperCase();
                        return label.includes('CEDULA') || label.includes('CÉDULA');
                    });

                    if (cedulaOption) {
                        documentTypeSelect.value = cedulaOption.value;
                        $(documentTypeSelect).trigger('change.select2');
                        form.value.document_type = cedulaOption.value;
                    }
                }
            };

            const openEditModal = async (id) => {
                isEditing.value = true;
                currentId.value = id;
                errors.value = {};
                clearPersonFormValidationUI();

                try {
                    const res = await fetch(urls.detail.replace('0', id));
                    const json = await res.json();

                    if (json.success) {
                        form.value = json.data;
                        photoPreview.value = json.data.photo_url;

                        showModal(document.getElementById('modalPersonOverlay'));

                        await nextTick();

                        // 1. Cargar Ubicaciones en Cascada (Secuencialmente)
                        if (json.data.country) {
                            await loadLocationChildren(json.data.country, 'id_province', json.data.province);
                        }
                        if (json.data.province) {
                            await loadLocationChildren(json.data.province, 'id_canton', json.data.canton);
                        }
                        if (json.data.canton) {
                            await loadLocationChildren(json.data.canton, 'id_parish', json.data.parish);
                        }

                        // 2. Iniciar Select2
                        initModalSelect2();

                        // 3. Forzar valores visuales
                        for (const [key, value] of Object.entries(json.data)) {
                            const el = $(`[name="${key}"]`);
                            if (el.length && el.hasClass('select2-field')) {
                                el.val(value).trigger('change.select2');
                            }
                        }
                    }
                } catch (e) {
                    console.error(e);
                }
            };

            // --- Reubicación de empleado ---
            window.openRelocateEmployeeModal = function (personId, personFullName, personArea) {
                // 1. Guardar referencias globales
                window.selectedRelocatePersonId = personId;
                window.selectedRelocatePersonName = personFullName;
                window.selectedRelocatePersonArea = personArea;

                // 2. Limpiar modal anterior
                $('#relocate-combos-wrapper').empty();

                // 3. Mostrar el modal (Quitando display:none y clase hidden)
                const modal = document.getElementById('modal-relocate-employee');
                if (modal) {
                    modal.style.display = 'flex';
                    modal.classList.remove('hidden');
                }

                // 4. Cargar nivel raíz (Nivel 1)
                loadUnitLevel(null);
            };

            window.closeRelocateModal = function () {
                const modal = document.getElementById('modal-relocate-employee');
                if (modal) {
                    modal.style.display = 'none';
                    modal.classList.add('hidden'); // Por si usas Tailwind/Bootstrap classes
                }
                // Limpiar selección para evitar errores futuros
                window.selectedRelocatePersonId = null;
                $('#relocate-combos-wrapper').empty();
            };

            function loadUnitLevel(parentId) {
                // Recuperamos la URL del dataset del HTML principal si la variable global urls no está accesible aquí
                let apiUrl = '/institution/api/unit-children/';
                const appEl = document.getElementById('personApp');
                if (appEl) {
                    try {
                        const u = JSON.parse(appEl.dataset.urls);
                        if (u.administrative_units) apiUrl = u.administrative_units;
                    } catch (e) {
                    }
                }

                const params = parentId ? {parent_id: parentId} : {};

                $.ajax({
                    url: apiUrl,
                    data: params,
                    success: function (data) {
                        if (!data.units || data.units.length === 0) return;

                        const uniqueId = 'unit-select-' + (parentId || 'root');
                        const $wrapper = $('<div class="form-group mb-3"></div>');
                        const $label = $('<label class="text-xs font-bold text-gray-600 mb-1 block">Seleccione Unidad:</label>');

                        const $select = $('<select>')
                            .attr('id', uniqueId)
                            .addClass('form-control select2-relocate w-full border p-2 rounded')
                            .css('width', '100%')
                            .append('<option value="">-- Seleccione --</option>');

                        data.units.forEach(function (u) {
                            // El backend debe devolver 'has_children' (true/false)
                            $select.append(`<option value="${u.id}" data-has-children="${u.has_children}">${u.name}</option>`);
                        });

                        $wrapper.append($label).append($select);
                        $('#relocate-combos-wrapper').append($wrapper);

                        // Inicializar Select2 si está disponible
                        if ($.fn.select2) {
                            $select.select2({
                                dropdownParent: $('#modal-relocate-employee'),
                                width: '100%'
                            });
                        }

                        // Evento Change
                        $select.on('change', function () {
                            const val = $(this).val();
                            const hasChild = $(this).find(':selected').data('has-children');

                            // Borrar siguientes niveles
                            $(this).closest('.form-group').nextAll().remove();

                            if (val && (hasChild === true || hasChild === "true" || hasChild === "True")) {
                                loadUnitLevel(val);
                            }
                        });
                    }
                });
            }

            $('#form-relocate-employee').on('submit', function (e) {
                e.preventDefault();
                const selects = $('#relocate-combos-wrapper select');
                const lastSelect = selects.last();
                const unitId = lastSelect.val();
                $.post('/person/relocate/', {
                    person_id: window.selectedRelocatePersonId,
                    unit_id: unitId,
                    csrfmiddlewaretoken: window.getCookie('csrftoken')
                }, function (resp) {
                    window.closeRelocateModal();
                    // Actualizar tabla si es necesario
                });
            });

            // ----------------------------------------------------
            // CICLO DE VIDA
            // ----------------------------------------------------
            onMounted(() => {
                initQuickSearch();
                initTableListeners();
                bindPersonFormValidationListeners();
                window.initializeSelect2();
                if (typeof addExportButtonsToTables === 'function') {
                    addExportButtonsToTables();
                }
                // Inicializar scroll horizontal con flecha
                if (typeof window.initTableHorizontalScroll === 'function') {
                    window.initTableHorizontalScroll();
                }
            });

            return {
                // Métodos
                fetchPeople, handleAdvancedSearch, resetFilters, applyQuickFilter,
                openCreateModal, openEditModal, submitPersonForm,
                openCredsModal, submitCredsForm, closeModal,
                openQuickView, closeQuickView,
                submitPersonFilters: () => {
                    if (typeof window.applyPersonFilters === 'function') {
                        window.applyPersonFilters();
                    }
                },

                // Estado Reactivo
                activeFilters,
                loadingQuickView, quickViewHtml, currentDetailUrl,
                isEditing, form, errors, photoPreview,
                credsForm, credsErrors
            };
        }
    });

    vueApp = app.mount('#personApp');
    // Exponer un wrapper global para la función fetchPeople del app Vue
    window.fetchPeople = (page) => {
        if (vueApp && typeof vueApp.fetchPeople === 'function') {
            return vueApp.fetchPeople(page);
        }
        console.warn('fetchPeople no está inicializado aún');
        return Promise.resolve();
    };

    // Inicializar Select2 para el modal de búsqueda avanzada
    window.initializeSelect2();

    // ========== Sincronizar scrollbar horizontal de la tabla ==========
    window.initTableXScroll = function() {
        const tc = document.querySelector('.table-container');
        if (!tc) return;

        const wrapper = tc.querySelector('.table-horizontal-wrapper');
        const table = tc.querySelector('table.managed-table');
        const xscroll = tc.querySelector('.table-xscroll');
        const xinner = tc.querySelector('.table-xscroll-inner');

        if (!wrapper || !table || !xscroll || !xinner) return;

        let isUserScrolling = false;

        function refreshXScroll() {
            // Establecer ancho del elemento interno igual al ancho de la tabla
            const w = table.scrollWidth;
            xinner.style.width = w + 'px';
            
            // Sincronizar scrollLeft desde wrapper a xscroll
            if (!isUserScrolling) {
                xscroll.scrollLeft = wrapper.scrollLeft;
            }
        }

        // Cuando el usuario mueve el scrollbar superior
        xscroll.addEventListener('scroll', function() {
            isUserScrolling = true;
            wrapper.scrollLeft = xscroll.scrollLeft;
            isUserScrolling = false;
        }, false);

        // Cuando el usuario mueve la tabla (teclado, trackpad, etc)
        wrapper.addEventListener('scroll', function() {
            if (!isUserScrolling) {
                xscroll.scrollLeft = wrapper.scrollLeft;
            }
        }, false);

        // Actualizar cuando la ventana cambie de tamaño
        window.addEventListener('resize', refreshXScroll);

        // Inicializar las dimensiones
        refreshXScroll();
        setTimeout(refreshXScroll, 100);
        setTimeout(refreshXScroll, 500);
    };

    // Ejecutar cuando el DOM está listo
    window.initTableXScroll();
});