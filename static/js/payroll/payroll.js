/**
 * PAYROLL.JS - GESTIÓN INTEGRAL DEL MÓDULO DE NÓMINA (SIGETH)
 * Archivo Maestro Unificado:
 * 1. Configuración de URLs y Helpers
 * 2. Modales Dinámicos (Periodos y Rubros) integrados con main.js
 * 3. Modales Estáticos (Generación y Cierre de Roles)
 * 4. Procesamiento, Recálculo y Polling de Nómina
 * 5. Búsqueda y Paginación Server-Side (Roles y Periodos)
 * 6. Fondos de Reserva y Novedades Masivas (Excel)
 */

const PAYROLL_URLS = {
    recalculate: '/payroll/payslips/recalculate/',
    syncMissing: '/payroll/generate/missing/',
    seal: (id) => `/payroll/period/${id}/mark-paid/`,
    calculate: '/payroll/api/calculate-working-days/',
    tableList: '/payroll/periods/',
    status: '/payroll/payslips/recalculate-status/'
};

window.currentGenPeriodId = null;

// Helper para extraer CSRF Token si no existe función global
function getPayrollCSRF() {
    if (typeof getCSRF === 'function') return getCSRF();
    const cookie = document.cookie.split(';').map(c => c.trim()).find(c => c.startsWith('csrftoken='));
    if (cookie) return decodeURIComponent(cookie.split('=')[1]);
    const el = document.querySelector('[name=csrfmiddlewaretoken]');
    return el ? el.value : '';
}

async function safeJsonParse(response) {
    const contentType = response.headers.get('content-type');
    if (contentType && contentType.includes('text/html')) {
        throw new Error('El servidor devolvió una respuesta inesperada.');
    }
    const data = await response.json();
    if (!response.ok || (data.status === 'error' || data.success === false)) {
        throw new Error(data.message || 'Error en la operación.');
    }
    return data;
}

/* =================================================================================
   1. INICIALIZADOR DE MODAL DE PERIODOS (Auto-selección, feriados y select limpio)
   ================================================================================= */
window.initializePeriodModal = function (modalOrRoot) {
    const root = (modalOrRoot instanceof HTMLElement)
        ? modalOrRoot
        : (document.getElementById('modal-root') || document);

    const form = root.querySelector('#periodForm');
    if (!form) return;

    const selectMonth = form.querySelector('[name="month"]');
    const inputYear = form.querySelector('[name="year"]');
    const inputStartDate = form.querySelector('[name="start_date"]');
    const inputEndDate = form.querySelector('[name="end_date"]');
    const inputWorkingDays = form.querySelector('[name="working_days"]');
    const statusText = form.querySelector('#period-calc-status-text');
    const holidaysBadge = form.querySelector('#period-holidays-badge');
    const submitBtn = form.querySelector('button[type="submit"]');

    if (!selectMonth || !inputYear) return;

    // Inicializar Select2 con dropdown flotante (no modifica la altura del modal)
    if (window.jQuery) {
        if ($(selectMonth).hasClass('select2-hidden-accessible')) {
            $(selectMonth).select2('destroy');
        }
        $(selectMonth).select2({
            width: '100%',
            dropdownParent: $(form).closest('.modal-container-medium')
        });
    }

    const now = new Date();
    const currentMonthNum = now.getMonth() + 1; // 1 - 12
    const currentYear = now.getFullYear();

    const monthNames = [
        "ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO",
        "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"
    ];
    const currentMonthName = monthNames[currentMonthNum - 1];

    // 1. Preseleccionar automáticamente el mes actual si viene vacío
    if (!selectMonth.value || selectMonth.value === '' || selectMonth.value === 'None') {
        for (const opt of selectMonth.options) {
            const val = opt.value.trim().toUpperCase();
            const txt = opt.text.trim().toUpperCase();

            if (val === currentMonthName || val === String(currentMonthNum) ||
                txt.includes(currentMonthName) || val === String(currentMonthNum).padStart(2, '0')) {
                selectMonth.value = opt.value;
                break;
            }
        }
        if (window.jQuery) {
            $(selectMonth).trigger('change.select2');
        }
    }

    if (!inputYear.value || inputYear.value === '' || inputYear.value === 'None') {
        inputYear.value = String(currentYear);
    }

    // 2. Consulta de feriados y días laborables
    async function calculate() {
        const selectedVal = (selectMonth.value || '').trim();
        const y = parseInt(inputYear.value, 10);

        if (!selectedVal || !y || isNaN(y) || String(y).length !== 4) return;

        if (submitBtn) submitBtn.disabled = true;
        if (statusText) statusText.textContent = 'Consultando feriados institucionales...';

        try {
            const url = `${PAYROLL_URLS.calculate}?month=${encodeURIComponent(selectedVal)}&year=${y}`;
            const response = await fetch(url, {
                headers: {'X-Requested-With': 'XMLHttpRequest'}
            });
            const data = await safeJsonParse(response);

            if (data.status === 'success' || data.success) {
                if (data.start_date && inputStartDate) inputStartDate.value = data.start_date;
                if (data.end_date && inputEndDate) inputEndDate.value = data.end_date;
                if (data.working_days !== undefined && inputWorkingDays) {
                    inputWorkingDays.value = data.working_days;
                }

                const holidays = typeof data.holidays_count === 'number' ? data.holidays_count : 0;

                if (holidaysBadge) {
                    holidaysBadge.textContent = `${holidays} Feriado(s)`;
                    holidaysBadge.className = holidays > 0 ? 'badge badge-amber' : 'badge badge-blue';
                }

                if (statusText) {
                    statusText.textContent = `${data.working_days} días laborables calculados.`;
                }
            }
        } catch (e) {
            if (statusText) statusText.textContent = 'Días laborables calculados automáticamente.';
            if (holidaysBadge) {
                holidaysBadge.textContent = '0 Feriados';
                holidaysBadge.className = 'badge badge-blue';
            }
        } finally {
            if (submitBtn) submitBtn.disabled = false;
        }
    }

    // Escuchadores de eventos
    if (window.jQuery) {
        $(selectMonth).on('change change.select2', calculate);
    } else {
        selectMonth.addEventListener('change', calculate);
    }
    inputYear.addEventListener('change', calculate);
    inputYear.addEventListener('input', function () {
        this.value = this.value.replace(/[^0-9]/g, '').slice(0, 4);
        if (this.value.length === 4) calculate();
    });

    // Disparar cálculo inicial
    setTimeout(calculate, 100);
};
/* =================================================================================
   2. INICIALIZADOR DE MODAL DE RUBROS
   ================================================================================= */
