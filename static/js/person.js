/* static/js/apps/person.js */

let vueApp = null;
window.currentStatFilter = null; // Variable global para guardar el clic de los stats

// =========================================================================
// 1. FILTROS Y RECARGA DE TABLA PARCIAL (Vanilla JS puro, sin cambiar URL)
// =========================================================================
window.applyPersonFilters = async function (page = 1) {
    const form = document.getElementById('personFiltersForm');
    if (!form) return;

    // Leer valores del formulario
    const q = form.querySelector('input[name="q"]')?.value.trim() || '';
    const area = form.querySelector('select[name="area"]')?.value || '';
    const isActive = form.querySelector('select[name="is_active"]')?.value || '';

    // Preparar parámetros (sin tocar la barra de direcciones del navegador)
    const params = new URLSearchParams();
    params.set('page', page);
    if (q) params.set('q', q);
    if (area) params.set('area', area);
    if (isActive) params.set('is_active', isActive);

    // Si hay un filtro desde las tarjetas (stats)
    if (window.currentStatFilter) {
        params.set('status', window.currentStatFilter);
    }

    // Buscar la URL del endpoint desde la tabla o usar la actual
    const listUrl = document.querySelector('.managed-table')?.dataset.listUrl || window.location.pathname;

    // Efecto visual de carga
    const oldTableContainer = document.querySelector('.table-container');
    if (oldTableContainer) {
        oldTableContainer.style.opacity = '0.4';
        oldTableContainer.style.pointerEvents = 'none';
    }

    try {
        const res = await fetch(`${listUrl}?${params.toString()}`, {
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        });

        const contentType = res.headers.get("content-type");
        const html = await (contentType && contentType.includes("application/json") ? res.json().then(d => d.html) : res.text());

        const temp = document.createElement('div');
        temp.innerHTML = html;

        const newTableContainer = temp.querySelector('.table-container');
        const newPagination = temp.querySelector('.pagination-container');
        const oldPagination = document.querySelector('.pagination-container');

        // Reemplazar tabla y paginador
        if (newTableContainer && oldTableContainer) oldTableContainer.replaceWith(newTableContainer);
        if (newPagination && oldPagination) oldPagination.replaceWith(newPagination);

        // Revivir los plugins sobre la tabla nueva
        setTimeout(() => {
            const newTable = document.querySelector('.managed-table');
            if (newTable) new TableManager(newTable);
            if (typeof addExportButtonsToTables === 'function') addExportButtonsToTables();
            if (typeof window.initTableHorizontalScroll === 'function') window.initTableHorizontalScroll();
        }, 50);

    } catch (e) {
        console.error('Error aplicando filtros:', e);
        if (oldTableContainer) {
            oldTableContainer.style.opacity = '1';
            oldTableContainer.style.pointerEvents = 'auto';
        }
    }
};

window.quickFilterStatus = function (statusValue) {
    window.currentStatFilter = statusValue; // Guardamos el filtro de la tarjeta
    window.applyPersonFilters(1);           // Recargamos la tabla
};


// =========================================================================
// 2. UTILIDADES GLOBALES (Select2 y Scroll Horizontal)
// =========================================================================
window.initializeSelect2 = () => {
    if (!window.$ || !$.fn.select2) return;

    const $areaSelect = $('#filter_area');
    if (!$areaSelect.length) return;

    // Limpieza radical para evitar duplicaciones causadas por la reactividad de Vue
    $areaSelect.siblings('.select2-container').remove();
    $areaSelect.removeClass('select2-hidden-accessible');
    $areaSelect.removeAttr('data-select2-id tabindex aria-hidden');
    $areaSelect.find('option').removeAttr('data-select2-id');

    // Inicializar limpio
    $areaSelect.select2({
        width: '100%',
        allowClear: true,
        placeholder: $areaSelect.data('placeholder') || 'Dependencia',
        minimumInputLength: parseInt($areaSelect.data('minimum-input-length') || '1', 10) || 1,
        language: {
            inputTooShort: (args) => {
                const remaining = args.minimum - args.input.length;
                return `Por favor ingrese ${remaining} carácter${remaining !== 1 ? 'es' : ''} más`;
            },
            noResults: () => 'No se encontraron resultados',
            searching: () => 'Buscando...'
        },
        ajax: {
            url: $areaSelect.data('ajax-url'),
            dataType: 'json',
            delay: 250,
            data: (params) => ({term: params.term}),
            processResults: function (data) {
                if (Array.isArray(data.results)) return {results: data.results};
                if (Array.isArray(data.units)) {
                    return {results: data.units.map(unit => ({id: String(unit.id), text: unit.name}))};
                }
                return {results: []};
            },
            cache: true
        }
    });
};

