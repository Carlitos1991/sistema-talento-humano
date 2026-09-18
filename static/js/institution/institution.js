/**
 * SIGETH - Módulo de Gestión Institucional y Estructura Organizacional
 * Arquitectura JavaScript Vanilla + Integración con motor central main.js
 */

document.addEventListener('DOMContentLoaded', () => {

    // =========================================================================
    // 1. STAT CARDS & LEVEL FILTERING
    // =========================================================================
    const levelCards = {};
    document.querySelectorAll('.stat-card[id^="card-filter-"]').forEach(card => {
        const levelId = card.id.replace('card-filter-', '');
        levelCards[levelId] = card;
    });

    window.filterByLevel = function (levelId, clickedCard = null) {
        Object.values(levelCards).forEach(card => {
            if (card) card.classList.add('opacity-low');
        });
        const activeCard = clickedCard || levelCards[levelId];
        if (activeCard) activeCard.classList.remove('opacity-low');

        const managedTable = document.querySelector('.managed-table');
        if (managedTable && managedTable._tableManager) {
            if (levelId === 'total') {
                managedTable._tableManager.filterByColumnData('level', 'all');
            } else {
                managedTable._tableManager.filterByColumnData('level', String(levelId));
            }
        }
    };

    // Variables de estado jerárquico y debounce de búsqueda
    let currentParentId = null;
    let currentLevelOrder = null;
    let unitSearchRequestId = 0;
    let unitSearchDebounceTimer = null;

    function ensureSelectOption(selectElement, value, labelText) {
        if (!selectElement || value === null || value === undefined || value === '') return;

        const stringValue = String(value);
        const existingOption = Array.from(selectElement.options).find(opt => opt.value === stringValue);
        if (existingOption) {
            selectElement.value = stringValue;
            return;
        }

        const newOption = document.createElement('option');
        newOption.value = stringValue;
        newOption.textContent = labelText || stringValue;
        newOption.selected = true;
        selectElement.appendChild(newOption);
        selectElement.value = stringValue;
    }

    function getUnitSearchInputElement() {
        return document.getElementById('unitSearchInput')
            || document.querySelector('[data-search-role="unit-search"]')
            || document.querySelector('#searchInput')
            || document.querySelector('.table-search-input')
            || document.querySelector('.search-input');
    }

    function getCurrentUnitSearchQuery() {
        const searchInput = getUnitSearchInputElement();
        return searchInput ? searchInput.value.trim() : '';
    }

    // Carga parcial asíncrona de unidades respetando jerarquía y filtros activos
    async function loadUnitsPartial({parentId = null, showInactive = false, query = ''} = {}) {
        const requestId = ++unitSearchRequestId;
        const requestParams = new URLSearchParams();
        if (parentId) requestParams.set('parent_id', parentId);
        if (showInactive) requestParams.set('show_inactive', 'true');
        if (query) requestParams.set('q', query);

        const requestUrl = '/institution/units/partial_table/?' + requestParams.toString();
        try {
            const response = await fetch(requestUrl, {
                headers: {'X-Requested-With': 'XMLHttpRequest'}
            });
            const htmlContent = await response.text();

            if (requestId !== unitSearchRequestId) return;

            const tableWrapper = document.getElementById('table-content-wrapper');
            if (tableWrapper) {
                tableWrapper.innerHTML = htmlContent;
                const newTable = tableWrapper.querySelector('.managed-table');
                if (newTable && typeof TableManager !== 'undefined') {
                    newTable.dataset.externalSearch = 'true';
                    new TableManager(newTable);
                }
            }
        } catch (error) {
            console.error('Error loading units partial table:', error);
        }
    }

    // Navegación en árbol jerárquico (Drill-down)
    window.filterByParent = function (parentId, nextLevelOrder) {
        if (!parentId || parentId === '' || parentId === 'None') {
            currentParentId = null;
            currentLevelOrder = 1;
        } else {
            currentParentId = parentId;
            currentLevelOrder = nextLevelOrder || null;
        }

        const toggleInactiveElement = document.getElementById('toggleInactiveUnits');
        const showInactive = toggleInactiveElement ? toggleInactiveElement.checked : false;
        const searchQuery = getCurrentUnitSearchQuery();

        loadUnitsPartial({parentId: currentParentId, showInactive, query: searchQuery});
    };

    // Escuchador de entrada con retardo para la caja de búsqueda
    const unitSearchInput = getUnitSearchInputElement();
    if (unitSearchInput) {
        unitSearchInput.addEventListener('input', function () {
            const searchQuery = this.value.trim();
            const toggleInactiveElement = document.getElementById('toggleInactiveUnits');
            const showInactive = toggleInactiveElement ? toggleInactiveElement.checked : false;

            clearTimeout(unitSearchDebounceTimer);
            unitSearchDebounceTimer = setTimeout(() => {
                loadUnitsPartial({parentId: currentParentId, showInactive, query: searchQuery});
            }, 250);
        });
    }

    // Eventos de clic para filtrado por tarjetas de niveles
    Object.entries(levelCards).forEach(([levelId, cardElement]) => {
        if (cardElement) {
            cardElement.addEventListener('click', () => window.filterByLevel(levelId, cardElement));
        }
    });

    // Helper para retornar a la unidad superior si la lista queda sin resultados
    window.handleEmptyBack = async function () {
        try {
            if (!currentParentId) {
                if (typeof window.refreshCurrentTable === 'function') {
                    window.refreshCurrentTable();
                } else {
                    location.reload();
                }
                return;
            }

            const response = await fetch(`/institution/units/detail/${currentParentId}/json/`, {
                headers: {'X-Requested-With': 'XMLHttpRequest'}
            });
            const responseData = await response.json();

            if (responseData.success && responseData.data) {
                const parentId = responseData.data.parent || null;
                const parentLevel = responseData.data.parent_level || 1;
                window.filterByParent(parentId, parentLevel);
                return;
            }

            window.refreshCurrentTable();
        } catch (error) {
            console.error('Error in handleEmptyBack fallback:', error);
            window.location.reload();
        }
    };

    // =========================================================================
    // 2. MODAL FORM LOGIC (CORRELATIVE CODE & PARENT GENERATOR)
    // =========================================================================
    window.initUnitModal = function () {
        const codeInput = document.getElementById('id_code');
        const levelInput = document.getElementById('id_level');
        const parentInput = document.getElementById('id_parent');

        const contextParentInput = document.getElementById('modal-context-parent');
        const contextParentId = contextParentInput ? contextParentInput.value : '';

        const formElement = document.getElementById('unitForm');
        if (!formElement) return;

        const isEditing = formElement.action.includes('update');

        if (!isEditing && codeInput && codeInput.value === '') {
            codeInput.value = 'Calculando...';
            const apiUrl = contextParentId
                ? '/institution/api/next-code/?parent_id=' + contextParentId
                : '/institution/api/next-code/?parent_id=null';

            fetch(apiUrl, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
                .then(res => res.json())
                .then(data => {
                    if (data.success) {
                        codeInput.value = data.next_code;
                        if (data.suggested_level && levelInput) {
                            levelInput.value = data.suggested_level;
                        }
                        if (contextParentId && parentInput) {
                            parentInput.value = contextParentId;
                        } else if (parentInput) {
                            parentInput.value = '';
                        }
                    }
                })
                .catch(err => console.error("Error generating correlative unit code:", err));
        }
    };

    async function loadParents(levelId, preselectedParentId = null) {
        const parentSelect = document.getElementById('id_parent');
        if (!parentSelect) return;

        parentSelect.innerHTML = '';
        let isDisabled = true;
        let placeholderText = '--- Seleccione Nivel Primero ---';

        if (levelId) {
            try {
                const response = await fetch(`/institution/api/parents/?level_id=${levelId}`, {
                    headers: {'X-Requested-With': 'XMLHttpRequest'}
                });
                const data = await response.json();

                if (data.results && data.results.length > 0) {
                    isDisabled = false;
                    placeholderText = '--- Seleccione Unidad Padre ---';

                    const defaultOption = document.createElement('option');
                    defaultOption.value = '';
                    defaultOption.textContent = placeholderText;
                    parentSelect.appendChild(defaultOption);

                    data.results.forEach(item => {
                        const opt = document.createElement('option');
                        opt.value = item.id;
                        opt.textContent = item.text;
                        if (String(item.id) === String(preselectedParentId)) {
                            opt.selected = true;
                        }
                        parentSelect.appendChild(opt);
                    });
                } else {
                    if (preselectedParentId) {
                        try {
                            const detailResponse = await fetch(`/institution/units/detail/${preselectedParentId}/json/`);
                            const detailData = await detailResponse.json();
                            if (detailData.success && detailData.data) {
                                ensureSelectOption(parentSelect, preselectedParentId, detailData.data.name || `Unidad ${preselectedParentId}`);
                                isDisabled = false;
                            } else {
                                const rootOption = document.createElement('option');
                                rootOption.value = '';
                                rootOption.textContent = '--- Unidad Raíz (No requiere padre) ---';
                                rootOption.selected = true;
                                parentSelect.appendChild(rootOption);
                            }
                        } catch (err) {
                            console.error('Error fetching preselected parent detail:', err);
                            const fallbackOption = document.createElement('option');
                            fallbackOption.value = '';
                            fallbackOption.textContent = '--- Unidad Raíz (No requiere padre) ---';
                            fallbackOption.selected = true;
                            parentSelect.appendChild(fallbackOption);
                        }
                    } else {
                        const rootOption = document.createElement('option');
                        rootOption.value = '';
                        rootOption.textContent = '--- Unidad Raíz (No requiere padre) ---';
                        rootOption.selected = true;
                        parentSelect.appendChild(rootOption);
                    }
                }
            } catch (err) {
                console.error('Error loading parents list:', err);
            }
        } else {
            const defaultOption = document.createElement('option');
            defaultOption.value = '';
            defaultOption.textContent = '--- Seleccione Nivel Primero ---';
            defaultOption.selected = true;
            parentSelect.appendChild(defaultOption);
        }

        parentSelect.disabled = isDisabled;
    }

    const btnAddUnit = document.getElementById('btn-add-unit');
    if (btnAddUnit) {
        btnAddUnit.onclick = () => openAjaxModal('/institution/units/create/', window.initUnitModal);
    }

    // =========================================================================
    // 3. IMMEDIATE BOSS ASSIGNMENT (SUBMIT LOGIC)
    // =========================================================================
    window.submitAssignBoss = async function () {
        const formElement = document.getElementById('assignBossForm');
        if (!formElement) return;

        const unitId = formElement.dataset.unitId;
        const submitButton = formElement.querySelector('button[type="submit"]');

        try {
            if (submitButton) submitButton.disabled = true;
            const formData = new FormData(formElement);
            const response = await fetch(`/institution/units/assign-boss/${unitId}/`, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': typeof getCSRF === 'function' ? getCSRF() : ''
                }
            });
            const data = await response.json();

            if (data.success) {
                closeModal(); // Cierre estándar del modal universal
                showToast(data.message || 'Jefe asignado correctamente.', 'success');

                // Si está en la vista de detalle, actualiza la tarjeta del header
                if (document.querySelector('.institution-detail-container')) {
                    try {
                        const detailResponse = await fetch(`/institution/units/detail/${unitId}/json/`);
                        const detailData = await detailResponse.json();
                        if (detailData.success && detailData.data) {
                            const headerRight = document.querySelector('.institution-header-card .header-right');
                            if (headerRight) {
                                const unitInfo = detailData.data;
                                if (unitInfo.boss_data) {
                                    const photoHtml = unitInfo.boss_data.photo_url
                                        ? `<img src="${unitInfo.boss_data.photo_url}" class="boss-photo boss-photo-xl" alt="Foto Jefe">`
                                        : `<div class="boss-photo boss-photo-xl boss-photo-initials">${(unitInfo.boss_data.text || '').split(' ').map(n => n[0] || '').slice(0, 2).join('')}</div>`;
                                    const profileLink = unitInfo.boss_data.person_id
                                        ? `<a href="/employee/detail/${unitInfo.boss_data.person_id}/" class="btn btn-profile-custom btn-profile-green mt-2 btn-boss-profile" title="Ver Detalle Completo"><i class="fa-solid fa-user"></i> Ver perfil</a>`
                                        : '';
                                    const changeButton = `<button type="button" class="btn btn-profile-custom btn-profile-green mt-2 btn-boss-profile" onclick="openAjaxModal('/institution/units/assign-boss/${unitId}/')" title="Asignar Jefe Inmediato"><i class="fa-solid fa-retweet"></i> Cambiar</button>`;
                                    const positionLabel = unitInfo.boss_data.position || 'JEFE INMEDIATO';

                                    headerRight.innerHTML = `
                                    <div class="boss-section boss-section-header boss-section-green-light header-boss-card">
                                        ${photoHtml}
                                        <div class="boss-info">
                                            <span class="boss-name">${unitInfo.boss_data.text}</span>
                                            <span class="boss-role boss-role-gray"><i class="fa-solid fa-user-tie"></i> ${positionLabel}</span>
                                            <div class="nomina-actions">${profileLink}${changeButton}</div>
                                        </div>
                                    </div>`;
                                } else {
                                    headerRight.innerHTML = `
                                    <div class="boss-section boss-section-header boss-section-green-light header-boss-card boss-card-empty">
                                        <div class="boss-empty-content">
                                            <h2 class="boss-name boss-empty-title"><i class="fa-solid fa-user-tie"></i> ASIGNAR JEFE INMEDIATO</h2>
                                            <button type="button" class="btn-red-circle" onclick="openAjaxModal('/institution/units/assign-boss/${unitId}/')" title="Asignar Jefe Inmediato">
                                                <i class="fas fa-user-tie"></i>
                                            </button>
                                        </div>
                                    </div>`;
                                }
                            }
                        }
                    } catch (err) {
                        console.error('Error refreshing header boss widget:', err);
                        setTimeout(() => location.reload(), 600);
                    }
                } else {
                    refreshCurrentTable();
                }
            } else {
                Swal.fire({
                    icon: 'warning',
                    title: 'Atención',
                    text: data.message || 'Revise los datos ingresados.',
                    confirmButtonText: 'Entendido'
                });
            }
        } catch (error) {
            console.error('Error submitting boss assignment:', error);
            Swal.fire({
                icon: 'error',
                title: 'Error',
                text: 'Error de comunicación con el servidor.',
                confirmButtonText: 'Entendido'
            });
        } finally {
            if (submitButton) submitButton.disabled = false;
        }
    };

});

