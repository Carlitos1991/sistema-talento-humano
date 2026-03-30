document.addEventListener('DOMContentLoaded', () => {
    const {createApp, ref} = Vue;

    // =========================================================================
    // 1. MAPA DE TARJETAS DE NIVEL Y FILTRADO
    // =========================================================================
    const levelCards = {};
    document.querySelectorAll('.stat-card[id^="card-filter-"]').forEach(card => {
        const levelId = card.id.replace('card-filter-', '');
        levelCards[levelId] = card;
    });

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

    // Estado actual de navegación (padre y nivel)
    let currentParentId = null;
    let currentLevelOrder = null;

    // Función para cargar la tabla parcial respetando el parent y show_inactive
    async function loadUnitsPartial({parentId = null, showInactive = false, q = ''} = {}) {
        const params = new URLSearchParams();
        if (parentId) params.set('parent_id', parentId);
        if (showInactive) params.set('show_inactive', 'true');
        if (q) params.set('q', q);

        const url = '/institution/units/partial_table/?' + params.toString();
        try {
            const r = await fetch(url);
            const html = await r.text();
            document.getElementById('table-content-wrapper').innerHTML = html;
            const newTable = document.querySelector('.managed-table');
            if (newTable) new TableManager(newTable);
        } catch (e) {
            console.error('Error cargando unidades:', e);
        }
    }

    // Filtrar por padre: hace drill-down y actualiza estado
    window.filterByParent = function (parentId, nextLevelOrder) {
        // Normalizar
        if (!parentId || parentId === '' || parentId === 'None') {
            currentParentId = null;
            currentLevelOrder = 1;
        } else {
            currentParentId = parentId;
            currentLevelOrder = nextLevelOrder || null;
        }

        const toggleEl = document.getElementById('toggleInactiveUnits');
        const showInactive = toggleEl && toggleEl.checked;
        const input = document.querySelector('.table-search-input');
        const q = input ? input.value.trim() : '';

        loadUnitsPartial({parentId: currentParentId, showInactive: showInactive, q: q});
    };

    // Inicialización visual
    // Removed stats-driven initialization to improve performance

    Object.entries(levelCards).forEach(([levelId, card]) => {
        if (card) {
            card.addEventListener('click', () => window.filterByLevel(levelId, card));
        }
    });

    // =========================================================================
    // 2. TOGGLE STATUS (ACTIVAR/DESACTIVAR)
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
                    await refreshTablePartial();
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

    // Auxiliar para recargar la tabla sin perder filtros
    async function refreshTablePartial() {
        const tm = document.querySelector('.managed-table')?._tableManager;
        const savedSearch = tm?.filterState.search || '';
        const savedFilter = {...tm?.filterState};
        // Respect current toggle state and parent when refreshing
        const toggleEl = document.getElementById('toggleInactiveUnits');
        const showInactive = toggleEl && toggleEl.checked;
        const input = document.querySelector('.table-search-input');
        const q = input ? input.value.trim() : '';
        const params = new URLSearchParams();
        if (currentParentId) params.set('parent_id', currentParentId);
        if (showInactive) params.set('show_inactive', 'true');
        if (q) params.set('q', q);
        const r = await fetch('/institution/units/partial_table/?' + params.toString());
        const html = await r.text();
        document.getElementById('table-content-wrapper').innerHTML = html;

        const newTable = document.querySelector('.managed-table');
        if (newTable) new TableManager(newTable);

        if (newTable && newTable._tableManager) {
            if (savedSearch) {
                const input = document.querySelector('.table-search-input');
                if (input) input.value = savedSearch;
            }
            newTable._tableManager.filterState = savedFilter;
            newTable._tableManager.applyGlobalFilters();
        }

        const activeCard = document.querySelector('.stat-card:not(.opacity-low)');
        if (activeCard) {
            window.filterByLevel(activeCard.id.replace('card-filter-', ''), activeCard);
        }
    }

    // Toggle para mostrar unidades inactivas
    window.toggleInactiveUnits = function (showInactive) {
        const val = showInactive ? true : false;
        const input = document.querySelector('.table-search-input');
        const q = input ? input.value.trim() : '';
        loadUnitsPartial({parentId: currentParentId, showInactive: val, q: q});
    };

    // =========================================================================
    // 3. MODAL CREAR / EDITAR UNIDAD (VUE APP)
    // =========================================================================
    let shouldLoadParentsOnLevelChange = true;

    async function loadParents(levelId, preselectedParentId = null) {
        const parentSelectEl = document.getElementById('id_parent');
        if (!parentSelectEl) {
            console.error('[loadParents] No se encontró elemento id_parent');
            return;
        }

        // Limpiar opciones anteriores
        parentSelectEl.innerHTML = '';
        
        let isDisabled = true;
        let placeholderText = '--- Seleccione Nivel Primero ---';

        console.log(`[loadParents] Cargando padres para nivel ${levelId}, preseleccionado: ${preselectedParentId}`);

        if (levelId) {
            try {
                const res = await fetch(`/institution/api/parents/?level_id=${levelId}`);
                const data = await res.json();
                console.log(`[loadParents] Response API:`, data);
                
                if (data.results && data.results.length > 0) {
                    isDisabled = false;
                    placeholderText = '--- Seleccione Unidad Padre ---';
                    
                    // Opción vacía/placeholder
                    const emptyOption = document.createElement('option');
                    emptyOption.value = '';
                    emptyOption.textContent = placeholderText;
                    parentSelectEl.appendChild(emptyOption);
                    
                    // Agregar opciones de padres disponibles
                    data.results.forEach(item => {
                        const option = document.createElement('option');
                        option.value = item.id;
                        option.textContent = item.text;
                        if (String(item.id) === String(preselectedParentId)) {
                            option.selected = true;
                            console.log(`[loadParents] Opción ${item.id} marcada como seleccionada`);
                        }
                        parentSelectEl.appendChild(option);
                    });
                } else {
                    placeholderText = '--- Unidad Raíz (No requiere padre) ---';
                    const emptyOption = document.createElement('option');
                    emptyOption.value = '';
                    emptyOption.textContent = placeholderText;
                    emptyOption.selected = true;
                    parentSelectEl.appendChild(emptyOption);
                    console.log(`[loadParents] Sin padres disponibles, unidad raíz`);
                }
            } catch (e) {
                console.error('[loadParents] Error cargando padres:', e);
            }
        } else {
            // Si no hay levelId, mostrar solo opción de raíz
            const emptyOption = document.createElement('option');
            emptyOption.value = '';
            emptyOption.textContent = '--- Seleccione Nivel Primero ---';
            emptyOption.selected = true;
            parentSelectEl.appendChild(emptyOption);
        }
        
        // Habilitar o deshabilitar el select según corresponda
        parentSelectEl.disabled = isDisabled;
        console.log(`[loadParents] Select disabled: ${isDisabled}, opciones totales: ${parentSelectEl.options.length}`);
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
                const modalTitle = ref('Nueva Unidad');
                const isActive = ref(true);  // Nueva variable para manejar el estado
                const formEl = 'unitForm';

                const openCreate = async (parentId = null) => {
                    isEditing.value = false;
                    currentId.value = null;
                    errors.value = {};
                    isActive.value = true;  // Por defecto las nuevas unidades están activas
                    const f = document.getElementById(formEl);
                    if (f) f.reset();
                    isVisible.value = true;
                    document.body.classList.add('no-scroll');

                    const levelSelect = document.getElementById('id_level');
                    const parentSelectEl = document.getElementById('id_parent');
                    const codeInput = document.getElementById('id_code');

                    // Resetear estados de bloqueo
                    if (levelSelect) levelSelect.disabled = false;
                    if (parentSelectEl) parentSelectEl.disabled = false;

                    const url = parentId ? `/institution/api/next-code/?parent_id=${parentId}` : `/institution/api/next-code/?parent_id=null`;

                    try {
                        const res = await fetch(url);
                        const data = await res.json();
                        if (data.success) {
                            if (codeInput) codeInput.value = data.next_code;
                            if (levelSelect) levelSelect.value = data.suggested_level;

                            if (parentId) {
                                modalTitle.value = 'Nueva Unidad Dependiente';
                                await loadParents(data.suggested_level, parentId);
                                if (parentSelectEl) {
                                    parentSelectEl.value = parentId;
                                    parentSelectEl.disabled = true;
                                }
                                if (levelSelect) levelSelect.disabled = true;
                            } else {
                                modalTitle.value = 'Nueva Unidad Administrativa';
                                await loadParents(data.suggested_level);
                            }
                        }
                    } catch (e) {
                        console.error(e);
                    }

                    // Configurar listener manual para cambios de nivel en modo Raíz
                    if (levelSelect) {
                        levelSelect.onchange = async () => {
                            if (!isEditing.value && !parentId) {
                                await loadParents(levelSelect.value);
                            }
                        };
                    }
                };

                const openEdit = async (id) => {
                    isEditing.value = true;
                    currentId.value = id;
                    errors.value = {};
                    try {
                        const res = await fetch(`/institution/units/detail/${id}/json/`);
                        const data = await res.json();
                        if (data.success) {
                            isVisible.value = true;
                            const d = data.data;
                            
                            // Esperar a que el DOM esté listo
                            await new Promise(resolve => setTimeout(resolve, 100));
                            
                            // Llenar los campos de texto
                            document.getElementById('id_name').value = d.name;
                            document.getElementById('id_code').value = d.code;
                            document.getElementById('id_address').value = d.address || '';
                            document.getElementById('id_phone').value = d.phone || '';
                            document.getElementById('id_mission').value = d.mission || '';
                            document.getElementById('id_level').value = d.level;
                            isActive.value = d.is_active;
                            
                            // Cargar padres y esperar a que se complete
                            await loadParents(d.level, d.parent);
                            
                            // EXPLICITAR: Establecer el valor parent después de que loadParents() haya completado
                            const parentSelectEl = document.getElementById('id_parent');
                            if (parentSelectEl && d.parent) {
                                parentSelectEl.value = String(d.parent);
                                console.log(`[DEBUG] Parent establecido a: ${d.parent}`);
                            } else if (parentSelectEl) {
                                parentSelectEl.value = '';
                                console.log(`[DEBUG] Parent está vacío (unidad raíz)`);
                            }
                        }
                    } catch (e) {
                        console.error(e);
                    }
                };

                const submitForm = async () => {
                    const form = document.getElementById(formEl);
                    
                    // DEBUG PASO 1: Ver el estado actual de los elementos
                    const parentSelectEl = document.getElementById('id_parent');
                    const levelSelectEl = document.getElementById('id_level');
                    
                    console.log('===== DEBUG SUBMIT =====');
                    console.log('1. Estado de elementos SELECT:');
                    console.log('   - id_parent (SELECT):', parentSelectEl?.tagName, 'value=', parentSelectEl?.value);
                    console.log('   - id_level (SELECT):', levelSelectEl?.tagName, 'value=', levelSelectEl?.value);
                    
                    // DEBUG PASO 2: Mostrar todas las opciones disponibles en parent
                    if (parentSelectEl) {
                        console.log('2. Opciones disponibles en id_parent:');
                        Array.from(parentSelectEl.options).forEach((opt, idx) => {
                            console.log(`   [${idx}] value="${opt.value}" text="${opt.text}" selected=${opt.selected}`);
                        });
                    }
                    
                    // DEBUG PASO 3: Crear FormData y mostrar qué contiene
                    const formData = new FormData(form);
                    console.log('3. Contenido de FormData ANTES de enviar:');
                    for (let [key, value] of formData.entries()) {
                        if (key === 'parent' || key === 'level') {
                            console.log(`   ${key} = "${value}"`);
                        }
                    }
                    
                    const url = isEditing.value
                        ? `/institution/units/update/${currentId.value}/`
                        : '/institution/units/create/';

                    console.log('4. URL de destino:', url);
                    console.log('5. isEditing:', isEditing.value);
                    console.log('===== FIN DEBUG =====');

                    try {
                        const res = await fetch(url, {
                            method: 'POST',
                            body: formData,
                            headers: {'X-Requested-With': 'XMLHttpRequest'}
                        });
                        const data = await res.json();

                        if (data.success) {
                            // 2. Cerrar modal y limpiar estados de scroll
                            closeModal();
                            isVisible.value = false;
                            document.body.classList.remove('no-scroll');

                            Swal.fire({
                                icon: 'success',
                                title: 'Guardado correctamente',
                                toast: true,
                                position: 'top-end',
                                showConfirmButton: false,
                                timer: 2000
                            });

                            const tableWrapper = document.getElementById('table-content-wrapper');

                            if (tableWrapper) {
                                await refreshTablePartial();
                            } else {
                                setTimeout(() => {
                                    location.reload();
                                }, 1200);
                            }

                        } else {
                            errors.value = data.errors || {};
                            if (!isEditing.value && modalTitle.value.includes('Dependiente')) {
                                $('#id_parent').attr('disabled', true);
                                if (levelEl) levelEl.readOnly = true;
                            }
                        }
                    } catch (e) {
                        console.error("Error al enviar formulario:", e);
                        Swal.fire('Error', 'No se pudo conectar con el servidor', 'error');
                    }
                };

                const closeModal = () => {
                    isVisible.value = false;
                    document.body.classList.remove('no-scroll');
                };

                // Exponer funciones al objeto window para acceso desde HTML
                window.openCreateUnit = openCreate;
                window.openEditUnit = openEdit;
                window.openCreateDependency = (pid) => openCreate(pid);

                return {isVisible, isEditing, errors, modalTitle, isActive, closeModal, submitForm};
            }
        });
        unitModalEl.__vue_app__ = app.mount('#unit-modal-app');
    }

    // Vincular botón principal
    const btnAdd = document.getElementById('btn-add-unit');
    if (btnAdd) btnAdd.onclick = () => window.openCreateUnit();

    // =============================================================================
    // 4. ASIGNAR JEFE
    // =============================================================================
    window.openAssignBoss = async function (unitId) {
        // 1. Create a container for the modal if it doesn't exist
        let modalContainer = document.getElementById('dynamic-modal-container');
        if (!modalContainer) {
            modalContainer = document.createElement('div');
            modalContainer.id = 'dynamic-modal-container';
            document.body.appendChild(modalContainer);
        }

        try {
            // 2. Fetch the modal content from the server
            const response = await fetch(`/institution/units/assign-boss/${unitId}/`, {
                headers: {'X-Requested-With': 'XMLHttpRequest'}
            });
            const html = await response.text();

            // 3. Inject the HTML and show the modal
            modalContainer.innerHTML = html;
            const modalElement = modalContainer.querySelector('.custom-modal-main'); // Use the project's specific modal class
            if (modalElement) {
                modalElement.classList.add('active'); // Use 'active' class to show
            }

            // 4. Initialize Select2 for the employee search
            $('#id_boss_assign').select2({
                dropdownParent: $(modalContainer.querySelector('.custom-modal-main')), // Attach to the visible modal
                width: '100%',
                placeholder: 'Buscar empleado...',
                ajax: {
                    url: '/institution/api/employee/search/',
                    dataType: 'json',
                    data: (params) => ({term: params.term}),
                    processResults: (data) => ({results: data.results})
                }
            });

        } catch (e) {
            console.error('Error opening assign boss modal:', e);
        }
    };

    // This function should be called by the 'Cancel' or 'Close' button inside the modal's HTML
    window.closeDynamicModal = function () {
        const modalContainer = document.getElementById('dynamic-modal-container');
        if (modalContainer) {
            modalContainer.innerHTML = ''; // Just clear the content
        }
    };

    window.submitAssignBoss = async function () {
        const form = document.getElementById('assignBossForm');
        const unitId = form.dataset.unitId;
        try {
            const formData = new FormData(form);
            const res = await fetch(`/institution/units/assign-boss/${unitId}/`, {
                method: 'POST',
                body: formData,
                headers: {'X-Requested-With': 'XMLHttpRequest'}
            });
            const data = await res.json();
            if (data.success) {
                closeDynamicModal();
                Swal.fire('Éxito', data.message, 'success').then(() => {
                    location.reload(); // Reload to see the change
                });
            } else {
                // Handle errors if needed
                console.error('Error assigning boss:', data.errors);
            }
        } catch (e) {
            console.error(e);
        }
    };
                if (document.getElementById('deliverables-app')) {
                    try {
                        const detailRes = await fetch(`/institution/units/detail/${unitId}/json/`);
                        const detailData = await detailRes.json();
                        if (detailData.success && detailData.data) {
                            const hdr = document.querySelector('.institution-header .header-right');
                            if (hdr) {
                                const d = detailData.data;
                                if (d.boss_data) {
                                    const photo = d.boss_data.photo_url ? `<img src="${d.boss_data.photo_url}" class="boss-photo boss-photo-xl" alt="Foto Jefe">` : `<div class="boss-photo boss-photo-xl boss-photo-initials">${(d.boss_data.text||'').split(' ').map(n=>n[0]||'').slice(0,2).join('')}</div>`;
                                    const profileBtn = d.boss_data.person_id ? `<a href="/employee/detail/${d.boss_data.person_id}/" class="btn btn-profile-custom btn-profile-green mt-2 btn-boss-profile" title="Ver Detalle Completo"><i class="fa-solid fa-user"></i> Ver perfil</a>` : '';
                                    const changeBtn = `<button type="button" class="btn btn-profile-custom btn-profile-green mt-2 btn-boss-profile" onclick="openAssignBoss('${unitId}')" title="Asignar Jefe Inmediato"><i class="fa-solid fa-retweet"></i> Cambiar</button>`;
                                    const positionLabel = d.boss_data.position ? d.boss_data.position : 'JEFE INMEDIATO';
                                    hdr.innerHTML = `\n                                        <div class="boss-section boss-section-header boss-section-green-light header-boss-card">\n                                            ${photo}\n                                            <div class="boss-info">\n                                                <span class="boss-name">${d.boss_data.text}</span>\n                                                <span class="boss-role boss-role-gray"><i class="fa-solid fa-user-tie"></i> ${positionLabel}</span>\n                                                <div class="nomina-actions">${profileBtn}${changeBtn}</div>\n                                            </div>\n                                        </div>`;
                                } else {
                                    hdr.innerHTML = `\n                                        <div class="boss-section boss-section-header boss-section-green-light header-boss-card">\n                                            <h2 class="boss-name" style="font-size: 14px"><i class="fa-solid fa-user-tie"></i> ASIGNAR JEFE INMEDIATO</h2>\n                                            <button type="button" class="btn-icon btn-list-action" onclick="openAssignBoss('${unitId}')" title="Asignar Jefe Inmediato">\n                                                <i class="fas fa-user-tie"></i>\n                                            </button>\n                                        </div>`;
                                }
                            }
                        }
                    } catch (e) {
                        console.error('Error actualizando header tras asignar jefe:', e);
                        // Fallback: recargar la página si ocurre un error
                        setTimeout(function() { window.location.reload(); }, 600);
                    }
                } else {
                    await refreshTablePartial();
                }
            } else {
                Swal.fire('Error', 'Revise los datos', 'error');
            }
        } catch (e) {
            console.error(e);
        }
    };
});
/* --- LÓGICA DE REUBICACIÓN DE EMPLEADOS (Migrada de person.js) --- */

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
    loadUnitLevelRelocate(null);
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

