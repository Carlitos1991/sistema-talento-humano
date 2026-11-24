/**
 * Arquitectura: Vanilla JS + Django Template
 * Estándar: Integración completa con core.js / main.js (Cero código inline)
 */
(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', () => {
        initSelect2Filters();
        initSearchDebounce();
        initIdentificationExcelUpload();
    });

    // =========================================================================
    // 1. DELEGACIÓN GLOBAL DE EVENTOS (FORMULARIOS, CLICKS, INPUTS, CHANGES)
    // =========================================================================

    document.addEventListener('submit', (event) => {
        if (event.target.matches('[data-permit-filter-form]')) {
            event.preventDefault();
            applyPermitFilters(1);
        } else if (event.target.matches('[data-prevent-submit]')) {
            event.preventDefault();
        }
    });

    document.addEventListener('click', (event) => {
        const actionEl = event.target.closest('[data-action]');
        if (actionEl) {
            const action = actionEl.dataset.action;

            switch (action) {
                case 'clear-permit-filters':
                    clearPermitFilters();
                    break;
                case 'open-permit-summary': {
                    const baseUrl = actionEl.dataset.summaryUrl;
                    if (!baseUrl) break;
                    const query = new URLSearchParams(collectFilters()).toString();
                    const finalUrl = query ? `${baseUrl}?${query}` : baseUrl;
                    if (typeof window.openAjaxModal === 'function') {
                        window.openAjaxModal(finalUrl);
                    }
                    break;
                }
                case
                'clear-identifications'
                :
                    clearLoadedIdentifications();
                    break;
                case
                'print-permit-report'
                : {
                    const url = actionEl.dataset.reportUrl;
                    if (url) window.open(url, '_blank', 'width=850,height=650,resizable=yes,scrollbars=yes');
                    break;
                }
                case
                'reset-parent-filter'
                :
                    if (typeof window.refreshCurrentTable === 'function') {
                        window.refreshCurrentTable({parent: ''});
                    }
                    break;
                case
                'toggle-permit-type'
                :
                    toggleStatusAjax(
                        actionEl.dataset.toggleUrl,
                        actionEl.dataset.itemName,
                        actionEl.dataset.isActive === 'true'
                    );
                    break;
                case
                'window-print'
                :
                    window.print();
                    break;
                case
                'approve-selected-binnacles'
                :
                    approveSelectedBinnacles();
                    break;
                case
                'reject-selected-binnacles'
                :
                    rejectSelectedBinnacles();
                    break;
                case
                'delete-selected-binnacles'
                :
                    deleteSelectedBinnacles();
                    break;
                case
                'filter-binnacles'
                :
                    filterBinnacles();
                    break;
                case
                'clear-binnacle-dates'
                :
                    clearBinnacleDates();
                    break;
                case
                'edit-binnacle'
                :
                    openEditBitacoraModal(
                        actionEl.dataset.binnacleId,
                        actionEl.dataset.startTime || '',
                        actionEl.dataset.endTime || ''
                    );
                    break;
                case
                'delete-binnacle-single'
                :
                    deleteBinnacleSingle(actionEl.dataset.binnacleId);
                    break;
                case
                'clear-history-dates'
                :
                    clearHistoryDates();
                    break;
                case
                'review-binnacle'
                :
                    reviewBinnacleModal(actionEl.dataset.binnacleId);
                    break;
            }
            return;
        }

        // Paginación específica del listado administrativo de permisos
        if (document.getElementById('filtersForm')) {
            const pageBtn = event.target.closest('.pagination-container .page-btn[data-page]');
            if (pageBtn && !pageBtn.disabled) {
                applyPermitFilters(Number.parseInt(pageBtn.dataset.page, 10) || 1);
            }
        }
    });

    document.addEventListener('input', (event) => {
        const target = event.target;
        if (target.matches('[data-action="filter-subtypes"]')) {
            filterSubtypesTable(target.value);
        } else if (target.id === 'binnacleSearchInput') {
            filterBinnacles();
        } else if (target.matches('#generatePermitForm #id_days, #generatePermitForm #id_hours, #generatePermitForm #id_minutes')) {
            calculatePermitEndDateTime();
        }
    });

    document.addEventListener('change', (event) => {
        const target = event.target;

        // Paginación manual en listado administrativo
        if (document.getElementById('filtersForm') && target.matches('.pagination-container .page-input')) {
            const page = Math.max(1, Math.min(Number.parseInt(target.value, 10) || 1, Number.parseInt(target.max, 10) || 1));
            applyPermitFilters(page);
            return;
        }

        // Vista previa de nombre de archivo adjunto
        if (target.matches('[data-filename-target]')) {
            const displayEl = document.getElementById(target.dataset.filenameTarget);
            if (displayEl) {
                const fn = target.files[0] ? target.files[0].name : '';
                displayEl.textContent = fn ? (fn.length > 14 ? `${fn.slice(0, 11)}...` : fn) : '';
            }
            return;
        }

        // Bitácoras pendientes: selección y filtros
        if (target.id === 'check-all-binnacles') {
            toggleAllBinnacles(target.checked);
        } else if (target.classList.contains('binnacle-check-item')) {
            updateBinnacleSelectionState();
        } else if (target.id === 'binnacle-filter-from' || target.id === 'binnacle-filter-to') {
            filterBinnacles();
        } else if (target.id === 'history-filter-from' || target.id === 'history-filter-to') {
            filterBinnacleHistoryRows();
        }

        // Modal Generar Permiso: cambio de tipo principal o fechas/horas
        if (target.id === 'id_permit_type_parent') {
            handlePermitParentTypeChange(target);
        } else if (target.id === 'id_permit_type') {
            handlePermitSubtypeChange(target);
        } else if (target.matches('#generatePermitForm #id_start_date, #generatePermitForm #id_start_time, #generatePermitForm #id_days, #generatePermitForm #id_hours, #generatePermitForm #id_minutes')) {
            calculatePermitEndDateTime();
        }
    });

    document.addEventListener('keydown', (event) => {
        if (document.getElementById('filtersForm')) {
            const input = event.target.closest('.pagination-container .page-input');
            if (input && event.key === 'Enter') {
                event.preventDefault();
                input.dispatchEvent(new Event('change', {bubbles: true}));
            }
        }
    });