window.initializeRubricModal = function (root) {
    const context = root || document;
    const $typeSelect = $(context).find('select[name="rubric_type"]');
    const divPriority = context.querySelector('#divPriority');
    const divIncomeSwitches = context.querySelector('#divIncomeSwitches');
    const divOrder = context.querySelector('#divOrder');
    const divName = context.querySelector('#divName');

    function toggleRubricFields() {
        if (!$typeSelect.length) return;
        const val = ($typeSelect.val() || '').toUpperCase();

        if (divPriority) divPriority.classList.add('hidden');
        if (divIncomeSwitches) divIncomeSwitches.classList.add('hidden');

        if (divName) divName.className = 'col-md-8 form-group';
        if (divPriority) divPriority.className = 'col-md-4 form-group hidden';
        if (divOrder) divOrder.className = 'col-md-4 form-group';

        if (val.includes('INCOME') || val === 'INGRESO' || val === '1') {
            if (divIncomeSwitches) divIncomeSwitches.classList.remove('hidden');
        } else if (val.includes('DEDUCTION') || val === 'DESCUENTO' || val === '2') {
            if (divPriority) divPriority.classList.remove('hidden');
            if (divName) divName.className = 'col-md-4 form-group';
        }
    }

    if ($typeSelect.length) {
        $typeSelect.on('change.select2 change', toggleRubricFields);
        setTimeout(toggleRubricFields, 100);
    }
};

/* =================================================================================
   3. MODALES ESTÁTICOS DE NÓMINA (Generar y Sellar)
   ================================================================================= */
window.openGenerateModal = function (id, name, hasScopeChanges) {
    window.currentGenPeriodId = id;
    const modal = document.getElementById('modalGeneratePayroll');
    if (modal) {
        const nameEl = document.getElementById('gen-period-name');
        if (nameEl) nameEl.innerText = name;
        const btnScope = document.getElementById('btn-generate-scope');
        if (btnScope) btnScope.style.display = (hasScopeChanges === 'true' || hasScopeChanges === true) ? 'flex' : 'none';
        modal.setAttribute('style', 'display: flex !important;');
        document.body.classList.add('modal-open');
    }
};

window.closeGenerateModal = function () {
    const modal = document.getElementById('modalGeneratePayroll');
    if (modal) {
        modal.setAttribute('style', 'display: none !important;');
        document.body.classList.remove('modal-open');
        const opt = document.getElementById('generate-options');
        const load = document.getElementById('generate-loading');
        if (opt) opt.style.display = 'block';
        if (load) load.style.display = 'none';
    }
};

window.openReportModal = function (id, name, isClosed) {
    window.currentGenPeriodId = id;
    const modal = document.getElementById('modalReportOptions');
    if (modal) {
        const nameEl = document.getElementById('rep-period-name');
        if (nameEl) nameEl.innerText = name;
        const sellarBtn = document.getElementById('sellar-container');
        if (sellarBtn) sellarBtn.style.display = (isClosed === 'true' || isClosed === true) ? 'none' : 'block';
        modal.setAttribute('style', 'display: flex !important;');
        document.body.classList.add('modal-open');
    }
};

window.closeReportModal = function () {
    const modal = document.getElementById('modalReportOptions');
    if (modal) {
        modal.setAttribute('style', 'display: none !important;');
        document.body.classList.remove('modal-open');
    }
};

/* =================================================================================
   4. MOTOR DE PROCESAMIENTO Y RECALCULO DE ROLES
   ================================================================================= */
window.submitGenerate = function (mode) {
    const periodId = window.currentGenPeriodId;
    if (!periodId) return;

    const opt = document.getElementById('generate-options');
    const load = document.getElementById('generate-loading');
    if (opt) opt.style.display = 'none';
    if (load) load.style.display = 'block';

    const formData = new FormData();
    formData.append('period_id', periodId);
    let targetUrl = PAYROLL_URLS.recalculate;

    if (mode === 'missing') targetUrl = PAYROLL_URLS.syncMissing;
    else if (mode === 'scope') formData.append('scope', 'true');

    fetch(targetUrl, {
        method: 'POST',
        body: formData,
        headers: {'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': getPayrollCSRF()}
    })
        .then(safeJsonParse)
        .then(data => {
            if (data.task_id) startGenerationPolling(data.task_id);
            else handleGenerationSuccess(data.message || 'Proceso completado.');
        })
        .catch(err => {
            window.closeGenerateModal();
            Swal.fire({icon: 'error', title: 'Error', text: err.message});
        });
};