/* =========================================================================
   4. MODAL ESTÁTICO: REUBICAR UNIDAD ADMINISTRATIVA
   ========================================================================= */

/**
 * Carga los datos de la unidad dentro de modal_relocate_unit.
 * La apertura y el cierre se gestionan con openModal() y closeModal() de main.js.
 */
window.initRelocateUnitModal = function (unitId) {
    const formElement = document.getElementById('relocateForm');
    if (formElement) formElement.reset();

    const errorContainer = document.getElementById('errorContainer');
    if (errorContainer) errorContainer.style.display = 'none';

    fetch(`/institution/units/detail/${unitId}/json/`, {
        headers: {'X-Requested-With': 'XMLHttpRequest'}
    })
        .then(response => response.json())
        .then(res => {
            if (res.success && res.data) {
                const nameField = document.getElementById('unitNameField');
                const parentField = document.getElementById('currentParentField');
                if (nameField) nameField.value = res.data.name || '';
                if (parentField) parentField.value = res.data.parent_name || 'Sin padre (Nivel Raíz)';

                return fetch(`/institution/api/parents/?level_id=${res.data.level}&direct_parent_only=false`, {
                    headers: {'X-Requested-With': 'XMLHttpRequest'}
                });
            }
        })
        .then(response => (response ? response.json() : null))
        .then(data => {
            const parentSelect = document.getElementById('id_new_parent');
            if (parentSelect && data && data.results) {
                parentSelect.innerHTML = '<option value="">--- Seleccione Nueva Unidad Padre ---</option>';
                data.results.forEach(item => {
                    if (String(item.id) !== String(unitId)) {
                        const option = document.createElement('option');
                        option.value = item.id;
                        option.textContent = item.text;
                        parentSelect.appendChild(option);
                    }
                });
            }

            if (formElement) {
                formElement.onsubmit = function (event) {
                    event.preventDefault();
                    const newParentId = document.getElementById('id_new_parent')?.value;
                    const formData = new FormData();
                    formData.append('parent', newParentId || '');

                    fetch(`/institution/units/change-parent/${unitId}/`, {
                        method: 'POST',
                        body: formData,
                        headers: {
                            'X-Requested-With': 'XMLHttpRequest',
                            'X-CSRFToken': typeof getCSRF === 'function' ? getCSRF() : ''
                        }
                    })
                        .then(res => res.json())
                        .then(data => {
                            if (data.success) {
                                closeModal('relocate-modal-container');
                                showToast(data.message || 'Unidad reubicada correctamente.', 'success');
                                setTimeout(() => location.reload(), 600);
                            } else {
                                Swal.fire({
                                    icon: 'warning',
                                    title: 'Atención',
                                    text: data.message || 'No se pudo reubicar la unidad.',
                                    confirmButtonText: 'Entendido'
                                });
                            }
                        })
                        .catch(err => {
                            console.error('Error relocating unit:', err);
                            Swal.fire({
                                icon: 'error',
                                title: 'Error',
                                text: 'Error de comunicación con el servidor.',
                                confirmButtonText: 'Entendido'
                            });
                        });
                };
            }
        })
        .catch(err => console.error('Error initializing relocate unit modal:', err));
};

