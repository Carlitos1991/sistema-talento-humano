/**
 * SIGETH - Labor Regime & Contract Types Module
 * Vanilla JS standard using global functions from main.js and style.css
 */

class LaborRegimeController {
    constructor() {
        this.activeFilterStatus = '';
        this.currentRegime = {id: null, name: ''};
        this.contractTypes = [];
        this.searchDebounceTimer = null;

        this.initDOMElements();
        this.bindEvents();
        this.initTableManager();
    }

    initDOMElements() {
        // Contenedores y Buscador
        this.tableWrapper = document.getElementById('table-content-wrapper');
        this.searchInput = document.getElementById('regime-search-input');

        // Tarjetas Estadísticas
        this.statCards = {
            all: document.getElementById('stat-card-total'),
            active: document.getElementById('stat-card-active'),
            inactive: document.getElementById('stat-card-inactive')
        };
        this.statValues = {
            total: document.getElementById('stat-val-total'),
            active: document.getElementById('stat-val-active'),
            inactive: document.getElementById('stat-val-inactive')
        };

        // Modal Formulario Régimen
        this.regimeModal = document.getElementById('regimeFormModalOverlay');
        this.regimeForm = document.getElementById('regimeForm');
        this.regimeModalTitle = document.getElementById('regime-modal-title');
        this.regimeSubmitText = document.getElementById('regime-submit-text');
        this.regimeCodeInput = document.getElementById('regime_code');
        this.regimeCodeHint = document.getElementById('regime-code-hint');
        this.btnCreateRegime = document.getElementById('btn-create-regime');
        this.btnCloseRegimeTop = document.getElementById('btn-close-regime-modal-top');
        this.btnCancelRegime = document.getElementById('btn-cancel-regime-form');

        // Modal Lista de Tipos de Contrato
        this.contractModal = document.getElementById('contractTypeListModalOverlay');
        this.contractRegimeTitle = document.getElementById('modal-regime-title-name');
        this.contractTypesTbody = document.getElementById('contract-types-tbody');
        this.btnCreateContractType = document.getElementById('btn-create-contract-type-open');
        this.btnCloseContractTop = document.getElementById('btn-close-contract-modal-top');
        this.btnCloseContractBottom = document.getElementById('btn-close-contract-modal-bottom');
    }

    bindEvents() {
        // Búsqueda en tiempo real
        if (this.searchInput) {
            this.searchInput.addEventListener('input', () => {
                clearTimeout(this.searchDebounceTimer);
                this.searchDebounceTimer = setTimeout(() => this.fetchRegimesTable(), 350);
            });
        }

        // Filtro por Estado en Stat Cards
        Object.values(this.statCards).forEach(card => {
            if (!card) return;
            card.addEventListener('click', () => {
                const status = card.dataset.status;
                this.filterByStatus(status);
            });
        });

        // Apertura y Cierre de Modal Régimen
        if (this.btnCreateRegime) this.btnCreateRegime.addEventListener('click', () => this.openCreateRegimeModal());
        if (this.btnCloseRegimeTop) this.btnCloseRegimeTop.addEventListener('click', () => this.closeRegimeModal());
        if (this.btnCancelRegime) this.btnCancelRegime.addEventListener('click', () => this.closeRegimeModal());
        if (this.regimeForm) this.regimeForm.addEventListener('submit', (e) => this.submitRegimeForm(e));

        // Acciones delegadas en la tabla principal de regímenes
        if (this.tableWrapper) {
            this.tableWrapper.addEventListener('click', (e) => {
                const btn = e.target.closest('button');
                if (!btn) return;

                const action = btn.dataset.action;
                const id = btn.dataset.id;
                const name = btn.dataset.name;
                const status = btn.dataset.status;

                if (action === 'edit-regime') this.openEditRegimeModal(id);
                if (action === 'toggle-status') this.toggleRegimeStatus(id, status);
                if (action === 'view-contract-types') this.openContractTypesModal(id, name);
            });
        }

        // Modal Modalidades de Contratación
        if (this.btnCreateContractType) this.btnCreateContractType.addEventListener('click', () => this.promptCreateContractType());
        if (this.btnCloseContractTop) this.btnCloseContractTop.addEventListener('click', () => this.closeContractTypesModal());
        if (this.btnCloseContractBottom) this.btnCloseContractBottom.addEventListener('click', () => this.closeContractTypesModal());

        // Acciones delegadas en la tabla de modalidades (modal)
        if (this.contractTypesTbody) {
            this.contractTypesTbody.addEventListener('click', (e) => {
                const btn = e.target.closest('button');
                if (!btn) return;

                const action = btn.dataset.action;
                const id = btn.dataset.id;

                if (action === 'edit-contract-type') {
                    const item = this.contractTypes.find(c => String(c.id) === String(id));
                    if (item) this.promptEditContractType(item);
                }
                if (action === 'toggle-contract-type') this.toggleContractTypeStatus(id);
                if (action === 'open-template-editor') {
                    window.open(`/contract/templates/create/${id}/`, '_blank');
                }
            });
        }
    }