function startGenerationPolling(taskId) {
    Swal.fire({
        title: 'Calculando Nómina',
        html: `<div id="poll-msg">Iniciando proceso asíncrono...</div>`,
        allowOutsideClick: false,
        showConfirmButton: false,
        didOpen: () => Swal.showLoading()
    });

    const poll = () => {
        fetch(`${PAYROLL_URLS.status}?task_id=${taskId}`)
            .then(safeJsonParse)
            .then(res => {
                if (res.done || res.status === 'SUCCESS' || res.success) {
                    handleGenerationSuccess(res.message || 'Nómina generada con éxito.');
                } else {
                    const msgEl = document.getElementById('poll-msg');
                    if (msgEl && res.progress) msgEl.innerText = `Progreso: ${res.progress}%`;
                    setTimeout(poll, 1000);
                }
            })
            .catch(err => Swal.fire('Error', err.message, 'error'));
    };
    poll();
}

function handleGenerationSuccess(message) {
    Swal.fire({
        icon: 'success',
        title: '¡Éxito!',
        text: message,
        timer: 2000,
        showConfirmButton: false
    }).then(() => {
        window.closeGenerateModal();
        if (typeof reloadTableData === 'function') {
            reloadTableData(window.location.href, '#period-table-container');
        } else {
            location.reload();
        }
    });
}

window.sellarComoPagados = function () {
    const periodId = window.currentGenPeriodId;
    if (!periodId) return;

    Swal.fire({
        title: '¿Sellar periodo?',
        text: "Marcarás todos los roles como pagados y no podrás realizar más cambios.",
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#10b981',
        confirmButtonText: 'Sí, sellar ahora'
    }).then((result) => {
        if (result.isConfirmed) {
            fetch(PAYROLL_URLS.seal(periodId), {
                method: 'POST',
                headers: {'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': getPayrollCSRF()}
            })
                .then(safeJsonParse)
                .then(() => {
                    Swal.fire({icon: 'success', title: 'Periodo Cerrado'}).then(() => {
                        window.closeReportModal();
                        location.reload();
                    });
                })
                .catch(err => Swal.fire('Error', err.message, 'error'));
        }
    });
};

/* =================================================================================
   5. RECARGA AJAX DEL PARTIAL DE PERIODOS (Sin parpadeo ni reload de página)
   ================================================================================= */
window.reloadPeriodTable = function () {
    const tableContainer = document.getElementById('period-table-container');
    if (!tableContainer) {
        return;
    }

    const toggleClosedBtn = document.getElementById('toggleClosedPeriods');
    const showClosed = toggleClosedBtn ? toggleClosedBtn.checked : false;
    const url = `${window.location.pathname}?show_closed=${showClosed}`;

    tableContainer.style.opacity = '0.5';

    fetch(url, {
        headers: {'X-Requested-With': 'XMLHttpRequest'}
    })
        .then(response => {
            if (!response.ok) throw new Error('Error al recargar periodos');
            return response.json();
        })
        .then(data => {
            if (data.html) {
                tableContainer.innerHTML = data.html;
            }
            tableContainer.style.opacity = '1';

            // Reinicializar TableManager si está disponible
            try {
                const newTable = tableContainer.querySelector('.managed-table');
                if (newTable && typeof TableManager !== 'undefined') {
                    new TableManager(newTable);
                }
            } catch (e) {
                console.warn('Error reinicializando TableManager:', e);
            }
        })
        .catch(err => {
            console.error('Error actualizando la tabla:', err);
            tableContainer.style.opacity = '1';
        });
};
/* =================================================================================
   6. CARGA MASIVA DE NOVEDADES (EXCEL)
   ================================================================================= */
window.noveltyParsedData = [];

window.toggleRubroSelects = function () {
    const typeSelect = document.getElementById('rubro_type');
    const type = typeSelect ? typeSelect.value.trim().toUpperCase() : '';
    const groupInc = document.getElementById('group_income');
    const groupDed = document.getElementById('group_deduction');
    const inputInc = document.getElementById('income_id');
    const inputDed = document.getElementById('deduction_id');

    if (groupInc) groupInc.classList.add('hidden');
    if (groupDed) groupDed.classList.add('hidden');

    if (inputInc) {
        inputInc.value = '';
        if (window.jQuery && $(inputInc).data('select2')) $(inputInc).val('').trigger('change.select2');
    }
    if (inputDed) {
        inputDed.value = '';
        if (window.jQuery && $(inputDed).data('select2')) $(inputDed).val('').trigger('change.select2');
    }

    if (type === 'INCOME' && groupInc) {
        groupInc.classList.remove('hidden');
    } else if (type === 'DEDUCTION' && groupDed) {
        groupDed.classList.remove('hidden');
    }

    window.checkAndLoad();
};