// =========================================================================
// 2. SELECT2 Y BÚSQUEDAS DINÁMICAS
// =========================================================================

    function initSelect2Filters() {
        if (!window.jQuery || !window.jQuery.fn.select2) return;

        document.querySelectorAll('#filtersForm select.select2').forEach((sel) => {
            const $sel = $(sel);
            const placeholder = sel.dataset.placeholder || 'Seleccionar...';
            $sel.select2({
                placeholder: placeholder,
                allowClear: true,
                width: '100%'
            });
        });
    }

    function initSearchDebounce() {
        const searchInput = document.getElementById('table-search-permits') || document.getElementById('table-search');
        if (!searchInput) return;

        let debounceTimer = null;
        const triggerSearch = () => {
            const query = searchInput.value.trim();
            if (document.getElementById('filtersForm')) {
                applyPermitFilters(1);
            } else if (typeof window.refreshCurrentTable === 'function') {
                window.refreshCurrentTable({q: query, page: 1});
            }
        };

        searchInput.addEventListener('input', () => {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(triggerSearch, 300);
        });

        searchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                clearTimeout(debounceTimer);
                triggerSearch();
            }
        });
    }

// =========================================================================
// 3. FILTRADO PARA PERMISOS ADMIN
// =========================================================================

    function collectFilters() {
        const form = document.getElementById('filtersForm');
        const params = {};

        if (form) {
            const formData = new FormData(form);
            for (const [key, val] of formData.entries()) {
                if (val && val.trim() !== '') {
                    params[key] = val.trim();
                }
            }
        }
        return params;
    }

    function applyPermitFilters(page = 1) {
        const params = collectFilters();
        params.page = page;
        fetchPermitTable(params);
    }

    window.applyPermitFilters = applyPermitFilters;

    function fetchPermitTable(params) {
        const query = new URLSearchParams(params);
        const wrapper = document.getElementById('table-content-wrapper');
        if (wrapper) {
            wrapper.style.opacity = '0.5';
            wrapper.style.pointerEvents = 'none';
        }

        fetch(`${window.location.pathname}?${query.toString()}`, {
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        })
            .then(async (response) => {
                if (!response.ok) throw new Error('No se pudo cargar la tabla de permisos.');
                return response.json();
            })
            .then((data) => {
                if (wrapper && data.html) {
                    wrapper.innerHTML = data.html;
                    const table = wrapper.querySelector('.managed-table');
                    if (table && window.TableManager) new window.TableManager(table);
                }
                if (data.pagination) updatePermitPagination(data.pagination);
            })
            .catch((error) => {
                console.error('Error al filtrar permisos:', error);
                if (window.showToast) window.showToast(error.message, 'error');
            })
            .finally(() => {
                if (wrapper) {
                    wrapper.style.opacity = '1';
                    wrapper.style.pointerEvents = 'auto';
                }
            });
    }

    function updatePermitPagination(pagination) {
        const container = document.querySelector('.pagination-container');
        if (!container) return;

        const totalPages = Math.max(1, pagination.total_pages || 1);
        const page = pagination.page || 1;
        const previousPage = Math.max(1, page - 1);
        const nextPage = Math.min(totalPages, page + 1);
        const hasPrevious = Boolean(pagination.has_previous);
        const hasNext = Boolean(pagination.has_next);

        container.innerHTML = `
            <span class="pagination-info">Mostrando ${pagination.start_index || 0}-${pagination.end_index || 0} de ${pagination.total_count || 0}</span>
            <div class="pagination-controls ${totalPages <= 1 ? 'invisible' : ''}">
                <button type="button" class="page-btn" data-page="1" ${hasPrevious ? '' : 'disabled'} title="Primera">
                    <i class="fas fa-angle-double-left"></i>
                </button>
                <button type="button" class="page-btn" data-page="${previousPage}" ${hasPrevious ? '' : 'disabled'} title="Anterior">
                    <i class="fas fa-angle-left"></i>
                </button>
                <div class="page-input-wrapper">
                    <input type="number" class="page-input" value="${page}" min="1" max="${totalPages}">
                    <span class="total-pages-badge">de ${totalPages}</span>
                </div>
                <button type="button" class="page-btn" data-page="${nextPage}" ${hasNext ? '' : 'disabled'} title="Siguiente">
                    <i class="fas fa-angle-right"></i>
                </button>
                <button type="button" class="page-btn" data-page="${totalPages}" ${hasNext ? '' : 'disabled'} title="Última">
                    <i class="fas fa-angle-double-right"></i>
                </button>
            </div>`;
    }

    function clearPermitFilters() {
        const form = document.getElementById('filtersForm');
        if (form) {
            form.reset();
            if (window.$ && $.fn.select2) {
                $(form).find('select.select2').val('').trigger('change');
            }
        }
        clearLoadedIdentifications();
        applyPermitFilters(1);
    }

