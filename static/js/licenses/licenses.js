/* static/js/licenses/licenses.js
   Client-side handlers for Medical Licenses, Receptions, and License Types
*/

(function () {
    'use strict';

    const getCsrfToken = (container = document) => {
        const input = container.querySelector('[name="csrfmiddlewaretoken"]')
            || document.querySelector('[name="csrfmiddlewaretoken"]');
        if (input && input.value) return input.value;
        const cookieMatch = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
        return cookieMatch ? decodeURIComponent(cookieMatch[1]) : '';
    };

    const updateReceptionEndDate = () => {
        const startInput = document.querySelector('#receptionForm [name="license_start_date"]');
        const daysInput = document.querySelector('#receptionForm [name="license_days"]');
        const endInput = document.querySelector('#receptionForm [name="license_end_date"]');
        if (!startInput || !daysInput || !endInput) return;

        const days = Number.parseInt(daysInput.value, 10);
        if (!startInput.value || !Number.isInteger(days) || days <= 0) {
            endInput.value = '';
            return;
        }
        const endDate = new Date(`${startInput.value}T00:00:00`);
        endDate.setDate(endDate.getDate() + days - 1);
        endInput.value = endDate.toISOString().slice(0, 10);
    };

    document.addEventListener('input', event => {
        if (event.target.matches('#receptionForm [name="license_start_date"], #receptionForm [name="license_days"]')) {
            updateReceptionEndDate();
        }
    });

    document.addEventListener('submit', event => {
        if (event.target.id === 'receptionForm') updateReceptionEndDate();
    });

    window.openReturnReceptionModal = function (licenseId) {
        if (typeof openAjaxModal === 'function') {
            openAjaxModal(`/licencias/${licenseId}/devolver-recepcion-modal/`);
        }
    };

    window.submitReturnReceptionForm = function (event) {
        event.preventDefault();
        const form = event.target;
        fetch(form.action, {
            method: 'POST',
            body: new FormData(form),
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': getCsrfToken(form)
            }
        })
            .then(async response => {
                const data = await response.json();
                if (!response.ok) throw new Error(data.message || 'No se pudo devolver la licencia.');
                return data;
            })
            .then(data => {
                if (typeof closeModal === 'function') closeModal();
                Swal.fire({
                    icon: 'success',
                    title: 'Licencia devuelta',
                    text: data.message,
                    timer: 1800,
                    showConfirmButton: false
                }).then(() => window.location.reload());
            })
            .catch(error => {
                Swal.fire({icon: 'error', title: 'Error', text: error.message});
            });
    };

    window.generateLicenseSubsidyReport = function (event) {
        event.preventDefault();
        const form = event.target;
        const submitButton = form.querySelector('[type="submit"]');
        if (submitButton) submitButton.disabled = true;

        fetch(form.action, {
            method: 'POST',
            body: new FormData(form),
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': getCsrfToken(form)
            }
        })
            .then(async response => {
                if (!response.ok) {
                    const data = await response.json().catch(() => ({}));
                    throw new Error(data.message || 'No se pudo generar el reporte.');
                }
                return response.blob();
            })
            .then(blob => {
                const url = URL.createObjectURL(blob);
                const link = document.createElement('a');
                link.href = url;
                link.download = `Reporte_Subsidios_${form.period.value}.xlsx`;
                link.click();
                URL.revokeObjectURL(url);
                if (typeof closeModal === 'function') closeModal();
            })
            .catch(error => {
                Swal.fire({icon: 'error', title: 'Reporte de subsidios', text: error.message});
            })
            .finally(() => {
                if (submitButton) submitButton.disabled = false;
            });
    };

    document.addEventListener('click', event => {
        const printButton = event.target.closest('.js-license-print-action');
        if (printButton) {
            event.preventDefault();
            window.open(`/personnel_actions/${printButton.dataset.actionId}/pdf/`, '_blank');
            return;
        }

        const registerButton = event.target.closest('.js-license-register-action');
        if (!registerButton) return;
        event.preventDefault();

        Swal.fire({
            icon: 'question',
            title: 'Registrar acción',
            text: 'Al registrar se generarán los permisos de justificación y cambios de horario.',
            showCancelButton: true,
            confirmButtonText: 'Registrar',
            cancelButtonText: 'Cancelar'
        }).then(result => {
            if (!result.isConfirmed) return null;
            return fetch(`/personnel_actions/${registerButton.dataset.actionId}/register/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCsrfToken(),
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });
        }).then(response => {
            if (!response) return null;
            return response.json().then(data => ({ok: response.ok, data}));
        }).then(result => {
            if (!result) return;
            if (!result.ok || !result.data.success) {
                throw new Error(result.data.message || 'No se pudo registrar la acción.');
            }
            window.location.reload();
        }).catch(error => {
            Swal.fire({icon: 'error', title: 'Error', text: error.message});
        });
    });

    // ==========================================
    // 1. LICENSE TYPES CATALOG
    // ==========================================
    window.initLicenseTypeFilters = function () {
        const toggleInactive = document.getElementById('toggleInactiveTypes');
        const searchInput = document.getElementById('table-search');

        const refreshTable = () => {
            const params = new URLSearchParams();
            if (toggleInactive && toggleInactive.checked) {
                params.set('show_inactive', 'true');
            }
            if (searchInput && searchInput.value.trim()) {
                params.set('q', searchInput.value.trim());
            }

            fetch(`${window.location.pathname}?${params.toString()}`, {
                headers: {'X-Requested-With': 'XMLHttpRequest'}
            })
                .then(res => res.json())
                .then(data => {
                    if (data.success && data.html) {
                        const wrapper = document.getElementById('table-content-wrapper');
                        if (wrapper) {
                            wrapper.innerHTML = data.html;
                            const newTable = wrapper.querySelector('.managed-table');
                            if (newTable && typeof TableManager !== 'undefined') {
                                new TableManager(newTable);
                            }
                        }
                    }
                })
                .catch(err => console.error('Error filtering license types:', err));
        };
        document.addEventListener('click', event => {
            const infoButton = event.target.closest('.license-type-info-btn');
            if (!infoButton) return;

            const losepText = infoButton.dataset.licenseTypeDescription || 'Sin observaciones registradas.';
            const ctText = infoButton.dataset.licenseTypeDescriptionCt || 'Usa la misma base legal de LOSEP.';

            Swal.fire({
                icon: 'info',
                title: infoButton.dataset.licenseTypeName || 'Tipo de licencia',
                html: `
                    <div style="text-align:left; font-size:0.9rem;">
                        <p><strong>Base Legal LOSEP:</strong><br>${losepText}</p>
                        <hr>
                        <p><strong>Base Legal Código de Trabajo (CT):</strong><br>${ctText}</p>
                    </div>
                `,
                confirmButtonText: 'Cerrar'
            });
        });

        if (toggleInactive) {
            toggleInactive.addEventListener('change', refreshTable);
        }

        if (searchInput) {
            let debounceTimer;
            searchInput.addEventListener('input', () => {
                clearTimeout(debounceTimer);
                debounceTimer = setTimeout(refreshTable, 250);
            });
        }
    };

    window.initLicenseTypeModalScripts = function () {
        if (window.$ && $.fn.select2) {
            $('#licenseTypeForm select.select2-modal, #licenseTypeForm select.select2-modal-requirements').select2({
                width: '100%',
                dropdownParent: $('#modal-root')
            });
        }
    };

    window.openRequirementModal = function () {
        fetch('/licencias/requisitos/crear-modal/', {
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        })
            .then(res => res.json())
            .then(data => {
                if (data.success && data.html) {
                    const submodalRoot = document.getElementById('submodal-root');
                    if (submodalRoot) submodalRoot.innerHTML = data.html;
                }
            })
            .catch(err => console.error('Error loading requirement modal:', err));
    };

    window.closeSubmodal = function () {
        const submodalRoot = document.getElementById('submodal-root');
        if (submodalRoot) submodalRoot.innerHTML = '';
    };

    window.submitRequirementFormAjax = function (event) {
        event.preventDefault();
        const form = event.target;

        fetch(form.action, {
            method: 'POST',
            body: new FormData(form),
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': getCsrfToken(form)
            }
        })
            .then(res => res.json())
            .then(data => {
                if (data.success && data.requirement) {
                    const selectReq = document.getElementById('id_requirements_list');
                    if (selectReq) {
                        const newOption = new Option(data.requirement.name, data.requirement.id, true, true);
                        selectReq.appendChild(newOption);
                        if (window.$ && $.fn.select2) {
                            $(selectReq).trigger('change');
                        }
                    }
                    window.closeSubmodal();
                    Swal.fire({
                        icon: 'success',
                        title: 'Requisito registrado',
                        text: data.message || 'Requisito creado correctamente.',
                        timer: 1500,
                        showConfirmButton: false
                    });
                } else {
                    Swal.fire({
                        icon: 'warning',
                        title: 'Validación',
                        text: 'Por favor verifique los datos ingresados.'
                    });
                }
            })
            .catch(err => {
                console.error('Error saving requirement:', err);
                Swal.fire({icon: 'error', title: 'Error', text: 'No se pudo guardar el requisito.'});
            });
    };

    // ==========================================
    // 2. MEDICAL LICENSES LIST
    // ==========================================
    window.initMedicalLicenseFilters = function () {
        const form = document.getElementById('license-filter-form');
        const searchInput = document.getElementById('table-search-license');
        const typeFilter = document.getElementById('filter_license_type');
        const legalizedFilter = document.getElementById('filter_is_legalized');
        const resetButton = document.getElementById('btnResetFilters');
        if (!form || !searchInput || !typeFilter || !legalizedFilter) return;

        const refresh = () => {
            const params = new URLSearchParams();
            const query = searchInput.value.trim();
            if (query) params.set('q', query);
            if (typeFilter.value) params.set('license_type', typeFilter.value);
            if (legalizedFilter.value) params.set('is_legalized', legalizedFilter.value);

            fetch(`${window.location.pathname}?${params.toString()}`, {
                headers: {'X-Requested-With': 'XMLHttpRequest'}
            })
                .then(response => response.json())
                .then(data => {
                    if (!data.success) throw new Error(data.message || 'No se pudo realizar la búsqueda.');
                    const wrapper = document.getElementById('table-content-wrapper');
                    if (wrapper) wrapper.innerHTML = data.html;
                })
                .catch(error => {
                    Swal.fire({icon: 'error', title: 'Error', text: error.message});
                });
        };

        form.addEventListener('submit', event => {
            event.preventDefault();
            refresh();
        });

        if (resetButton) {
            resetButton.addEventListener('click', () => {
                searchInput.value = '';
                typeFilter.value = '';
                legalizedFilter.value = '';
                refresh();
            });
        }
    };

    window.initMedicalLicenseStats = function () {
        const cards = document.querySelectorAll('#license-stats-row [data-license-status]');
        if (!cards.length) return;

        const setActiveCard = status => {
            cards.forEach(card => {
                card.classList.toggle('opacity-low', status !== 'all' && card.dataset.licenseStatus !== status);
            });
        };

        setActiveCard('all');
        cards.forEach(card => {
            card.addEventListener('click', () => {
                const filter = document.getElementById('filter_is_legalized');
                if (!filter) return;
                const status = card.dataset.licenseStatus;
                setActiveCard(status);
                filter.value = status === 'all' ? '' : status === 'pending' ? 'pending_registered' : status;
                document.getElementById('license-filter-form')?.dispatchEvent(
                    new Event('submit', {bubbles: true, cancelable: true})
                );
            });
        });
    };

    window.showLicenseSubsidyAmount = function (button) {
        const rawAmount = String(button.dataset.subsidyAmount || '0').replace(',', '.').trim();
        const parsedAmount = Number.parseFloat(rawAmount);
        const amount = Number.isFinite(parsedAmount) ? parsedAmount.toFixed(2) : '0.00';
        Swal.fire({
            icon: 'info',
            title: 'Descuento por subsidio',
            text: `Valor calculado: $${amount}`,
            confirmButtonText: 'Cerrar'
        });
    };

    // ==========================================
    // 3. DOCUMENT RECEPTION
    // ==========================================
    const receptionState = {
        status: 'all',
        sort: '',
        page: 1
    };

    window.loadTypeRequirements = function (typeId) {
        const container = document.getElementById('requirements_checklist_container');
        if (!container) return;

        if (!typeId) {
            container.innerHTML = '<div class="muted-note-inline">Seleccione un tipo de licencia para desplegar los anexos requeridos.</div>';
            return;
        }

        container.innerHTML = '<div class="loading-state-inline"><i class="fas fa-spinner fa-spin"></i> Cargando anexos requeridos...</div>';

        fetch(`/licencias/recepcion/obtener-requisitos/${typeId}/`, {
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        })
            .then(res => res.json())
            .then(data => {
                if (data.success && data.requirements && data.requirements.length > 0) {
                    const box = document.createElement('div');
                    box.className = 'reception-checklist-box';

                    data.requirements.forEach(req => {
                        const item = document.createElement('div');
                        item.className = 'reception-requirement-item';

                        const label = document.createElement('label');
                        label.className = 'requirement-label';
                        label.setAttribute('for', `req_${req.id}`);

                        const icon = document.createElement('i');
                        icon.className = 'fas fa-file-lines text-primary';

                        const textSpan = document.createElement('span');
                        textSpan.textContent = req.name;

                        label.appendChild(icon);
                        label.appendChild(textSpan);

                        const checkbox = document.createElement('input');
                        checkbox.type = 'checkbox';
                        checkbox.name = 'requirements_checked';
                        checkbox.value = req.id;
                        checkbox.id = `req_${req.id}`;
                        checkbox.className = 'requirement-checkbox';

                        item.appendChild(label);
                        item.appendChild(checkbox);
                        box.appendChild(item);
                    });

                    container.innerHTML = '';
                    container.appendChild(box);
                } else {
                    container.innerHTML = '<div class="muted-note-inline"><i class="fas fa-info-circle"></i> Este tipo de licencia no requiere anexos preconfigurados.</div>';
                }
            })
            .catch(err => {
                console.error('Error loading requirements:', err);
                container.innerHTML = '<div class="error-note-inline"><i class="fas fa-exclamation-triangle"></i> No se pudieron cargar los requisitos.</div>';
            });
    };

    if (window.$) {
        $(document).on('change', 'select[name="license_type"]', function () {
            window.loadTypeRequirements($(this).val());
        });
    }

    window.onModalLoaded = function () {
        const modalRoot = document.getElementById('modal-root');
        if (!modalRoot) return;

        // 1. Inicialización de Select2 en modales de Recepción y Licencia Médica
        if (window.$ && $.fn.select2) {
            $(modalRoot).find('select.select2-modal').each(function () {
                $(this).select2({
                    width: '100%',
                    dropdownParent: $(modalRoot)
                });
            });

            // Carga dinámica de checklist en Nueva Recepción
            const $receptionTypeSelect = $(modalRoot).find('#receptionForm select[name="license_type"]');
            if ($receptionTypeSelect.length) {
                $receptionTypeSelect.off('change.loadReq').on('change.loadReq', function () {
                    window.loadTypeRequirements($(this).val());
                });
                if ($receptionTypeSelect.val()) {
                    window.loadTypeRequirements($receptionTypeSelect.val());
                }
            }
        }

        // 2. Listeners condicionales para switches en Nueva Licencia Médica (#licenseCreateForm)
        const substituteCheckbox = modalRoot.querySelector('#id_has_substitute');
        const substituteWrapper = modalRoot.querySelector('#substitute-field-wrapper');
        const substituteSelect = modalRoot.querySelector('#id_substitute');

        const toggleSubstituteField = () => {
            if (!substituteCheckbox || !substituteWrapper) return;
            const isChecked = substituteCheckbox.checked;
            substituteWrapper.classList.toggle('hidden', !isChecked);

            if (substituteSelect) {
                substituteSelect.required = isChecked;
                if (!isChecked) {
                    substituteSelect.value = '';
                    if (window.$ && $.fn.select2) {
                        $(substituteSelect).val('').trigger('change');
                    }
                }
            }
        };

        if (substituteCheckbox) {
            substituteCheckbox.addEventListener('change', toggleSubstituteField);
            toggleSubstituteField();
        }

        const reducedHoursCheckbox = modalRoot.querySelector('#id_has_reduced_hours');
        const reducedHoursWrapper = modalRoot.querySelector('#reduced-hours-field-wrapper');
        const reducedHoursInput = modalRoot.querySelector('#id_reduced_hours');

        const toggleReducedHoursField = () => {
            if (!reducedHoursCheckbox || !reducedHoursWrapper) return;
            const isChecked = reducedHoursCheckbox.checked;
            reducedHoursWrapper.classList.toggle('hidden', !isChecked);

            if (reducedHoursInput) {
                reducedHoursInput.required = isChecked;
                if (!isChecked) {
                    reducedHoursInput.value = '';
                } else if (!reducedHoursInput.value) {
                    reducedHoursInput.value = '2.00';
                }
            }
        };

        if (reducedHoursCheckbox) {
            reducedHoursCheckbox.addEventListener('change', toggleReducedHoursField);
            toggleReducedHoursField();
        }
    };

    window.openValidateReceptionModal = function (receptionId) {
        if (typeof openAjaxModal === 'function') {
            openAjaxModal(`/licencias/recepcion/${receptionId}/validar-modal/`);
        }
    };

    window.submitValidateReceptionForm = function (event) {
        event.preventDefault();
        const form = event.target;

        fetch(form.action, {
            method: 'POST',
            body: new FormData(form),
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': getCsrfToken(form)
            }
        })
            .then(async res => {
                const data = await res.json();
                if (!res.ok) throw new Error(data.message || 'No se pudieron actualizar los requisitos.');
                return data;
            })
            .then(data => {
                if (data.success) {
                    if (typeof closeModal === 'function') closeModal();
                    applyReceptionFilters(receptionState.page);
                    Swal.fire({
                        icon: 'success',
                        title: 'Requisitos actualizados',
                        text: data.message,
                        timer: 1800,
                        showConfirmButton: false
                    });
                }
            })
            .catch(err => {
                Swal.fire({icon: 'error', title: 'Error', text: err.message});
            });
    };

    window.openDeliverReceptionModal = function (receptionId) {
        if (typeof openAjaxModal === 'function') {
            openAjaxModal(`/licencias/recepcion/${receptionId}/entregar-modal/`, () => {
                if (window.$ && $.fn.select2) {
                    $('#deliverReceptionModal select.select2-modal').select2({
                        width: '100%',
                        dropdownParent: $('#deliverReceptionModal')
                    });
                }
            });
        }
    };

    function getSelectedReceptionIds() {
        return Array.from(document.querySelectorAll('.reception-select:checked')).map(input => input.value);
    }

    function updateReceptionSelectionState() {
        const selected = getSelectedReceptionIds();
        const button = document.getElementById('btn-reception-deliver');
        if (button) button.disabled = selected.length === 0;

        const all = Array.from(document.querySelectorAll('.reception-select'));
        const selectAll = document.querySelector('.reception-select-all');
        if (selectAll) {
            selectAll.checked = all.length > 0 && all.every(input => input.checked);
            selectAll.indeterminate = selected.length > 0 && selected.length < all.length;
        }
    }

    document.addEventListener('click', event => {
        if (event.target.closest('.reception-select, .reception-select-all')) {
            window.requestAnimationFrame(updateReceptionSelectionState);
        }
    });

    window.openReceptionDetailModal = function (receptionId) {
        if (typeof openAjaxModal === 'function') {
            openAjaxModal(`/licencias/recepcion/${receptionId}/detalle-modal/`);
        }
    };

    window.openReceptionDeliveryReport = function (batch, receptionId, deliveredTo) {
        const params = new URLSearchParams();
        if (batch) {
            params.set('batch', batch);
        } else {
            params.set('ids', receptionId);
        }
        if (deliveredTo) params.set('delivered_to', deliveredTo);
        window.open(`/licencias/recepcion/reporte/?${params.toString()}`, '_blank');
    };

    window.openBulkDeliverReceptionModal = function () {
        const ids = getSelectedReceptionIds();
        if (!ids.length) return;
        openAjaxModal('/licencias/recepcion/remitir-modal/', root => {
            const idsInput = root.querySelector('#bulk-reception-ids');
            const count = root.querySelector('#bulk-reception-count');
            if (idsInput) idsInput.value = ids.join(',');
            if (count) count.textContent = ids.length;
            if (window.$ && $.fn.select2) {
                $('#bulkDeliverReceptionModal select.select2-modal').select2({
                    width: '100%',
                    dropdownParent: $('#bulkDeliverReceptionModal')
                });
            }
        });
    };

    window.submitBulkDeliverReceptionForm = function (event) {
        event.preventDefault();
        const form = event.target;
        fetch(form.action, {
            method: 'POST',
            body: new FormData(form),
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': getCsrfToken(form)
            }
        })
            .then(async res => {
                const data = await res.json();
                if (!res.ok) throw new Error(data.message || 'No se pudieron remitir las recepciones.');
                return data;
            })
            .then(data => {
                if (typeof closeModal === 'function') closeModal();
                if (data.pdf_url) window.open(data.pdf_url, '_blank');
                applyReceptionFilters(1);
                Swal.fire({
                    icon: 'success',
                    title: 'Recepciones remitidas',
                    text: data.message,
                    timer: 1800,
                    showConfirmButton: false
                });
            })
            .catch(error => {
                Swal.fire({icon: 'error', title: 'Error', text: error.message});
            });
    };

    window.submitDeliverReceptionForm = function (event) {
        event.preventDefault();
        const form = event.target;

        fetch(form.action, {
            method: 'POST',
            body: new FormData(form),
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': getCsrfToken(form)
            }
        })
            .then(async res => {
                const data = await res.json();
                if (!res.ok) throw new Error(data.message || 'No se pudo entregar el expediente.');
                return data;
            })
            .then(data => {
                if (data.success) {
                    if (typeof closeModal === 'function') closeModal();
                    if (data.pdf_url) window.open(data.pdf_url, '_blank');
                    applyReceptionFilters(receptionState.page);
                    Swal.fire({
                        icon: 'success',
                        title: 'Expediente entregado',
                        text: data.message,
                        timer: 1800,
                        showConfirmButton: false
                    });
                }
            })
            .catch(err => {
                Swal.fire({icon: 'error', title: 'Error', text: err.message});
            });
    };

    function getFilterParams(targetPage = null) {
        const form = document.getElementById('reception-filter-form');
        const params = new URLSearchParams();

        if (form) {
            const formData = new FormData(form);
            for (const [key, val] of formData.entries()) {
                const cleanVal = val ? val.trim() : '';
                if (cleanVal !== '') {
                    params.set(key, cleanVal);
                }
            }
        }

        if (receptionState.status && receptionState.status !== 'all') {
            params.set('status', receptionState.status);
        }
        if (receptionState.sort) {
            params.set('sort', receptionState.sort);
        }

        params.set('page', targetPage !== null ? targetPage : receptionState.page);
        return params;
    }

    function applyReceptionFilters(page = 1) {
        receptionState.page = page;
        const wrapper = document.getElementById('table-content-wrapper');
        if (!wrapper) return;

        const table = wrapper.querySelector('.managed-table');
        const listUrl = table ? table.getAttribute('data-list-url') : window.location.pathname;
        const params = getFilterParams(page);

        wrapper.style.opacity = '0.5';
        wrapper.style.pointerEvents = 'none';

        fetch(`${listUrl}?${params.toString()}`, {
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        })
            .then(res => res.json())
            .then(data => {
                if (data.html) {
                    wrapper.innerHTML = data.html;
                    updateReceptionSelectionState();
                }
                if (data.stats) {
                    const map = {
                        'stat-total': data.stats.total,
                        'stat-registered': data.stats.registered,
                        'stat-approved': data.stats.approved,
                        'stat-delivered': data.stats.delivered
                    };
                    Object.entries(map).forEach(([id, value]) => {
                        const el = document.getElementById(id);
                        if (el) el.innerText = value || 0;
                    });
                }
            })
            .catch(err => console.error('Error updating reception table:', err))
            .finally(() => {
                wrapper.style.opacity = '1';
                wrapper.style.pointerEvents = 'auto';
            });
    }

    window.applyReceptionFilters = applyReceptionFilters;

    function filterByStatus(status) {
        receptionState.status = status;
        document.querySelectorAll('#reception-stats-row .stat-card').forEach(c => c.classList.add('opacity-low'));
        const activeId = status === 'all' ? 'card-filter-all' : `card-filter-${status.toLowerCase()}`;
        const activeCard = document.getElementById(activeId);
        if (activeCard) activeCard.classList.remove('opacity-low');

        applyReceptionFilters(1);
    }

    window.filterByReceptionStatus = filterByStatus;

    function toggleAdvancedSearch() {
        const container = document.getElementById('advanced-search-container-reception');
        const icon = document.getElementById('icon-toggle-advanced-reception');
        if (!container) return;

        const isHidden = container.classList.contains('hidden');
        container.classList.toggle('hidden', !isHidden);
        if (icon) {
            icon.classList.toggle('fa-chevron-down', !isHidden);
            icon.classList.toggle('fa-chevron-up', isHidden);
        }
        if (isHidden && window.$ && $.fn.select2) {
            $('#advanced-search-container-reception select.select2').select2({width: '100%'});
        }
    }

    function clearFilters() {
        const form = document.getElementById('reception-filter-form');
        if (form) {
            form.reset();
            if (window.$ && $.fn.select2) {
                $(form).find('select.select2').val('').trigger('change');
            }
        }
        filterByStatus('all');
    }

    window.changeReceptionStatus = async function (receptionId, targetStatus) {
        const actionMsg = targetStatus === 'DELIVERED'
            ? '¿Desea marcar como ENTREGADO y remitir esta recepción para la elaboración de la Acción de Personal?'
            : '¿Está seguro de DAR DE BAJA esta recepción?';

        const result = await Swal.fire({
            icon: targetStatus === 'CANCELLED' ? 'warning' : 'question',
            title: targetStatus === 'CANCELLED' ? 'Dar de baja recepción' : 'Confirmar cambio',
            text: actionMsg,
            showCancelButton: true,
            confirmButtonText: 'Sí, continuar',
            cancelButtonText: 'Cancelar',
            reverseButtons: true
        });
        if (!result.isConfirmed) return;

        const formData = new FormData();
        formData.append('status', targetStatus);

        fetch(`/licencias/recepcion/${receptionId}/estado/`, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': getCsrfToken()
            }
        })
            .then(async res => {
                const data = await res.json();
                if (!res.ok) throw new Error(data.message || 'No se pudo cambiar el estado.');
                return data;
            })
            .then(data => {
                if (data.success) {
                    applyReceptionFilters(receptionState.page);
                    Swal.fire({
                        icon: 'success',
                        title: 'Estado actualizado',
                        text: data.message,
                        timer: 1800,
                        showConfirmButton: false
                    });
                }
            })
            .catch(err => {
                Swal.fire({icon: 'error', title: 'Error', text: err.message});
            });
    };

    document.addEventListener('DOMContentLoaded', () => {
        if (document.getElementById('toggleInactiveTypes')) {
            window.initLicenseTypeFilters();
        }
        window.initMedicalLicenseFilters();
        window.initMedicalLicenseStats();

        if (window.$ && $.fn.select2) {
            $('#reception-filter-form select.select2').select2({width: '100%'});
        }

        const searchInput = document.getElementById('table-search-reception');
        if (searchInput) {
            let debounceTimer = null;
            searchInput.addEventListener('input', () => {
                clearTimeout(debounceTimer);
                debounceTimer = setTimeout(() => applyReceptionFilters(1), 400);
            });
        }

        const filterForm = document.getElementById('reception-filter-form');
        if (filterForm) {
            filterForm.addEventListener('submit', e => {
                e.preventDefault();
                applyReceptionFilters(1);
            });
        }

        const btnToggle = document.getElementById('btn-toggle-advanced-reception');
        if (btnToggle) btnToggle.addEventListener('click', toggleAdvancedSearch);

        const btnClear = document.getElementById('btn-reception-clear');
        if (btnClear) btnClear.addEventListener('click', clearFilters);

        const btnDeliver = document.getElementById('btn-reception-deliver');
        if (btnDeliver) btnDeliver.addEventListener('click', openBulkDeliverReceptionModal);

        document.addEventListener('change', event => {
            if (event.target.matches('.reception-select')) updateReceptionSelectionState();
            if (event.target.matches('.reception-select-all')) {
                document.querySelectorAll('.reception-select').forEach(input => {
                    input.checked = event.target.checked;
                });
                updateReceptionSelectionState();
            }
        });
        updateReceptionSelectionState();

        const statusFilter = document.getElementById('filter_status');
        if (statusFilter) {
            statusFilter.addEventListener('change', () => {
                receptionState.status = 'all';
                document.querySelectorAll('#reception-stats-row .stat-card').forEach(c => c.classList.add('opacity-low'));
                applyReceptionFilters(1);
            });
        }

        const statsRow = document.getElementById('reception-stats-row');
        if (statsRow) {
            statsRow.addEventListener('click', e => {
                const card = e.target.closest('.stat-card');
                if (card && card.dataset.receptionStatus) {
                    e.preventDefault();
                    filterByStatus(card.dataset.receptionStatus);
                }
            });
        }
    });

    document.addEventListener('click', e => {
        const pageBtn = e.target.closest('#js-pagination .page-btn');
        if (pageBtn && !pageBtn.disabled && !pageBtn.classList.contains('disabled')) {
            const targetPage = parseInt(pageBtn.dataset.page, 10);
            if (!Number.isNaN(targetPage)) {
                e.preventDefault();
                applyReceptionFilters(targetPage);
            }
        }
    }, true);

    document.addEventListener('change', e => {
        const pageInput = e.target.closest('#js-pagination .page-input');
        if (!pageInput) return;
        const page = Math.max(1, parseInt(pageInput.value, 10) || 1);
        const maxPage = parseInt(pageInput.max, 10) || page;
        applyReceptionFilters(Math.min(page, maxPage));
    });

    document.addEventListener('keydown', e => {
        if (e.key !== 'Enter') return;
        const pageInput = e.target.closest('#js-pagination .page-input');
        if (!pageInput) return;
        e.preventDefault();
        const page = Math.max(1, parseInt(pageInput.value, 10) || 1);
        const maxPage = parseInt(pageInput.max, 10) || page;
        applyReceptionFilters(Math.min(page, maxPage));
    });
    // ==========================================
    // 4. VALIDACIÓN Y ENVÍO DE NUEVA RECEPCIÓN
    // ==========================================
    const clearFieldError = field => {
        if (!field) return;
        field.classList.remove('is-invalid');
        const select2Container = field.nextElementSibling;
        if (select2Container && select2Container.classList.contains('select2')) {
            const selection = select2Container.querySelector('.select2-selection');
            if (selection) selection.classList.remove('is-invalid');
        }
    };

    const markFieldError = field => {
        if (!field) return;
        field.classList.add('is-invalid');
        const select2Container = field.nextElementSibling;
        if (select2Container && select2Container.classList.contains('select2')) {
            const selection = select2Container.querySelector('.select2-selection');
            if (selection) selection.classList.add('is-invalid');
        }
    };

    document.addEventListener('input', event => {
        if (event.target.closest('#receptionForm')) clearFieldError(event.target);
    });

    if (window.$) {
        $(document).on('change', '#receptionForm select, #receptionForm input', function () {
            clearFieldError(this);
        });
    }

    document.addEventListener('submit', event => {
        const form = event.target;
        if (!form.matches('#receptionForm')) return;

        event.preventDefault();
        event.stopImmediatePropagation();

        if (form.dataset.submitting === 'true') return;

        updateReceptionEndDate();

        const alertBox = form.querySelector('#receptionFormAlert');
        if (alertBox) {
            alertBox.classList.add('hidden');
            alertBox.innerHTML = '';
        }

        const requiredFields = [
            {name: 'employee', label: 'Servidor Municipal'},
            {name: 'license_type', label: 'Tipo de Licencia'},
            {name: 'license_start_date', label: 'Inicio de Licencia'},
            {name: 'license_days', label: 'Número de Días'},
            {name: 'supporting_document', label: 'Documento Habilitante'}
        ];

        const missingLabels = [];
        let firstInvalidField = null;

        requiredFields.forEach(({name, label}) => {
            const field = form.querySelector(`[name="${name}"]`);
            if (!field) return;
            clearFieldError(field);

            const value = String(field.value ?? '').trim();
            const isInvalid = value === '' || (name === 'license_days' && Number(value) < 0);
            if (isInvalid) {
                markFieldError(field);
                missingLabels.push(label);
                if (!firstInvalidField) firstInvalidField = field;
            }
        });

        if (missingLabels.length > 0) {
            if (firstInvalidField) firstInvalidField.focus();
            if (alertBox) {
                alertBox.innerHTML = `<strong>Complete los campos obligatorios:</strong> ${missingLabels.join(', ')}.`;
                alertBox.classList.remove('hidden');
            }
            Swal.fire({
                icon: 'warning',
                title: 'Campos obligatorios incompletos',
                html: `Por favor complete:<br><strong>${missingLabels.join(', ')}</strong>`,
                confirmButtonText: 'Entendido'
            });
            return;
        }

        form.dataset.submitting = 'true';
        const submitBtns = form.querySelectorAll('button[type="submit"], input[type="submit"]');
        submitBtns.forEach(btn => {
            btn.disabled = true;
            btn.dataset.originalHtml = btn.innerHTML;
            btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Guardando...';
        });

        fetch(form.action, {
            method: 'POST',
            body: new FormData(form),
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': getCsrfToken(form)
            }
        })
            .then(async response => {
                const data = await response.json().catch(() => ({}));
                if (!response.ok || !data.success) {
                    if (data.errors) {
                        Object.keys(data.errors).forEach(fieldName => {
                            markFieldError(form.querySelector(`[name="${fieldName}"]`));
                        });
                    }
                    throw new Error(data.message || 'Revise los campos obligatorios.');
                }
                return data;
            })
            .then(data => {
                if (typeof closeModal === 'function') closeModal();
                applyReceptionFilters(1);
                Swal.fire({
                    icon: 'success',
                    title: 'Recepción registrada',
                    text: data.message || 'Registro guardado correctamente.',
                    timer: 1800,
                    showConfirmButton: false
                });
            })
            .catch(error => {
                if (alertBox) {
                    alertBox.textContent = error.message;
                    alertBox.classList.remove('hidden');
                }
                Swal.fire({
                    icon: 'warning',
                    title: 'Validación',
                    text: error.message
                });
            })
            .finally(() => {
                if (document.body.contains(form)) {
                    form.dataset.submitting = 'false';
                    submitBtns.forEach(btn => {
                        btn.disabled = false;
                        if (btn.dataset.originalHtml) btn.innerHTML = btn.dataset.originalHtml;
                    });
                }
            });
    }, true);
})();