window.checkAndLoad = function () {
    const periodEl = document.getElementById('period_id');
    const typeEl = document.getElementById('rubro_type');
    const incEl = document.getElementById('income_id');
    const dedEl = document.getElementById('deduction_id');

    const period_id = periodEl ? periodEl.value : '';
    const rubro_type = typeEl ? typeEl.value : '';
    let rubro_id = '';

    if (rubro_type === 'INCOME' && incEl) rubro_id = incEl.value;
    if (rubro_type === 'DEDUCTION' && dedEl) rubro_id = dedEl.value;

    const tbody = document.getElementById('novelty_tbody');
    const tableCard = document.querySelector('.novelty-table-card');
    if (!tbody) return;

    if (tableCard) tableCard.classList.remove('is-saved');

    if (period_id && rubro_type && rubro_id) {
        tbody.innerHTML = '<tr><td colspan="3" class="text-center py-5 text-muted"><i class="fas fa-spinner fa-spin fa-2x mb-2 text-primary"></i><br>Cargando datos guardados...</td></tr>';

        fetch(`${window.NOVELTY_URLS.get}?period_id=${period_id}&rubro_type=${rubro_type}&rubro_id=${rubro_id}`, {
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        })
            .then(res => res.json())
            .then(res => {
                if (res.status === 'success' && res.data && res.data.length > 0) {
                    // Datos recuperados de la base de datos (sin modificaciones pendientes)
                    window.noveltyParsedData = res.data.map(item => ({
                        ...item,
                        isModified: false
                    }));
                    window.renderTable(false, true); // true = verde
                } else {
                    window.noveltyParsedData = [];
                    window.renderTable(true, false);
                }
            })
            .catch(() => {
                window.noveltyParsedData = [];
                window.renderTable(true, false);
            });
    } else {
        window.noveltyParsedData = [];
        window.renderTable(true, false);
    }
};