// =========================================================================
// 4. GENERACIÓN DE PERMISO (SUBTIPOS, REGLAS Y CÁLCULO DE FIN)
// =========================================================================

    function handlePermitParentTypeChange(selectEl) {
        const selectedOption = selectEl.options[selectEl.selectedIndex];
        const parentId = selectEl.value;
        const subtypeContainer = document.getElementById('subtype-container');
        const subtypeSelect = document.getElementById('id_permit_type');

        if (!parentId) {
            if (subtypeContainer) subtypeContainer.classList.add('hidden');
            if (subtypeSelect) {
                subtypeSelect.innerHTML = '<option value="">-- Seleccione subtipo --</option>';
                subtypeSelect.required = false;
            }
            togglePermitRequirementSections(false, false);
            return;
        }

        const urlTemplate = selectEl.dataset.subtypesUrlTemplate || '/permitrequest/types/0/subtypes-json/';
        const url = urlTemplate.replace('/0/', `/${parentId}/`);

        fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
            .then((r) => r.json())
            .then((data) => {
                const subtypes = data.subtypes || data.results || [];
                if (subtypes.length > 0 && subtypeContainer && subtypeSelect) {
                    subtypeSelect.innerHTML = '<option value="">-- Seleccione subtipo --</option>';
                    subtypes.forEach((sub) => {
                        const opt = document.createElement('option');
                        opt.value = sub.id;
                        opt.textContent = sub.name;
                        opt.dataset.needsJustification = sub.needs_justification ? 'true' : 'false';
                        opt.dataset.requiresAttachment = sub.requires_attachment ? 'true' : 'false';
                        subtypeSelect.appendChild(opt);
                    });
                    subtypeContainer.classList.remove('hidden');
                    subtypeSelect.required = true;
                    togglePermitRequirementSections(false, false);
                } else {
                    if (subtypeContainer) subtypeContainer.classList.add('hidden');
                    if (subtypeSelect) {
                        subtypeSelect.innerHTML = `<option value="${parentId}" selected>${selectedOption.textContent}</option>`;
                        subtypeSelect.required = false;
                    }
                    togglePermitRequirementSections(
                        selectedOption.dataset.needsJustification === 'true',
                        selectedOption.dataset.requiresAttachment === 'true'
                    );
                }
            })
            .catch(() => {
                togglePermitRequirementSections(
                    selectedOption.dataset.needsJustification === 'true',
                    selectedOption.dataset.requiresAttachment === 'true'
                );
            });
    }

    function handlePermitSubtypeChange(selectEl) {
        const opt = selectEl.options[selectEl.selectedIndex];
        if (!opt || !opt.value) {
            togglePermitRequirementSections(false, false);
            return;
        }
        togglePermitRequirementSections(
            opt.dataset.needsJustification === 'true',
            opt.dataset.requiresAttachment === 'true'
        );
    }

    function togglePermitRequirementSections(needsJustification, requiresAttachment) {
        const reasonSection = document.getElementById('reason-section');
        const reasonInput = document.getElementById('id_reason');
        const attachmentSection = document.getElementById('attachment-section');
        const attachmentInput = document.getElementById('id_justification_file');

        if (reasonSection) {
            reasonSection.classList.toggle('hidden', !needsJustification);
            if (reasonInput) reasonInput.required = needsJustification;
        }
        if (attachmentSection) {
            attachmentSection.classList.toggle('hidden', !requiresAttachment);
            if (attachmentInput) attachmentInput.required = requiresAttachment;
        }
    }

    function calculatePermitEndDateTime() {
        const startDate = document.getElementById('id_start_date')?.value;
        const startTime = document.getElementById('id_start_time')?.value;
        const days = parseInt(document.getElementById('id_days')?.value || '0', 10) || 0;
        const hours = parseInt(document.getElementById('id_hours')?.value || '0', 10) || 0;
        const minutes = parseInt(document.getElementById('id_minutes')?.value || '0', 10) || 0;
        const displayEl = document.getElementById('calculated-end');
        const endDateInput = document.getElementById('id_end_date');
        const endTimeInput = document.getElementById('id_end_time');

        if (!startDate || !startTime || !displayEl) return;

        const [year, month, day] = startDate.split('-').map(Number);
        const [hour, minute] = startTime.split(':').map(Number);
        const dt = new Date(year, month - 1, day, hour, minute);

        dt.setDate(dt.getDate() + days);
        dt.setHours(dt.getHours() + hours);
        dt.setMinutes(dt.getMinutes() + minutes);

        const pad = (n) => String(n).padStart(2, '0');
        const isoDate = `${dt.getFullYear()}-${pad(dt.getMonth() + 1)}-${pad(dt.getDate())}`;
        const formattedDate = `${pad(dt.getDate())}/${pad(dt.getMonth() + 1)}/${dt.getFullYear()}`;
        const formattedTime = `${pad(dt.getHours())}:${pad(dt.getMinutes())}`;

        if (endDateInput) endDateInput.value = isoDate;
        if (endTimeInput) endTimeInput.value = formattedTime;
        displayEl.textContent = `${formattedDate} ${formattedTime}`;
    }