window.initTableHorizontalScroll = () => {
    const tableContainer = document.querySelector('.table-container');
    if (!tableContainer) return;
    const table = tableContainer.querySelector('table');
    if (!table) return;

    tableContainer.classList.add('table-container-has-scroll-helper');
    let helperGroup = tableContainer.querySelector('.table-scroll-helper-group');

    if (!helperGroup) {
        helperGroup = document.createElement('div');
        helperGroup.className = 'table-scroll-helper-group';

        const startButton = document.createElement('button');
        startButton.className = 'table-scroll-nav-button table-scroll-nav-start';
        startButton.innerHTML = '<i class="fas fa-angles-left"></i>';

        const endButton = document.createElement('button');
        endButton.className = 'table-scroll-nav-button table-scroll-nav-end';
        endButton.innerHTML = '<i class="fas fa-angles-right"></i>';

        helperGroup.appendChild(startButton);
        helperGroup.appendChild(endButton);
        tableContainer.appendChild(helperGroup);
    }

    const updateScrollIndicator = () => {
        const hasHorizontalScroll = tableContainer.scrollWidth > tableContainer.clientWidth;
        const atStart = tableContainer.scrollLeft <= 4;
        const atEnd = tableContainer.scrollLeft + tableContainer.clientWidth >= tableContainer.scrollWidth - 4;

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

        const startButton = tableContainer.querySelector('.table-scroll-nav-start');
        if (startButton) {
            startButton.style.display = hasHorizontalScroll && atEnd ? 'inline-flex' : 'none';
            if (!startButton.dataset.bound) {
                startButton.addEventListener('click', () => tableContainer.scrollTo({left: 0, behavior: 'smooth'}));
                startButton.dataset.bound = '1';
            }
        }

        const endButton = tableContainer.querySelector('.table-scroll-nav-end');
        if (endButton) {
            endButton.style.display = hasHorizontalScroll && !atEnd ? 'inline-flex' : 'none';
            endButton.style.width = '28px';
            endButton.style.height = '28px';
            endButton.style.background = 'rgba(14, 165, 233, 0.78)';
            endButton.style.boxShadow = '0 8px 16px rgba(37, 99, 235, 0.16)';
            endButton.style.color = '#ffffff';
            if (!endButton.dataset.bound) {
                endButton.addEventListener('click', () => tableContainer.scrollTo({
                    left: tableContainer.scrollWidth,
                    behavior: 'smooth'
                }));
                endButton.dataset.bound = '1';
            }
        }
    };

    updateScrollIndicator();
    window.addEventListener('resize', updateScrollIndicator);
    tableContainer.addEventListener('scroll', updateScrollIndicator);
};


// =========================================================================
// 3. REUBICACIÓN DE EMPLEADOS
// =========================================================================
window.openRelocateEmployeeModal = function (personId, personFullName, personArea) {
    window.selectedRelocatePersonId = personId;
    window.selectedRelocatePersonName = personFullName;
    window.selectedRelocatePersonArea = personArea;
    $('#relocate-combos-wrapper').empty();

    const modal = document.getElementById('modal-relocate-employee');
    if (modal) {
        modal.style.display = 'flex';
        modal.classList.remove('hidden');
    }
    loadUnitLevel(null);
};

window.closeRelocateModal = function () {
    const modal = document.getElementById('modal-relocate-employee');
    if (modal) {
        modal.style.display = 'none';
        modal.classList.add('hidden');
    }
    window.selectedRelocatePersonId = null;
    $('#relocate-combos-wrapper').empty();
};

function loadUnitLevel(parentId) {
    let apiUrl = '/institution/api/unit-children/';
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

            data.units.forEach(u => {
                $select.append(`<option value="${u.id}" data-has-children="${u.has_children}">${u.name}</option>`);
            });

            $wrapper.append($label).append($select);
            $('#relocate-combos-wrapper').append($wrapper);

            if ($.fn.select2) {
                $select.select2({dropdownParent: $('#modal-relocate-employee'), width: '100%'});
            }

            $select.on('change', function () {
                const val = $(this).val();
                const hasChild = $(this).find(':selected').data('has-children');
                $(this).closest('.form-group').nextAll().remove();
                if (val && (hasChild === true || hasChild === "true" || hasChild === "True")) {
                    loadUnitLevel(val);
                }
            });
        }
    });
}