window.renderTable = function (isEmpty = false, isAllSaved = false) {
    const tbody = document.getElementById('novelty_tbody');
    const tableCard = document.querySelector('.novelty-table-card');
    const btnSave = document.getElementById('btn_save_novelties');
    if (!tbody) return;
    tbody.innerHTML = '';

    if (isEmpty || !window.noveltyParsedData || window.noveltyParsedData.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="3" class="text-muted novelty-empty-cell">
                    <div class="novelty-empty-state">
                        <i class="fas fa-table fa-3x"></i>
                        <span>Selecciona el Periodo y el Rubro para ver los datos.</span>
                        <small>Pon "0" en una celda para eliminar ese descuento.</small>
                    </div>
                </td>
            </tr>`;
        if (btnSave) btnSave.classList.add('hidden');
        if (tableCard) tableCard.classList.remove('is-saved');
        window.updateTotal();
        return;
    }

    // Verificar si queda al menos un registro modificado pendiente
    const hasModifications = window.noveltyParsedData.some(r => r.isModified);
    if (tableCard) {
        if (!hasModifications || isAllSaved) {
            tableCard.classList.add('is-saved');
        } else {
            tableCard.classList.remove('is-saved');
        }
    }

    // Ordenar alfabéticamente por nombres para que los nuevos no queden al final
    window.noveltyParsedData.sort((a, b) => (a.nombres || '').localeCompare(b.nombres || ''));

    window.noveltyParsedData.forEach((row, index) => {
        const tr = document.createElement('tr');
        tr.id = `row-novelty-${index}`;

        // Si se editó o es nuevo = AMARILLO. Si viene de BD y no cambió = VERDE
        if (row.isModified) {
            tr.className = 'row-modified';
        } else {
            tr.className = 'row-saved';
        }

        if (row.valor === 0) {
            tr.style.backgroundColor = '#fef2f2';
        }

        tr.innerHTML = `
            <td class="col-cedula align-middle"><span class="badge-code">${row.cedula}</span></td>
            <td class="col-empleado fw-bold text-secondary text-truncate align-middle" title="${row.nombres}">${row.nombres}</td>
            <td class="col-monto text-end align-middle">
                <input type="number" step="0.01" class="input-field text-end fw-bold"
                       style="width: 95px; padding: 4px 8px; margin: 0; display: inline-block; ${row.valor === 0 ? 'border-color: #ef4444; color: #ef4444;' : ''}"
                       value="${row.valor}"
                       data-index="${index}"
                       oninput="window.updateValue(${index}, this.value)"
                       onchange="window.updateValue(${index}, this.value)">
            </td>`;
        tbody.appendChild(tr);
    });

    if (btnSave) btnSave.classList.remove('hidden');
    window.updateTotal();
    window.filterTableLocal();
};
window.updateValue = function (index, newValue) {
    if (!window.noveltyParsedData || !window.noveltyParsedData[index]) return;

    let val = parseFloat(newValue);
    const numericVal = isNaN(val) || val < 0 ? 0 : parseFloat(val.toFixed(2));

    window.noveltyParsedData[index].valor = numericVal;
    window.noveltyParsedData[index].isModified = true; // Marca el registro como pendiente de guardar

    // Cambiar la fila inmediatamente a amarillo sin redibujar toda la tabla
    const rowEl = document.getElementById(`row-novelty-${index}`);
    if (rowEl) {
        rowEl.classList.remove('row-saved');
        rowEl.classList.add('row-modified');
    }

    window.updateTotal();
};

window.updateTotal = function () {
    const total = window.noveltyParsedData.reduce((sum, row) => sum + (parseFloat(row.valor) || 0), 0);
    const totalEl = document.getElementById('total_sum');
    if (totalEl) {
        const parts = total.toFixed(2).split('.');
        const integerPart = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, '.');
        totalEl.innerText = `$ ${integerPart},${parts[1]}`;
    }
};

window.uploadExcel = function () {
    const period_id = document.getElementById('period_id')?.value;
    const rubro_type = document.getElementById('rubro_type')?.value;
    const income_id = document.getElementById('income_id')?.value;
    const deduction_id = document.getElementById('deduction_id')?.value;
    const fileInput = document.getElementById('excel_file');

    const rubroId = rubro_type === 'INCOME' ? income_id : deduction_id;

    if (!period_id || !rubro_type || !rubroId) {
        Swal.fire('Atención', 'Primero selecciona el Periodo, el Tipo y el Rubro específico.', 'warning');
        return;
    }

    if (!fileInput || !fileInput.files || fileInput.files.length === 0) {
        Swal.fire('Atención', 'Selecciona un archivo Excel (.xlsx)', 'warning');
        return;
    }

    const resetDropzoneUI = () => {
        if (fileInput) fileInput.value = '';
        const zone = document.getElementById('excel_dropzone');
        const label = document.getElementById('excel_file_name');
        if (zone) zone.classList.remove('has-file', 'is-dragover');
        if (label) label.textContent = 'Haz clic o arrastra tu Excel aquí';
        if (typeof window.refreshExcelDropzone === 'function') {
            window.refreshExcelDropzone();
        }
    };

    const processUpload = () => {
        const formData = new FormData();
        formData.append('file', fileInput.files[0]);
        formData.append('rubro_type', rubro_type);
        formData.append('rubro_id', rubroId);

        fetch(window.NOVELTY_URLS.parse, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': getPayrollCSRF()
            }
        })
            .then(safeJsonParse)
            .then(res => {
                if (res.status === 'success') {
                    let actualizados = 0;
                    let agregados = 0;

                    res.data.forEach(newRow => {
                        const parsedVal = parseFloat((parseFloat(newRow.valor) || 0).toFixed(2));
                        const existingIndex = window.noveltyParsedData.findIndex(r => r.emp_id === newRow.emp_id);

                        if (existingIndex >= 0) {
                            // CÉDULA EXISTE: solo si el valor es diferente se marca en amarillo
                            const prevVal = parseFloat((window.noveltyParsedData[existingIndex].valor || 0).toFixed(2));
                            if (prevVal !== parsedVal) {
                                window.noveltyParsedData[existingIndex].valor = parsedVal;
                                window.noveltyParsedData[existingIndex].isModified = true; // Amarillo
                                actualizados++;
                            }
                        } else {
                            // CÉDULA NUEVA: se agrega al arreglo y se marca en amarillo
                            newRow.valor = parsedVal;
                            newRow.isModified = true; // Amarillo
                            window.noveltyParsedData.push(newRow);
                            agregados++;
                        }
                    });

                    // Renderizar tabla: preserva en verde los que no cambiaron y en amarillo los nuevos/editados
                    window.renderTable(false, false);

                    if (res.not_found && res.not_found.length > 0) {
                        Swal.fire({
                            title: 'Advertencia',
                            html: `Se procesó el archivo (${actualizados} modificados, ${agregados} agregados).<br>No se encontraron <b>${res.not_found.length}</b> cédulas en la base de datos.<br><small class="text-muted">Revisa las cédulas no registradas.</small>`,
                            icon: 'warning'
                        });
                    } else {
                        if (typeof showToast === 'function') {
                            showToast(`Excel cargado: ${actualizados} modificados, ${agregados} agregados.`, 'success');
                        }
                    }
                }
                resetDropzoneUI();
            })
            .catch(err => {
                resetDropzoneUI();
                Swal.fire('Error', err.message, 'error');
            });
    };

    // Modal con confirmación directa y limpia (2 botones)
    if (window.noveltyParsedData && window.noveltyParsedData.length > 0) {
        Swal.fire({
            title: '¿Cargar y actualizar novedades?',
            text: 'Las cédulas que ya existan serán sustituidas con el nuevo valor, y los empleados nuevos se agregarán a la lista.',
            icon: 'question',
            showCancelButton: true,
            confirmButtonText: '<i class="fas fa-check me-1"></i> Continuar',
            cancelButtonText: 'Cancelar',
            confirmButtonColor: '#10b981',
            cancelButtonColor: '#64748b'
        }).then((result) => {
            if (result.isConfirmed) {
                processUpload();
            } else {
                resetDropzoneUI();
            }
        });
    } else {
        processUpload();
    }
};
window.saveNovelties = function () {
    const period_id = document.getElementById('period_id')?.value;
    const rubro_type = document.getElementById('rubro_type')?.value;
    const rubro_id = rubro_type === 'INCOME'
        ? document.getElementById('income_id')?.value
        : document.getElementById('deduction_id')?.value;

    if (!period_id || !rubro_type || !rubro_id) {
        Swal.fire('Atención', 'Selecciona el Periodo y el Rubro antes de guardar.', 'warning');
        return;
    }

    const payload = {
        period_id: period_id,
        rubro_type: rubro_type,
        rubro_id: rubro_id,
        items: window.noveltyParsedData
    };

    fetch(window.NOVELTY_URLS.save, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getPayrollCSRF(),
            'X-Requested-With': 'XMLHttpRequest'
        },
        body: JSON.stringify(payload)
    })
        .then(safeJsonParse)
        .then(() => {
            showToast('Novedades guardadas exitosamente.', 'success');

            // Restablecer el estado de modificación de todos los registros y devolverlos a verde
            if (window.noveltyParsedData) {
                window.noveltyParsedData.forEach(row => {
                    row.isModified = false;
                });
            }

            const tableCard = document.querySelector('.novelty-table-card');
            if (tableCard) tableCard.classList.add('is-saved');

            window.renderTable(false, true); // Regresan todas a verde
        })
        .catch(err => Swal.fire('Error', err.message, 'error'));
};
window.deleteAllNovelties = function () {
    const period_id = document.getElementById('period_id')?.value;
    const rubro_type = document.getElementById('rubro_type')?.value;
    const rubro_id = rubro_type === 'INCOME'
        ? document.getElementById('income_id')?.value
        : document.getElementById('deduction_id')?.value;

    if (!period_id || !rubro_type || !rubro_id) {
        Swal.fire('Atención', 'Selecciona el Periodo y el Rubro correspondiente.', 'warning');
        return;
    }

    Swal.fire({
        title: '¿Eliminar todas las novedades?',
        text: 'Se borrarán los valores registrados para este rubro en este periodo.',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: 'Sí, eliminar',
        cancelButtonText: 'Cancelar',
        customClass: {confirmButton: 'swal2-confirm btn-swal-danger'}
    }).then(res => {
        if (res.isConfirmed) {
            const payload = {period_id, rubro_type, rubro_id, items: []};
            fetch(window.NOVELTY_URLS.save, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getPayrollCSRF(),
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify(payload)
            })
                .then(safeJsonParse)
                .then(() => {
                    showToast('Registros eliminados.', 'success');
                    window.checkAndLoad();
                })
                .catch(err => Swal.fire('Error', err.message, 'error'));
        }
    });
};
window.exportNoveltiesToExcel = function () {
    const periodSelect = document.getElementById('period_id');
    const period_name = periodSelect && periodSelect.options[periodSelect.selectedIndex]
        ? periodSelect.options[periodSelect.selectedIndex].text.trim()
        : '';
    const rubroTypeEl = document.getElementById('rubro_type');
    const rubro_type = rubroTypeEl ? rubroTypeEl.value : '';

    if (!rubro_type) {
        Swal.fire('Atención', 'Primero selecciona el Tipo y el Rubro para poder descargar.', 'warning');
        return;
    }

    const selectEl = rubro_type === 'INCOME'
        ? document.getElementById('income_id')
        : document.getElementById('deduction_id');
    const rubro_name = selectEl && selectEl.options[selectEl.selectedIndex]
        ? selectEl.options[selectEl.selectedIndex].text.trim()
        : 'Reporte';

    if (!window.noveltyParsedData || window.noveltyParsedData.length === 0) {
        Swal.fire('Atención', 'No hay datos en la tabla para exportar.', 'info');
        return;
    }

    const valorColLabel = rubro_type === 'INCOME' ? 'Ingreso ($)' : 'Descuento ($)';

    let excelHtml = `
        <html xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:x="urn:schemas-microsoft-com:office:excel" xmlns="http://www.w3.org/TR/REC-html40">
        <head><meta charset="utf-8"></head>
        <body>
            <table>
                <tr><td colspan="3" style="font-size: 14pt; font-weight: bold; text-align: center; font-family: Arial, sans-serif;">${rubro_name.toUpperCase()}</td></tr>
                <tr><td colspan="3" style="font-size: 10pt; color: #475569; text-align: center; font-family: Arial, sans-serif; font-weight: bold;">PERIODO: ${period_name}</td></tr>
                <tr><td colspan="3"></td></tr>
                <thead>
                    <tr style="background-color: #f1f5f9; font-weight: bold; font-family: Arial, sans-serif; font-size: 10pt;">
                        <th style="border: 1px solid #cbd5e1; padding: 6px; text-align: left;">Cédula</th>
                        <th style="border: 1px solid #cbd5e1; padding: 6px; text-align: left;">Nombres y Apellidos</th>
                        <th style="border: 1px solid #cbd5e1; padding: 6px; text-align: right;">${valorColLabel}</th>
                    </tr>
                </thead>
                <tbody style="font-family: Arial, sans-serif; font-size: 9.5pt;">`;

    window.noveltyParsedData.forEach(row => {
        excelHtml += `
            <tr>
                <td style="border: 1px solid #e2e8f0; padding: 4px; mso-number-format:'\\@';">${row.cedula}</td>
                <td style="border: 1px solid #e2e8f0; padding: 4px;">${row.nombres}</td>
                <td style="border: 1px solid #e2e8f0; padding: 4px; text-align: right;">${parseFloat(row.valor || 0).toFixed(2)}</td>
            </tr>`;
    });

    excelHtml += `</tbody></table></body></html>`;

    const blob = new Blob([excelHtml], {type: 'application/vnd.ms-excel;charset=utf-8;'});
    const link = document.createElement("a");
    const cleanRubroName = rubro_name.replace(/[^a-zA-Z0-9]/g, "_");
    const cleanPeriodName = period_name.replace(/[^a-zA-Z0-9]/g, "_");

    link.href = URL.createObjectURL(blob);
    link.setAttribute("download", `Reporte_${cleanRubroName}_${cleanPeriodName}.xls`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
};
window.filterTableLocal = function () {
    const term = (document.getElementById('searchTable')?.value || '').toLowerCase();
    const rows = document.querySelectorAll('#novelty_tbody tr');
    rows.forEach(row => {
        const text = row.textContent.toLowerCase();
        row.style.display = text.includes(term) ? '' : 'none';
    });
};

window.initNoveltyEvents = function () {
    const rubroTypeSelect = document.getElementById('rubro_type');
    const incomeSelect = document.getElementById('income_id');
    const deductionSelect = document.getElementById('deduction_id');
    const periodSelect = document.getElementById('period_id');

    if (rubroTypeSelect) {
        rubroTypeSelect.addEventListener('change', window.toggleRubroSelects);
        if (window.jQuery) $(rubroTypeSelect).on('change change.select2', window.toggleRubroSelects);
    }
    if (incomeSelect) {
        incomeSelect.addEventListener('change', window.checkAndLoad);
        if (window.jQuery) $(incomeSelect).on('change change.select2', window.checkAndLoad);
    }
    if (deductionSelect) {
        deductionSelect.addEventListener('change', window.checkAndLoad);
        if (window.jQuery) $(deductionSelect).on('change change.select2', window.checkAndLoad);
    }
    if (periodSelect) {
        periodSelect.addEventListener('change', window.checkAndLoad);
        if (window.jQuery) $(periodSelect).on('change change.select2', window.checkAndLoad);
    }

    if (periodSelect && periodSelect.value) {
        window.checkAndLoad();
    }
};
/* =================================================================================
   7. LISTADO Y BÚSQUEDA DE ROLES (PAYSLIP LIST)
   ================================================================================= */
(function () {
    const container = document.getElementById('payslip-table-container');
    const searchInput = document.getElementById('searchInput');
    const regimeFilter = document.getElementById('regimeFilter');
    if (!container || !searchInput) return;

    let debounceTimer = null;

    function initPaginationControls(root) {
        const pagination = (root || document).querySelector('#js-pagination');
        if (!pagination) return;

        pagination.querySelectorAll('[data-page]').forEach(btn => {
            btn.onclick = function (e) {
                e.preventDefault();
                const page = this.getAttribute('data-page');
                if (page) performPayslipSearch({page: Number(page)});
            };
        });

        const pageInput = pagination.querySelector('#page-input');
        if (pageInput) {
            const submit = () => {
                const p = parseInt(pageInput.value.trim(), 10) || 1;
                performPayslipSearch({page: p});
            };
            pageInput.onkeypress = (e) => {
                if (e.key === 'Enter') submit();
            };
            pageInput.onblur = submit;
        }
    }

    function performPayslipSearch(options = {}) {
        const periodId = window.CURRENT_PERIOD_ID || new URLSearchParams(window.location.search).get('period_id');
        if (!periodId) return;

        const checkbox = document.getElementById('toggleWithheld');
        const showWithheld = checkbox && checkbox.checked ? 'only' : 'exclude';

        const params = new URLSearchParams({
            period_id: periodId,
            q: searchInput.value.trim(),
            regime: regimeFilter ? regimeFilter.value : '',
            show_withheld: showWithheld,
            page: options.page || 1
        });

        container.style.opacity = '0.5';

        fetch(`${window.URLS.baseList}?${params.toString()}`, {
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        })
            .then(res => res.json())
            .then(data => {
                container.innerHTML = data.html;
                container.style.opacity = '1';

                if (data.total_roles !== undefined) {
                    const el = document.getElementById('total-roles');
                    if (el) el.innerText = data.total_roles;
                }
                if (data.total_liquidado !== undefined) {
                    const el2 = document.getElementById('total-liquidado');
                    if (el2) el2.innerText = `$ ${parseFloat(data.total_liquidado || 0).toLocaleString('es-EC', {
                        minimumFractionDigits: 2,
                        maximumFractionDigits: 2
                    })}`;
                }

                initPaginationControls(container);
            })
            .catch(() => {
                container.style.opacity = '1';
            });
    }

    // Escuchadores del buscador con debounce
    searchInput.addEventListener('input', () => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => performPayslipSearch({page: 1}), 300);
    });

    searchInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            clearTimeout(debounceTimer);
            performPayslipSearch({page: 1});
        }
    });

    if (regimeFilter) {
        regimeFilter.addEventListener('change', () => performPayslipSearch({page: 1}));
    }

    window.performSearchWithOptions = () => performPayslipSearch({page: 1});

    // Delegación para switches de retención
    container.addEventListener('change', (e) => {
        const target = e.target;
        if (target && target.classList.contains('toggle-withhold-btn')) {
            const payslipId = target.dataset.id;
            const textSpan = target.nextElementSibling?.querySelector('.switch-text');
            const checked = target.checked;

            fetch(`/payroll/payslips/${payslipId}/toggle-withhold/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getPayrollCSRF(),
                    'X-Requested-With': 'XMLHttpRequest'
                }
            })
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        if (textSpan) textSpan.textContent = data.is_withheld ? 'Retenido' : 'Normal';
                    } else {
                        target.checked = !checked;
                        if (textSpan) textSpan.textContent = !checked ? 'Retenido' : 'Normal';
                    }
                })
                .catch(() => {
                    target.checked = !checked;
                });
        }
    });

    initPaginationControls(container);
})();