// =========================================================================
// 5. GESTIÓN DE BITÁCORAS
// =========================================================================

    function updateBinnacleSelectionState() {
        const selected = document.querySelectorAll('.binnacle-check-item:checked');
        const count = selected.length;
        const show = count > 0;

        const btnApprove = document.getElementById('btn-approve-selected-binnacles');
        const btnReject = document.getElementById('btn-reject-selected-binnacles');
        const btnDelete = document.getElementById('btn-delete-selected-binnacles');

        [btnApprove, btnReject, btnDelete].forEach((btn) => {
            if (btn) btn.classList.toggle('hidden', !show);
        });

        document.querySelectorAll('#binnacle-bulk-actions .selected-count').forEach((span) => {
            span.textContent = String(count);
        });
    }

    function toggleAllBinnacles(checked) {
        document.querySelectorAll('#binnacle-pending-tbody .binnacle-row:not(.hidden) .binnacle-check-item')
            .forEach((chk) => {
                chk.checked = checked;
            });
        updateBinnacleSelectionState();
    }

    function getSelectedBinnacleIds() {
        return Array.from(document.querySelectorAll('.binnacle-check-item:checked'))
            .map((c) => parseInt(c.value, 10));
    }

    function filterBinnacles() {
        const searchInput = document.getElementById('binnacleSearchInput');
        const fromInput = document.getElementById('binnacle-filter-from');
        const toInput = document.getElementById('binnacle-filter-to');
        const rows = document.querySelectorAll('#binnacle-pending-tbody .binnacle-row');
        if (!rows.length) return;

        const query = (searchInput?.value || '').toLowerCase().trim();
        const fromDate = fromInput?.value || '';
        const toDate = toInput?.value || '';
        let visibleCount = 0;

        rows.forEach((row) => {
            const rowDate = row.dataset.date || '';
            const rowText = row.textContent.toLowerCase();

            const matchText = !query || rowText.includes(query);
            const matchDate = (!fromDate || !rowDate || rowDate >= fromDate) &&
                (!toDate || !rowDate || rowDate <= toDate);

            row.classList.toggle('hidden', !(matchText && matchDate));
            if (matchText && matchDate) visibleCount++;
        });

        const counter = document.getElementById('binnacle-total-counter');
        if (counter) counter.innerHTML = `Mostrando: <strong>${visibleCount}</strong>`;
    }

    function clearBinnacleDates() {
        const searchInput = document.getElementById('binnacleSearchInput');
        const fromInput = document.getElementById('binnacle-filter-from');
        const toInput = document.getElementById('binnacle-filter-to');
        if (searchInput) searchInput.value = '';
        if (fromInput) fromInput.value = '';
        if (toInput) toInput.value = '';
        filterBinnacles();
    }

    function approveSelectedBinnacles() {
        const ids = getSelectedBinnacleIds();
        if (!ids.length) return;

        Swal.fire({
            title: `¿Aprobar ${ids.length} bitácora(s)?`,
            icon: 'question',
            showCancelButton: true,
            confirmButtonText: 'Sí, aprobar'
        }).then((res) => {
            if (!res.isConfirmed) return;
            fetch('/permitrequest/bitacora/approve/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': typeof getCSRF === 'function' ? getCSRF() : '',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify({ids})
            })
                .then((r) => r.json())
                .then((data) => {
                    if (data.success) {
                        if (window.showToast) showToast(data.message, 'success');
                        if (window.closeModal) closeModal();
                        if (typeof window.refreshCurrentTable === 'function') window.refreshCurrentTable();
                    } else {
                        Swal.fire('Error', data.message, 'error');
                    }
                });
        });
    }

    function rejectSelectedBinnacles() {
        const ids = getSelectedBinnacleIds();
        if (!ids.length) return;

        Swal.fire({
            title: 'Rechazar bitácoras',
            text: 'Ingrese el motivo del rechazo:',
            input: 'textarea',
            inputPlaceholder: 'Especifique la razón...',
            showCancelButton: true,
            confirmButtonText: 'Confirmar rechazo',
            inputValidator: (v) => !v && 'Debe ingresar un motivo'
        }).then((res) => {
            if (!res.isConfirmed || !res.value) return;
            fetch('/permitrequest/bitacora/reject/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': typeof getCSRF === 'function' ? getCSRF() : '',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify({ids, reason: res.value})
            })
                .then((r) => r.json())
                .then((data) => {
                    if (data.success) {
                        if (window.showToast) showToast(data.message, 'success');
                        if (window.closeModal) closeModal();
                        if (typeof window.refreshCurrentTable === 'function') window.refreshCurrentTable();
                    } else {
                        Swal.fire('Error', data.message, 'error');
                    }
                });
        });
    }

    function deleteSelectedBinnacles() {
        const ids = getSelectedBinnacleIds();
        if (!ids.length) return;

        Swal.fire({
            title: `¿Eliminar ${ids.length} bitácora(s)?`,
            icon: 'warning',
            showCancelButton: true,
            confirmButtonText: 'Sí, eliminar',
            customClass: {confirmButton: 'swal2-confirm btn-swal-danger'}
        }).then((res) => {
            if (!res.isConfirmed) return;
            fetch('/permitrequest/bitacora/delete/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': typeof getCSRF === 'function' ? getCSRF() : '',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify({ids})
            })
                .then((r) => r.json())
                .then((data) => {
                    if (data.success) {
                        if (window.showToast) showToast(data.message, 'success');
                        if (window.closeModal) closeModal();
                        if (typeof window.refreshCurrentTable === 'function') window.refreshCurrentTable();
                    } else {
                        Swal.fire('Error', data.message, 'error');
                    }
                });
        });
    }

    function deleteBinnacleSingle(id) {
        Swal.fire({
            title: '¿Eliminar bitácora?',
            text: 'Se eliminará la bitácora seleccionada. Esta acción es irreversible.',
            icon: 'warning',
            showCancelButton: true,
            confirmButtonText: 'Sí, eliminar',
            cancelButtonText: 'Cancelar',
            customClass: {
                confirmButton: 'swal2-confirm btn-swal-danger',
                cancelButton: 'swal2-cancel btn-swal-cancel'
            }
        }).then((res) => {
            if (!res.isConfirmed) return;
            fetch('/permitrequest/bitacora/delete/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': typeof getCSRF === 'function' ? getCSRF() : '',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify({ids: [id]})
            })
                .then((r) => r.json())
                .then((data) => {
                    if (data.success) {
                        if (window.showToast) showToast(data.message, 'success');
                        document.querySelector(`tr[data-id="${id}"]`)?.remove();
                        updateBinnacleSelectionState();
                        if (typeof window.refreshCurrentTable === 'function') window.refreshCurrentTable();
                    } else {
                        Swal.fire('Error', data.message, 'error');
                    }
                })
                .catch(() => {
                    Swal.fire('Error', 'Error de comunicación con el servidor', 'error');
                });
        });
    }

    function openEditBitacoraModal(bitacoraId, currentStart, currentEnd) {
        Swal.fire({
            title: 'Editar bitácora',
            html: `
                <div class="swal-bitacora-time-grid">
                    <div class="swal-bitacora-time-col">
                        <input id="swal-start" type="time" class="form-control text-center swal-bitacora-time-input" value="${currentStart}">
                    </div>
                    <div class="swal-bitacora-time-col">
                        <input id="swal-end" type="time" class="form-control text-center swal-bitacora-time-input" value="${currentEnd}">
                    </div>
                </div>
                <div class="swal-bitacora-field">
                    <label class="swal-bitacora-label" for="swal-note">Agregar mensaje (se añadirá al historial)</label>
                    <textarea id="swal-note" class="form-control no-resize" rows="3" placeholder="Ingrese el nuevo mensaje..."></textarea>
                </div>
                <div class="swal-bitacora-field">
                    <label class="swal-bitacora-label">Adjuntar PDF (opcional, máximo 2MB)</label>
                    <label for="swal-file" class="swal-bitacora-dropzone">
                        <i class="fas fa-file-pdf swal-bitacora-pdf-icon"></i>
                        <div class="swal-bitacora-file-meta">
                            <span class="swal-bitacora-file-title" id="swal-file-title">Seleccionar archivo PDF</span>
                            <span class="swal-bitacora-file-subtitle" id="swal-file-subtitle">Haz click para elegir un archivo</span>
                        </div>
                        <input id="swal-file" type="file" accept="application/pdf" class="file-input-hidden">
                    </label>
                </div>
            `,
            didOpen: () => {
                const fileInput = document.getElementById('swal-file');
                if (fileInput) {
                    fileInput.addEventListener('change', () => {
                        const file = fileInput.files?.[0];
                        if (!file) return;
                        document.getElementById('swal-file-title').textContent = file.name;
                        document.getElementById('swal-file-subtitle').textContent = `${(file.size / 1024).toFixed(1)} KB`;
                    });
                }
            },
            showCancelButton: true,
            confirmButtonText: 'Aceptar',
            cancelButtonText: 'Cancelar',
            customClass: {
                confirmButton: 'btn-blue-rectangle px-4 py-2',
                cancelButton: 'btn-dark-blue-rectangle-outline px-4 py-2'
            },
            preConfirm: () => {
                const start = document.getElementById('swal-start').value;
                const end = document.getElementById('swal-end').value;
                const note = document.getElementById('swal-note').value.trim();
                const file = document.getElementById('swal-file')?.files?.[0] || null;

                if (!start || !end) {
                    Swal.showValidationMessage('Debe ingresar las horas de entrada y salida');
                    return false;
                }
                if (file && file.size > 2 * 1024 * 1024) {
                    Swal.showValidationMessage('El archivo PDF no debe superar los 2 MB');
                    return false;
                }

                const formData = new FormData();
                formData.append('start_time', start);
                formData.append('end_time', end);
                if (note) formData.append('response_note', note);
                if (file) formData.append('justification_file', file);

                return fetch(`/permitrequest/bitacora/edit/${bitacoraId}/`, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': typeof getCSRF === 'function' ? getCSRF() : '',
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    body: formData
                })
                    .then((res) => res.json())
                    .then((data) => {
                        if (!data.success) throw new Error(data.message || 'Error al actualizar');
                        return data;
                    })
                    .catch((err) => {
                        Swal.showValidationMessage(err.message || 'Error de comunicación');
                    });
            }
        }).then((res) => {
            if (res.isConfirmed && res.value?.success) {
                if (window.showToast) showToast(res.value.message || 'Bitácora actualizada', 'success');
                if (window.closeModal) closeModal();
                if (typeof window.refreshCurrentTable === 'function') window.refreshCurrentTable();
            }
        });
    }

    function clearHistoryDates() {
        const fromInput = document.getElementById('history-filter-from');
        const toInput = document.getElementById('history-filter-to');
        if (fromInput) fromInput.value = '';
        if (toInput) toInput.value = '';
        filterBinnacleHistoryRows();
    }

    function filterBinnacleHistoryRows() {
        const from = document.getElementById('history-filter-from')?.value || '';
        const to = document.getElementById('history-filter-to')?.value || '';
        document.querySelectorAll('#binnacle-history-tbody tr[data-date]').forEach((row) => {
            const date = row.dataset.date || '';
            const hide = (from && date < from) || (to && date > to);
            row.classList.toggle('hidden', hide);
        });
    }

    function reviewBinnacleModal(id) {
        Swal.fire({
            title: 'Revisar / Modificar bitácora',
            text: 'Ingrese el motivo por el cual se devolverá a estado PENDIENTE:',
            input: 'textarea',
            inputPlaceholder: 'Indique la observación o corrección requerida...',
            showCancelButton: true,
            confirmButtonText: 'Confirmar y pasar a pendiente',
            inputValidator: (v) => !v && 'Debe ingresar un motivo'
        }).then((res) => {
            if (!res.isConfirmed || !res.value) return;
            fetch(`/permitrequest/bitacora/review/${id}/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': typeof getCSRF === 'function' ? getCSRF() : '',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify({reason: res.value})
            })
                .then((r) => r.json())
                .then((data) => {
                    if (data.success) {
                        if (window.showToast) showToast(data.message, 'success');
                        document.querySelector(`#binnacle-history-tbody tr[data-id="${id}"]`)?.remove();
                        if (typeof window.refreshCurrentTable === 'function') window.refreshCurrentTable();
                    } else {
                        Swal.fire('Error', data.message || 'No autorizado', 'error');
                    }
                });
        });
    }

    function filterSubtypesTable(term) {
        const q = (term || '').toLowerCase().trim();
        document.querySelectorAll('#subtypes-tbody tr[data-name]').forEach((row) => {
            const name = row.dataset.name || '';
            row.classList.toggle('hidden', !name.includes(q));
        });
    }

    function toggleStatusAjax(url, name, isActive) {
        if (!url) return;
        const actionText = isActive ? 'dar de baja' : 'dar de alta';
        Swal.fire({
            title: '¿Cambiar estado?',
            text: `¿Está seguro de ${actionText} a "${name}"?`,
            icon: 'question',
            showCancelButton: true,
            confirmButtonText: 'Sí, cambiar',
            cancelButtonText: 'Cancelar',
            customClass: {
                confirmButton: 'btn-blue-rectangle px-3 py-2',
                cancelButton: 'btn-dark-blue-rectangle-outline px-3 py-2'
            }
        }).then((res) => {
            if (!res.isConfirmed) return;
            fetch(url, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': typeof getCSRF === 'function' ? getCSRF() : '',
                    'X-Requested-With': 'XMLHttpRequest'
                }
            })
                .then((r) => r.json())
                .then((data) => {
                    if (data.success) {
                        if (window.showToast) showToast(data.message || 'Estado modificado', 'success');
                        if (window.closeModal) closeModal();
                        if (typeof window.refreshCurrentTable === 'function') window.refreshCurrentTable();
                    } else {
                        Swal.fire('Error', data.message || 'No se pudo cambiar el estado', 'error');
                    }
                })
                .catch(() => {
                    Swal.fire('Error', 'Error de comunicación', 'error');
                });
        });
    }

