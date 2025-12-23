/* static/js/institution.js */

document.addEventListener('DOMContentLoaded', () => {
    const {createApp, ref, nextTick} = Vue;
    const tableContainer = document.getElementById('table-content-wrapper');
    const searchInput = document.getElementById('table-search');
    let currentFilters = {q: '', status: 'all', page: 1};

    // Configuración Toast (Superior Derecha)
    const Toast = Swal.mixin({
        toast: true,
        position: 'top-end',
        showConfirmButton: false,
        timer: 3000,
        timerProgressBar: true,
        didOpen: (toast) => {
            toast.addEventListener('mouseenter', Swal.stopTimer);
            toast.addEventListener('mouseleave', Swal.resumeTimer);
        }
    });

    // =========================================================
    // 1. LÓGICA DE TABLA
    // =========================================================
    window.fetchUnits = function (params = {}) {
        if (params.reset) currentFilters = {q: '', status: 'all', page: 1};
        else Object.assign(currentFilters, params);

        const url = new URL(window.location.href);
        Object.keys(currentFilters).forEach(key => {
            if (currentFilters[key]) url.searchParams.set(key, currentFilters[key]);
        });

        fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
            .then(res => res.text())
            .then(html => {
                if (tableContainer) {
                    tableContainer.innerHTML = html;
                    updatePaginationUI();
                }
            });
    };

    function updatePaginationUI() {
        const meta = document.getElementById('pagination-metadata');
        if (!meta) return;
        const total = meta.dataset.total, start = meta.dataset.start, end = meta.dataset.end,
            page = parseInt(meta.dataset.page);

        const pageInfo = document.getElementById('page-info');
        if (pageInfo) pageInfo.textContent = total == 0 ? "Sin resultados" : `Mostrando ${start}-${end} de ${total}`;

        const pageDisplay = document.getElementById('current-page-display');
        if (pageDisplay) pageDisplay.textContent = page;

        const btnPrev = document.getElementById('btn-prev');
        const btnNext = document.getElementById('btn-next');
        if (btnPrev) btnPrev.disabled = meta.dataset.hasPrev !== 'true';
        if (btnNext) btnNext.disabled = meta.dataset.hasNext !== 'true';
    }

    if (searchInput) {
        let timeout;
        searchInput.addEventListener('input', (e) => {
            clearTimeout(timeout);
            timeout = setTimeout(() => window.fetchUnits({q: e.target.value, page: 1}), 500);
        });
    }

    window.filterByStatus = function (status) {
        document.querySelectorAll('.stat-card').forEach(c => c.classList.add('opacity-low'));
        const activeCard = document.getElementById(status === 'all' ? 'card-filter-all' : (status === 'true' ? 'card-filter-active' : 'card-filter-inactive'));
        if (activeCard) activeCard.classList.remove('opacity-low');
        window.fetchUnits({status: status, page: 1});
    };

    // =========================================================
    // 2. LÓGICA DEL MODAL (Vue + jQuery Select2)
    // =========================================================

    // Función Global para cargar padres (CASCADA)
    async function loadParents(levelId, preselectedParentId = null) {
        const parentSelect = $('#id_parent');
        parentSelect.empty();

        if (!levelId) {
            parentSelect.append(new Option("--- Seleccione un Nivel Primero ---", "", true, true));
            parentSelect.prop('disabled', true);
            return;
        }

        try {
            const res = await fetch(`/institution/api/parents/?level_id=${levelId}`);
            const data = await res.json();

            if (data.results && data.results.length > 0) {
                // TIENE PADRES
                parentSelect.append(new Option("--- Seleccione Unidad Padre ---", "", true, !preselectedParentId));

                data.results.forEach(item => {
                    const isSelected = String(item.id) === String(preselectedParentId);
                    parentSelect.append(new Option(item.text, item.id, isSelected, isSelected));
                });

                parentSelect.prop('disabled', false);
            } else {
                // ES RAÍZ
                parentSelect.append(new Option("--- Es una unidad raíz ---", "", true, true));
                parentSelect.prop('disabled', true);
            }
            parentSelect.trigger('change');

        } catch (e) {
            console.error(e);
            parentSelect.append(new Option("Error al cargar", "", true, true));
        }
    }

    // Inicializador de Select2
    function initializeSelects() {
        // A. JEFE INMEDIATO (AJAX) - Optimizado para 5000+ empleados
        // Destruir si existe para evitar duplicados
        if ($('#id_boss').data('select2')) {
            $('#id_boss').select2('destroy');
        }

        $('#id_boss').select2({
            dropdownParent: $('#unit-modal-app'),
            width: '100%',
            allowClear: true,
            ajax: {
                url: '/institution/api/employees/search/',
                dataType: 'json',
                delay: 300,
                data: function (params) {
                    return {
                        term: params.term || '',
                        page: params.page || 1
                    };
                },
                processResults: function (data) {
                    return {
                        results: data.results || []
                    };
                },
                cache: true
            },
            placeholder: 'Escriba para buscar por nombre o cédula...',
            minimumInputLength: 0,
            language: {
                noResults: () => "No se encontraron empleados",
                searching: () => "Buscando...",
                inputTooShort: () => "Escriba al menos 2 caracteres",
                loadingMore: () => "Cargando más resultados..."
            },
            escapeMarkup: function(markup) { return markup; },
            templateResult: function(employee) {
                if (employee.loading) return employee.text;
                return employee.text;
            },
            templateSelection: function(employee) {
                return employee.text || employee.id;
            }
        });

        // B. NIVEL
        if ($('#id_level').data('select2')) {
            $('#id_level').select2('destroy');
        }
        
        $('#id_level').select2({
            dropdownParent: $('#unit-modal-app'),
            width: '100%',
            placeholder: "Seleccione Nivel"
        }).off('change').on('change', function () {
            // .off() evita acumulación de eventos
            loadParents($(this).val());
        });

        // C. PADRE
        if ($('#id_parent').data('select2')) {
            $('#id_parent').select2('destroy');
        }
        
        $('#id_parent').select2({
            dropdownParent: $('#unit-modal-app'),
            width: '100%',
            placeholder: "--- Seleccione Nivel Primero ---"
        });
    }

    // APP VUE
    if (document.getElementById('unit-modal-app')) {
        const app = createApp({
            delimiters: ['[[', ']]'],
            setup() {
                const isVisible = ref(false);
                const isEditing = ref(false);
                const currentId = ref(null);
                const errors = ref({});
                const formEl = 'unitForm';

                // Variable para control visual
                const isParentDisabled = ref(true);

                const openCreate = async () => {
                    isEditing.value = false;
                    currentId.value = null;
                    errors.value = {};
                    isParentDisabled.value = true;

                    document.getElementById(formEl).reset();

                    isVisible.value = true;
                    document.body.classList.add('no-scroll');

                    // Esperar a que Vue renderice el DOM antes de activar Select2
                    await nextTick();

                    // Resetear Selects visualmente
                    $('#id_level').val(null).trigger('change');
                    $('#id_parent').val(null).trigger('change');
                    $('#id_boss').val(null).trigger('change');

                    // Inicializar plugins
                    initializeSelects();
                    loadParents(null);
                };

                const openEdit = async (id) => {
                    isEditing.value = true;
                    currentId.value = id;
                    errors.value = {};

                    try {
                        const res = await fetch(`/institution/units/detail/${id}/`);
                        const result = await res.json();

                        if (result.success) {
                            const d = result.data;
                            const form = document.getElementById(formEl);

                            form.querySelector('[name=name]').value = d.name;
                            form.querySelector('[name=code]').value = d.code || '';
                            form.querySelector('[name=address]').value = d.address || '';
                            form.querySelector('[name=phone]').value = d.phone || '';

                            isVisible.value = true;
                            document.body.classList.add('no-scroll');

                            // Esperar DOM
                            await nextTick();
                            initializeSelects();

                            // Llenar Jefe
                            if (d.boss_data) {
                                const option = new Option(d.boss_data.text, d.boss_data.id, true, true);
                                $('.select2-ajax').append(option).trigger('change');
                            } else {
                                $('.select2-ajax').val(null).trigger('change');
                            }

                            // Llenar Nivel y cargar padres
                            $('#id_level').val(d.level).trigger('change.select2');
                            await loadParents(d.level, d.parent);

                            // Actualizar estado variable reactiva
                            isParentDisabled.value = $('#id_parent').prop('disabled');
                        }
                    } catch (e) {
                        console.error(e);
                        Toast.fire({icon: 'error', title: 'Error al cargar datos'});
                    }
                };

                const closeModal = () => {
                    isVisible.value = false;
                    document.body.classList.remove('no-scroll');
                };

                const submitForm = async () => {
                    const formData = new FormData(document.getElementById(formEl));

                    // Limpieza si está deshabilitado
                    if ($('#id_parent').prop('disabled')) {
                        formData.delete('parent');
                    }

                    const url = isEditing.value
                        ? `/institution/units/update/${currentId.value}/`
                        : `/institution/units/create/`;

                    try {
                        const res = await fetch(url, {
                            method: 'POST', body: formData,
                            headers: {'X-Requested-With': 'XMLHttpRequest'}
                        });
                        const data = await res.json();

                        if (data.success) {
                            Toast.fire({
                                icon: 'success',
                                title: isEditing.value ? 'Actualizado' : 'Creado',
                                text: data.message
                            });
                            closeModal();
                            window.fetchUnits();
                            if (data.new_stats) updateStats(data.new_stats);
                        } else {
                            errors.value = data.errors;
                            Toast.fire({icon: 'warning', title: 'Revise el formulario'});
                        }
                    } catch (e) {
                        Toast.fire({icon: 'error', title: 'Error del servidor'});
                    }
                };

                window.openCreateUnit = openCreate;
                window.openEditUnit = openEdit;

                // CORRECCIÓN PRINCIPAL: Retornar isParentDisabled
                return {
                    isVisible,
                    isEditing,
                    errors,
                    isParentDisabled, // <--- ESTO FALTABA
                    closeModal,
                    submitForm
                };
            }
        }).mount('#unit-modal-app');
    }

    // =========================================
    // 3. TOGGLE STATUS
    // =========================================
    window.toggleUnitStatus = async (btnElement, url, name) => {
        const isCurrentlyActive = btnElement.classList.contains('btn-delete-action');
        const actionVerb = isCurrentlyActive ? 'Desactivar' : 'Activar';
        const btnClass = isCurrentlyActive ? 'btn-swal-danger' : 'btn-swal-success';

        const result = await Swal.fire({
            title: `¿${actionVerb} unidad?`,
            text: `Vas a cambiar el estado de "${name}"`,
            icon: 'warning',
            showCancelButton: true,
            buttonsStyling: false,
            customClass: {
                confirmButton: `swal2-confirm ${btnClass}`,
                cancelButton: 'swal2-cancel btn-swal-cancel',
                popup: 'swal2-popup'
            },
            confirmButtonText: `Sí, ${actionVerb.toLowerCase()}`,
            cancelButtonText: 'Cancelar'
        });

        if (result.isConfirmed) {
            try {
                const formData = new FormData();
                formData.append('csrfmiddlewaretoken', document.querySelector('[name=csrfmiddlewaretoken]').value);
                const res = await fetch(url, {method: 'POST', body: formData});
                const data = await res.json();

                if (data.success) {
                    Toast.fire({icon: 'success', title: 'Estado Actualizado', text: data.message});
                    window.fetchUnits();
                    if (data.new_stats) updateStats(data.new_stats);
                } else {
                    Toast.fire({icon: 'error', title: data.message});
                }
            } catch (e) {
                console.error(e);
            }
        }
    };

    function updateStats(stats) {
        if (!stats) return;
        document.getElementById('stat-total').textContent = stats.total;
        document.getElementById('stat-active').textContent = stats.active;
        document.getElementById('stat-inactive').textContent = stats.inactive;
    }

    // Inicializar listeners Paginación
    const btnP = document.getElementById('btn-prev');
    const btnN = document.getElementById('btn-next');
    const btnA = document.getElementById('btn-add-unit');

    if (btnP) btnP.onclick = () => window.fetchUnits({page: currentFilters.page - 1});
    if (btnN) btnN.onclick = () => window.fetchUnits({page: currentFilters.page + 1});
    if (btnA) btnA.onclick = () => window.openCreateUnit();

    // Carga inicial
    window.fetchUnits();
});