window.downloadFilteredReport = function (type) {
    const searchInput = document.getElementById('searchInput');
    const regimeFilter = document.getElementById('regimeFilter');
    const checkbox = document.getElementById('toggleWithheld');

    const periodId = window.CURRENT_PERIOD_ID || new URLSearchParams(window.location.search).get('period_id');
    if (!periodId) return alert('Seleccione un periodo.');

    const q = searchInput ? searchInput.value.trim() : '';
    const regime = regimeFilter ? regimeFilter.value : '';
    const show_withheld = checkbox && checkbox.checked ? 'only' : 'exclude';

    let url = '';
    if (type === 'banco') {
        url = `/payroll/reports/bank/${periodId}/?q=${encodeURIComponent(q)}&regime=${encodeURIComponent(regime)}&show_withheld=${show_withheld}`;
    } else if (type === 'negativos') {
        url = `/payroll/reports/negative-balances/${periodId}/`;
    } else {
        url = `/payroll/reports/grouped/${periodId}/?q=${encodeURIComponent(q)}&regime=${encodeURIComponent(regime)}&show_withheld=${show_withheld}`;
    }

    window.open(url, '_blank');
};
/* =================================================================================
   8. ACCIONES DE ROLES (Recálculo filtrado, Ver Detalle y Envío por Correo)
   ================================================================================= */