/* =========================================================================
   5. REUBICACIÓN DE PERSONAL
   ========================================================================= */

function loadUnitLevelRelocate(parentId) {
    const apiUrl = '/institution/api/unit-children/';
    const queryParams = parentId ? {parent_id: parentId} : {};

    $.ajax({
        url: apiUrl,
        data: queryParams,
        success: function (data) {
            if (!data.units || data.units.length === 0) return;

            const uniqueId = 'unit-select-' + (parentId || 'root');
            const $wrapper = $('<div class="form-group mb-3"></div>');
            const $label = $('<label class="text-xs font-bold text-gray-600 mb-1 block">Seleccione Unidad:</label>');

            const $select = $('<select>')
                .attr('id', uniqueId)
                .addClass('form-control select2-relocate w-full border p-2 rounded')
                .append('<option value="">-- Seleccione --</option>');

            data.units.forEach(unitItem => {
                $select.append(`<option value="${unitItem.id}" data-has-children="${unitItem.has_children}">${unitItem.name}</option>`);
            });

            $wrapper.append($label).append($select);
            $('#relocate-combos-wrapper').append($wrapper);

            $select.select2({
                dropdownParent: $('#modal-relocate-employee'),
                width: '100%'
            }).on('change', function () {
                const selectedValue = $(this).val();
                const hasChildren = $(this).find(':selected').data('has-children');
                $(this).closest('.form-group').nextAll().remove();
                if (selectedValue && (hasChildren === true || hasChildren === "true" || hasChildren === "True")) {
                    loadUnitLevelRelocate(selectedValue);
                }
            });
        }
    });
}