// =========================================================================
// 6. BÚSQUEDA POR EXCEL DE CÉDULAS (IDENTIFICATIONS BATCH UPLOAD)
// =========================================================================

    function initIdentificationExcelUpload() {
        const fileInput = document.getElementById('identification_excel_input');
        if (!fileInput) return;

        fileInput.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (!file) return;

            const maxSizeBytes = 1024 * 1024;
            if (file.size > maxSizeBytes) {
                if (typeof Swal !== 'undefined') {
                    Swal.fire({
                        icon: 'warning',
                        title: 'Archivo muy pesado',
                        text: 'El archivo Excel no debe superar 1 MB.'
                    });
                }
                fileInput.value = '';
                return;
            }

            const formData = new FormData();
            formData.append('identification_file', file);

            const iconBox = document.getElementById('permit-excel-icon-box');
            const originalIconHtml = iconBox ? iconBox.innerHTML : '';
            if (iconBox) {
                iconBox.innerHTML = '<i class="fas fa-spinner fa-spin permit-excel-spinner"></i>';
            }

            const uploadUrl = fileInput.dataset.uploadUrl || '/permitrequest/admin/parse-identifications/';

            fetch(uploadUrl, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': typeof getCSRF === 'function' ? getCSRF() : '',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: formData
            })
                .then((r) => r.json())
                .then((data) => {
                    if (data.success) {
                        const hiddenInput = document.getElementById('filter_document_numbers');
                        if (hiddenInput) hiddenInput.value = 'session';

                        const badgeBox = document.getElementById('identification-badge-container');
                        const countText = document.getElementById('identification-count-text');
                        const dropzone = document.getElementById('permit-excel-dropzone-label');

                        if (badgeBox && countText) {
                            countText.textContent = `${data.count} cédula(s)`;
                            badgeBox.classList.remove('hidden');
                        }
                        if (dropzone) dropzone.classList.add('file-selected');
                        if (typeof window.showToast === 'function') window.showToast(data.message, 'success');
                    } else if (typeof Swal !== 'undefined') {
                        Swal.fire({
                            icon: 'warning',
                            title: 'Atención',
                            text: data.message || 'No se pudo procesar el archivo'
                        });
                    }
                })
                .catch(() => {
                    if (typeof Swal !== 'undefined') {
                        Swal.fire({
                            icon: 'error',
                            title: 'Error',
                            text: 'Error de comunicación al procesar el archivo.'
                        });
                    }
                })
                .finally(() => {
                    if (iconBox) iconBox.innerHTML = originalIconHtml;
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
})
();