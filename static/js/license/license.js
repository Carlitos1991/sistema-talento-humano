/* static/js/license/license.js
   Gestión de Recepción de Licencias Médicas y Catálogos de Tipos - SIGETH
*/

(function () {
    'use strict';

    window.returnReception = async function (url) {
        const result = typeof Swal !== 'undefined'
            ? await Swal.fire({
                icon: 'warning',
                title: 'Devolver a recepción',
                text: 'La licencia volverá al listado de recepción.',
                showCancelButton: true,
                confirmButtonText: 'Devolver',
                cancelButtonText: 'Cancelar'
            })
            : {isConfirmed: window.confirm('¿Devolver la licencia a recepción?')};
        if (!result.isConfirmed) return;
        const token = document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
        fetch(url, {
            method: 'POST',
            headers: {'X-CSRFToken': token, 'X-Requested-With': 'XMLHttpRequest'}
        })
            .then(response => response.json().then(data => ({ok: response.ok, data})))
            .then(({ok, data}) => {
                if (!ok || !data.success) throw new Error(data.message || 'No se pudo devolver la licencia.');
                window.location.reload();
            })
            .catch(error => {
                if (typeof Swal !== 'undefined') Swal.fire({icon: 'error', title: 'Error', text: error.message});
            });
    };

    // ==========================================
    // 1. MÓDULO DE TIPOS DE LICENCIAS (CATÁLOGO)
    // ==========================================
    window.initLicenseTypeFilters = function () {
        const toggleInactive = document.getElementById('toggleInactiveTypes');
        const searchInput = document.getElementById('table-search');

        const refreshTable = () => {
            const showInactive = toggleInactive ? toggleInactive.checked : false;
            const query = searchInput ? searchInput.value.trim() : '';

            const params = new URLSearchParams();
            if (showInactive) {
                params.set('show_inactive', 'true');
            }
            if (query) {
                params.set('q', query);
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
                .catch(err => console.error('Error al filtrar tipos de licencias:', err));
        };

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

    window.initLicenseTypeModalScripts = function (isEdit = false) {
        if (window.$ && $.fn.select2) {
            $('#licenseTypeForm select.select2-modal').select2({
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
                    if (submodalRoot) {
                        submodalRoot.innerHTML = data.html;
                    }
                }
            })
            .catch(err => console.error('Error al abrir modal de requisito:', err));
    };

    window.closeSubmodal = function () {
        const submodalRoot = document.getElementById('submodal-root');
        if (submodalRoot) submodalRoot.innerHTML = '';
    };

    window.submitRequirementFormAjax = function (event) {
        event.preventDefault();
        const form = event.target;
        const formData = new FormData(form);

        fetch(form.action, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': form.querySelector('[name=csrfmiddlewaretoken]')?.value || ''
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
                    if (typeof showToast === 'function') {
                        showToast(data.message || 'Requisito creado correctamente.', 'success');
                    }
                } else {
                    alert('Por favor verifique los datos ingresados.');
                }
            })
            .catch(err => console.error('Error al guardar requisito:', err));
    };

    // ==========================================
    // 2. MÓDULO DE RECEPCIÓN DOCUMENTAL
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
            container.innerHTML = '<span class="text-muted small">Seleccione un tipo de licencia para desplegar los anexos requeridos.</span>';
            return;
        }

        container.innerHTML = '<div class="text-center py-2"><i class="fas fa-spinner fa-spin text-primary me-2"></i> Cargando anexos requeridos...</div>';

        fetch(`/licencias/recepcion/obtener-requisitos/${typeId}/`, {
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        })
            .then(res => res.json())
            .then(data => {
                if (data.success && data.requirements && data.requirements.length > 0) {
                    let html = '<div class="reception-checklist-box">';
                    data.requirements.forEach(req => {
                        html += `
                            <div class="reception-requirement-item">
                                <label class="form-label mb-0 cursor-pointer d-flex align-items-center" for="req_${req.id}">
                                    <i class="fas fa-file-lines text-primary me-2"></i>
                                    <span class="font-weight-medium">${req.name}</span>
                                </label>
                                <div class="form-check form-switch requirement-switch mb-0">
                                    <input type="checkbox" name="requirements_checked" value="${req.id}" id="req_${req.id}" class="form-check-input cursor-pointer">
                                </div>
                            </div>
                        `;
                    });
                    html += '</div>';
                    container.innerHTML = html;
                } else {
                    container.innerHTML = '<div class="text-muted small p-2"><i class="fas fa-info-circle me-1"></i> Este tipo de licencia no requiere anexos preconfigurados.</div>';
                }
            })
            .catch(err => {
                console.error('Error al cargar requisitos:', err);
                container.innerHTML = '<span class="text-danger small"><i class="fas fa-exclamation-triangle me-1"></i> No se pudieron cargar los requisitos.</span>';
            });
    };
    // Escucha delegada global por respaldos de Select2 u otros selects
    $(document).on('change', 'select[name="license_type"]', function () {
        window.loadTypeRequirements($(this).val());
    });
    /**
     * Hook global invocado tras cargar cualquier modal AJAX
     */
    window.onModalLoaded = function () {
        const modalRoot = document.getElementById('modal-root');
        if (!modalRoot) return;

        // Select2 en Nueva Recepción
        const $typeSelect = $(modalRoot).find('select[name="license_type"]');
        const $empSelect = $(modalRoot).find('select[name="employee"]');

        if ($empSelect.length && window.$ && $.fn.select2) {
            $empSelect.select2({width: '100%', dropdownParent: $(modalRoot)});
        }

        if ($typeSelect.length && window.$ && $.fn.select2) {
            $typeSelect.select2({width: '100%', dropdownParent: $(modalRoot)});
            $typeSelect.off('change.loadReq').on('change.loadReq', function () {
                window.loadTypeRequirements($(this).val());
            });

            if ($typeSelect.val()) {
                window.loadTypeRequirements($typeSelect.val());
            }
        }
    };
    // ==========================================
    // 2. CONTROLADORES DE MODALES Y ACCIONES
    // ==========================================

    window.openValidateReceptionModal = function (receptionId) {
        if (typeof openAjaxModal === 'function') {
            openAjaxModal(`/licencias/recepcion/${receptionId}/validar-modal/`);
        }
    };
    window.submitValidateReceptionForm = function (event) {
        event.preventDefault();
        const form = event.target;
        const formData = new FormData(form);

        fetch(form.action, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': form.querySelector('[name=csrfmiddlewaretoken]')?.value || ''
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
                    if (typeof applyReceptionFilters === 'function') applyReceptionFilters();
                    if (typeof Swal !== 'undefined') {
                        Swal.fire({icon: 'success', title: 'Requisitos actualizados', text: data.message, timer: 1800, showConfirmButton: false});
                    }
                }
            })
            .catch(err => {
                console.error('Error al validar recepcion:', err);
                if (typeof Swal !== 'undefined') Swal.fire({icon: 'error', title: 'Error', text: err.message});
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

    window.openReceptionDetailModal = function (receptionId) {
        openAjaxModal(`/licencias/recepcion/${receptionId}/detalle-modal/`);
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
                'X-CSRFToken': form.querySelector('[name=csrfmiddlewaretoken]')?.value || ''
            }
        })
            .then(async res => {
                const data = await res.json();
                if (!res.ok) throw new Error(data.message || 'No se pudieron remitir las recepciones.');
                return data;
            })
            .then(data => {
                closeModal();
                if (data.pdf_url) window.open(data.pdf_url, '_blank');
                applyReceptionFilters(1);
                if (typeof Swal !== 'undefined') {
                    Swal.fire({icon: 'success', title: 'Recepciones remitidas', text: data.message, timer: 1800, showConfirmButton: false});
                }
            })
            .catch(error => {
                if (typeof Swal !== 'undefined') Swal.fire({icon: 'error', title: 'Error', text: error.message});
            });
    };
    window.submitDeliverReceptionForm = function (event) {
        event.preventDefault();
        const form = event.target;
        const formData = new FormData(form);

        fetch(form.action, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': form.querySelector('[name=csrfmiddlewaretoken]')?.value || ''
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
                    if (data.pdf_url) {
                        window.open(data.pdf_url, '_blank');
                    }
                    if (typeof applyReceptionFilters === 'function') applyReceptionFilters();
                    if (typeof Swal !== 'undefined') {
                        Swal.fire({icon: 'success', title: 'Expediente entregado', text: data.message, timer: 1800, showConfirmButton: false});
                    }
                }
            })
            .catch(err => {
                console.error('Error al entregar expedientes:', err);
                if (typeof Swal !== 'undefined') Swal.fire({icon: 'error', title: 'Error', text: err.message});
            });
    };

    function getFilterParams(targetPage = null) {
        const form = document.getElementById('reception-filter-form');
        const params = new URLSearchParams();

        if (form) {
            const formData = new FormData(form);
            for (let [key, val] of formData.entries()) {
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

        const pageToApply = targetPage !== null ? targetPage : receptionState.page;
        params.set('page', pageToApply);

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
                    if (document.getElementById('stat-total')) document.getElementById('stat-total').innerText = data.stats.total || 0;
                    if (document.getElementById('stat-registered')) document.getElementById('stat-registered').innerText = data.stats.registered || 0;
                    if (document.getElementById('stat-approved')) document.getElementById('stat-approved').innerText = data.stats.approved || 0;
                    if (document.getElementById('stat-delivered')) document.getElementById('stat-delivered').innerText = data.stats.delivered || 0;
                }
            })
            .catch(err => console.error("Error al actualizar la tabla de recepciones:", err))
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
        if (isHidden) {
            container.classList.remove('hidden');
            if (icon) {
                icon.classList.remove('fa-chevron-down');
                icon.classList.add('fa-chevron-up');
            }
            if (window.$ && $.fn.select2) {
                $('#advanced-search-container-reception select.select2').each(function () {
                    $(this).select2({width: '100%'});
                });
            }
        } else {
            container.classList.add('hidden');
            if (icon) {
                icon.classList.remove('fa-chevron-up');
                icon.classList.add('fa-chevron-down');
            }
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

        if (typeof Swal !== 'undefined') {
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
        } else if (!window.confirm(actionMsg)) {
            return;
        }

        const formData = new FormData();
        formData.append('status', targetStatus);

        fetch(`/licencias/recepcion/${receptionId}/estado/`, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]')?.value || ''
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
                    if (typeof Swal !== 'undefined') {
                        Swal.fire({icon: 'success', title: 'Estado actualizado', text: data.message, timer: 1800, showConfirmButton: false});
                    }
                }
            })
            .catch(err => {
                console.error('Error al cambiar estado:', err);
                if (typeof Swal !== 'undefined') Swal.fire({icon: 'error', title: 'Error', text: err.message});
            });
    };

    window.exportReceptionTable = function (format) {
        const tableEl = document.querySelector('.exportable-table');
        if (!tableEl) return;
        if (format === 'excel' && typeof exportTableToExcel === 'function') {
            exportTableToExcel(tableEl);
        } else if (format === 'pdf' && typeof exportTableToPDF === 'function') {
            exportTableToPDF(tableEl);
        }
    };

    document.addEventListener('DOMContentLoaded', () => {
        // Inicializar Tipos de Licencias si estamos en esa vista
        if (document.getElementById('toggleInactiveTypes') || document.getElementById('table-search')) {
            window.initLicenseTypeFilters();
        }

        // Inicializar Recepciones si estamos en esa vista
        if (window.$ && $.fn.select2) {
            $('#reception-filter-form select.select2').select2({width: '100%'});
        }

        const searchInput = document.getElementById('table-search-reception');
        if (searchInput) {
            let debounceTimer = null;
            searchInput.addEventListener('input', () => {
                clearTimeout(debounceTimer);
                debounceTimer = setTimeout(() => {
                    applyReceptionFilters(1);
                }, 400);
            });
        }

        const filterForm = document.getElementById('reception-filter-form');
        if (filterForm) {
            filterForm.addEventListener('submit', (e) => {
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
            statsRow.addEventListener('click', (e) => {
                const card = e.target.closest('.stat-card');
                if (card && card.dataset.receptionStatus) {
                    e.preventDefault();
                    filterByStatus(card.dataset.receptionStatus);
                }
            });
        }
    });

    // Paginación por delegación de eventos
    document.addEventListener('click', (e) => {
        const pageBtn = e.target.closest('#js-pagination .page-btn');
        if (pageBtn) {
            if (pageBtn.disabled || pageBtn.classList.contains('disabled')) return;
            const targetPage = parseInt(pageBtn.dataset.page);
            if (!isNaN(targetPage)) {
                e.preventDefault();
                applyReceptionFilters(targetPage);
            }
        }
    }, true);
})();