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
        let currentEditUnit = null;

        function ensureSelectOption(selectEl, value, label) {
            if (!selectEl || value === null || value === undefined || value === '') {
                return;
            }

            const stringValue = String(value);
            const existing = Array.from(selectEl.options).find(option => option.value === stringValue);
            if (existing) {
                selectEl.value = stringValue;
                return;
            }

            const option = document.createElement('option');
            option.value = stringValue;
            option.textContent = label || stringValue;
            option.selected = true;
            selectEl.appendChild(option);
            selectEl.value = stringValue;
        }

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

        // Exponer helper para volver al listado previo cuando la tabla está vacía
        window.handleEmptyBack = async function () {
            try {
                if (!currentParentId) {
                    await refreshTablePartial();
                    return;
                }

                const res = await fetch(`/institution/units/detail/${currentParentId}/json/`);
                const data = await res.json();

                if (data.success && data.data) {
                    const parentId = data.data.parent || null;
                    const parentLevel = data.data.parent_level || 1;
                    window.filterByParent(parentId, parentLevel);
                    return;
                }

                await refreshTablePartial();
            } catch (e) {
                console.error('Error en handleEmptyBack:', e);
                // Fallback: recargar la página
                window.location.reload();
            }
        };

        // Toggle para mostrar unidades inactivas
        window.toggleInactiveUnits = function (showInactive) {
            const val = showInactive ? true : false;
            const input = document.querySelector('.table-search-input');
            const q = input ? input.value.trim() : '';
            loadUnitsPartial({parentId: currentParentId, showInactive: val, q: q});
        };

        // =========================================================================
        // 3. LÓGICA NATIVA MODAL UNIDADES
        // =========================================================================
        let shouldLoadParentsOnLevelChange = true;
        window.initUnitModal = function () {
            // 1. Buscamos los elementos exactos del formulario
            const codeInput = document.getElementById('id_code');
            const levelInput = document.getElementById('id_level');
            const parentInput = document.getElementById('id_parent');

            // 2. Leemos el ID del padre oculto en el HTML (inyectado por la URL)
            const contextParentInput = document.getElementById('modal-context-parent');
            const contextParentId = contextParentInput ? contextParentInput.value : '';

            const formElement = document.getElementById('unitForm');
            if (!formElement) return;

            // 3. Verificamos si estamos editando o creando
            const isEditing = formElement.action.includes('update');

            // 4. EL MOTOR AUTOMÁTICO: Si es un registro Nuevo y el código está vacío
            if (!isEditing && codeInput && codeInput.value === '') {
                codeInput.value = 'Calculando...';
                // Armamos la URL exacta como la tenías en Vue
                const url = contextParentId
                    ? '/institution/api/next-code/?parent_id=' + contextParentId
                    : '/institution/api/next-code/?parent_id=null';

                // Hacemos la consulta silenciosa al backend
                fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
                    .then(res => res.json())
                    .then(data => {
                        if (data.success) {
                            // ¡Bingo! Colocamos el código autogenerado en la pantalla
                            codeInput.value = data.next_code;

                            // Llenamos los campos ocultos de jerarquía en segundo plano
                            if (data.suggested_level && levelInput) {
                                levelInput.value = data.suggested_level;
                            }

                            if (contextParentId && parentInput) {
                                parentInput.value = contextParentId;
                            } else if (parentInput) {
                                parentInput.value = ''; // Es un nivel Raíz
                            }
                        }
                    })
                    .catch(err => console.error("Error autogenerando el código correlativo:", err));
            }
        };

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

            if (levelId) {
                try {
                    const res = await fetch(`/institution/api/parents/?level_id=${levelId}`);
                    const data = await res.json();

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
                            }
                            parentSelectEl.appendChild(option);
                        });
                    } else {
                        // Sin padres activos en la respuesta. Si estamos en edición y
                        // tenemos un parent preseleccionado, intentar obtener su info
                        // y agregarlo como opción para que el select NO quede deshabilitado
                        if (preselectedParentId) {
                            try {
                                const detailRes = await fetch(`/institution/units/detail/${preselectedParentId}/json/`);
                                const detailData = await detailRes.json();
                                if (detailData.success && detailData.data) {
                                    const p = detailData.data;
                                    ensureSelectOption(parentSelectEl, preselectedParentId, p.name || `Unidad ${preselectedParentId}`);
                                    isDisabled = false;
                                } else {
                                    // Fallback: opción raíz
                                    placeholderText = '--- Unidad Raíz (No requiere padre) ---';
                                    const emptyOption = document.createElement('option');
                                    emptyOption.value = '';
                                    emptyOption.textContent = placeholderText;
                                    emptyOption.selected = true;
                                    parentSelectEl.appendChild(emptyOption);
                                }
                            } catch (e) {
                                console.error('[loadParents] Error obteniendo parent preseleccionado:', e);
                                placeholderText = '--- Unidad Raíz (No requiere padre) ---';
                                const emptyOption = document.createElement('option');
                                emptyOption.value = '';
                                emptyOption.textContent = placeholderText;
                                emptyOption.selected = true;
                                parentSelectEl.appendChild(emptyOption);
                            }
                        } else {
                            placeholderText = '--- Unidad Raíz (No requiere padre) ---';
                            const emptyOption = document.createElement('option');
                            emptyOption.value = '';
                            emptyOption.textContent = placeholderText;
                            emptyOption.selected = true;
                            parentSelectEl.appendChild(emptyOption);
                        }
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
        }

        const btnAdd = document.getElementById('btn-add-unit');
        if (btnAdd) btnAdd.onclick = () => openAjaxModal('/institution/units/create/', window.initUnitModal);

        // =============================================================================
        // 4. ASIGNAR JEFE
        // =============================================================================
        window.openAssignBoss = async function (unitId) {
            // 1. Create a container for the modal if it doesn't exist
            let modalContainer = document.getElementById('dynamic-modal-container');
            if (!modalContainer) {
                modalContainer = document.createElement('div');
                modalContainer.id = 'dynamic-modal-container';
                // Add the overlay class for proper styling
                modalContainer.classList.add('custom-modal-overlay');
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
                modalContainer.style.display = 'flex'; // Explicitly show the overlay

                const modalElement = modalContainer.querySelector('.custom-modal-dialog'); // Use the project's specific modal class
                if (modalElement) {
                    modalElement.classList.add('active'); // Use 'active' class to show
                }

                // 4. Initialize Select2 for the employee search
                $('#id_boss_assign').select2({
                    dropdownParent: $(modalContainer.querySelector('.custom-modal-dialog')), // Attach to the visible modal
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
                modalContainer.style.display = 'none'; // Re-hide the overlay
            }
        };

        window.submitAssignBoss = async function () {
            const form = document.getElementById('assignBossForm');
            if (!form) {
                console.error('Assign boss form not found');
                return;
            }
            const unitId = form.dataset.unitId;
            const btn = form.querySelector('button[type="submit"]');

            try {
                if (btn) btn.disabled = true;
                const formData = new FormData(form);
                const res = await fetch(`/institution/units/assign-boss/${unitId}/`, {
                    method: 'POST',
                    body: formData,
                    headers: {'X-Requested-With': 'XMLHttpRequest'}
                });
                const data = await res.json();

                if (data.success) {
                    closeDynamicModal();
                    await Swal.fire('Éxito', data.message, 'success');

                    // Si estamos en la página de detalle, actualizamos el header.
                    // Si no, refrescamos la tabla.
                    if (document.getElementById('deliverables-app')) {
                        try {
                            const detailRes = await fetch(`/institution/units/detail/${unitId}/json/`);
                            const detailData = await detailRes.json();
                            if (detailData.success && detailData.data) {
                                const hdr = document.querySelector('.institution-header .header-right');
                                if (hdr) {
                                    const d = detailData.data;
                                    if (d.boss_data) {
                                        const photo = d.boss_data.photo_url ? `<img src="${d.boss_data.photo_url}" class="boss-photo boss-photo-xl" alt="Foto Jefe">` : `<div class="boss-photo boss-photo-xl boss-photo-initials">${(d.boss_data.text || '').split(' ').map(n => n[0] || '').slice(0, 2).join('')}</div>`;
                                        const profileBtn = d.boss_data.person_id ? `<a href="/employee/detail/${d.boss_data.person_id}/" class="btn btn-profile-custom btn-profile-green mt-2 btn-boss-profile" title="Ver Detalle Completo"><i class="fa-solid fa-user"></i> Ver perfil</a>` : '';
                                        const changeBtn = `<button type="button" class="btn btn-profile-custom btn-profile-green mt-2 btn-boss-profile" onclick="openAssignBoss('${unitId}')" title="Asignar Jefe Inmediato"><i class="fa-solid fa-retweet"></i> Cambiar</button>`;
                                        const positionLabel = d.boss_data.position ? d.boss_data.position : 'JEFE INMEDIATO';
                                        hdr.innerHTML = `
                                        <div class="boss-section boss-section-header boss-section-green-light header-boss-card">
                                            ${photo}
                                            <div class="boss-info">
                                                <span class="boss-name">${d.boss_data.text}</span>
                                                <span class="boss-role boss-role-gray"><i class="fa-solid fa-user-tie"></i> ${positionLabel}</span>
                                                <div class="nomina-actions">${profileBtn}${changeBtn}</div>
                                            </div>
                                        </div>`;
                                    } else {
                                        hdr.innerHTML = `
                                        <div class="boss-section boss-section-header boss-section-green-light header-boss-card">
                                            <h2 class="boss-name" style="font-size: 14px"><i class="fa-solid fa-user-tie"></i> ASIGNAR JEFE INMEDIATO</h2>
                                            <button type="button" class="btn-icon btn-list-action" onclick="openAssignBoss('${unitId}')" title="Asignar Jefe Inmediato">
                                                <i class="fas fa-user-tie"></i>
                                            </button>
                                        </div>`;
                                    }
                                }
                            }
                        } catch (e) {
                            console.error('Error actualizando header tras asignar jefe:', e);
                            // Fallback: recargar la página si ocurre un error
                            setTimeout(function () {
                                window.location.reload();
                            }, 600);
                        }
                    } else {
                        // Si no es la vista de detalle, refrescar la tabla parcial
                        await refreshTablePartial();
                    }
                } else {
                    Swal.fire('Error', data.message || 'Revise los datos', 'error');
                }
            } catch (e) {
                console.error(e);
                Swal.fire('Error', 'Error de conexión', 'error');
            } finally {
                if (btn) btn.disabled = false;
            }
        };
    }
)
;
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
window.exportUnitEmployees = function (unitId, statusCode) {
    const url = `/institution/units/${unitId}/export-employees/?status=${statusCode}`;
    window.location.href = url;
};
