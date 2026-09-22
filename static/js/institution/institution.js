/**
 * SIGETH - Módulo de Gestión Institucional y Estructura Organizacional
 * Archivo Unificado: Jerarquía, Entregables, Reubicación de Unidades y Empleados
 */

document.addEventListener('DOMContentLoaded', () => {

    // =========================================================================
    // 1. STAT CARDS & FILTRADO DE NIVELES (VISTA GENERAL)
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

    let currentParentId = null;
    let currentLevelOrder = null;
    let unitSearchRequestId = 0;
    let unitSearchDebounceTimer = null;

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
            console.error('Error cargando tabla parcial de unidades:', error);
        }
    }

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

    Object.entries(levelCards).forEach(([levelId, cardElement]) => {
        if (cardElement) {
            cardElement.addEventListener('click', () => window.filterByLevel(levelId, cardElement));
        }
    });

    const btnAddUnit = document.getElementById('btn-add-unit');
    if (btnAddUnit) {
        btnAddUnit.onclick = () => openAjaxModal('/institution/units/create/', window.initUnitModal);
    }
});

// =========================================================================
// 2. MODAL FORM: CÓDIGO CORRELATIVO Y AUTO-COMPLETADO
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
            .catch(err => console.error("Error generando código correlativo:", err));
    }
};

// Callback para creación de dependencia desde el detalle de la unidad
window.bindUnitCreateModal = function () {
    window.initUnitModal();
    const form = document.getElementById('unitForm');
    if (form) {
        form.onsubmit = function (e) {
            submitAjaxForm(e, (data) => {
                closeModal();
                showToast(data.message || 'Dependencia creada correctamente.', 'success');
                setTimeout(() => location.reload(), 600);
            });
        };
    }
};

// =========================================================================
// 3. GESTIÓN AISLADA DE ENTREGABLES (ACORDEÓN Y AJAX)
// =========================================================================
window.refreshDeliverablesTable = function (unitId) {
    const wrapper = document.getElementById('deliverables-table-wrapper');
    if (!wrapper) return;

    fetch(`/institution/units/${unitId}/deliverables/partial/`, {
        headers: {'X-Requested-With': 'XMLHttpRequest'}
    })
        .then(res => res.text())
        .then(html => {
            wrapper.innerHTML = html;
            wrapper.style.display = 'block';
        })
        .catch(err => console.error('Error actualizando entregables:', err));
};

window.bindDeliverableForm = function (unitId) {
    const root = document.getElementById('modal-root');
    const form = root ? root.querySelector('form') : null;
    if (form) {
        form.onsubmit = function (e) {
            submitAjaxForm(e, (data) => {
                closeModal();
                showToast(data.message || 'Entregable guardado correctamente.', 'success');
                window.refreshDeliverablesTable(unitId);
            });
        };
    }
};

window.toggleDeliverablesAccordion = function (headerElement) {
    const contentElement = document.getElementById('deliverables-table-wrapper');
    const indicatorIcon = headerElement.querySelector('.accordion-indicator');
    if (!contentElement) return;

    const isHidden = contentElement.style.display === 'none';
    contentElement.style.display = isHidden ? 'block' : 'none';

    if (indicatorIcon) {
        indicatorIcon.classList.toggle('fa-chevron-up', isHidden);
        indicatorIcon.classList.toggle('fa-chevron-down', !isHidden);
    }
};

// =========================================================================
// 4. MODAL ESTÁTICO: REUBICAR UNIDAD ADMINISTRATIVA
// =========================================================================
window.initRelocateUnitModal = function (unitId) {
    const modalEl = document.getElementById('relocate-modal-container');
    const formElement = document.getElementById('relocateForm');
    const parentSelect = document.getElementById('id_new_parent');

    if (formElement) formElement.reset();

    const errorContainer = document.getElementById('errorContainer');
    if (errorContainer) errorContainer.style.display = 'none';

    if (parentSelect) {
        parentSelect.innerHTML = '<option value="">--- Cargando unidades disponibles ---</option>';
        if (typeof $ !== 'undefined' && $(parentSelect).hasClass('select2-hidden-accessible')) {
            $(parentSelect).select2('destroy');
        }
    }

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

                if (typeof $ !== 'undefined' && $.fn.select2) {
                    $(parentSelect).select2({
                        width: '100%',
                        dropdownParent: $(modalEl)
                    });
                }
            }

            if (formElement) {
                formElement.onsubmit = function (event) {
                    event.preventDefault();
                    const newParentId = document.getElementById('id_new_parent')?.value;

                    if (!newParentId) {
                        Swal.fire({
                            icon: 'warning',
                            title: 'Atención',
                            text: 'Por favor seleccione la nueva unidad padre.'
                        });
                        return;
                    }

                    const formData = new FormData();
                    formData.append('parent', newParentId);

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
                                    text: data.message || 'No se pudo reubicar la unidad.'
                                });
                            }
                        })
                        .catch(err => {
                            console.error('Error reubicando unidad:', err);
                            Swal.fire({
                                icon: 'error',
                                title: 'Error',
                                text: 'Error de comunicación con el servidor.'
                            });
                        });
                };
            }
        })
        .catch(err => console.error('Error inicializando modal de reubicación:', err));
};

// =========================================================================
// 5. EXPORTACIONES & UTILIDADES
// =========================================================================
window.exportUnitEmployees = function (unitId, statusCode) {
    window.location.href = `/institution/units/${unitId}/export-employees/?status=${statusCode}`;
};