window.recalculateCurrentFilter = function () {
    const periodId = window.CURRENT_PERIOD_ID || new URLSearchParams(window.location.search).get('period_id');
    if (!periodId) return Swal.fire('Atención', 'Periodo no definido', 'warning');

    const searchInput = document.getElementById('searchInput');
    const regimeFilter = document.getElementById('regimeFilter');
    const checkbox = document.getElementById('toggleWithheld');

    const q = searchInput ? searchInput.value.trim() : '';
    const regime = regimeFilter ? regimeFilter.value : '';
    const show_withheld = checkbox && checkbox.checked ? 'only' : '';

    Swal.fire({
        title: '¿Recalcular roles filtrados?',
        text: 'Se actualizarán las fórmulas y sueldos para los roles visibles en este filtro.',
        icon: 'question',
        showCancelButton: true,
        confirmButtonText: '<i class="fas fa-sync-alt me-1"></i> Sí, recalcular',
        cancelButtonText: 'Cancelar',
        confirmButtonColor: '#10b981'
    }).then(result => {
        if (result.isConfirmed) {
            Swal.fire({
                title: 'Recalculando Nómina...',
                allowOutsideClick: false,
                didOpen: () => Swal.showLoading()
            });

            const formData = new FormData();
            formData.append('period_id', periodId);
            formData.append('q', q);
            formData.append('regime', regime);
            formData.append('show_withheld', show_withheld);

            // CORREGIDO: Ruta exacta registrada en urls.py
            fetch('/payroll/payslips/recalculate/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getPayrollCSRF(),
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: formData
            })
                .then(safeJsonParse)
                .then(data => {
                    Swal.fire({
                        icon: 'success',
                        title: '¡Completado!',
                        text: data.message || 'Roles recalculados correctamente.',
                        timer: 2000,
                        showConfirmButton: false
                    }).then(() => {
                        if (typeof window.performSearchWithOptions === 'function') {
                            window.performSearchWithOptions();
                        } else {
                            location.reload();
                        }
                    });
                })
                .catch(err => Swal.fire('Error', err.message, 'error'));
        }
    });
};