function loadUnitLevelRelocate(parentId) {
    // Endpoint definido en institution:api_unit_children
    const apiUrl = '/institution/api/unit-children/';
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
                .append('<option value="">-- Seleccione --</option>');

            data.units.forEach(u => {
                $select.append(`<option value="${u.id}" data-has-children="${u.has_children}">${u.name}</option>`);
            });

            $wrapper.append($label).append($select);
            $('#relocate-combos-wrapper').append($wrapper);

            $select.select2({
                dropdownParent: $('#modal-relocate-employee'),
                width: '100%'
            }).on('change', function () {
                const val = $(this).val();
                const hasChild = $(this).find(':selected').data('has-children');
                $(this).closest('.form-group').nextAll().remove();
                if (val && (hasChild === true || hasChild === "true" || hasChild === "True")) {
                    loadUnitLevelRelocate(val);
                }
            });
        }
    });
}

// Handler para el envío del formulario de reubicación
$(document).on('submit', '#form-relocate-employee', function (e) {
    e.preventDefault();
    let finalUnitId = null;
    let finalUnitText = '';

    $('#relocate-combos-wrapper select').each(function () {
        if ($(this).val()) {
            finalUnitId = $(this).val();
            finalUnitText = $(this).find('option:selected').text();
        }
    });

    if (!finalUnitId) {
        Swal.fire({icon: 'warning', title: 'Seleccione una unidad final', toast: true, position: 'top-end'});
        return;
    }

    const btn = $(this).find('button[type="submit"]');
    btn.prop('disabled', true).html('Guardando...');

    $.ajax({
        url: '/person/relocate/',
        method: 'POST',
        headers: {'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value},
        data: {
            person_id: window.selectedRelocatePersonId,
            unit_id: finalUnitId
        },
        success: function (resp) {
            if (resp.success) {
                Swal.fire({
                    icon: 'success',
                    title: 'Reubicación exitosa',
                    html: `Empleado movido a <b>${finalUnitText}</b>`,
                    timer: 2000
                }).then(() => {
                    location.reload(); // Recargamos para actualizar la nómina de la unidad
                });
            } else {
                Swal.fire({icon: 'error', title: resp.message});
            }
        },
        error: () => Swal.fire({icon: 'error', title: 'Error de servidor'}),
        complete: () => btn.prop('disabled', false).html('Confirmar Reubicación')
    });
});

// =========================================================================
// FUNCIÓN PARA EXPORTAR EMPLEADOS DE UNA UNIDAD A EXCEL
// =========================================================================
window.exportUnitEmployees = function(unitId, statusCode) {
    const url = `/institution/units/${unitId}/export-employees/?status=${statusCode}`;
    window.location.href = url;
};
