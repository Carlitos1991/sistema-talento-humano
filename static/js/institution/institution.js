/* static/js/institution.js */

document.addEventListener('DOMContentLoaded', () => {
    const {createApp, ref, nextTick} = Vue;
    const tableContainer = document.getElementById('table-content-wrapper');
    const searchInput = document.getElementById('table-search');
    let currentFilters = {q: '', level: '', parent: '', page: 1};

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

        if ('q' in params || 'level' in params || 'parent' in params) {
            params.page = 1;
        }

        // Fusionar nuevos parámetros con los actuales
        Object.assign(currentFilters, params);

        // Limpieza de filtros mutuamente excluyentes
        if (params.level) currentFilters.parent = '';
        if (params.parent) currentFilters.level = '';

        // Construir URL
        const url = new URL(window.location.href);
        Object.keys(currentFilters).forEach(key => {
            // Solo enviamos parámetros que tengan valor
            if (currentFilters[key] !== '' && currentFilters[key] !== null) {
                url.searchParams.set(key, currentFilters[key]);
            } else {
                url.searchParams.delete(key);
            }
        });

        fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
            .then(res => {
                if (!res.ok) throw new Error("Error en la petición");
                return res.json();
            })
            .then(data => {
                if (tableContainer) {
                    tableContainer.innerHTML = data.html;
                    updatePaginationUI();

                    // Actualizar estadísticas de las tarjetas
                    updateLevelStats(data.level_stats);

                    // Mostrar/Ocultar botón de reset según si hay drill-down
                    const btnReset = document.getElementById('btn-reset-filters');
                    if (btnReset) {
                        btnReset.classList.toggle('hidden', !currentFilters.parent);
                    }
                }
            })
            .catch(err => {
                console.error("Error fetching units:", err);
                if (currentFilters.page > 1) {
                    window.fetchUnits({page: 1});
                }
            });
    };


    function updatePaginationUI() {
        const meta = document.getElementById('pagination-metadata');
        if (!meta) return;

        // Leer datos como Strings y convertir si es necesario
        const total = meta.dataset.total;
        const start = meta.dataset.start;
        const end = meta.dataset.end;
        const page = meta.dataset.page;
        const hasPrev = meta.dataset.hasPrev === 'true';
        const hasNext = meta.dataset.hasNext === 'true';

        const pageInfo = document.getElementById('page-info');
        if (pageInfo) pageInfo.textContent = (total == 0 || total === undefined)
            ? "Sin resultados"
            : `Mostrando ${start}-${end} de ${total}`;

        const pageDisplay = document.getElementById('current-page-display');
        if (pageDisplay) pageDisplay.textContent = page;

        const btnPrev = document.getElementById('btn-prev');
        const btnNext = document.getElementById('btn-next');

        if (btnPrev) {
            btnPrev.disabled = !hasPrev;
            btnPrev.onclick = () => window.fetchUnits({page: parseInt(currentFilters.page) - 1});
        }
        if (btnNext) {
            btnNext.disabled = !hasNext;
            btnNext.onclick = () => window.fetchUnits({page: parseInt(currentFilters.page) + 1});
        }
    }

    if (searchInput) {
        let timeout;
        searchInput.addEventListener('input', (e) => {
            clearTimeout(timeout);
            timeout = setTimeout(() => {
                window.fetchUnits({q: e.target.value, page: 1});
            }, 300);
        });
    }

    window.filterByLevel = function (levelId, cardElement = null) {
        document.querySelectorAll('.stat-card').forEach(c => c.classList.add('opacity-low'));

        if (!cardElement) {
            cardElement = document.getElementById(`stat-card-${levelId}`);
        }
        if (cardElement) {
            cardElement.classList.remove('opacity-low');
        }

        window.fetchUnits({level: levelId});
    };
    // --- FILTRO POR PADRE (DRILL-DOWN) ---
    window.filterByParent = function (parentId) {
        document.querySelectorAll('.stat-card').forEach(c => c.classList.add('opacity-low'));

        if (!parentId || parentId === 'None') {
            window.fetchUnits({parent: '', level: '', q: ''});
            const firstCard = document.querySelector('.stat-card');
            if (firstCard) firstCard.classList.remove('opacity-low');
        } else {
            window.fetchUnits({parent: parentId});
        }
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
        createApp({
            delimiters: ['[[', ']]'],
            setup() {
                const isVisible = ref(false);
                const isEditing = ref(false);
                const currentId = ref(null);
                const errors = ref({});
                const formEl = 'unitForm';

                // --- ABRIR CREAR (Automático) ---
                const openCreate = async () => {
                    isEditing.value = false;
                    currentId.value = null;
                    errors.value = {};

                    const formObj = document.getElementById(formEl);
                    if (formObj) formObj.reset();

                    isVisible.value = true;
                    document.body.classList.add('no-scroll');

                    // 1. Detectar contexto
                    const parentId = currentFilters.parent || '';

                    // 2. Obtener código
                    try {
                        const url = `/institution/api/next-code/?parent_id=${parentId}`;
                        const res = await fetch(url);
                        const data = await res.json();

                        if (data.success) {
                            if (formObj) {
                                formObj.querySelector('[name=code]').value = data.next_code;
                                if (data.suggested_level) formObj.querySelector('[name=level]').value = data.suggested_level;

                                const parentInput = formObj.querySelector('[name=parent]');
                                if (parentInput) parentInput.value = parentId ? parentId : '';
                            }
                        }
                    } catch (e) {
                        console.error("Error code auto:", e);
                    }
                };

                // --- ABRIR EDITAR ---
                const openEdit = async (id) => {
                    isEditing.value = true;
                    currentId.value = id;
                    errors.value = {};

                    try {
                        const res = await fetch(`/institution/units/detail/${id}/json/`);
                        if (!res.ok) throw new Error();
                        const result = await res.json();

                        if (result.success) {
                            const d = result.data;
                            isVisible.value = true;
                            document.body.classList.add('no-scroll');
                            await nextTick();

                            const form = document.getElementById(formEl);
                            if (form) {
                                form.querySelector('[name=name]').value = d.name;
                                form.querySelector('[name=code]').value = d.code || '';
                                form.querySelector('[name=address]').value = d.address || '';
                                form.querySelector('[name=phone]').value = d.phone || '';
                                form.querySelector('[name=level]').value = d.level;
                                form.querySelector('[name=parent]').value = d.parent || '';
                                form.querySelector('[name=boss]').value = d.boss || '';
                            }
                        }
                    } catch (e) {
                        Toast.fire({icon: 'error', title: 'Error al cargar datos'});
                    }
                };

                const closeModal = () => {
                    isVisible.value = false;
                    document.body.classList.remove('no-scroll');
                };

                const submitForm = async () => {
                    const formData = new FormData(document.getElementById(formEl));
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

                return {isVisible, isEditing, errors, closeModal, submitForm};
            }
        }).mount('#unit-modal-app');
    }
    // 3. TOGGLE STATUS
    window.toggleUnitStatus = async (btnElement, url, name, id) => {
        const result = await Swal.fire({
            title: '¿Cambiar estado?',
            text: `Unidad: ${name}`,
            icon: 'warning',
            showCancelButton: true,
            confirmButtonText: 'Sí, cambiar',
            cancelButtonText: 'Cancelar'
        });

        if (result.isConfirmed) {
            try {
                const formData = new FormData();
                formData.append('csrfmiddlewaretoken', document.querySelector('[name=csrfmiddlewaretoken]').value);
                const res = await fetch(url, {method: 'POST', body: formData});
                const data = await res.json();

                if (data.success) {
                    Toast.fire({icon: 'success', title: data.message});
                    // Actualizar estadísticas si vienen en la respuesta
                    if (data.level_stats) {
                        updateLevelStats(data.level_stats);
                    }
                    // Recargar tabla para ver cambios
                    window.fetchUnits();
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

    function updateLevelStats(levelStats) {
        if (!levelStats || !Array.isArray(levelStats)) return;
        
        levelStats.forEach(stat => {
            const card = document.getElementById(`stat-card-${stat.id}`);
            if (card) {
                const numberElement = card.querySelector('.number');
                if (numberElement) {
                    numberElement.textContent = stat.count;
                }
            }
        });
    }

    const btnP = document.getElementById('btn-prev');
    const btnN = document.getElementById('btn-next');
    const btnA = document.getElementById('btn-add-unit');

    if (btnP) btnP.onclick = () => window.fetchUnits({page: currentFilters.page - 1});
    if (btnN) btnN.onclick = () => window.fetchUnits({page: currentFilters.page + 1});
    if (btnA) btnA.onclick = () => window.openCreateUnit();
    const firstStat = document.querySelector('.stat-card[data-first="true"]');
    if (firstStat) {
        const levelId = firstStat.dataset.levelId;
        // Simulamos click para cargar visuales y datos
        window.filterByLevel(levelId, firstStat);
    }
    updatePaginationUI();
});

// ==========================================
// 4. LÓGICA ASIGNAR JEFE (SIN BOOTSTRAP)
// ==========================================

window.openAssignBoss = async function (unitId) {
    // 1. Crear contenedor si no existe
    let modalContainer = document.getElementById('assign-boss-modal-container');

    // Si no existe el div en el HTML, lo creamos dinámicamente
    if (!modalContainer) {
        modalContainer = document.createElement('div');
        modalContainer.id = 'assign-boss-modal-container';
        modalContainer.className = 'custom-modal-overlay'; // Clase para CSS propio
        // Estructura interna básica para centrar contenido
        modalContainer.innerHTML = '<div class="custom-modal-dialog"></div>';
        document.body.appendChild(modalContainer);
    }

    // 2. Cargar formulario desde el servidor
    try {
        const res = await fetch(`/institution/units/assign-boss/${unitId}/`, {
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        });

        if (!res.ok) throw new Error('Error al cargar modal');

        const html = await res.text();

        // Inyectamos el HTML dentro del dialog
        // Nota: Asegúrate que modalContainer tenga un hijo, si no, inyectamos directo
        if (modalContainer.firstElementChild) {
            modalContainer.firstElementChild.innerHTML = html;
        } else {
            modalContainer.innerHTML = html;
        }

        // 3. Inicializar Select2 (Buscador)
        if (typeof $ !== 'undefined') {
            $('#id_boss_assign').select2({
                dropdownParent: $('#assign-boss-modal-container'),
                width: '100%',
                placeholder: 'Buscar empleado activo...',
                allowClear: true,
                ajax: {
                    url: '/institution/api/employee/search/',
                    dataType: 'json',
                    delay: 250,
                    data: (params) => ({term: params.term}),
                    processResults: (data) => ({results: data.results})
                }
            });
        }

        // 4. MOSTRAR EL MODAL
        modalContainer.style.display = 'flex'; // Usamos flex para centrar
        document.body.classList.add('modal-open'); // Bloquear scroll

        // Guardamos el ID para el submit
        modalContainer.dataset.unitId = unitId;

        // Cerrar al hacer clic fuera (en el fondo oscuro)
        modalContainer.onclick = function (e) {
            if (e.target === modalContainer) {
                closeAssignModal();
            }
        };

    } catch (e) {
        console.error(e);
        Swal.fire('Error', 'No se pudo cargar el formulario.', 'error');
    }
};

window.closeAssignModal = function () {
    const modalContainer = document.getElementById('assign-boss-modal-container');
    if (modalContainer) {
        modalContainer.style.display = 'none';
        document.body.classList.remove('modal-open');
        // Opcional: Limpiar contenido para ahorrar memoria
        if (modalContainer.firstElementChild) modalContainer.firstElementChild.innerHTML = '';
    }
};

window.submitAssignBoss = async function () {
    const container = document.getElementById('assign-boss-modal-container');
    const unitId = container.dataset.unitId;
    const form = document.getElementById('assignBossForm');

    if (!form) return;

    try {
        const formData = new FormData(form);
        const res = await fetch(`/institution/units/assign-boss/${unitId}/`, {
            method: 'POST',
            body: formData,
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        });
        const data = await res.json();

        if (data.success) {
            window.closeAssignModal();
            Swal.fire({
                icon: 'success',
                title: '¡Listo!',
                text: data.message,
                timer: 2000,
                showConfirmButton: false
            });
            // Recargar tabla de unidades
            if (typeof window.fetchUnits === 'function') {
                window.fetchUnits();
            } else {
                window.location.reload();
            }
        } else {
            Swal.fire('Atención', 'Seleccione un empleado válido.', 'warning');
        }
    } catch (e) {
        console.error(e);
        Swal.fire('Error', 'Error de conexión con el servidor', 'error');
    }
};