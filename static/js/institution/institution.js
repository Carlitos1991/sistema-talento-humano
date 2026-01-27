/* static/js/institution.js */

document.addEventListener('DOMContentLoaded', () => {
    const {createApp, ref, nextTick} = Vue;
    const tableContainer = document.getElementById('table-content-wrapper');
    const searchInput = document.getElementById('table-search');
    let currentFilters = {q: '', status: 'all', page: 1};

    // Configuración Toast
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

    // 1. LÓGICA DE TABLA
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

    // 2. LÓGICA DEL MODAL
    let shouldLoadParentsOnLevelChange = true;

    async function loadParents(levelId, preselectedParentId = null) {
        const parentSelect = $('#id_parent');

        // Destruir para limpiar
        if (parentSelect.data('select2')) {
            parentSelect.select2('destroy');
        }
        parentSelect.empty();

        let isDisabled = true;
        let placeholderText = "--- Seleccione Nivel Primero ---";

        if (!levelId) {
            parentSelect.append(new Option(placeholderText, "", true, true));
        } else {
            try {
                const res = await fetch(`/institution/api/parents/?level_id=${levelId}`);
                const data = await res.json();

                if (data.results && data.results.length > 0) {
                    // Si tiene padres (Nivel > 1), habilitamos
                    isDisabled = false;
                    placeholderText = "--- Seleccione Unidad Padre ---";
                    parentSelect.append(new Option(placeholderText, "", true, !preselectedParentId));

                    data.results.forEach(item => {
                        const isSelected = String(item.id) === String(preselectedParentId);
                        parentSelect.append(new Option(item.text, item.id, isSelected, isSelected));
                    });
                } else {
                    // Si es raíz (Nivel 1), deshabilitamos y mostramos mensaje
                    placeholderText = "--- Es una unidad raíz (No requiere padre) ---";
                    parentSelect.append(new Option(placeholderText, "", true, true));
                }

            } catch (e) {
                console.error('Error en loadParents:', e);
                placeholderText = "Error al cargar datos";
                parentSelect.append(new Option(placeholderText, "", true, true));
            }
        }

        parentSelect.prop('disabled', isDisabled);

        parentSelect.select2({
            dropdownParent: $('#unit-modal-app'),
            width: '100%',
            placeholder: placeholderText,
            language: {noResults: () => "No se encontraron resultados"}
        });

        document.dispatchEvent(new CustomEvent('parent-state-changed', {
            detail: {disabled: isDisabled}
        }));
    }

    function initializeSelects() {
        // A. Boss
        if ($('#id_boss').data('select2')) $('#id_boss').select2('destroy');
        $('#id_boss').select2({
            dropdownParent: $('#unit-modal-app'),
            width: '100%',
            allowClear: true,
            placeholder: 'Escriba para buscar empleado...',
            minimumInputLength: 1,
            ajax: {
                url: '/institution/api/employees/search/',
                dataType: 'json',
                delay: 300,
                data: (params) => ({term: params.term || '', page: params.page || 1}),
                processResults: (data) => ({results: data.results || []}),
                cache: true
            },
            language: {
                noResults: () => "No se encontraron empleados",
                searching: () => "Buscando...",
                inputTooShort: () => "Escriba al menos 1 carácter"
            }
        });

        // B. Level
        if ($('#id_level').data('select2')) $('#id_level').select2('destroy');
        $('#id_level').select2({
            dropdownParent: $('#unit-modal-app'),
            width: '100%',
            placeholder: "Seleccione Nivel"
        }).on('change', function () {
            if (shouldLoadParentsOnLevelChange) {
                loadParents($(this).val());
            }
        });

        // C. Parent
        if ($('#id_parent').data('select2')) $('#id_parent').select2('destroy');
        $('#id_parent').select2({
            dropdownParent: $('#unit-modal-app'),
            width: '100%',
            placeholder: "--- Seleccione Nivel Primero ---"
        });
        $('#id_parent').select2('enable', false);
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
                const isParentDisabled = ref(true);

                const handleParentStateChange = (e) => {
                    isParentDisabled.value = e.detail.disabled;
                };
                document.addEventListener('parent-state-changed', handleParentStateChange);

                // --- ABRIR CREAR ---
                const openCreate = async () => {
                    isEditing.value = false;
                    currentId.value = null;
                    errors.value = {};
                    isParentDisabled.value = true;

                    document.getElementById(formEl).reset();
                    isVisible.value = true;
                    document.body.classList.add('no-scroll');

                    await nextTick();
                    initializeSelects();

                    // Aseguramos que el nivel esté HABILITADO al crear
                    $('#id_level').prop('disabled', false);

                    shouldLoadParentsOnLevelChange = true;
                    $('#id_level').val(null).trigger('change');
                    $('#id_boss').val(null).trigger('change');
                    await loadParents(null);
                };

                // --- ABRIR EDITAR ---
                const openEdit = async (id) => {
                    isEditing.value = true;
                    currentId.value = id;
                    errors.value = {};

                    try {
                        const res = await fetch(`/institution/units/detail/${id}/`);
                        const result = await res.json();

                        if (result.success) {
                            const d = result.data;

                            isVisible.value = true;
                            document.body.classList.add('no-scroll');
                            await nextTick();
                            initializeSelects();

                            // Llenar datos texto
                            const form = document.getElementById(formEl);
                            form.querySelector('[name=name]').value = d.name;
                            form.querySelector('[name=code]').value = d.code || '';
                            form.querySelector('[name=address]').value = d.address || '';
                            form.querySelector('[name=phone]').value = d.phone || '';

                            // --- LÓGICA DE NIVEL BLOQUEADO ---
                            shouldLoadParentsOnLevelChange = false;

                            // 1. Establecer valor
                            $('#id_level').val(d.level).trigger('change');

                            // 2. Bloquear el combo de Nivel (Requirement: Read-only on edit)
                            $('#id_level').prop('disabled', true);

                            // 3. Cargar padres (loadParents manejará si el 2do combo se habilita o no)
                            await loadParents(d.level, d.parent);

                            shouldLoadParentsOnLevelChange = true;

                            // Llenar Jefe
                            if (d.boss_data) {
                                if ($('#id_boss').find(`option[value="${d.boss_data.id}"]`).length === 0) {
                                    $('#id_boss').append(new Option(d.boss_data.text, d.boss_data.id, true, true));
                                }
                                $('#id_boss').val(d.boss_data.id).trigger('change');
                            } else {
                                $('#id_boss').val(null).trigger('change');
                            }
                        }
                    } catch (e) {
                        console.error('Error en openEdit:', e);
                        Toast.fire({icon: 'error', title: 'Error al cargar datos'});
                    }
                };

                const closeModal = () => {
                    isVisible.value = false;
                    document.body.classList.remove('no-scroll');
                };

                const submitForm = async () => {
                    // --- TRUCO IMPORTANTE ---
                    // Al editar, el nivel está disabled. Los campos disabled NO se envían en FormData.
                    // Django dará error de validación. Debemos habilitarlo temporalmente.
                    const wasLevelDisabled = $('#id_level').prop('disabled');
                    if (wasLevelDisabled) {
                        $('#id_level').prop('disabled', false);
                    }

                    const formData = new FormData(document.getElementById(formEl));

                    // Restauramos el estado disabled si estaba bloqueado
                    if (wasLevelDisabled) {
                        $('#id_level').prop('disabled', true);
                    }

                    // Limpieza del padre si está deshabilitado
                    if ($('#id_parent').select2('enable') === false) {
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
                        console.error('Error en submitForm:', e);
                        Toast.fire({icon: 'error', title: 'Error del servidor'});
                    }
                };

                window.openCreateUnit = openCreate;
                window.openEditUnit = openEdit;

                return {
                    isVisible,
                    isEditing,
                    errors,
                    isParentDisabled,
                    closeModal,
                    submitForm
                };
            }
        }).mount('#unit-modal-app');
    }

    // 3. TOGGLE STATUS
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

    const btnP = document.getElementById('btn-prev');
    const btnN = document.getElementById('btn-next');
    const btnA = document.getElementById('btn-add-unit');

    if (btnP) btnP.onclick = () => window.fetchUnits({page: currentFilters.page - 1});
    if (btnN) btnN.onclick = () => window.fetchUnits({page: currentFilters.page + 1});
    if (btnA) btnA.onclick = () => window.openCreateUnit();

    window.fetchUnits();
});