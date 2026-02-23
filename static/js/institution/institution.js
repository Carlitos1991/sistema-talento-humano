document.addEventListener('DOMContentLoaded', () => {
    const {createApp, ref} = Vue;

    // =========================================================================
    // 1. MAPA DE TARJETAS DE NIVEL
    // =========================================================================
    const levelCards = {};
    document.querySelectorAll('.stat-card[id^="card-filter-"]').forEach(card => {
        const levelId = card.id.replace('card-filter-', '');
        levelCards[levelId] = card;
    });

    // =========================================================================
    // 2. FILTRADO POR NIVEL — delega a TableManager
    // =========================================================================
    window.filterByLevel = function (levelId, clickedCard = null) {
        Object.values(levelCards).forEach(c => {
            if (c) c.classList.add('opacity-low');
        });
        const activeCard = clickedCard || levelCards[levelId];
        if (activeCard) activeCard.classList.remove('opacity-low');

        const table = document.querySelector('.managed-table');
        if (table && table._tableManager) {
            if (levelId === 'total') {
                table._tableManager.filterByColumnData('level', 'all');
            } else {
                table._tableManager.filterByColumnData('level', String(levelId));
            }
        }
    };

    // =========================================================================
    // 3. DRILL-DOWN POR PADRE — también delega a TableManager
    // =========================================================================
    window.filterByParent = function (parentId) {
        const table = document.querySelector('.managed-table');
        if (!table || !table._tableManager) return;

        if (!parentId || parentId === '' || parentId === 'None') {
            table._tableManager.filterByColumnData('parent', 'all');
            const firstCard = document.querySelector('.stat-card');
            if (firstCard) {
                Object.values(levelCards).forEach(c => {
                    if (c) c.classList.add('opacity-low');
                });
                firstCard.classList.remove('opacity-low');
            }
        } else {
            Object.values(levelCards).forEach(c => {
                if (c) c.classList.add('opacity-low');
            });
            table._tableManager.filterByColumnData('parent', String(parentId));
        }
    };

    // =========================================================================
    // 4. INICIALIZACIÓN DE TARJETAS Y STATS-ROW
    // =========================================================================
    const statsRow = document.getElementById('stats-row');

    setTimeout(() => {
        window.filterByLevel('1');
        if (statsRow) statsRow.style.display = 'flex';
    }, 50);

    Object.entries(levelCards).forEach(([levelId, card]) => {
        if (card) {
            card.addEventListener('click', () => window.filterByLevel(levelId, card));
        }
    });

    // =========================================================================
    // 5. TOGGLE STATUS — recarga HTML parcial y reinicia TableManager
    // =========================================================================
    window.toggleUnitStatus = async (btnElement, url, name, id) => {
        const isDeactivate = btnElement.classList.contains('btn-delete-action');

        const result = await Swal.fire({
            title: `¿${isDeactivate ? 'Desactivar' : 'Activar'} unidad?`,
            text: `Vas a cambiar el estado de "${name}"`,
            icon: 'warning',
            showCancelButton: true,
            confirmButtonText: 'Sí, cambiar',
            cancelButtonText: 'Cancelar'
        });

        if (result.isConfirmed) {
            try {
                const formData = new FormData();
                const token = document.querySelector('[name=csrfmiddlewaretoken]');
                if (token) formData.append('csrfmiddlewaretoken', token.value);

                const res = await fetch(url, {
                    method: 'POST',
                    body: formData,
                    headers: {'X-Requested-With': 'XMLHttpRequest'}
                });
                const data = await res.json();

                if (data.success) {
                    const tm = document.querySelector('.managed-table')?._tableManager;
                    const savedSearch = tm?.filterState.search || '';
                    const savedFilter = {...tm?.filterState};
                    const r = await fetch('/institution/units/partial_table/');
                    const html = await r.text();
                    document.getElementById('table-content-wrapper').innerHTML = html;

                    // Reiniciar TableManager sobre la nueva tabla
                    const newTable = document.querySelector('.managed-table');
                    if (newTable) new TableManager(newTable);
                    if (savedSearch) {
                        const input = document.querySelector('.table-search-input');
                        if (input) {
                            input.value = savedSearch;
                        }
                    }
                    newTable._tableManager.filterState = savedFilter;
                    newTable._tableManager.applyGlobalFilters();

                    // Reaplicar filtro de nivel activo
                    const activeCard = document.querySelector('.stat-card:not(.opacity-low)');
                    if (activeCard) {
                        const activeLevelId = activeCard.id.replace('card-filter-', '');
                        window.filterByLevel(activeLevelId, activeCard);
                    } else {
                        window.filterByLevel('total');
                    }

                    Swal.fire('Éxito', data.message, 'success');
                } else {
                    Swal.fire('Error', data.message, 'error');
                }
            } catch (e) {
                console.error(e);
                Swal.fire('Error', 'Error de conexión', 'error');
            }
        }
    };

    // =========================================================================
    // 6. MODAL CREAR / EDITAR UNIDAD (Vue)
    // =========================================================================
    let shouldLoadParentsOnLevelChange = true;

    async function loadParents(levelId, preselectedParentId = null) {
        const parentSelect = $('#id_parent');
        if (parentSelect.data('select2')) parentSelect.select2('destroy');
        parentSelect.empty();

        let isDisabled = true;
        let placeholderText = '--- Seleccione Nivel Primero ---';

        if (!levelId) {
            parentSelect.append(new Option(placeholderText, '', true, true));
        } else {
            try {
                const res = await fetch(`/institution/api/parents/?level_id=${levelId}`);
                const data = await res.json();

                if (data.results && data.results.length > 0) {
                    isDisabled = false;
                    placeholderText = '--- Seleccione Unidad Padre ---';
                    parentSelect.append(new Option(placeholderText, '', true, !preselectedParentId));
                    data.results.forEach(item => {
                        const isSelected = String(item.id) === String(preselectedParentId);
                        parentSelect.append(new Option(item.text, item.id, isSelected, isSelected));
                    });
                } else {
                    placeholderText = '--- Es una unidad raíz (No requiere padre) ---';
                    parentSelect.append(new Option(placeholderText, '', true, true));
                }
            } catch (e) {
                console.error('Error en loadParents:', e);
                parentSelect.append(new Option('Error al cargar datos', '', true, true));
            }
        }

        parentSelect.prop('disabled', isDisabled);
        parentSelect.select2({
            dropdownParent: $('#unit-modal-app'),
            width: '100%',
            placeholder: placeholderText,
            allowClear: !isDisabled
        });
    }

    async function fetchNextCode(levelId, parentId) {
        const codeInput = document.getElementById('id_code');
        if (!codeInput) return;

        const params = new URLSearchParams();
        if (parentId) params.set('parent_id', parentId);
        else if (levelId) params.set('level_id', levelId);

        try {
            const res = await fetch(`/institution/api/next-code/?${params}`);
            const data = await res.json();
            if (data.success) {
                codeInput.value = data.next_code;
                // Si el backend sugiere un nivel (ej: al crear dependencia), lo seleccionamos
                if (data.suggested_level) {
                    const levelSelect = document.getElementById('id_level');
                    if (levelSelect && levelSelect.value != data.suggested_level) {
                        levelSelect.value = data.suggested_level;
                        // Disparamos evento change manualmente si es necesario, 
                        // pero cuidado con bucles infinitos si loadParents llama a fetchNextCode
                    }
                }
            }
        } catch (e) {
            console.error('Error fetchNextCode:', e);
        }
    }

    const unitModalEl = document.getElementById('unit-modal-app');
    if (unitModalEl && !unitModalEl.__vue_app__) {
        const app = createApp({
            delimiters: ['[[', ']]'],
            setup() {
                const isVisible = ref(false);
                const isEditing = ref(false);
                const errors = ref({});
                const currentId = ref(null);
                const modalTitle = ref('Nueva Unidad Administrativa');
                const contextInfo = ref('');
                const formEl = 'unitForm';
                const isActive = ref(true);

                Vue.onMounted(() => {
                    const checkbox = document.getElementById('id_is_active');
                    if (checkbox) {
                        isActive.value = checkbox.checked;
                        checkbox.onchange = () => {
                            isActive.value = checkbox.checked;
                        };
                    }
                });

                const openCreate = async (parentId = null, levelOrder = null) => {
                    isEditing.value = false;
                    currentId.value = null;
                    errors.value = {};
                    const f = document.getElementById(formEl);
                    if (f) f.reset();

                    // Resetear checkbox de estado a true por defecto en creación
                    const isActiveCheckbox = document.getElementById('id_is_active');
                    if (isActiveCheckbox) isActiveCheckbox.checked = true;

                    isVisible.value = true;
                    document.body.classList.add('no-scroll');

                    // Lógica diferenciada: Crear Raíz vs Crear Dependencia
                    if (parentId) {
                        modalTitle.value = 'Nueva Unidad Dependiente';
                        // Crear Dependencia
                        // 1. Buscar el nivel correspondiente al orden (levelOrder)
                        // Esto requiere que el select de niveles tenga los IDs correctos.
                        // Como no tenemos el ID del nivel directamente, podemos inferirlo o dejar que fetchNextCode lo sugiera.
                        // Pero para cargar los padres correctos necesitamos el ID del nivel HIJO.

                        // Estrategia:
                        // a) Cargar next-code con parent_id. El backend nos dará el código y el ID del nivel sugerido.
                        // b) Usar ese ID de nivel para cargar la lista de padres (donde parentId debería estar).
                        // c) Preseleccionar parentId.

                        const res = await fetch(`/institution/api/next-code/?parent_id=${parentId}`);
                        const data = await res.json();

                        if (data.success) {
                            const codeInput = document.getElementById('id_code');
                            if (codeInput) codeInput.value = data.next_code;

                            if (data.suggested_level) {
                                const levelSelect = document.getElementById('id_level');
                                if (levelSelect) levelSelect.value = data.suggested_level;
                                await loadParents(data.suggested_level, parentId);
                            }
                            contextInfo.value = `Código: ${data.next_code} · Nivel sugerido automáticamente`;
                        }

                    } else {
                        // Crear Unidad Raíz (Nivel 1)
                        modalTitle.value = 'Nueva Unidad Administrativa';
                        // 1. Obtener código para nivel raíz (sin padre)
                        const res = await fetch(`/institution/api/next-code/?parent_id=null`);
                        const data = await res.json();

                        if (data.success) {
                            const codeInput = document.getElementById('id_code');
                            if (codeInput) codeInput.value = data.next_code;

                            if (data.suggested_level) {
                                const levelSelect = document.getElementById('id_level');
                                if (levelSelect) levelSelect.value = data.suggested_level;
                                await loadParents(data.suggested_level);
                            }
                            contextInfo.value = `Código: ${data.next_code} · Nivel Raíz (sin unidad padre)`;
                        }
                    }

                    // Configurar listeners
                    const levelSelect = document.getElementById('id_level');
                    if (levelSelect) {
                        shouldLoadParentsOnLevelChange = true;
                        levelSelect.onchange = async function () {
                            if (!shouldLoadParentsOnLevelChange) return;
                            await loadParents(this.value);
                            const parentEl = document.getElementById('id_parent');
                            await fetchNextCode(this.value, parentEl ? parentEl.value : null);
                        };

                        $('#id_parent').off('change').on('change', async function () {
                            await fetchNextCode(levelSelect.value, $(this).val());
                        });
                    }
                };

                const openEdit = async (id) => {
                    isEditing.value = true;
                    currentId.value = id;
                    errors.value = {};
                    try {
                        const res = await fetch(`/institution/units/detail/${id}/json/`, {
                            headers: {'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json'}
                        });
                        const data = await res.json();
                        if (data.success) {
                            isVisible.value = true;
                            document.body.classList.add('no-scroll');
                            await new Promise(r => setTimeout(r, 50));

                            const d = data.data;
                            const setVal = (elId, val) => {
                                const el = document.getElementById(elId);
                                if (el) el.value = val || '';
                            };
                            setVal('id_name', d.name);
                            setVal('id_code', d.code);
                            setVal('id_address', d.address);
                            setVal('id_phone', d.phone);
                            setVal('id_mission', d.mission);

                            modalTitle.value = 'Editar Unidad Administrativa';
                            contextInfo.value = `Editando: ${d.name}`;

                            // Checkbox estado
                            const isActiveCheckbox = document.getElementById('id_is_active');
                            if (isActiveCheckbox) isActiveCheckbox.checked = d.is_active;

                            const levelSelect = document.getElementById('id_level');
                            if (levelSelect) {
                                levelSelect.value = d.level;
                                shouldLoadParentsOnLevelChange = false;
                                await loadParents(d.level, d.parent);
                                shouldLoadParentsOnLevelChange = true;

                                levelSelect.onchange = async function () {
                                    if (!shouldLoadParentsOnLevelChange) return;
                                    await loadParents(this.value);
                                    const parentEl = document.getElementById('id_parent');
                                    await fetchNextCode(this.value, parentEl ? parentEl.value : null);
                                };

                                $('#id_parent').off('change').on('change', async function () {
                                    await fetchNextCode(levelSelect.value, $(this).val());
                                });
                            }
                        } else {
                            alert('Error al cargar datos de la unidad');
                        }
                    } catch (e) {
                        console.error(e);
                        alert('Error del servidor');
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
                        : '/institution/units/create/';
                    try {
                        const res = await fetch(url, {
                            method: 'POST',
                            body: formData,
                            headers: {'X-Requested-With': 'XMLHttpRequest'}
                        });
                        const data = await res.json();
                        if (data.success) {
                            closeModal();
                            Swal.fire({
                                toast: true,
                                position: 'top-end',
                                icon: 'success',
                                title: isEditing.value ? 'Unidad editada correctamente.' : 'Unidad creada correctamente.',
                                showConfirmButton: false,
                                timer: 2000,
                                timerProgressBar: true
                            });
                            setTimeout(async () => {
                                // Guardar estado de filtros y búsqueda
                                const tm = document.querySelector('.managed-table')?._tableManager;
                                const savedSearch = tm?.filterState.search || '';
                                const savedFilter = {...tm?.filterState};
                                // Parpadeo visual
                                const tableWrapper = document.getElementById('table-content-wrapper');
                                if (tableWrapper) {
                                    tableWrapper.style.opacity = '0.5';
                                }
                                const r = await fetch('/institution/units/partial_table/');
                                const html = await r.text();
                                document.getElementById('table-content-wrapper').innerHTML = html;
                                // Reiniciar TableManager sobre la nueva tabla
                                const newTable = document.querySelector('.managed-table');
                                if (newTable) new TableManager(newTable);
                                // Restaurar búsqueda y filtros
                                if (savedSearch) {
                                    const input = document.querySelector('.table-search-input');
                                    if (input) {
                                        input.value = savedSearch;
                                    }
                                }
                                if (newTable && newTable._tableManager) {
                                    newTable._tableManager.filterState = savedFilter;
                                    newTable._tableManager.applyGlobalFilters();
                                }
                                // Restaurar selección visual del filtro stat
                                const activeCard = document.querySelector('.stat-card:not(.opacity-low)');
                                if (activeCard) {
                                    const activeLevelId = activeCard.id.replace('card-filter-', '');
                                    window.filterByLevel(activeLevelId, activeCard);
                                }
                                // Quitar parpadeo
                                if (tableWrapper) {
                                    setTimeout(() => { tableWrapper.style.opacity = '1'; }, 300);
                                }
                            }, 1200);
                        } else {
                            errors.value = data.errors || {};
                        }
                    } catch (e) {
                        alert('Error del servidor');
                    }
                };

                window.openCreateUnit = openCreate;
                window.openEditUnit = openEdit;
                window.openCreateDependency = (unitId, levelOrder) => openCreate(unitId, levelOrder);

                return {isVisible, isEditing, errors, modalTitle, contextInfo, closeModal, submitForm};
            }
        });
        unitModalEl.__vue_app__ = app.mount('#unit-modal-app');
    }

    // Vincular botón de crear (NUEVA UNIDAD - NIVEL 1)
    const btnAdd = document.getElementById('btn-add-unit');
    if (btnAdd) btnAdd.onclick = () => window.openCreateUnit(); // Sin argumentos = Raíz

    // Función global para el botón de "Crear Dependencia" en la tabla
    window.openCreateDependency = function (parentId, levelOrder) {
        if (window.openCreateUnit) {
            window.openCreateUnit(parentId, levelOrder);
        }
    };
});


// =============================================================================
// 7. ASIGNAR JEFE (acceso global)
// =============================================================================
window.openAssignBoss = async function (unitId) {
    let modalContainer = document.getElementById('assign-boss-modal-container');
    if (!modalContainer) {
        modalContainer = document.createElement('div');
        modalContainer.id = 'assign-boss-modal-container';
        modalContainer.className = 'custom-modal-overlay';
        modalContainer.innerHTML = '<div class="custom-modal-dialog"></div>';
        document.body.appendChild(modalContainer);
    }

    try {
        const res = await fetch(`/institution/units/assign-boss/${unitId}/`, {
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        });
        if (!res.ok) throw new Error('Error al cargar modal');
        const html = await res.text();

        if (modalContainer.firstElementChild) {
            modalContainer.firstElementChild.innerHTML = html;
        } else {
            modalContainer.innerHTML = html;
        }

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

        modalContainer.style.display = 'flex';
        document.body.classList.add('modal-open');
        modalContainer.dataset.unitId = unitId;
        modalContainer.onclick = (e) => {
            if (e.target === modalContainer) window.closeAssignModal();
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
                icon: 'success', title: '¡Listo!', text: data.message,
                timer: 2000, showConfirmButton: false
            });
            location.reload();
        } else {
            Swal.fire('Atención', 'Seleccione un empleado válido.', 'warning');
        }
    } catch (e) {
        console.error(e);
        Swal.fire('Error', 'Error de conexión con el servidor', 'error');
    }
};