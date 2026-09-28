/**
 * permit.js - Módulo Consolidado de Permisos y Bitácoras (SIGETH)
 * Arquitectura: Vanilla JS + Django Template
 * Estándar: Integración completa con main.js
 */

(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', () => {
        initSelect2Filters();
        initSearchDebounce();
    });

    // =========================================================================
    // 1. SELECT2 Y BÚSQUEDAS DINÁMICAS
    // =========================================================================

    function initSelect2Filters() {
        if (!window.jQuery || !window.jQuery.fn.select2) {
            return;
        }

        document.querySelectorAll('#filtersForm select.select2').forEach((sel) => {
            const $sel = $(sel);
            const ajaxUrl = sel.dataset.ajaxUrl;
            const placeholder = sel.dataset.placeholder || 'Seleccionar...';
            const minLen = parseInt(sel.dataset.minimumInputLength || '1', 10) || 1;

            if (ajaxUrl) {
                $sel.select2({
                    placeholder: placeholder,
                    allowClear: true,
                    minimumInputLength: minLen,
                    width: '100%',
                    language: {
                        inputTooShort: (args) => `Ingrese ${args.minimum - args.input.length} carácter(es) más`,
                        noResults: () => 'No se encontraron resultados',
                        searching: () => 'Buscando...'
                    },
                    ajax: {
                        url: ajaxUrl,
                        dataType: 'json',
                        delay: 250,
                        data: (params) => ({term: params.term}),
                        processResults: (data) => {
                            if (Array.isArray(data.results)) return {results: data.results};
                            if (Array.isArray(data.units)) {
                                return {
                                    results: data.units.map((u) => ({id: String(u.id), text: u.name}))
                                };
                            }
                            return {results: []};
                        },
                        cache: true
                    }
                });
            } else {
                $sel.select2({
                    placeholder: placeholder,
                    allowClear: true,
                    width: '100%'
                });
            }
        });
    }

    function initSearchDebounce() {
        const searchInput = document.getElementById('table-search-permits') || document.getElementById('table-search');
        if (!searchInput) return;

        let debounceTimer = null;
        searchInput.addEventListener('input', (e) => {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(() => {
                const query = e.target.value.trim();
                if (document.getElementById('filtersForm')) {
                    applyPermitFilters(1);
                } else if (typeof window.refreshCurrentTable === 'function') {
                    window.refreshCurrentTable({q: query, page: 1});
                }
            }, 300);
        });

        searchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                clearTimeout(debounceTimer);
                const query = e.target.value.trim();
                if (document.getElementById('filtersForm')) {
                    applyPermitFilters(1);
                } else if (typeof window.refreshCurrentTable === 'function') {
                    window.refreshCurrentTable({q: query, page: 1});
                }
            }
        });
    }

    // =========================================================================
    // 2. FILTRADO PARA PERMISOS ADMIN
    // =========================================================================

    function collectFilters() {
        const form = document.getElementById('filtersForm');
        const params = {};

        if (form) {
            const formData = new FormData(form);
            for (let [key, val] of formData.entries()) {
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

        if (typeof window.refreshCurrentTable === 'function') {
            window.refreshCurrentTable(params);
        }
    }

    window.handlePermitSearch = function (e) {
        if (e) e.preventDefault();
        applyPermitFilters(1);
    };

    window.clearPermitFilters = function () {
        const form = document.getElementById('filtersForm');
        if (form) {
            form.reset();
            if (window.$ && $.fn.select2) {
                $(form).find('select.select2').val('').trigger('change');
            }
        }
        if (typeof window.clearLoadedIdentifications === 'function') {
            window.clearLoadedIdentifications();
        }
        applyPermitFilters(1);
    };

    window.printPermitReport = function (permitId) {
        if (!permitId) return;
        const url = `/permitrequest/admin/${permitId}/report/`;
        window.open(url, '_blank', 'width=850,height=650,resizable=yes,scrollbars=yes');
    };

    // =========================================================================
    // 3. GESTIÓN DE BITÁCORAS
    // =========================================================================

    window.updateBinnacleSelectionState = function () {
        const selected = document.querySelectorAll('.binnacle-check-item:checked');
        const show = selected.length > 0;
        const btnApprove = document.getElementById('btn-approve-selected-binnacles');
        const btnReject = document.getElementById('btn-reject-selected-binnacles');
        const btnDelete = document.getElementById('btn-delete-selected-binnacles');

        if (btnApprove) btnApprove.style.display = show ? 'inline-flex' : 'none';
        if (btnReject) btnReject.style.display = show ? 'inline-flex' : 'none';
        if (btnDelete) btnDelete.style.display = show ? 'inline-flex' : 'none';
    };

    window.toggleAllBinnacles = function (checked) {
        document.querySelectorAll('.binnacle-check-item').forEach(chk => chk.checked = checked);
        window.updateBinnacleSelectionState();
    };

    function getSelectedBinnacleIds() {
        return Array.from(document.querySelectorAll('.binnacle-check-item:checked')).map(c => parseInt(c.value, 10));
    }

    window.clearBinnacleDates = function () {
        const fromInput = document.getElementById('binnacle-filter-from');
        const toInput = document.getElementById('binnacle-filter-to');
        if (fromInput) fromInput.value = '';
        if (toInput) toInput.value = '';
        filterBinnacleRows();
    };

    function filterBinnacleRows() {
        const from = document.getElementById('binnacle-filter-from')?.value;
        const to = document.getElementById('binnacle-filter-to')?.value;
        document.querySelectorAll('#binnacle-pending-tbody tr[data-date]').forEach(row => {
            const date = row.dataset.date;
            let match = true;
            if (from && date < from) match = false;
            if (to && date > to) match = false;
            row.style.display = match ? '' : 'none';
        });
    }

    document.addEventListener('change', (e) => {
        if (e.target && (e.target.id === 'binnacle-filter-from' || e.target.id === 'binnacle-filter-to')) {
            filterBinnacleRows();
        }
    });

    window.approveSelectedBinnacles = function () {
        const ids = getSelectedBinnacleIds();
        if (!ids.length) return;

        Swal.fire({
            title: `¿Aprobar ${ids.length} bitácora(s)?`,
            icon: 'question',
            showCancelButton: true,
            confirmButtonText: 'Sí, aprobar'
        }).then(res => {
            if (res.isConfirmed) {
                fetch('/permitrequest/bitacora/approve/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': typeof getCSRF === 'function' ? getCSRF() : '',
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    body: JSON.stringify({ids: ids})
                })
                    .then(r => r.json())
                    .then(data => {
                        if (data.success) {
                            showToast(data.message, 'success');
                            closeModal();
                            if (typeof refreshCurrentTable === 'function') refreshCurrentTable();
                        } else {
                            Swal.fire('Error', data.message, 'error');
                        }
                    });
            }
        });
    };

    window.rejectSelectedBinnacles = function () {
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
        }).then(res => {
            if (res.isConfirmed && res.value) {
                fetch('/permitrequest/bitacora/reject/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': typeof getCSRF === 'function' ? getCSRF() : '',
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    body: JSON.stringify({ids: ids, reason: res.value})
                })
                    .then(r => r.json())
                    .then(data => {
                        if (data.success) {
                            showToast(data.message, 'success');
                            closeModal();
                            if (typeof refreshCurrentTable === 'function') refreshCurrentTable();
                        } else {
                            Swal.fire('Error', data.message, 'error');
                        }
                    });
            }
        });
    };

    window.deleteSelectedBinnacles = function () {
        const ids = getSelectedBinnacleIds();
        if (!ids.length) return;

        Swal.fire({
            title: `¿Eliminar ${ids.length} bitácora(s)?`,
            icon: 'warning',
            showCancelButton: true,
            confirmButtonText: 'Sí, eliminar',
            customClass: {confirmButton: 'swal2-confirm btn-swal-danger'}
        }).then(res => {
            if (res.isConfirmed) {
                fetch('/permitrequest/bitacora/delete/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': typeof getCSRF === 'function' ? getCSRF() : '',
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    body: JSON.stringify({ids: ids})
                })
                    .then(r => r.json())
                    .then(data => {
                        if (data.success) {
                            showToast(data.message, 'success');
                            closeModal();
                            if (typeof refreshCurrentTable === 'function') refreshCurrentTable();
                        } else {
                            Swal.fire('Error', data.message, 'error');
                        }
                    });
            }
        });
    };

    window.deleteBinnacleSingle = function (id) {
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
        }).then(res => {
            if (res.isConfirmed) {
                fetch('/permitrequest/bitacora/delete/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': typeof getCSRF === 'function' ? getCSRF() : '',
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    body: JSON.stringify({ids: [id]})
                })
                    .then(r => r.json())
                    .then(data => {
                        if (data.success) {
                            showToast(data.message, 'success');
                            document.querySelector(`tr[data-id="${id}"]`)?.remove();
                            if (typeof refreshCurrentTable === 'function') refreshCurrentTable();
                        } else {
                            Swal.fire('Error', data.message, 'error');
                        }
                    })
                    .catch(err => {
                        console.error(err);
                        Swal.fire('Error', 'Error de comunicación con el servidor', 'error');
                    });
            }
        });
    };

    window.openEditBitacoraModal = function (bitacoraId, currentStart, currentEnd) {
        Swal.fire({
            title: 'Editar bitácora',
            html: `
                <div style="display: flex; gap: 12px; align-items: center; justify-content: center; margin-bottom: 16px;">
                    <div style="flex: 1;">
                        <input id="swal-start" type="time" class="form-control text-center" style="height: 42px; font-size: 1rem;" value="${currentStart}">
                    </div>
                    <div style="flex: 1;">
                        <input id="swal-end" type="time" class="form-control text-center" style="height: 42px; font-size: 1rem;" value="${currentEnd}">
                    </div>
                </div>

                <div style="text-align: left; margin-bottom: 14px;">
                    <label style="font-weight: 600; color: #1e293b; font-size: 0.88rem; margin-bottom: 6px; display: block;">
                        Agregar mensaje (se añadirá al historial)
                    </label>
                    <textarea id="swal-note" class="form-control" rows="3" style="resize: none;" placeholder="Ingrese el nuevo mensaje..."></textarea>
                </div>

                <div style="text-align: left;">
                    <label style="font-weight: 600; color: #1e293b; font-size: 0.88rem; margin-bottom: 6px; display: block;">
                        Adjuntar PDF (opcional, máximo 2MB)
                    </label>
                    <label for="swal-file" style="border: 1px dashed #cbd5e1; border-radius: 8px; padding: 12px 16px; display: flex; align-items: center; gap: 14px; cursor: pointer; background: #f8fafc; margin: 0;">
                        <i class="fas fa-file-pdf" style="font-size: 2rem; color: #dc2626;"></i>
                        <div style="display: flex; flex-direction: column;">
                            <span style="font-weight: 700; color: #0f172a; font-size: 0.9rem;" id="swal-file-title">Seleccionar archivo PDF</span>
                            <span style="font-size: 0.78rem; color: #64748b;" id="swal-file-subtitle">Haz click para elegir un archivo</span>
                        </div>
                        <input id="swal-file" type="file" accept="application/pdf" style="display: none;" 
                               onchange="if(this.files[0]){ document.getElementById('swal-file-title').innerText = this.files[0].name; document.getElementById('swal-file-subtitle').innerText = (this.files[0].size / 1024).toFixed(1) + ' KB'; }">
                    </label>
                </div>
            `,
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
                const fileInput = document.getElementById('swal-file');
                const file = fileInput && fileInput.files ? fileInput.files[0] : null;

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
                    .then(res => res.json())
                    .then(data => {
                        if (!data.success) {
                            throw new Error(data.message || 'Error al actualizar');
                        }
                        return data;
                    })
                    .catch(err => {
                        Swal.showValidationMessage(err.message || 'Error de comunicación');
                    });
            }
        }).then(res => {
            if (res.isConfirmed && res.value && res.value.success) {
                showToast(res.value.message || 'Bitácora actualizada', 'success');
                closeModal();
                if (typeof refreshCurrentTable === 'function') refreshCurrentTable();
            }
        });
    };

    window.clearHistoryDates = function () {
        const fromInput = document.getElementById('history-filter-from');
        const toInput = document.getElementById('history-filter-to');
        if (fromInput) fromInput.value = '';
        if (toInput) toInput.value = '';
        window.filterBinnacleHistoryRows();
    };

    window.filterBinnacleHistoryRows = function () {
        const from = document.getElementById('history-filter-from')?.value;
        const to = document.getElementById('history-filter-to')?.value;
        document.querySelectorAll('#binnacle-history-tbody tr[data-date]').forEach(row => {
            const date = row.dataset.date;
            let match = true;
            if (from && date < from) match = false;
            if (to && date > to) match = false;
            row.style.display = match ? '' : 'none';
        });
    };

    window.reviewBinnacleModal = function (id) {
        Swal.fire({
            title: 'Revisar / Modificar bitácora',
            text: 'Ingrese el motivo por el cual se devolverá a estado PENDIENTE:',
            input: 'textarea',
            inputPlaceholder: 'Indique la observación o corrección requerida...',
            showCancelButton: true,
            confirmButtonText: 'Confirmar y pasar a pendiente',
            inputValidator: (v) => !v && 'Debe ingresar un motivo'
        }).then(res => {
            if (res.isConfirmed && res.value) {
                fetch(`/permitrequest/bitacora/review/${id}/`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': typeof getCSRF === 'function' ? getCSRF() : '',
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    body: JSON.stringify({reason: res.value})
                })
                    .then(r => r.json())
                    .then(data => {
                        if (data.success) {
                            showToast(data.message, 'success');
                            document.querySelector(`#binnacle-history-tbody tr[data-id="${id}"]`)?.remove();
                            if (typeof refreshCurrentTable === 'function') refreshCurrentTable();
                        } else {
                            Swal.fire('Error', data.message || 'No autorizado', 'error');
                        }
                    });
            }
        });
    };

    window.filterSubtypesTable = function (term) {
        const q = (term || '').toLowerCase().trim();
        document.querySelectorAll('#subtypes-tbody tr[data-name]').forEach(row => {
            const name = row.dataset.name || '';
            row.style.display = name.includes(q) ? '' : 'none';
        });
    };

})();