window.openPayslipDetail = function (url) {
    if (typeof openAjaxModal === 'function') {
        openAjaxModal(url);
    } else {
        fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
            .then(res => res.text())
            .then(html => {
                const root = document.getElementById('modal-root') || document.body;
                root.innerHTML = html;
                const modal = root.querySelector('.modal-overlay');
                if (modal) {
                    modal.style.display = 'flex';
                }
            });
    }
};

window.sendPayslipEmail = function (payslipId) {
    Swal.fire({
        title: '¿Enviar rol por correo institucional?',
        text: 'Se generará el archivo oficial en PDF con código QR y se enviará a la cuenta de correo del funcionario.',
        icon: 'question',
        showCancelButton: true,
        confirmButtonText: '<i class="fas fa-paper-plane me-1"></i> Enviar Correo',
        cancelButtonText: 'Cancelar',
        confirmButtonColor: '#eab308'
    }).then(res => {
        if (res.isConfirmed) {
            Swal.fire({
                title: 'Enviando notificación...',
                text: 'Generando PDF y conectando con el servidor de correo...',
                allowOutsideClick: false,
                didOpen: () => Swal.showLoading()
            });

            // CORREGIDO: Ruta en plural 'payslips' según urls.py
            fetch(`/payroll/payslips/${payslipId}/send-email/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getPayrollCSRF(),
                    'X-Requested-With': 'XMLHttpRequest'
                }
            })
                .then(safeJsonParse)
                .then(data => {
                    Swal.fire({
                        icon: 'success',
                        title: '¡Enviado!',
                        text: data.message || 'Notificación enviada correctamente al funcionario.'
                    });
                })
                .catch(err => Swal.fire('Error al enviar', err.message, 'error'));
        }
    });
};
/* =================================================================================
   9. DELEGACIÓN DE EVENTOS GLOBAL
   ================================================================================= */
document.addEventListener('click', (e) => {
    const btnGen = e.target.closest('[data-generate-id]');
    if (btnGen) {
        e.preventDefault();
        window.openGenerateModal(
            btnGen.getAttribute('data-generate-id'),
            btnGen.getAttribute('data-generate-name'),
            btnGen.getAttribute('data-has-scope-changes') === 'true'
        );
    }

    const btnRep = e.target.closest('[data-report-id]');
    if (btnRep) {
        e.preventDefault();
        window.openReportModal(
            btnRep.getAttribute('data-report-id'),
            btnRep.getAttribute('data-report-name'),
            btnRep.getAttribute('data-report-closed') === 'true'
        );
    }
});
window.uploadMassExcel = function (input, url, label) {
    if (!input.files || !input.files[0]) return;

    const file = input.files[0];
    const formData = new FormData();
    formData.append('file', file);

    Swal.fire({
        title: `Procesando ${label}`,
        text: 'Leyendo archivo Excel y actualizando nómina...',
        allowOutsideClick: false,
        didOpen: () => Swal.showLoading()
    });

    fetch(url, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getPayrollCSRF(),
            'X-Requested-With': 'XMLHttpRequest'
        },
        body: formData
    })
        .then(safeJsonParse)
        .then(data => {
            showToast(data.message || 'Configuración actualizada exitosamente.', 'success');
            if (typeof refreshCurrentTable === 'function') {
                refreshCurrentTable();
            } else {
                location.reload();
            }
        })
        .catch(err => {
            Swal.fire({
                icon: 'error',
                title: 'Error al procesar archivo',
                text: err.message || 'Ocurrió un error inesperado al subir el Excel.'
            });
        })
        .finally(() => {
            input.value = '';
        });
};