// =========================================================================
// 4. DELEGACIÓN GLOBAL DE CLICS (Fuera de Vue para que sobrevivan al AJAX)
// =========================================================================
document.addEventListener('click', (e) => {
    // Delegar clic vista rápida
    const btnQuickView = e.target.closest('[data-action="quick-view"], .btn-quick-view');
    if (btnQuickView) {
        e.preventDefault();
        const personId = btnQuickView.dataset.id;
        if (personId && typeof window.openQuickView === 'function') {
            window.openQuickView(personId);
        }
    }
});


// =========================================================================
// 5. INICIALIZACIÓN VUE APP (Modales, Vista Rápida y Formulario)
// =========================================================================
document.addEventListener('DOMContentLoaded', () => {
    const appElement = document.getElementById('personApp');
    if (!appElement) return;

    // Prevención de error si dataset.urls viene vacío o con sintaxis inválida ('undefined')
    let urls = {};
    try {
        const urlsRaw = appElement.getAttribute('data-urls');
        if (urlsRaw && urlsRaw !== 'undefined') {
            urls = JSON.parse(urlsRaw);
        }
    } catch (e) {
        console.warn('Advertencia: No se pudo parsear dataset.urls', e);
    }

    const {createApp, ref, nextTick, onMounted} = Vue;

    const app = createApp({
        setup() {
            // Variables reactivas
            const loadingQuickView = ref(false);
            const quickViewHtml = ref('');
            const currentDetailUrl = ref('#');
            const isEditing = ref(false);
            const form = ref({});
            const errors = ref({});
            const photoPreview = ref(null);
            const currentId = ref(null);
            const credsForm = ref({username: '', password: '', role: ''});
            const credsErrors = ref({});

            // ----------------------------------------------------
            // EJECUCIÓN POST-CARGA DE VUE
            // ----------------------------------------------------
            onMounted(() => {
                // Al ejecutarse aquí, Vue ya renderizó el HTML, evitando que destruya nuestros plugins
                window.initializeSelect2();

                if (typeof window.initTableHorizontalScroll === 'function') {
                    window.initTableHorizontalScroll();
                }

                // Asignar listeners del buscador
                document.getElementById('personFiltersForm')?.addEventListener('submit', (e) => {
                    e.preventDefault();
                    window.applyPersonFilters(1);
                });

                document.getElementById('personFiltersClear')?.addEventListener('click', () => {
                    const formFilters = document.getElementById('personFiltersForm');
                    if (formFilters) formFilters.reset();

                    window.currentStatFilter = null; // Limpiar selección de los stats
                    const $areaSelect = $('#filter_area');
                    if ($areaSelect.length) $areaSelect.val(null).trigger('change');

                    window.applyPersonFilters(1);
                });

                // Listener formulario reubicación
                $(document).off('submit', '#form-relocate-employee').on('submit', '#form-relocate-employee', function (e) {
                    e.preventDefault();
                    let finalUnitId = null;
                    $('#relocate-combos-wrapper select').each(function () {
                        if ($(this).val()) finalUnitId = $(this).val();
                    });

                    if (!finalUnitId) {
                        Swal.fire({
                            toast: true,
                            position: 'top-end',
                            icon: 'warning',
                            title: 'Seleccione una unidad administrativa',
                            showConfirmButton: false,
                            timer: 2500
                        });
                        return;
                    }
                    const btn = $(this).find('button[type="submit"]');
                    const originalText = btn.html();
                    btn.prop('disabled', true).html('Guardando...');

                    $.ajax({
                        url: '/person/relocate/',
                        method: 'POST',
                        headers: {'X-CSRFToken': typeof getCSRF === 'function' ? getCSRF() : ''},
                        data: {person_id: window.selectedRelocatePersonId, unit_id: finalUnitId},
                        success: function (resp) {
                            if (resp.success) {
                                Swal.fire({
                                    toast: true,
                                    position: 'top-end',
                                    icon: 'success',
                                    title: 'Reubicación exitosa',
                                    showConfirmButton: false,
                                    timer: 3500
                                });
                                window.closeRelocateModal();
                                setTimeout(() => location.reload(), 1800);
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
                        complete: function () {
                            btn.prop('disabled', false).html(originalText);
                        }
                    });
                });
            });

            // ----------------------------------------------------
            // LÓGICA DE MODALES
            // ----------------------------------------------------
            const openQuickView = async (id) => {
                loadingQuickView.value = true;
                quickViewHtml.value = '<div class="p-4 text-center text-gray-500">Cargando información...</div>';
                currentDetailUrl.value = `/employee/detail/${id}/`;
                showModal(document.getElementById('modalQuickViewOverlay'));

                try {
                    const res = await fetch(`/person/quick-view/${id}/`);
                    if (res.ok) {
                        quickViewHtml.value = await res.text();
                    } else {
                        quickViewHtml.value = '<p class="text-error p-4">No se pudo cargar la información.</p>';
                    }
                } catch (e) {
                    quickViewHtml.value = '<p class="text-error p-4">Error de conexión.</p>';
                } finally {
                    loadingQuickView.value = false;
                }
            };

            const closeQuickView = () => hideModal(document.getElementById('modalQuickViewOverlay'));

            const showModal = (el) => {
                if (el) {
                    const scrollBarWidth = window.innerWidth - document.documentElement.clientWidth;
                    if (scrollBarWidth > 0) document.body.style.paddingRight = `${scrollBarWidth}px`;
                    el.classList.remove('hidden');
                    document.body.classList.add('no-scroll');
                }
            };

            const hideModal = (el) => {
                if (el) {
                    el.classList.add('hidden');
                    setTimeout(() => {
                        const overlays = Array.from(document.querySelectorAll('.modal-overlay'));
                        const anyVisible = overlays.some(o => !o.classList.contains('hidden'));
                        if (!anyVisible) {
                            document.body.classList.remove('no-scroll');
                            document.body.style.paddingRight = '';
                        }
                    }, 50);
                }
            };

            const closeModal = () => {
                hideModal(document.getElementById('modalPersonOverlay'));
                hideModal(document.getElementById('modalCredentialsOverlay'));
            };

            const clearPersonFormValidationUI = () => {
                const formEl = document.getElementById('personFormHtml');
                if (!formEl) return;
                formEl.querySelectorAll('input.is-invalid, select.is-invalid, textarea.is-invalid').forEach(el => el.classList.remove('is-invalid'));
                formEl.querySelectorAll('.field-error-msg').forEach(msgEl => {
                    msgEl.textContent = '';
                    msgEl.classList.remove('has-message');
                });
                formEl.querySelectorAll('.form-group').forEach(group => group.classList.remove('has-error'));
                formEl.querySelectorAll('.select2-container .select2-selection.is-invalid').forEach(el => el.classList.remove('is-invalid'));
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
                        headers: {'X-CSRFToken': typeof getCSRF === 'function' ? getCSRF() : ''}
                    });
                    const data = await res.json();

                    if (data.success) {
                        if (window.Toast) window.Toast.fire({icon: 'success', title: data.message});
                        hideModal(document.getElementById('modalPersonOverlay'));
                        window.applyPersonFilters(1);
                    } else {
                        errors.value = data.errors;
                        if (window.Toast) window.Toast.fire({icon: 'warning', title: 'Revise el formulario'});
                    }
                } catch (e) {
                    if (window.Toast) window.Toast.fire({icon: 'error', title: 'Error servidor'});
                }
            };

            const initModalSelect2 = () => {
                const $selects = $('#modalPersonOverlay select.select2-field');
                $selects.each(function () {
                    if ($(this).hasClass("select2-hidden-accessible")) $(this).select2('destroy');
                });
                $selects.select2({
                    dropdownParent: $('#modalPersonOverlay'),
                    width: '100%',
                    placeholder: "-- Seleccione --",
                    allowClear: true
                }).on('change', function () {
                    const fieldName = $(this).attr('name');
                    if (form.value && fieldName) form.value[fieldName] = $(this).val();
                });
            };

            const openCreateModal = async () => {
                isEditing.value = false;
                currentId.value = null;
                form.value = {has_disability: false, has_catastrophic_illness: false, is_substitute: false};
                errors.value = {};
                photoPreview.value = null;

                const formEl = document.getElementById('personFormHtml');
                if (formEl) formEl.reset();

                showModal(document.getElementById('modalPersonOverlay'));
                await nextTick();
                initModalSelect2();
            };

            const openEditModal = async (id) => {
                isEditing.value = true;
                currentId.value = id;
                errors.value = {};

                try {
                    const res = await fetch(urls.detail.replace('0', id));
                    const json = await res.json();
                    if (json.success) {
                        form.value = json.data;
                        photoPreview.value = json.data.photo_url;
                        showModal(document.getElementById('modalPersonOverlay'));
                        await nextTick();
                        initModalSelect2();
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

            // EXPOSICIÓN GLOBAL A LA VENTANA PARA QUE LOS BOTONES HTML RESPONDAN
            window.openCreateModal = openCreateModal;
            window.openEditModal = openEditModal;
            window.openQuickView = openQuickView;
            window.closeQuickView = closeQuickView;

            return {
                loadingQuickView, quickViewHtml, currentDetailUrl,
                isEditing, form, errors, photoPreview,
                credsForm, credsErrors,
                submitPersonForm, closeModal,
                openCreateModal // Exponer al template de Vue
            };
        }
    });

    vueApp = app.mount('#personApp');
});