    initTableManager() {
        const table = this.tableWrapper ? this.tableWrapper.querySelector('.managed-table') : null;
        if (table && typeof TableManager === 'function') {
            new TableManager(table);
        }
    }

    // =========================================================================
    // 1. GESTIÓN DE REGÍMENES LABORALES
    // =========================================================================

    filterByStatus(status) {
        if (this.activeFilterStatus === status) {
            this.activeFilterStatus = '';
        } else {
            this.activeFilterStatus = status;
        }

        // Actualizar opacidad visual de las tarjetas
        Object.values(this.statCards).forEach(card => {
            if (!card) return;
            const cardStatus = card.dataset.status;
            card.classList.toggle('opacity-low', this.activeFilterStatus !== '' && this.activeFilterStatus !== cardStatus);
        });

        this.fetchRegimesTable();
    }

    async fetchRegimesTable() {
        const params = new URLSearchParams();
        const searchVal = (this.searchInput?.value || '').trim();
        if (searchVal) params.set('name', searchVal);
        if (this.activeFilterStatus) params.set('is_active', this.activeFilterStatus);

        try {
            const res = await fetch(`/contract/regimes/partial-table/?${params.toString()}`, {
                headers: {'X-Requested-With': 'XMLHttpRequest'}
            });
            const data = await res.json();

            if (this.tableWrapper) {
                this.tableWrapper.innerHTML = data.table_html;
                this.initTableManager();
            }

            if (data.stats) {
                if (this.statValues.total) this.statValues.total.textContent = data.stats.total;
                if (this.statValues.active) this.statValues.active.textContent = data.stats.active;
                if (this.statValues.inactive) this.statValues.inactive.textContent = data.stats.inactive;
            }
        } catch (error) {
            console.error('Error fetching regimes table:', error);
            showToast('Error al actualizar la tabla de regímenes', 'error');
        }
    }

    openCreateRegimeModal() {
        this.regimeForm.reset();
        document.getElementById('regime_id').value = '';
        this.regimeModalTitle.textContent = 'Nuevo Régimen Laboral';
        this.regimeSubmitText.textContent = 'GUARDAR';

        this.regimeCodeInput.removeAttribute('readonly');
        this.regimeCodeInput.classList.remove('bg-readonly');
        this.regimeCodeHint.classList.add('hidden');

        this.regimeModal.classList.remove('hidden');
        document.body.classList.add('no-scroll');
    }

