/**
 * SIGETH - Labor Regime & Contract Types Module
 */
(function () {
    'use strict';

    let currentStatusFilter = '';
    let currentSearchQuery = '';
    let activeRegimeId = null;
    let activeRegimeName = '';

    document.addEventListener('DOMContentLoaded', () => {
        initStatCardFilters();
        initSearchInput();
        initRegimeModalEvents();
        initTableDelegation();
        initContractTypeModalEvents();
    });

    function getCsrfToken() {
        if (typeof window.getCSRF === 'function') return window.getCSRF();
        const hidden = document.querySelector('[name=csrfmiddlewaretoken]');
        if (hidden && hidden.value) return hidden.value;
        const match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : '';
    }

    function notify(message, icon = 'success') {
        if (typeof window.showToast === 'function') {
            window.showToast(message, icon === 'error' ? 'error' : icon);
            return;
        }
        if (typeof Swal !== 'undefined') {
            Swal.fire({
                toast: true,
                position: 'top-end',
                icon: icon,
                title: message,
                showConfirmButton: false,
                timer: 2500,
                timerProgressBar: true
            });
        }
    }

    function escapeHtml(value) {
        return String(value ?? '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    // =========================================================================
    // 1. FILTROS Y ACTUALIZACIÓN PARCIAL DE TABLA
    // =========================================================================

    function initStatCardFilters() {
        const cards = document.querySelectorAll('.stats-row .stat-card');
        if (!cards.length) return;

        cards[0].classList.add('active-filter');

        cards.forEach((card) => {
            card.addEventListener('click', () => {
                cards.forEach((c) => c.classList.remove('active-filter'));
                card.classList.add('active-filter');
                currentStatusFilter = card.dataset.status || '';
                refreshRegimeTable();
            });
        });
    }

    function initSearchInput() {
        const input = document.getElementById('regime-search-input');
        if (!input) return;

        let debounceTimer = null;
        input.addEventListener('input', () => {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(() => {
                currentSearchQuery = input.value.trim();
                refreshRegimeTable();
            }, 300);
        });

        input.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                clearTimeout(debounceTimer);
                currentSearchQuery = input.value.trim();
                refreshRegimeTable();
            }
        });
    }

    async function refreshRegimeTable() {
        const params = new URLSearchParams();
        if (currentSearchQuery) params.set('name', currentSearchQuery);
        if (currentStatusFilter) params.set('is_active', currentStatusFilter);

        try {
            const response = await fetch(`/contract/regimes/partial-table/?${params.toString()}`, {
                headers: {'X-Requested-With': 'XMLHttpRequest'}
            });
            const data = await response.json();

            const wrapper = document.getElementById('table-content-wrapper');
            if (wrapper && data.table_html) {
                wrapper.innerHTML = data.table_html;
            }

            if (data.stats) {
                const totalEl = document.getElementById('stat-val-total');
                const activeEl = document.getElementById('stat-val-active');
                const inactiveEl = document.getElementById('stat-val-inactive');
                if (totalEl) totalEl.textContent = data.stats.total ?? 0;
                if (activeEl) activeEl.textContent = data.stats.active ?? 0;
                if (inactiveEl) inactiveEl.textContent = data.stats.inactive ?? 0;
            }
        } catch (error) {
            notify('Error al actualizar el listado de regímenes.', 'error');
        }
    }

    // =========================================================================
    // 2. MODAL DE RÉGIMEN LABORAL (CREAR / EDITAR / ESTADO)
    // =========================================================================

    function initRegimeModalEvents() {
        const btnCreate = document.getElementById('btn-create-regime');
        const btnCloseTop = document.getElementById('btn-close-regime-modal-top');
        const btnCancel = document.getElementById('btn-cancel-regime-form');
        const form = document.getElementById('regimeForm');

        if (btnCreate) btnCreate.addEventListener('click', () => openRegimeModal());
        if (btnCloseTop) btnCloseTop.addEventListener('click', closeRegimeModal);
        if (btnCancel) btnCancel.addEventListener('click', closeRegimeModal);
        if (form) form.addEventListener('submit', submitRegimeForm);
    }

    function openRegimeModal(regime = null) {
        const overlay = document.getElementById('regimeFormModalOverlay');
        const form = document.getElementById('regimeForm');
        const idInput = document.getElementById('regime_id');
        const codeInput = document.getElementById('regime_code');
        const nameInput = document.getElementById('regime_name');
        const descInput = document.getElementById('regime_description');
        const titleEl = document.getElementById('regime-modal-title');
        const submitText = document.getElementById('regime-submit-text');
        const codeHint = document.getElementById('regime-code-hint');

        if (form) form.reset();

        if (regime) {
            if (idInput) idInput.value = regime.id;
            if (codeInput) {
                codeInput.value = regime.code || '';
                codeInput.readOnly = true;
            }
            if (nameInput) nameInput.value = regime.name || '';
            if (descInput) descInput.value = regime.description || '';
            if (titleEl) titleEl.textContent = 'Editar Régimen Laboral';
            if (submitText) submitText.textContent = 'ACTUALIZAR';
            if (codeHint) codeHint.classList.remove('hidden');
        } else {
            if (idInput) idInput.value = '';
            if (codeInput) {
                codeInput.value = '';
                codeInput.readOnly = false;
            }
            if (titleEl) titleEl.textContent = 'Nuevo Régimen Laboral';
            if (submitText) submitText.textContent = 'GUARDAR';
            if (codeHint) codeHint.classList.add('hidden');
        }

        if (overlay) overlay.classList.remove('hidden');
        document.body.classList.add('no-scroll');
    }

    function closeRegimeModal() {
        const overlay = document.getElementById('regimeFormModalOverlay');
        if (overlay) overlay.classList.add('hidden');
        document.body.classList.remove('no-scroll');
    }

    async function loadRegimeForEdit(regimeId) {
        try {
            const response = await fetch(`/contract/regimes/detail/${regimeId}/`, {
                headers: {'X-Requested-With': 'XMLHttpRequest'}
            });
            const data = await response.json();
            if (data.success && data.regime) {
                openRegimeModal(data.regime);
            } else {
                notify('No se pudo obtener el detalle del régimen.', 'error');
            }
        } catch (error) {
            notify('Error de conexión con el servidor.', 'error');
        }
    }

    async function submitRegimeForm(e) {
        e.preventDefault();
        const form = e.target;
        const regimeId = (document.getElementById('regime_id')?.value || '').trim();
        const url = regimeId
            ? `/contract/regimes/update/${regimeId}/`
            : '/contract/regimes/create/';

        const submitBtn = document.getElementById('btn-submit-regime-form');
        if (submitBtn) submitBtn.disabled = true;

        try {
            const response = await fetch(url, {
                method: 'POST',
                body: new FormData(form),
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': getCsrfToken()
                }
            });
            const data = await response.json();

            if (response.ok && data.success) {
                notify(data.message || 'Régimen guardado correctamente.', 'success');
                closeRegimeModal();
                await refreshRegimeTable();
            } else if (data.errors) {
                const msg = Object.entries(data.errors)
                    .map(([field, errs]) => `• <b>${escapeHtml(field)}:</b> ${escapeHtml(errs.join(', '))}`)
                    .join('<br>');
                Swal.fire({title: 'Error de Validación', html: msg, icon: 'warning'});
            } else {
                Swal.fire('Error', data.message || 'No se pudo guardar el régimen.', 'error');
            }
        } catch (error) {
            notify('Error técnico al guardar el régimen.', 'error');
        } finally {
            if (submitBtn) submitBtn.disabled = false;
        }
    }

    function toggleRegimeStatus(regimeId, isCurrentlyActive) {
        const actionLabel = isCurrentlyActive ? 'dar de baja' : 'activar';

        Swal.fire({
            title: `¿Desea ${actionLabel} este régimen?`,
            icon: 'question',
            showCancelButton: true,
            confirmButtonText: 'Sí, continuar',
            cancelButtonText: 'Cancelar'
        }).then(async (result) => {
            if (!result.isConfirmed) return;

            try {
                const response = await fetch(`/contract/regimes/toggle-status/${regimeId}/`, {
                    method: 'POST',
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest',
                        'X-CSRFToken': getCsrfToken()
                    }
                });
                const data = await response.json();
                if (data.success) {
                    notify(data.message || 'Estado actualizado.', 'success');
                    await refreshRegimeTable();
                } else {
                    Swal.fire('Atención', data.message || 'No se pudo cambiar el estado.', 'warning');
                }
            } catch (error) {
                notify('Error de red al cambiar estado.', 'error');
            }
        });
    }

    // =========================================================================
    // 3. DELEGACIÓN DE EVENTOS EN TABLA PRINCIPAL
    // =========================================================================

    function initTableDelegation() {
        document.addEventListener('click', (e) => {
            const btn = e.target.closest('#laborRegimeTable button[data-action]');
            if (!btn) return;

            const action = btn.dataset.action;
            const id = btn.dataset.id;

            if (action === 'edit-regime') {
                loadRegimeForEdit(id);
            } else if (action === 'toggle-status') {
                toggleRegimeStatus(id, btn.dataset.status === 'true');
            } else if (action === 'view-contract-types') {
                openContractTypesModal(id, btn.dataset.name || '');
            }
        });
    }

    // =========================================================================
    // 4. MODAL DE MODALIDADES CONTRACTUALES (CONTRACT TYPES)
    // =========================================================================

    function initContractTypeModalEvents() {
        const btnCloseTop = document.getElementById('btn-close-contract-modal-top');
        const btnCloseBottom = document.getElementById('btn-close-contract-modal-bottom');
        const btnAdd = document.getElementById('btn-create-contract-type-open');
        const wrapper = document.getElementById('contract-types-table-wrapper');

        if (btnCloseTop) btnCloseTop.addEventListener('click', closeContractTypesModal);
        if (btnCloseBottom) btnCloseBottom.addEventListener('click', closeContractTypesModal);
        if (btnAdd) btnAdd.addEventListener('click', () => openContractTypeFormSwal());

        if (wrapper) {
            wrapper.addEventListener('click', (e) => {
                const btn = e.target.closest('button[data-ct-action]');
                if (!btn) return;

                const action = btn.dataset.ctAction;
                const ctId = btn.dataset.id;

                if (action === 'edit') {
                    openContractTypeFormSwal({
                        id: ctId,
                        code: btn.dataset.code || '',
                        name: btn.dataset.name || '',
                        category: btn.dataset.category || 'CONTRATO'
                    });
                } else if (action === 'toggle') {
                    toggleContractTypeStatus(ctId);
                }
            });
        }
    }

    async function loadContractTypesList() {
        if (!activeRegimeId) return;
        const wrapper = document.getElementById('contract-types-table-wrapper');
        if (!wrapper) return;

        try {
            const response = await fetch(`/contract/regimes/${activeRegimeId}/contract-types/`, {
                headers: {'X-Requested-With': 'XMLHttpRequest'}
            });
            if (!response.ok) {
                notify(`Error ${response.status} al consultar las modalidades.`, 'error');
                return;
            }
            const data = await response.json();
            if (data.success && typeof data.table_html === 'string') {
                wrapper.innerHTML = data.table_html;
            }
        } catch (error) {
            notify('Error al cargar las modalidades contractuales.', 'error');
        }
    }

    async function openContractTypesModal(regimeId, regimeName) {
        activeRegimeId = regimeId;
        activeRegimeName = regimeName;

        const titleEl = document.getElementById('modal-regime-title-name');
        if (titleEl) titleEl.textContent = regimeName || '-';

        const overlay = document.getElementById('contractTypeListModalOverlay');
        if (overlay) overlay.classList.remove('hidden');
        document.body.classList.add('no-scroll');

        await loadContractTypesList();
    }

    function closeContractTypesModal() {
        const overlay = document.getElementById('contractTypeListModalOverlay');
        if (overlay) overlay.classList.add('hidden');
        document.body.classList.remove('no-scroll');
        activeRegimeId = null;
        activeRegimeName = '';
    }

    async function openContractTypeFormSwal(contractType = null) {
        if (!activeRegimeId) return;
        const isEdit = Boolean(contractType && contractType.id);

        const {value: formValues} = await Swal.fire({
            title: isEdit ? 'Editar Modalidad Contractual' : 'Nueva Modalidad Contractual',
            html: `
                <div class="contract-type-swal-form">
                    <div class="form-group">
                        <label class="form-label">Código *</label>
                        <input id="swal-ct-code" type="text" class="form-control uppercase-input"
                               value="${escapeHtml(contractType?.code || '')}"
                               ${isEdit ? 'readonly' : ''}
                               placeholder="EJ: CONTRATO_OCASIONAL">
                    </div>
                    <div class="form-group">
                        <label class="form-label">Nombre de la Modalidad *</label>
                        <input id="swal-ct-name" type="text" class="form-control"
                               value="${escapeHtml(contractType?.name || '')}"
                               placeholder="Ej: Contrato de Servicios Ocasionales">
                    </div>
                    <div class="form-group">
                        <label class="form-label">Categoría *</label>
                        <select id="swal-ct-category" class="input-field">
                            <option value="CONTRATO" ${(contractType?.category || 'CONTRATO') === 'CONTRATO' ? 'selected' : ''}>Contrato</option>
                            <option value="ACCION_PERSONAL" ${contractType?.category === 'ACCION_PERSONAL' ? 'selected' : ''}>Acción de Personal / Nombramiento</option>
                        </select>
                    </div>
                </div>
            `,
            showCancelButton: true,
            confirmButtonText: isEdit ? 'Actualizar' : 'Guardar',
            cancelButtonText: 'Cancelar',
            preConfirm: () => {
                const code = document.getElementById('swal-ct-code').value.trim().toUpperCase();
                const name = document.getElementById('swal-ct-name').value.trim();
                const category = document.getElementById('swal-ct-category').value;

                if (!code) {
                    Swal.showValidationMessage('El código es obligatorio.');
                    return false;
                }
                if (!name) {
                    Swal.showValidationMessage('El nombre de la modalidad es obligatorio.');
                    return false;
                }
                return {code, name, contract_type_category: category};
            }
        });

        if (!formValues) return;

        const formData = new FormData();
        formData.append('labor_regime', activeRegimeId);
        formData.append('code', formValues.code);
        formData.append('name', formValues.name);
        formData.append('contract_type_category', formValues.contract_type_category);

        const url = isEdit
            ? `/contract/contract-types/update/${contractType.id}/`
            : '/contract/contract-types/create/';

        try {
            const response = await fetch(url, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': getCsrfToken()
                }
            });
            const data = await response.json();

            if (response.ok && data.success) {
                notify(data.message || 'Modalidad guardada correctamente.', 'success');
                await loadContractTypesList();
                await refreshRegimeTable();
            } else if (data.errors) {
                const msg = Object.entries(data.errors)
                    .map(([field, errs]) => `• <b>${escapeHtml(field)}:</b> ${escapeHtml(errs.join(', '))}`)
                    .join('<br>');
                Swal.fire({title: 'Error de Validación', html: msg, icon: 'warning'});
            } else {
                Swal.fire('Error', data.message || 'No se pudo guardar la modalidad.', 'error');
            }
        } catch (error) {
            notify('Error técnico al guardar la modalidad.', 'error');
        }
    }

    async function toggleContractTypeStatus(contractTypeId) {
        try {
            const response = await fetch(`/contract/contract-types/toggle-status/${contractTypeId}/`, {
                method: 'POST',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': getCsrfToken()
                }
            });
            const data = await response.json();
            if (data.success) {
                notify(data.message || 'Estado actualizado.', 'success');
                await loadContractTypesList();
                await refreshRegimeTable();
            } else {
                Swal.fire('Atención', data.message || 'No se pudo actualizar el estado.', 'warning');
            }
        } catch (error) {
            notify('Error de red al actualizar la modalidad.', 'error');
        }
    }
})();