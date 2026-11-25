/**
 * SIGETH - Management Period Module
 * Uses global TableManager from main.js for sorting and pagination
 */

(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', () => {
        initSelect2Filters();
        initFilterEvents();
        initSearchDebounce();
        initIdentificationExcelUpload();
        initTableActions();
        initWizardEvents();
        initDetailEvents();
        initPeriodPagination();
        initHistoricalModalAjaxForm();
    });

    function getSchedulesData() {
        const node = document.getElementById('periodSchedulesData');
        if (!node) return [];
        try {
            const parsed = JSON.parse(node.textContent || '[]');
            return Array.isArray(parsed) ? parsed : [];
        } catch (error) {
            return [];
        }
    }

    // =========================================================================
    // 1. SELECT2 & FILTER MANAGEMENT
    // =========================================================================

    function initSelect2Filters() {
        if (!window.jQuery || !window.jQuery.fn.select2) return;
        $('#filtersForm select.select2').select2({
            width: '100%',
            allowClear: true
        });
    }

    function initFilterEvents() {
        const form = document.getElementById('filtersForm');
        const btnClear = document.getElementById('btn-clear-period-filters');
        const btnClearExcel = document.getElementById('btn-clear-identifications');

        if (form) {
            form.addEventListener('submit', (e) => {
                e.preventDefault();
                applyPeriodFilters(1);
            });
        }

        if (btnClear) {
            btnClear.addEventListener('click', () => clearPeriodFilters());
        }

        if (btnClearExcel) {
            btnClearExcel.addEventListener('click', () => {
                clearLoadedIdentifications();
                applyPeriodFilters(1);
            });
        }
    }

    function collectFilters() {
        const form = document.getElementById('filtersForm');
        const params = {};
        if (form) {
            const formData = new FormData(form);
            for (const [key, val] of formData.entries()) {
                if (val && String(val).trim() !== '') {
                    params[key] = String(val).trim();
                }
            }
        }
        return params;
    }

    function applyPeriodFilters(page = 1) {
        const params = collectFilters();
        params.page = page;

        if (window._currentTableSort) {
            const table = document.querySelector('.managed-table');
            if (table) {
                const ths = table.querySelectorAll('thead th');
                const th = ths[window._currentTableSort.col];
                if (th && th.dataset.field) {
                    params.sort_field = th.dataset.field;
                    params.sort_dir = window._currentTableSort.asc ? 'asc' : 'desc';
                }
            }
        }

        const searchParams = new URLSearchParams(params);
        window.history.pushState(null, '', '?' + searchParams.toString());

        if (typeof window.refreshCurrentTable === 'function') {
            window.refreshCurrentTable(params);
        }
    }

    function initPeriodPagination() {
        document.addEventListener('click', (event) => {
            const button = event.target.closest('#js-pagination .page-btn');
            if (!button || button.disabled) return;

            const table = document.querySelector('#managementPeriodTable');
            if (!table || table.dataset.externalPagination !== 'true') return;

            const page = Number.parseInt(button.dataset.page, 10);
            if (!Number.isInteger(page) || page < 1) return;

            event.preventDefault();
            event.stopPropagation();
            applyPeriodFilters(page);
        });

        document.addEventListener('change', (event) => {
            const input = event.target.closest('#period-page-input');
            if (!input) return;

            const page = Number.parseInt(input.value, 10);
            if (!Number.isInteger(page) || page < 1) return;

            event.preventDefault();
            applyPeriodFilters(page);
        });

        document.addEventListener('keydown', (event) => {
            const input = event.target.closest('#period-page-input');
            if (!input || event.key !== 'Enter') return;

            event.preventDefault();
            const page = Number.parseInt(input.value, 10);
            if (!Number.isInteger(page) || page < 1) return;

            applyPeriodFilters(page);
        });
    }

    function clearPeriodFilters() {
        const form = document.getElementById('filtersForm');
        if (form) {
            form.reset();
            if (window.$ && $.fn.select2) {
                $(form).find('select.select2').val('').trigger('change');
            }
        }
        clearLoadedIdentifications();
        window.history.pushState(null, '', window.location.pathname);
        applyPeriodFilters(1);
    }

    function initSearchDebounce() {
        const searchInput = document.getElementById('table-search-input');
        if (!searchInput) return;

        let debounceTimer = null;
        searchInput.addEventListener('input', () => {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(() => applyPeriodFilters(1), 350);
        });

        searchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                clearTimeout(debounceTimer);
                applyPeriodFilters(1);
            }
        });
    }

    // =========================================================================
    // 2. EXCEL IDENTIFICATION UPLOADER
    // =========================================================================

    function initIdentificationExcelUpload() {
        const fileInput = document.getElementById('identification_excel_input');
        if (!fileInput) return;

        fileInput.addEventListener('change', function (e) {
            const file = e.target.files[0];
            if (!file) return;

            const maxSizeBytes = 1 * 1024 * 1024;
            if (file.size > maxSizeBytes) {
                Swal.fire({
                    icon: 'warning',
                    title: 'Archivo muy pesado',
                    text: 'El archivo Excel no debe superar 1 MB.'
                });
                fileInput.value = '';
                return;
            }

            const formData = new FormData();
            formData.append('identification_file', file);

            const iconBox = document.getElementById('permit-excel-icon-box');
            const originalIcon = iconBox ? iconBox.innerHTML : '';
            if (iconBox) {
                iconBox.innerHTML = '<i class="fas fa-spinner fa-spin permit-excel-main-icon"></i>';
            }

            fetch('/contract/periods/parse-identifications/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': typeof getCSRF === 'function' ? getCSRF() : '',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: formData
            })
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        const hiddenInput = document.getElementById('filter_document_numbers');
                        if (hiddenInput) hiddenInput.value = data.document_numbers.join(',');

                        const badgeBox = document.getElementById('identification-badge-container');
                        const countText = document.getElementById('identification-count-text');
                        const dropzone = document.getElementById('permit-excel-dropzone-label');

                        if (badgeBox && countText) {
                            countText.innerText = `${data.count} cédula(s)`;
                            badgeBox.classList.remove('hidden');
                        }
                        if (dropzone) dropzone.classList.add('file-selected');

                        showToast(data.message, 'success');
                        applyPeriodFilters(1);
                    } else {
                        Swal.fire({
                            icon: 'warning',
                            title: 'Atención',
                            text: data.message || 'No se pudo procesar el archivo.'
                        });
                    }
                })
                .catch(err => {
                    console.error('Error uploading excel:', err);
                    showToast('Error al procesar el archivo Excel', 'error');
                })
                .finally(() => {
                    if (iconBox) iconBox.innerHTML = originalIcon;
                    fileInput.value = '';
                });
        });
    }

    function clearLoadedIdentifications() {
        const hiddenInput = document.getElementById('filter_document_numbers');
        if (hiddenInput) hiddenInput.value = '';

        const badgeBox = document.getElementById('identification-badge-container');
        if (badgeBox) badgeBox.classList.add('hidden');

        const dropzone = document.getElementById('permit-excel-dropzone-label');
        if (dropzone) dropzone.classList.remove('file-selected');

        const fileInput = document.getElementById('identification_excel_input');
        if (fileInput) fileInput.value = '';
    }

    // =========================================================================
    // 3. HISTORICAL PERIOD MODAL FORM (AJAX)
    // =========================================================================

    function initHistoricalModalSelect2(modalEl) {
        if (!modalEl || !window.jQuery || !window.jQuery.fn.select2) return;
        const $modal = $(modalEl);
        const form = modalEl.querySelector('#historicalPeriodForm');
        const searchUrl = form?.dataset.employeeSearchUrl || '/contract/periods/historical/search-employees/';

        const $empSelect = $modal.find('.select2-employee-ajax');
        if ($empSelect.length && !$empSelect.data('select2')) {
            $empSelect.select2({
                width: '100%',
                dropdownParent: $modal,
                minimumInputLength: 3,
                placeholder: 'Escriba 3 o más letras o cédula...',
                allowClear: true,
                language: {
                    inputTooShort: () => 'Escriba 3 o más caracteres para buscar...',
                    searching: () => 'Buscando servidores...',
                    noResults: () => 'No se encontraron servidores'
                },
                ajax: {
                    url: searchUrl,
                    dataType: 'json',
                    delay: 250,
                    data: (params) => ({q: params.term || ''}),
                    processResults: (data) => ({results: data.results || []}),
                    cache: true
                }
            });
        }

        $modal.find('select.select2-field').each(function () {
            const $sel = $(this);
            if (!$sel.data('select2')) {
                $sel.select2({
                    width: '100%',
                    dropdownParent: $modal,
                    allowClear: true
                });
            }
        });
    }

    function initHistoricalModalAjaxForm() {
        const existingModal = document.getElementById('historicalPeriodModal');
        if (existingModal) initHistoricalModalSelect2(existingModal);

        const observer = new MutationObserver((mutations) => {
            for (const mutation of mutations) {
                for (const node of mutation.addedNodes) {
                    if (node.nodeType !== 1) continue;
                    const modal = node.id === 'historicalPeriodModal'
                        ? node
                        : node.querySelector?.('#historicalPeriodModal');
                    if (modal) initHistoricalModalSelect2(modal);
                }
            }
        });
        observer.observe(document.body, {childList: true, subtree: true});

        document.addEventListener('submit', async (e) => {
            const form = e.target.closest('#historicalPeriodForm');
            if (!form) return;
            e.preventDefault();

            const submitBtn = form.querySelector('button[type="submit"]');
            if (submitBtn) submitBtn.disabled = true;

            try {
                const response = await fetch(form.action, {
                    method: 'POST',
                    body: new FormData(form),
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest',
                        'X-CSRFToken': typeof getCSRF === 'function' ? getCSRF() : ''
                    }
                });
                const data = await response.json();

                if (response.ok && data.success) {
                    showToast(data.message || 'Contrato histórico registrado.', 'success');
                    const modal = document.getElementById('historicalPeriodModal');
                    if (modal) modal.remove();
                    if (typeof window.refreshCurrentTable === 'function') {
                        window.refreshCurrentTable();
                    }
                } else if (data.errors) {
                    const errorMsg = Object.entries(data.errors)
                        .map(([field, errs]) => `• <b>${field}:</b> ${errs.join(', ')}`)
                        .join('<br>');
                    Swal.fire({title: 'Error de Validación', html: errorMsg, icon: 'warning'});
                } else {
                    Swal.fire('Error', data.message || 'No se pudo guardar el registro histórico.', 'error');
                }
            } catch (error) {
                showToast('Error de red al guardar el contrato histórico', 'error');
            } finally {
                if (submitBtn) submitBtn.disabled = false;
            }
        });
    }

    // =========================================================================
    // 4. TABLE ACTIONS (SIGN, TERMINATE, PRINT, VIEW)
    // =========================================================================

    function initTableActions() {
        const wrapper = document.getElementById('table-app');
        if (!wrapper) return;

        wrapper.addEventListener('click', (e) => {
            const btn = e.target.closest('button');
            if (!btn) return;

            const action = btn.dataset.action;
            const periodId = btn.dataset.id;
            const category = btn.dataset.contractCategory;

            if (action === 'view') openPeriodDetail(periodId);
            if (action === 'sign') signPeriod(periodId, category);
            if (action === 'terminate') terminatePeriod(periodId);
            if (action === 'print') printPeriod(periodId);
        });
    }

    function printPeriod(periodId) {
        if (!periodId) return;
        window.open(`/contract/periods/print/${periodId}/`, '_blank');
    }

    function signPeriod(periodId, category = '') {
        const isAction = (category || '').toUpperCase() === 'ACCION_PERSONAL';
        const label = isAction ? 'Acción de Personal' : 'Contrato';

        Swal.fire({
            title: `¿Legalizar ${label}?`,
            text: 'El estado cambiará formalmente a FIRMADO.',
            icon: 'question',
            showCancelButton: true,
            confirmButtonText: 'Sí, Legalizar',
            cancelButtonText: 'Cancelar'
        }).then(async (result) => {
            if (result.isConfirmed) {
                try {
                    const response = await fetch(`/contract/periods/sign/${periodId}/`, {
                        method: 'POST',
                        headers: {
                            'X-Requested-With': 'XMLHttpRequest',
                            'X-CSRFToken': typeof getCSRF === 'function' ? getCSRF() : ''
                        }
                    });
                    const data = await response.json();
                    if (data.success) {
                        showToast(data.message || `${label} legalizado correctamente.`, 'success');
                        if (typeof window.refreshCurrentTable === 'function') window.refreshCurrentTable();
                    } else {
                        Swal.fire('Atención', data.message || 'No se pudo firmar.', 'warning');
                    }
                } catch (error) {
                    showToast('Error al legalizar el documento', 'error');
                }
            }
        });
    }

    async function terminatePeriod(periodId) {
        const {value: formValues, isConfirmed} = await Swal.fire({
            title: 'Finalizar Gestión Laboral',
            html: `
                <div class="swal-form-grid">
                    <div>
                        <label class="form-label">Motivo de salida *</label>
                        <textarea id="swal-terminate-reason" class="input-field" rows="3" placeholder="Detalle el motivo"></textarea>
                    </div>
                    <div>
                        <label class="form-label">Fecha fin de gestión *</label>
                        <input id="swal-terminate-end-date" type="date" class="form-control" />
                    </div>
                </div>
            `,
            showCancelButton: true,
            confirmButtonText: 'Finalizar Gestión',
            cancelButtonText: 'Cancelar',
            preConfirm: () => {
                const reason = document.getElementById('swal-terminate-reason').value.trim();
                const endDate = document.getElementById('swal-terminate-end-date').value;
                if (!reason) {
                    Swal.showValidationMessage('El motivo de salida es obligatorio.');
                    return false;
                }
                if (!endDate) {
                    Swal.showValidationMessage('La fecha fin de gestión es obligatoria.');
                    return false;
                }
                return {reason, end_date: endDate};
            }
        });

        if (isConfirmed && formValues) {
            const formData = new FormData();
            formData.append('reason', formValues.reason);
            formData.append('end_date', formValues.end_date);

            try {
                const response = await fetch(`/contract/periods/terminate/${periodId}/`, {
                    method: 'POST',
                    body: formData,
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest',
                        'X-CSRFToken': typeof getCSRF === 'function' ? getCSRF() : ''
                    }
                });
                const data = await response.json();
                if (data.success) {
                    showToast(data.message || 'Gestión finalizada con éxito.', 'success');
                    if (typeof window.refreshCurrentTable === 'function') window.refreshCurrentTable();
                } else {
                    Swal.fire('Error', data.message || 'No se pudo finalizar la gestión.', 'error');
                }
            } catch (error) {
                showToast('Error técnico al finalizar gestión', 'error');
            }
        }
    }

    // =========================================================================
    // 5. WIZARD CREATION FLOW
    // =========================================================================

    let wizardStep = 1;
    let selectedContractType = {id: null, name: '', code: '', category: ''};
    let selectedEmployee = {id: null, fullName: '', photo: null, budgetLine: null};
    let unitLevels = [];

    function initWizardEvents() {
        const btnOpen = document.getElementById('btn-open-wizard');
        const btnCloseTop = document.getElementById('btn-close-wizard-top');
        const btnCancel = document.getElementById('btn-wizard-cancel');
        const btnPrev = document.getElementById('btn-wizard-prev');
        const form = document.getElementById('wizardForm');
        const btnValidate = document.getElementById('btn-validate-employee');
        const searchDocInput = document.getElementById('wizard-search-doc-input');

        if (btnOpen) btnOpen.addEventListener('click', openWizard);
        if (btnCloseTop) btnCloseTop.addEventListener('click', closeWizard);
        if (btnCancel) btnCancel.addEventListener('click', closeWizard);
        if (btnPrev) btnPrev.addEventListener('click', () => setWizardStep(wizardStep - 1));

        document.querySelectorAll('.js-select-contract-type').forEach(card => {
            card.addEventListener('click', () => {
                selectedContractType = {
                    id: card.dataset.id,
                    name: card.dataset.name,
                    code: (card.dataset.code || '').toUpperCase(),
                    category: (card.dataset.category || '').toUpperCase()
                };
                setWizardStep(2);
            });
        });

        if (btnValidate) btnValidate.addEventListener('click', validateEmployee);
        if (searchDocInput) {
            searchDocInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    validateEmployee();
                }
            });
        }

        if (form) form.addEventListener('submit', submitWizardForm);
    }

    function openWizard() {
        wizardStep = 1;
        resetWizardData();
        setWizardStep(1);
        const overlay = document.getElementById('wizardModalOverlay');
        if (overlay) overlay.classList.remove('hidden');
        document.body.classList.add('no-scroll');
    }

    function closeWizard() {
        const overlay = document.getElementById('wizardModalOverlay');
        if (overlay) overlay.classList.add('hidden');
        document.body.classList.remove('no-scroll');
        resetWizardData();
    }

    function resetWizardData() {
        const form = document.getElementById('wizardForm');
        if (form) form.reset();
        selectedContractType = {id: null, name: '', code: '', category: ''};
        selectedEmployee = {id: null, fullName: '', photo: null, budgetLine: null};
        unitLevels = [];
        const c1 = document.getElementById('wizard-action-unit-levels-container');
        const c2 = document.getElementById('wizard-contract-unit-levels-container');
        if (c1) c1.innerHTML = '';
        if (c2) c2.innerHTML = '';
    }

    function setWizardStep(step) {
        wizardStep = step;
        [1, 2, 3].forEach(s => {
            const pane = document.getElementById(`wizard-step-${s}`);
            const ind = document.getElementById(`step-indicator-${s}`);
            if (pane) pane.classList.toggle('hidden', s !== step);
            if (ind) {
                ind.classList.remove('active', 'completed');
                if (s === step) ind.classList.add('active');
                else if (s < step) ind.classList.add('completed');
            }
        });

        const btnPrev = document.getElementById('btn-wizard-prev');
        const btnCancel = document.getElementById('btn-wizard-cancel');
        const btnSubmit = document.getElementById('btn-wizard-submit');
        if (btnPrev) btnPrev.classList.toggle('hidden', step === 1);
        if (btnCancel) btnCancel.classList.toggle('hidden', step > 1);
        if (btnSubmit) btnSubmit.classList.toggle('hidden', step !== 3);

        if (step === 2) {
            const input = document.getElementById('wizard-search-doc-input');
            if (input) {
                input.value = '';
                input.focus();
            }
        }

        if (step === 3) {
            setupStepThree();
            loadInitialUnits();
        }
    }

    async function validateEmployee() {
        const input = document.getElementById('wizard-search-doc-input');
        const docNumber = (input?.value || '').trim();
        if (!docNumber) {
            showToast('Por favor ingrese la cédula.', 'warning');
            return;
        }

        const btn = document.getElementById('btn-validate-employee');
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
        }

        try {
            const res = await fetch(`/contract/periods/validate-employee/${encodeURIComponent(docNumber)}/?contract_type_id=${selectedContractType.id}`);
            const data = await res.json();

            if (data.success && data.employee) {
                const isProf = selectedContractType.code === 'SERVICIOS_PROFESIONALES';
                const hasLine = data.employee.budget_line && data.employee.budget_line.id;

                if (!isProf && !hasLine) {
                    Swal.fire({
                        title: 'Atención',
                        text: 'La persona no tiene una partida presupuestaria asignada. Debe asignarle una partida antes de continuar.',
                        icon: 'warning',
                        confirmButtonText: 'Entendido'
                    });
                    return;
                }

                selectedEmployee = {
                    id: data.employee.id,
                    fullName: data.employee.full_name,
                    photo: data.employee.photo,
                    budgetLine: data.employee.budget_line
                };

                if (data.employee.contract_type_category) {
                    selectedContractType.category = data.employee.contract_type_category;
                }

                setWizardStep(3);
            } else {
                Swal.fire({
                    title: 'Atención',
                    text: data.message || 'No se pudo validar el empleado.',
                    icon: 'warning',
                    confirmButtonText: 'Entendido'
                });
            }
        } catch (e) {
            showToast('Error de comunicación con el servidor', 'error');
        } finally {
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = '<i class="fas fa-search"></i>';
            }
        }
    }

    function setupStepThree() {
        document.getElementById('wizard_employee_id').value = selectedEmployee.id || '';
        document.getElementById('wizard_contract_type_id').value = selectedContractType.id || '';
        document.getElementById('wizard_budget_line_id').value = selectedEmployee.budgetLine ? selectedEmployee.budgetLine.id : '';

        document.getElementById('wizard-display-employee-name').textContent = selectedEmployee.fullName || '-';
        document.getElementById('wizard-display-contract-name').textContent = selectedContractType.name || '-';

        const photo = document.getElementById('wizard-display-photo');
        if (selectedEmployee.photo) photo.src = selectedEmployee.photo;

        const container = document.getElementById('wizard-budget-inherited-container');
        if (selectedEmployee.budgetLine) {
            container.innerHTML = `
                <small class="text-white-opacity block-meta">PARTIDA HEREDADA</small>
                <strong class="text-accent block-meta">${selectedEmployee.budgetLine.number}</strong>
                <span class="block-meta small text-white-opacity">${selectedEmployee.budgetLine.position}</span>
            `;
        } else {
            container.innerHTML = `
                <small class="text-white-opacity block-meta">MODO MANUAL</small>
                <strong class="text-accent block-meta">SIN PARTIDA</strong>
                <span class="block-meta small text-white-opacity">SERVICIOS PROFESIONALES</span>
            `;
        }

        const isProf = selectedContractType.code === 'SERVICIOS_PROFESIONALES';
        const isAction = selectedContractType.category === 'ACCION_PERSONAL';

        const manual = document.getElementById('wizard-manual-compensation-section');
        if (manual) {
            const showManual = isProf && !isAction;
            manual.classList.toggle('hidden', !showManual);
            manual.querySelectorAll('input, select, textarea').forEach(el => {
                el.disabled = !showManual;
            });
        }

        const actionFields = document.getElementById('wizard-action-specific-fields');
        const contractFields = document.getElementById('wizard-contract-specific-fields');

        if (actionFields && contractFields) {
            actionFields.classList.toggle('hidden', !isAction);
            contractFields.classList.toggle('hidden', isAction);

            actionFields.querySelectorAll('input, select, textarea').forEach(el => {
                el.disabled = !isAction;
            });
            contractFields.querySelectorAll('input, select, textarea').forEach(el => {
                el.disabled = isAction;
            });
        }
    }

    async function loadInitialUnits() {
        try {
            const res = await fetch('/institution/ajax/unit-children/');
            const data = await res.json();
            if (data.success && data.units) {
                unitLevels = [{options: data.units, selectedId: null}];
                renderUnitLevels();
            }
        } catch (e) {
            console.error('Error loading units:', e);
        }
    }

    async function handleUnitChange(index, selectedId) {
        unitLevels = unitLevels.slice(0, index + 1);
        unitLevels[index].selectedId = selectedId ? parseInt(selectedId, 10) : null;

        document.getElementById('wizard_administrative_unit_id').value = selectedId || '';

        if (!selectedId) {
            renderUnitLevels();
            return;
        }

        try {
            const res = await fetch(`/institution/ajax/unit-children/?parent_id=${selectedId}`);
            const data = await res.json();
            if (data.success && data.units && data.units.length > 0) {
                unitLevels.push({options: data.units, selectedId: null});
            }
        } catch (e) {
            console.error('Error loading sub-units:', e);
        }

        renderUnitLevels();
    }

    function renderUnitLevels() {
        const isAction = selectedContractType.category === 'ACCION_PERSONAL';
        const container = document.getElementById(isAction ? 'wizard-action-unit-levels-container' : 'wizard-contract-unit-levels-container');
        if (!container) return;

        container.innerHTML = '';
        unitLevels.forEach((level, index) => {
            const box = document.createElement('div');
            box.className = 'unit-level-box';

            const label = document.createElement('label');
            label.textContent = index === 0 ? 'Dirección / Unidad Raíz' : `Sub-dependencia Nivel ${index + 1}`;

            const select = document.createElement('select');
            select.className = 'input-field';
            select.innerHTML = '<option value="">-- Seleccione una opción --</option>';

            level.options.forEach(opt => {
                const optEl = document.createElement('option');
                optEl.value = opt.id;
                optEl.textContent = (opt.name || '').toUpperCase();
                if (level.selectedId === opt.id) optEl.selected = true;
                select.appendChild(optEl);
            });

            select.addEventListener('change', (e) => handleUnitChange(index, e.target.value));

            box.appendChild(label);
            box.appendChild(select);
            container.appendChild(box);
        });
    }

    async function submitWizardForm(e) {
        e.preventDefault();
        const unitId = document.getElementById('wizard_administrative_unit_id').value;
        if (!unitId) {
            Swal.fire({
                title: 'Atención',
                text: 'Debe seleccionar la unidad administrativa.',
                icon: 'warning',
                confirmButtonText: 'Entendido'
            });
            return;
        }

        const form = document.getElementById('wizardForm');
        const formData = new FormData(form);
        const submitBtn = document.getElementById('btn-wizard-submit');
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Guardando...';
        }

        try {
            const response = await fetch('/contract/periods/create/', {
                method: 'POST',
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': typeof getCSRF === 'function' ? getCSRF() : ''
                }
            });
            const result = await response.json();

            if (response.ok && result.success) {
                showToast(result.message || 'Gestión registrada correctamente', 'success');
                closeWizard();
                if (typeof window.refreshCurrentTable === 'function') window.refreshCurrentTable();
            } else {
                let errorMsg = result.message || 'Existen errores en el formulario.';
                if (result.errors) {
                    errorMsg = Object.entries(result.errors).map(([f, err]) => `• <b>${f}:</b> ${err}`).join('<br>');
                }
                Swal.fire({
                    title: 'Error de Validación',
                    html: errorMsg,
                    icon: 'warning',
                    confirmButtonText: 'Entendido'
                });
            }
        } catch (error) {
            showToast('Error técnico al guardar la gestión', 'error');
        } finally {
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.innerHTML = '<i class="fas fa-check-double"></i> FINALIZAR GESTIÓN';
            }
        }
    }

    // =========================================================================
    // 6. DETAIL MODAL, PDF UPLOAD & EDIT
    // =========================================================================

    let activePeriodDetail = null;

    function initDetailEvents() {
        const closeTop = document.getElementById('btn-close-detail-top');
        const closeBottom = document.getElementById('btn-close-detail-bottom');
        const editBtn = document.getElementById('btn-detail-edit');
        const uploadBtn = document.getElementById('btn-upload-doc');
        const deleteDocBtn = document.getElementById('btn-delete-doc');

        if (closeTop) closeTop.addEventListener('click', closePeriodDetail);
        if (closeBottom) closeBottom.addEventListener('click', closePeriodDetail);
        if (editBtn) editBtn.addEventListener('click', openDetailEditSwal);
        if (uploadBtn) uploadBtn.addEventListener('click', uploadPeriodDocument);
        if (deleteDocBtn) deleteDocBtn.addEventListener('click', deletePeriodDocument);
    }

    function toggleDocumentState(signedUrl) {
        const uploadBox = document.getElementById('detail-doc-upload-box');
        const viewBox = document.getElementById('detail-doc-view-box');
        const docLink = document.getElementById('detail-doc-link');

        if (!uploadBox || !viewBox) return;

        if (signedUrl) {
            uploadBox.classList.add('hidden');
            viewBox.classList.remove('hidden');
            if (docLink) docLink.href = signedUrl;
        } else {
            uploadBox.classList.remove('hidden');
            viewBox.classList.add('hidden');
            if (docLink) docLink.href = '#';
        }
    }

    async function openPeriodDetail(periodId) {
        if (!periodId) return;
        try {
            const res = await fetch(`/contract/periods/detail/${periodId}/`);
            const data = await res.json();
            if (data.success && data.period) {
                activePeriodDetail = data.period;
                const p = data.period;

                document.getElementById('detail-document-number').textContent = p.document_number || '-';
                document.getElementById('detail-employee-name').textContent = p.employee_name || '-';
                document.getElementById('detail-status-badge').textContent = p.status_name || '-';
                document.getElementById('detail-position-name').textContent = p.position_name || '-';
                document.getElementById('detail-budget-number').textContent = p.budget_line_number || '-';
                document.getElementById('detail-unit-name').textContent = p.unit_name || 'N/A';
                document.getElementById('detail-memo').textContent = p.institutional_need_memo || 'N/A';
                document.getElementById('detail-cert').textContent = p.budget_certification || 'N/A';
                document.getElementById('detail-workplace').textContent = p.workplace || 'N/A';
                document.getElementById('detail-contract-type').textContent = p.contract_type_name || '-';
                document.getElementById('detail-remuneration').textContent = p.remuneration || '-';
                document.getElementById('detail-start-date').textContent = p.start_date_formatted || '-';
                document.getElementById('detail-end-date').textContent = p.end_date_formatted || 'INDEFINIDO';
                document.getElementById('detail-schedule').textContent = p.schedule_name || 'SIN HORARIO';

                const isAction = p.contract_type_category === 'ACCION_PERSONAL';
                const funcSection = document.getElementById('detail-functions-section');
                const actionSection = document.getElementById('detail-action-section');

                if (funcSection) funcSection.classList.toggle('hidden', isAction);
                if (actionSection) actionSection.classList.toggle('hidden', !isAction);

                const funcText = document.getElementById('detail-job-functions');
                if (funcText) funcText.textContent = p.job_functions || 'Sin funciones registradas.';

                const motText = document.getElementById('detail-action-motivation');
                const expText = document.getElementById('detail-action-explanation');
                if (motText) motText.textContent = p.action_motivation || '-';
                if (expText) expText.textContent = p.action_explanation || '-';

                toggleDocumentState(p.signed_document_url);

                if (p.employee_photo) {
                    document.getElementById('detail-employee-photo').src = p.employee_photo;
                }

                const editBtn = document.getElementById('btn-detail-edit');
                if (editBtn) {
                    editBtn.classList.toggle('hidden', p.status_code !== 'SIN_FIRMAR');
                }

                const overlay = document.getElementById('detailModalOverlay');
                if (overlay) overlay.classList.remove('hidden');
                document.body.classList.add('no-scroll');
            }
        } catch (e) {
            showToast('Error al consultar el expediente', 'error');
        }
    }

    function closePeriodDetail() {
        const overlay = document.getElementById('detailModalOverlay');
        if (overlay) overlay.classList.add('hidden');
        document.body.classList.remove('no-scroll');
        activePeriodDetail = null;
    }

    async function uploadPeriodDocument() {
        if (!activePeriodDetail) return;
        const fileInput = document.getElementById('detail-doc-file-input');
        const file = fileInput?.files?.[0];
        if (!file) {
            showToast('Seleccione un archivo PDF primero.', 'warning');
            return;
        }

        const formData = new FormData();
        formData.append('contract_file', file);

        try {
            const res = await fetch(`/contract/periods/upload-doc/${activePeriodDetail.id}/`, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': typeof getCSRF === 'function' ? getCSRF() : ''
                }
            });
            const data = await res.json();
            if (data.success) {
                showToast(data.message || 'Documento cargado.', 'success');
                activePeriodDetail.signed_document_url = data.file_url;
                toggleDocumentState(data.file_url);
                fileInput.value = '';
            } else {
                Swal.fire('Error', data.message || 'No se pudo cargar el PDF.', 'error');
            }
        } catch (error) {
            showToast('Error al subir el documento', 'error');
        }
    }

    async function deletePeriodDocument() {
        if (!activePeriodDetail) return;
        try {
            const res = await fetch(`/contract/periods/delete-doc/${activePeriodDetail.id}/`, {
                method: 'POST',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': typeof getCSRF === 'function' ? getCSRF() : ''
                }
            });
            const data = await res.json();
            if (data.success) {
                showToast(data.message || 'Documento eliminado.', 'success');
                activePeriodDetail.signed_document_url = null;
                toggleDocumentState(null);
            } else {
                Swal.fire('Atención', data.message || 'No se pudo eliminar.', 'warning');
            }
        } catch (error) {
            showToast('Error al eliminar el documento', 'error');
        }
    }

    async function openDetailEditSwal() {
        const p = activePeriodDetail;
        if (!p) return;

        const schedules = getSchedulesData();
        let scheduleOptions = '<option value="">Seleccione un horario...</option>';
        schedules.forEach(s => {
            scheduleOptions += `<option value="${s.id}" ${s.name === p.schedule_name ? 'selected' : ''}>${s.name}</option>`;
        });

        const {value: formValues} = await Swal.fire({
            title: 'Modificar Datos Administrativos',
            width: '800px',
            padding: '2rem',
            html: `
                <div class="swal-form-grid-2">
                    <div class="form-group">
                        <label class="form-label">Número de Documento</label>
                        <input id="swal-doc" type="text" class="input-field readonly-styled" value="${p.document_number || ''}" readonly>
                        <small class="form-hint">Secuencial asignado por el sistema.</small>
                    </div>
                    <div class="form-group">
                        <label class="form-label">Lugar de Trabajo</label>
                        <input id="swal-workplace" class="form-control" value="${p.workplace === 'N/A' ? '' : p.workplace || ''}">
                    </div>
                    <div class="form-group">
                        <label class="form-label">Memo Necesidad</label>
                        <input id="swal-memo" class="form-control" value="${p.institutional_need_memo || ''}">
                    </div>
                    <div class="form-group">
                        <label class="form-label">Cert. Presupuestaria</label>
                        <input id="swal-cert" class="form-control" value="${p.budget_certification || ''}">
                    </div>
                    <div class="form-group">
                        <label class="form-label">Fecha Inicio</label>
                        <input type="date" id="swal-start" class="form-control" value="${p.start_date || ''}">
                    </div>
                    <div class="form-group">
                        <label class="form-label">Fecha Fin</label>
                        <input type="date" id="swal-end" class="form-control" value="${p.end_date || ''}">
                    </div>
                </div>
                <div class="form-group swal-form-spacer">
                    <label class="form-label">Horario Laboral</label>
                    <select id="swal-schedule" class="form-control">${scheduleOptions}</select>
                </div>
                <div class="form-group swal-form-spacer">
                    <label class="form-label">Funciones del Puesto</label>
                    <textarea id="swal-functions" class="form-control" rows="3">${p.job_functions || ''}</textarea>
                </div>
            `,
            showCancelButton: true,
            confirmButtonText: 'Guardar Cambios',
            cancelButtonText: 'Cancelar',
            preConfirm: () => {
                const start = document.getElementById('swal-start').value;
                if (!start) {
                    Swal.showValidationMessage('La fecha de inicio es obligatoria.');
                    return false;
                }
                return {
                    doc: document.getElementById('swal-doc').value.trim(),
                    workplace: document.getElementById('swal-workplace').value.trim().toUpperCase(),
                    memo: document.getElementById('swal-memo').value.trim().toUpperCase(),
                    cert: document.getElementById('swal-cert').value.trim().toUpperCase(),
                    start: start,
                    end: document.getElementById('swal-end').value,
                    schedule: document.getElementById('swal-schedule').value,
                    functions: document.getElementById('swal-functions').value.trim()
                };
            }
        });

        if (formValues) {
            const formData = new FormData();
            Object.keys(formValues).forEach(k => formData.append(k, formValues[k]));

            try {
                const res = await fetch(`/contract/periods/update-partial/${p.id}/`, {
                    method: 'POST',
                    body: formData,
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest',
                        'X-CSRFToken': typeof getCSRF === 'function' ? getCSRF() : ''
                    }
                });
                const result = await res.json();
                if (result.success) {
                    showToast(result.message || 'Expediente actualizado', 'success');
                    openPeriodDetail(p.id);
                    if (typeof window.refreshCurrentTable === 'function') window.refreshCurrentTable();
                } else {
                    Swal.fire('Error', result.message || 'No se pudo actualizar.', 'error');
                }
            } catch (err) {
                showToast('Error técnico al actualizar el expediente', 'error');
            }
        }
    }
})();