$(document).on('submit', '#form-relocate-employee', function (event) {
    event.preventDefault();
    let destinationUnitId = null;
    let destinationUnitText = '';

    $('#relocate-combos-wrapper select').each(function () {
        if ($(this).val()) {
            destinationUnitId = $(this).val();
            destinationUnitText = $(this).find('option:selected').text();
        }
    });

    if (!destinationUnitId) {
        Swal.fire({
            icon: 'warning',
            title: 'Atención',
            text: 'Seleccione una unidad de destino.',
            confirmButtonText: 'Entendido'
        });
        return;
    }

    const submitBtn = $(this).find('button[type="submit"]');
    submitBtn.prop('disabled', true).html('Guardando...');

    $.ajax({
        url: '/person/relocate/',
        method: 'POST',
        headers: {'X-CSRFToken': typeof getCSRF === 'function' ? getCSRF() : ''},
        data: {
            person_id: window.selectedRelocatePersonId,
            unit_id: destinationUnitId
        },
        success: function (response) {
            if (response.success) {
                closeModal('modal-relocate-employee');
                showToast(`Empleado reubicado en ${destinationUnitText}`, 'success');
                setTimeout(() => location.reload(), 800);
            } else {
                Swal.fire({
                    icon: 'error',
                    title: 'Error',
                    text: response.message || 'No se pudo reubicar al empleado.',
                    confirmButtonText: 'Entendido'
                });
            }
        },
        error: () => Swal.fire({
            icon: 'error',
            title: 'Error',
            text: 'Error de comunicación con el servidor.',
            confirmButtonText: 'Entendido'
        }),
        complete: () => submitBtn.prop('disabled', false).html('Confirmar Reubicación')
    });
});

/* =========================================================================
   6. UI HELPERS (ACCORDION & EXPORTS)
   ========================================================================= */

// Exportar empleados de una dependencia a Excel
window.exportUnitEmployees = function (unitId, statusCode) {
    window.location.href = `/institution/units/${unitId}/export-employees/?status=${statusCode}`;
};

// Alternar despliegue del acordeón de entregables
window.toggleDeliverablesAccordion = function (headerElement) {
    const contentElement = document.getElementById('table-content-wrapper');
    const indicatorIcon = headerElement.querySelector('.accordion-indicator');
    if (!contentElement) return;

    const isHidden = contentElement.style.display === 'none';
    contentElement.style.display = isHidden ? 'block' : 'none';

    if (indicatorIcon) {
        indicatorIcon.classList.toggle('fa-chevron-up', isHidden);
        indicatorIcon.classList.toggle('fa-chevron-down', !isHidden);
    }
};