    async openEditRegimeModal(id) {
        try {
            const res = await fetch(`/contract/regimes/detail/${id}/`);
            const data = await res.json();

            if (data.success && data.regime) {
                const r = data.regime;
                document.getElementById('regime_id').value = r.id;
                this.regimeCodeInput.value = r.code;
                document.getElementById('regime_name').value = r.name;
                document.getElementById('regime_description').value = r.description || '';

                this.regimeModalTitle.textContent = 'Editar Régimen Laboral';
                this.regimeSubmitText.textContent = 'ACTUALIZAR';

                this.regimeCodeInput.setAttribute('readonly', 'true');
                this.regimeCodeInput.classList.add('bg-readonly');
                this.regimeCodeHint.classList.remove('hidden');

                this.regimeModal.classList.remove('hidden');
                document.body.classList.add('no-scroll');
            }
        } catch (error) {
            showToast('Error al consultar datos del régimen', 'error');
        }
    }

    closeRegimeModal() {
        this.regimeModal.classList.add('hidden');
        document.body.classList.remove('no-scroll');
        this.regimeForm.reset();
    }

    async submitRegimeForm(e) {
        e.preventDefault();
        const regimeId = document.getElementById('regime_id').value;
        const url = regimeId ? `/contract/regimes/update/${regimeId}/` : '/contract/regimes/create/';

        const formData = new FormData(this.regimeForm);
        formData.set('code', this.regimeCodeInput.value.toUpperCase().trim());
        formData.set('name', document.getElementById('regime_name').value.toUpperCase().trim());

        const btnSubmit = document.getElementById('btn-submit-regime-form');
        btnSubmit.disabled = true;

        try {
            const res = await fetch(url, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': typeof getCSRF === 'function' ? getCSRF() : '',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: formData
            });
            const data = await res.json();

            if (res.ok && data.success) {
                showToast(data.message || 'Régimen guardado con éxito', 'success');
                this.closeRegimeModal();
                this.fetchRegimesTable();
            } else {
                let errorMsg = data.message || 'Existen errores en el formulario.';
                if (data.errors) {
                    errorMsg = Object.entries(data.errors).map(([f, err]) => `• <b>${f}:</b> ${err}`).join('<br>');
                }
                Swal.fire({
                    title: 'Atención',
                    html: errorMsg,
                    icon: 'warning',
                    confirmButtonText: 'Entendido'
                });
            }
        } catch (error) {
            showToast('Error al guardar el régimen laboral', 'error');
        } finally {
            btnSubmit.disabled = false;
        }
    }

    toggleRegimeStatus(id, currentStatus) {
        const isActive = String(currentStatus) === 'true';
        const url = `/contract/regimes/toggle-status/${id}/`;
        const itemName = 'este régimen laboral';

        toggleStatusAjax(url, itemName, isActive, () => {
            this.fetchRegimesTable();
        });
    }

    // =========================================================================
    // 2. GESTIÓN DE MODALIDADES DE CONTRATACIÓN (MODAL)
    // =========================================================================

    openContractTypesModal(regimeId, regimeName) {
        this.currentRegime = {id: regimeId, name: regimeName};
        if (this.contractRegimeTitle) this.contractRegimeTitle.textContent = regimeName;

        this.contractModal.classList.remove('hidden');
        document.body.classList.add('no-scroll');
        this.fetchContractTypes();
    }

    closeContractTypesModal() {
        this.contractModal.classList.add('hidden');
        document.body.classList.remove('no-scroll');
        this.currentRegime = {id: null, name: ''};
        this.contractTypes = [];
    }

    async fetchContractTypes() {
        if (!this.currentRegime.id) return;
        this.contractTypesTbody.innerHTML = `
            <tr>
                <td colspan="5" class="text-center py-4">
                    <i class="fas fa-spinner fa-spin text-primary fa-2x"></i>
                    <p class="text-muted small mt-2 mb-0">Cargando modalidades...</p>
                </td>
            </tr>`;

        try {
            const res = await fetch(`/contract/regimes/${this.currentRegime.id}/contract-types/`);
            const data = await res.json();

            if (data.success) {
                this.contractTypes = data.contract_types || [];
                this.renderContractTypesTable();
            }
        } catch (error) {
            showToast('Error al cargar modalidades de contratación', 'error');
            this.contractTypesTbody.innerHTML = '';
        }
    }

    renderContractTypesTable() {
        if (!this.contractTypes.length) {
            this.contractTypesTbody.innerHTML = `
                <tr>
                    <td colspan="5">
                        <div class="empty-state-container py-4">
                            <i class="fas fa-folder-open empty-state-icon"></i>
                            <p class="empty-state-text">No existen modalidades registradas para este régimen.</p>
                        </div>
                    </td>
                </tr>`;
            return;
        }

        this.contractTypesTbody.innerHTML = this.contractTypes.map(type => {
            const isContrato = type.category === 'CONTRATO';
            const categoryBadge = isContrato
                ? '<span class="badge badge-blue"><i class="fas fa-file-contract me-1"></i> Contrato</span>'
                : '<span class="badge badge-purple"><i class="fas fa-user-check me-1"></i> Acción de Personal</span>';

            const statusBadge = type.is_active
                ? '<span class="badge badge-green">Activo</span>'
                : '<span class="badge badge-gray">Inactivo</span>';

            const toggleBtn = type.is_active
                ? `<button type="button" class="btn-red-circle" data-action="toggle-contract-type" data-id="${type.id}" title="Desactivar Modalidad"><i class="fas fa-toggle-on"></i></button>`
                : `<button type="button" class="btn-green-circle" data-action="toggle-contract-type" data-id="${type.id}" title="Activar Modalidad"><i class="fas fa-toggle-off"></i></button>`;

            return `
                <tr>
                    <td><code class="text-blue bold">${type.code}</code></td>
                    <td class="bold">${type.name}</td>
                    <td>${categoryBadge}</td>
                    <td class="text-center">${statusBadge}</td>
                    <td class="actions text-center">
                        <div class="actions-wrapper">
                            <button type="button" class="btn-dark-blue-circle" data-action="open-template-editor" data-id="${type.id}" title="Editor de Plantilla">
                                <i class="fas fa-file-signature"></i>
                            </button>
                            <button type="button" class="btn-blue-circle" data-action="edit-contract-type" data-id="${type.id}" title="Editar">
                                <i class="fas fa-pen-to-square"></i>
                            </button>
                            ${toggleBtn}
                        </div>
                    </td>
                </tr>`;
        }).join('');
    }

    async promptCreateContractType() {
        const {value: formValues} = await Swal.fire({
            title: 'Nueva Modalidad Laboral',
            html: `
                <div style="text-align: left; padding: 0.5rem; font-family: 'Inter', sans-serif;">
                    <div class="form-group mb-3">
                        <label class="form-label font-weight-700">Código Único *</label>
                        <input id="swal-contract-code" class="form-control uppercase-input" placeholder="EJ: CT_OCASIONAL">
                    </div>
                    <div class="form-group mb-3">
                        <label class="form-label font-weight-700">Nombre de la Modalidad *</label>
                        <input id="swal-contract-name" class="form-control uppercase-input" placeholder="EJ: CONTRATO OCASIONAL">
                    </div>
                    <div class="form-group mb-0">
                        <label class="form-label font-weight-700">Categoría de Documento</label>
                        <select id="swal-contract-category" class="input-field">
                            <option value="CONTRATO">Contrato</option>
                            <option value="ACCION_PERSONAL">Acción de Personal</option>
                        </select>
                    </div>
                </div>`,
            showCancelButton: true,
            confirmButtonText: 'Guardar Modalidad',
            cancelButtonText: 'Cancelar',
            preConfirm: () => {
                const code = document.getElementById('swal-contract-code').value.trim().toUpperCase();
                const name = document.getElementById('swal-contract-name').value.trim().toUpperCase();
                if (!code || !name) {
                    Swal.showValidationMessage('El código y el nombre son obligatorios.');
                    return false;
                }
                return {
                    code: code,
                    name: name,
                    contract_type_category: document.getElementById('swal-contract-category').value,
                    labor_regime: this.currentRegime.id
                };
            }
        });

        if (formValues) {
            const formData = new FormData();
            Object.keys(formValues).forEach(k => formData.append(k, formValues[k]));

            try {
                const res = await fetch('/contract/contract-types/create/', {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': typeof getCSRF === 'function' ? getCSRF() : '',
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    body: formData
                });
                const data = await res.json();

                if (res.ok && data.success) {
                    showToast(data.message || 'Modalidad registrada', 'success');
                    this.fetchContractTypes();
                    this.fetchRegimesTable();
                } else {
                    Swal.fire('Atención', data.errors?.code?.[0] || data.message || 'No se pudo crear la modalidad', 'warning');
                }
            } catch (error) {
                showToast('Error al registrar la modalidad', 'error');
            }
        }
    }

    async promptEditContractType(type) {
        const {value: formValues} = await Swal.fire({
            title: 'Editar Modalidad Laboral',
            html: `
                <div style="text-align: left; padding: 0.5rem; font-family: 'Inter', sans-serif;">
                    <div class="form-group mb-3">
                        <label class="form-label font-weight-700">Código Único (Solo Lectura)</label>
                        <input id="swal-edit-code" class="form-control bg-readonly" readonly value="${type.code}">
                    </div>
                    <div class="form-group mb-3">
                        <label class="form-label font-weight-700">Nombre de la Modalidad *</label>
                        <input id="swal-edit-name" class="form-control uppercase-input" value="${type.name}">
                    </div>
                    <div class="form-group mb-0">
                        <label class="form-label font-weight-700">Categoría de Documento</label>
                        <select id="swal-edit-category" class="input-field">
                            <option value="CONTRATO" ${type.category === 'CONTRATO' ? 'selected' : ''}>Contrato</option>
                            <option value="ACCION_PERSONAL" ${type.category === 'ACCION_PERSONAL' ? 'selected' : ''}>Acción de Personal</option>
                        </select>
                    </div>
                </div>`,
            showCancelButton: true,
            confirmButtonText: 'Guardar Cambios',
            cancelButtonText: 'Cancelar',
            preConfirm: () => {
                const name = document.getElementById('swal-edit-name').value.trim().toUpperCase();
                if (!name) {
                    Swal.showValidationMessage('El nombre es obligatorio.');
                    return false;
                }
                return {
                    code: type.code,
                    name: name,
                    contract_type_category: document.getElementById('swal-edit-category').value,
                    labor_regime: this.currentRegime.id
                };
            }
        });

        if (formValues) {
            const formData = new FormData();
            Object.keys(formValues).forEach(k => formData.append(k, formValues[k]));

            try {
                const res = await fetch(`/contract/contract-types/update/${type.id}/`, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': typeof getCSRF === 'function' ? getCSRF() : '',
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    body: formData
                });
                const data = await res.json();

                if (res.ok && data.success) {
                    showToast(data.message || 'Modalidad actualizada', 'success');
                    this.fetchContractTypes();
                } else {
                    Swal.fire('Atención', data.message || 'No se pudo actualizar la modalidad', 'warning');
                }
            } catch (error) {
                showToast('Error al actualizar la modalidad', 'error');
            }
        }
    }

    async toggleContractTypeStatus(typeId) {
        try {
            const res = await fetch(`/contract/contract-types/toggle-status/${typeId}/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': typeof getCSRF === 'function' ? getCSRF() : '',
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });
            const data = await res.json();
            if (data.success) {
                showToast(data.message || 'Estado actualizado', 'success');
                this.fetchContractTypes();
            }
        } catch (error) {
            showToast('Error al cambiar el estado de la modalidad', 'error');
        }
    }
}

// Inicialización limpia
document.addEventListener('DOMContentLoaded', () => {
    window.laborRegimeController = new LaborRegimeController();
});