window.toggleStatusAjax = function (url, name, isActive) {
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
    }).then(res => {
        if (res.isConfirmed) {
            fetch(url, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': typeof getCSRF === 'function' ? getCSRF() : '',
                    'X-Requested-With': 'XMLHttpRequest'
                }
            })
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        showToast(data.message || 'Estado modificado', 'success');
                        closeModal();
                        if (typeof refreshCurrentTable === 'function') refreshCurrentTable();
                    } else {
                        Swal.fire('Error', data.message || 'No se pudo cambiar el estado', 'error');
                    }
                })
                .catch(err => {
                    console.error(err);
                    Swal.fire('Error', 'Error de comunicación', 'error');
                });
        }
    });
};
// =========================================================================
// 4. BÚSQUEDA POR EXCEL DE CÉDULAS (IDENTIFICATIONS BATCH UPLOAD)
// =========================================================================

document.addEventListener('DOMContentLoaded', () => {
    initIdentificationExcelUpload();
});

function initIdentificationExcelUpload() {
    const fileInput = document.getElementById('identification_excel_input');
    if (!fileInput) return;

    fileInput.addEventListener('change', function (e) {
        const file = e.target.files[0];
        if (!file) return;

        // Validación estricta en frontend: Máximo 1 MB (1024 * 1024 bytes)
        const maxSizeBytes = 1 * 1024 * 1024;
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
            iconBox.innerHTML = '<i class="fas fa-spinner fa-spin" style="font-size: 32px; color: #10b981;"></i>';
        }

        fetch('/permitrequest/admin/parse-identifications/', {
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
                    if (hiddenInput) {
                        hiddenInput.value = data.document_numbers.join(',');
                    }

                    const badgeBox = document.getElementById('identification-badge-container');
                    const countText = document.getElementById('identification-count-text');
                    const dropzone = document.getElementById('permit-excel-dropzone-label');

                    if (badgeBox && countText) {
                        countText.innerText = `${data.count} cédula(s)`;
                        badgeBox.style.display = 'inline-flex';
                    }
                    if (dropzone) {
                        dropzone.classList.add('file-selected');
                    }

                    if (typeof showToast === 'function') {
                        showToast(data.message, 'success');
                    }
                } else {
                    if (typeof Swal !== 'undefined') {
                        Swal.fire({
                            icon: 'warning',
                            title: 'Atención',
                            text: data.message || 'No se pudo procesar el archivo'
                        });
                    }
                }
            })
            .catch(err => {
                console.error('Error uploading identification excel:', err);
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

window.clearLoadedIdentifications = function () {
    const hiddenInput = document.getElementById('filter_document_numbers');
    if (hiddenInput) hiddenInput.value = '';

    const badgeBox = document.getElementById('identification-badge-container');
    if (badgeBox) badgeBox.style.display = 'none';

    const dropzone = document.getElementById('permit-excel-dropzone-label');
    if (dropzone) dropzone.classList.remove('file-selected');

    const fileInput = document.getElementById('identification_excel_input');
    if (fileInput) fileInput.value = '';
};