/**
 * PAYROLL.JS - GESTIÓN INTEGRAL DEL MÓDULO DE NÓMINA Y RRHH
 * Unificación de: Periodos, Generación, Modales, Roles (Payslips), Fondos de Reserva y Rubros.
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

async function safeJsonParse(response) {
    const contentType = response.headers.get('content-type');
    if (contentType && contentType.includes('text/html')) throw new Error('Error: El servidor devolvió HTML (Posible error 500).');
    const data = await response.json();
    if (!response.ok || (data.status === 'error' || data.success === false)) throw new Error(data.message || 'Error interno.');
    return data;
}

/* =================================================================================
   1. MODALES ESTÁTICOS DE NÓMINA (Generar y Sellar)
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
        document.getElementById('generate-options').style.display = 'block';
        document.getElementById('generate-loading').style.display = 'none';
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
   2. MOTOR DE PROCESAMIENTO Y RECALCULO DE ROLES
   ================================================================================= */
window.submitGenerate = function (mode) {
    const periodId = window.currentGenPeriodId;
    if (!periodId) return;

    document.getElementById('generate-options').style.display = 'none';
    document.getElementById('generate-loading').style.display = 'block';

    const formData = new FormData();
    formData.append('period_id', periodId);
    let targetUrl = PAYROLL_URLS.recalculate;

    if (mode === 'missing') targetUrl = PAYROLL_URLS.syncMissing;
    else if (mode === 'scope') formData.append('scope', 'true');

    fetch(targetUrl, {
        method: 'POST', body: formData,
        headers: {'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': getCSRF()}
    })
        .then(safeJsonParse)
        .then(data => {
            if (data.task_id) startGenerationPolling(data.task_id);
            else handleGenerationSuccess(data.message || 'Proceso completado.');
        })
        .catch(err => {
            window.closeGenerateModal();
            Swal.fire({icon: 'error', title: 'Error', text: err.message, scrollbarPadding: false, heightAuto: false});
        });
};

function startGenerationPolling(taskId) {
    Swal.fire({
        title: 'Calculando Nómina',
        html: `<div id="poll-msg">Iniciando proceso asíncrono...</div>`,
        allowOutsideClick: false, showConfirmButton: false, scrollbarPadding: false, heightAuto: false,
        didOpen: () => Swal.showLoading()
    });

    const poll = () => {
        fetch(`${PAYROLL_URLS.status}?task_id=${taskId}`)
            .then(safeJsonParse)
            .then(res => {
                if (res.done || res.status === 'SUCCESS' || res.success) {
                    handleGenerationSuccess(res.message || 'Nómina generada.');
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
        icon: 'success', title: '¡Éxito!', text: message, timer: 2000,
        showConfirmButton: false, scrollbarPadding: false, heightAuto: false
    }).then(() => {
        window.closeGenerateModal();
        if (window.reloadTableData) window.reloadTableData(PAYROLL_URLS.tableList, '#period-table-container');
    });
}

window.sellarComoPagados = function () {
    const periodId = window.currentGenPeriodId;
    if (!periodId) return;

    Swal.fire({
        title: '¿Sellar periodo?',
        text: "Marcarás todos los roles como pagados y no podrás realizar más cambios.",
        icon: 'warning', showCancelButton: true, confirmButtonColor: '#10b981',
        confirmButtonText: 'Sí, sellar ahora', scrollbarPadding: false, heightAuto: false
    }).then((result) => {
        if (result.isConfirmed) {
            fetch(PAYROLL_URLS.seal(periodId), {
                method: 'POST', headers: {'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': getCSRF()}
            })
                .then(safeJsonParse)
                .then(() => {
                    Swal.fire({
                        icon: 'success',
                        title: 'Periodo Cerrado',
                        scrollbarPadding: false,
                        heightAuto: false
                    }).then(() => {
                        window.closeReportModal();
                        if (window.reloadTableData) window.reloadTableData(PAYROLL_URLS.tableList, '#period-table-container');
                    });
                })
                .catch(err => Swal.fire('Error', err.message, 'error'));
        }
    });
};

/* =================================================================================
   3. INICIALIZADORES DE MODALES (Rubros y Periodos)
   ================================================================================= */

window.initializePeriodModal = function (root) {
    const monthSelect = root.querySelector('[name="month"]');
    const yearInput = root.querySelector('[name="year"]');
    const startDateInput = root.querySelector('[name="start_date"]');
    const endDateInput = root.querySelector('[name="end_date"]');
    const workingDaysInput = root.querySelector('[name="working_days"]');
    const submitBtn = root.querySelector('button[type="submit"]');

    if (!monthSelect || !yearInput) return;

    async function calculate() {
        const month = monthSelect.value;
        const year = yearInput.value;
        if (!month || !year || year.length !== 4) return;
        if (submitBtn) submitBtn.disabled = true;

        try {
            const url = `${PAYROLL_URLS.calculate}?month=${month}&year=${year}`;
            const response = await fetch(url);
            const data = await safeJsonParse(response);

            if (data.status === 'success') {
                if (startDateInput) startDateInput.value = data.start_date;
                if (endDateInput) endDateInput.value = data.end_date;
                if (workingDaysInput) workingDaysInput.value = data.working_days;

                if (data.warning || data.info) {
                    Swal.fire({
                        title: data.warning ? 'Feriados' : 'Info',
                        text: data.warning || data.info,
                        icon: data.warning ? 'warning' : 'info',
                        scrollbarPadding: false, heightAuto: false
                    });
                }
            }
        } catch (e) {
            console.error("Error:", e);
        } finally {
            if (submitBtn) submitBtn.disabled = false;
        }
    }

    $(monthSelect).on('change.select2', calculate);
    yearInput.addEventListener('change', calculate);
    yearInput.addEventListener('input', function () {
        this.value = this.value.replace(/[^0-9]/g, '').slice(0, 4);
        if (this.value.length === 4) calculate();
    });
    setTimeout(calculate, 300);
};

// LA MAGIA DE LOS RUBROS
window.initializeRubricModal = function (root) {
    const $typeSelect = $(root).find('select[name="rubric_type"]');

    const divPriority = root.querySelector('#divPriority');
    const divIncomeSwitches = root.querySelector('#divIncomeSwitches');
    const divOrder = root.querySelector('#divOrder');
    const divName = root.querySelector('#divName'); // Capturamos el contenedor del Nombre

    function toggleRubricFields() {
        if (!$typeSelect.length) return;
        const val = ($typeSelect.val() || '').toUpperCase();

        // 1. Ocultar todos los campos dinámicos por defecto
        if (divPriority) divPriority.classList.add('hidden-field');
        if (divIncomeSwitches) divIncomeSwitches.classList.add('hidden-field');

        // 2. Restaurar tamaños base de la grilla (Nombre al 66%, Prioridad oculta al 33%)
        if (divName) divName.className = 'col-md-8 form-group';
        if (divPriority) divPriority.className = 'col-md-4 form-group hidden-field';
        if (divOrder) divOrder.className = 'col-md-4 form-group';

        // 3. Mostrar u Ocultar según la selección
        if (val.includes('INCOME') || val === 'INGRESO' || val === '1') {
            // Es Ingreso: Mostrar bloque de 3 switches
            if (divIncomeSwitches) divIncomeSwitches.classList.remove('hidden-field');
        } else if (val.includes('DEDUCTION') || val === 'DESCUENTO' || val === '2') {
            // Es Descuento: Mostramos la prioridad y encogemos el nombre
            if (divPriority) {
                divPriority.classList.remove('hidden-field');
            }
            if (divName) {
                divName.className = 'col-md-4 form-group'; // Encogemos a 33.33%
            }
        }
        // Si es Aporte, se queda como el default (Nombre al 66.67%, lo demás oculto)
    }

    if ($typeSelect.length) {
        $typeSelect.on('change.select2 change', toggleRubricFields);
        setTimeout(toggleRubricFields, 100);
    }
};
/* =================================================================================
   4. LÓGICA DE FONDOS DE RESERVA
   ================================================================================= */
document.addEventListener('change', function (e) {
    const input = e.target;
    if (!input.classList.contains('fr-checkbox')) return;

    const personId = input.dataset.personId;
    const field = input.dataset.field;
    if (!personId || !field) return;

    const wrapper = document.querySelector(`label[for="${input.id || ''}"]`);
    const textEl = wrapper && wrapper.querySelector('.modern-toggle-text');
    const checked = input.checked;

    if (checked) {
        if (wrapper) wrapper.classList.add('modern-toggle-green');
        if (textEl) textEl.textContent = 'Mensualiza';
    } else {
        if (wrapper) wrapper.classList.remove('modern-toggle-green');
        if (textEl) textEl.textContent = 'Acumula';
    }

    const infoUrl = `/employee/person/${personId}/get-payroll-info/`;
    const url = input.dataset.updateUrl || `/employee/person/${personId}/update-payroll-info/`;

    fetch(infoUrl, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
        .then(r => r.json())
        .then(infoResp => {
            const current = (infoResp && infoResp.data) ? infoResp.data : {};
            const formData = new FormData();

            const monthly = (field === 'monthly_payment') ? checked : !!current.monthly_payment;
            const reserve = (field === 'reserve_funds' || field === 'fondos_reserva') ? checked : !!current.reserve_funds;

            if (monthly) formData.append('monthly_payment', 'on');
            if (reserve) formData.append('reserve_funds', 'on');

            if (typeof current.family_dependents !== 'undefined') formData.append('family_dependents', String(current.family_dependents));
            if (typeof current.education_dependents !== 'undefined') formData.append('education_dependents', String(current.education_dependents));

            return fetch(url, {
                method: 'POST', body: formData,
                headers: {'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': getCSRF()}
            });
        })
        .then(resp => resp.json())
        .then(data => {
            if (!data || data.success === false) {
                input.checked = !checked; // Rollback visual
                Swal.fire('Error', data.message || 'No se pudo actualizar.', 'error');
            }
        }).catch(err => {
        input.checked = !checked;
        Swal.fire('Error', 'Error de comunicación', 'error');
    });
});

/* =================================================================================
   5. DELEGACIÓN DE EVENTOS GLOBAL
   ================================================================================= */
document.addEventListener('click', function (e) {
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
/* =================================================================================
   6. CARGA MASIVA DE NOVEDADES (EXCEL)
   ================================================================================= */
window.noveltyParsedData = [];

window.toggleRubroSelects = function () {
    const type = document.getElementById('rubro_type').value;
    const groupInc = document.getElementById('group_income');
    const groupDed = document.getElementById('group_deduction');

    if (groupInc) groupInc.classList.add('hidden');
    if (groupDed) groupDed.classList.add('hidden');

    document.getElementById('income_id').value = '';
    document.getElementById('deduction_id').value = '';

    if (type === 'INCOME' && groupInc) groupInc.classList.remove('hidden');
    if (type === 'DEDUCTION' && groupDed) groupDed.classList.remove('hidden');

    window.checkAndLoad();
};

window.checkAndLoad = function () {
    const period_id = document.getElementById('period_id').value;
    const rubro_type = document.getElementById('rubro_type').value;
    let rubro_id = null;

    if (rubro_type === 'INCOME') rubro_id = document.getElementById('income_id').value;
    if (rubro_type === 'DEDUCTION') rubro_id = document.getElementById('deduction_id').value;

    if (period_id && rubro_type && rubro_id) {
        document.getElementById('novelty_tbody').innerHTML = '<tr><td colspan="3" class="text-center py-5 text-muted"><i class="fas fa-spinner fa-spin fa-2x mb-2"></i><br>Cargando datos guardados...</td></tr>';

        fetch(`${window.NOVELTY_URLS.get}?period_id=${period_id}&rubro_type=${rubro_type}&rubro_id=${rubro_id}`)
            .then(res => res.json())
            .then(res => {
                if (res.status === 'success') {
                    window.noveltyParsedData = res.data;
                    window.renderTable();
                }
            });
    } else {
        window.noveltyParsedData = [];
        window.renderTable(true);
    }
};

window.uploadExcel = function () {
    const period_id = document.getElementById('period_id').value;
    const rubro_type = document.getElementById('rubro_type').value;
    const fileInput = document.getElementById('excel_file');

    if (!period_id || !rubro_type || (!document.getElementById('income_id').value && !document.getElementById('deduction_id').value)) {
        Swal.fire('Atención', 'Primero selecciona el Tipo y el Rubro en la configuración.', 'warning');
        return;
    }

    if (fileInput.files.length === 0) {
        Swal.fire('Error', 'Selecciona un archivo Excel', 'warning');
        return;
    }

    const doUpload = (mergeMode) => {
        const formData = new FormData();
        formData.append('file', fileInput.files[0]);
        const rubroId = rubro_type === 'INCOME' ? document.getElementById('income_id').value : document.getElementById('deduction_id').value;
        formData.append('rubro_type', rubro_type);
        formData.append('rubro_id', rubroId);

        fetch(window.NOVELTY_URLS.parse, {
            method: 'POST',
            body: formData,
            headers: {'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': getCSRF()}
        })
            .then(response => response.json())
            .then(res => {
                if (res.status === 'success') {
                    res.data.forEach(newRow => {
                        const existingIndex = window.noveltyParsedData.findIndex(r => r.emp_id === newRow.emp_id);
                        if (existingIndex >= 0) {
                            if (mergeMode === 'add') {
                                const current = parseFloat(window.noveltyParsedData[existingIndex].valor) || 0;
                                const incoming = parseFloat(newRow.valor) || 0;
                                window.noveltyParsedData[existingIndex].valor = parseFloat((current + incoming).toFixed(2));
                            } else {
                                window.noveltyParsedData[existingIndex].valor = parseFloat((parseFloat(newRow.valor) || 0).toFixed(2));
                            }
                        } else {
                            newRow.valor = parseFloat((parseFloat(newRow.valor) || 0).toFixed(2));
                            window.noveltyParsedData.push(newRow);
                        }
                    });

                    window.renderTable();

                    if (res.not_found.length > 0) {
                        const cedulasFaltantes = res.not_found.join(', ');
                        Swal.fire({
                            title: 'Advertencia',
                            html: `No se encontraron <b>${res.not_found.length}</b> cédulas del Excel en la base de datos:<br><br>
                               <div style="max-height: 120px; overflow-y: auto; background-color: #f8fafc; padding: 10px; border-radius: 6px; font-size: 0.95rem; color: #334155; border: 1px dashed #cbd5e1; text-align: justify; word-wrap: break-word;">
                                  ${cedulasFaltantes}
                               </div>
                               <br><small style="color: #64748b;">Los demás registros sí se cargaron correctamente en la tabla.</small>`,
                            icon: 'warning',
                            confirmButtonColor: '#3b82f6'
                        });
                    } else {
                        Swal.fire({
                            toast: true, position: 'top-end', icon: 'success',
                            title: mergeMode === 'add' ? 'Excel adicionado con éxito' : 'Excel reemplazado con éxito',
                            showConfirmButton: false, timer: 2000
                        });
                    }
                } else {
                    Swal.fire('Error', res.message, 'error');
                }
                fileInput.value = '';
            });
    };

    if (window.noveltyParsedData.length > 0) {
        Swal.fire({
            title: '¿Cómo deseas cargar el nuevo Excel?',
            text: 'Reemplazar: sustituye valores existentes. Adicionar: suma por cédula.',
            icon: 'question',
            showCancelButton: true, showDenyButton: true,
            confirmButtonText: 'Reemplazar todo', denyButtonText: 'Adicionar', cancelButtonText: 'Cancelar'
        }).then((result) => {
            if (result.isConfirmed) doUpload('replace');
            else if (result.isDenied) doUpload('add');
            else fileInput.value = '';
        });
    } else {
        doUpload('replace');
    }
};

window.renderTable = function (isEmpty = false) {
    const tbody = document.getElementById('novelty_tbody');
    if (!tbody) return;
    tbody.innerHTML = '';

    if (isEmpty || window.noveltyParsedData.length === 0) {
        tbody.innerHTML = '<tr><td colspan="3" class="text-center py-5 text-muted">No hay datos para este rubro. Puedes subir un Excel para agregar.</td></tr>';
        document.getElementById('btn_save_novelties').classList.add('hidden');
        window.updateTotal();
        return;
    }

    window.noveltyParsedData.forEach((row, index) => {
        const tr = document.createElement('tr');
        if (row.valor === 0) tr.style.backgroundColor = '#fef2f2';

        tr.innerHTML = `
        <td class="text-truncate" style="padding: 6px 15px; vertical-align: middle;"><span class="badge-code">${row.cedula}</span></td>
        <td class="fw-bold text-secondary text-truncate" title="${row.nombres}" style="font-size: 0.85rem; padding: 6px 15px; vertical-align: middle;">${row.nombres}</td>
        <td class="text-end" style="padding: 4px 15px; vertical-align: middle;">
            <input type="number" step="0.01" class="input-field text-end fw-bold"
                   style="width: 85px; padding: 4px 8px; margin: 0; height: auto; display: inline-block; ${row.valor === 0 ? 'border-color: #ef4444; color: #ef4444;' : 'color: #0f4c81;'}"
                   value="${row.valor}" 
                   onchange="window.updateValue(${index}, this.value)"
                   onkeyup="window.updateValue(${index}, this.value)">
        </td>`;
        tbody.appendChild(tr);
    });

    document.getElementById('btn_save_novelties').classList.remove('hidden');
    window.updateTotal();
    window.filterTableLocal();
};

window.updateValue = function (index, newValue) {
    let val = parseFloat(newValue);
    window.noveltyParsedData[index].valor = isNaN(val) || val < 0 ? 0 : val;
    window.renderTable();
};

window.updateTotal = function () {
    const total = window.noveltyParsedData.reduce((sum, row) => sum + (parseFloat(row.valor) || 0), 0);
    const totalEl = document.getElementById('total_sum');
    if (totalEl) {
        const parts = total.toFixed(2).split('.');
        const integerPart = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, '.');
        const decimalPart = parts[1];

        totalEl.innerText = `$ ${integerPart},${decimalPart}`;
    }
};

window.saveNovelties = function () {
    const period_id = document.getElementById('period_id').value;
    const rubro_type = document.getElementById('rubro_type').value;
    let rubro_id = rubro_type === 'INCOME' ? document.getElementById('income_id').value : document.getElementById('deduction_id').value;

    const payload = {
        period_id: period_id, rubro_type: rubro_type, rubro_id: rubro_id,
        items: window.noveltyParsedData
    };

    fetch(window.NOVELTY_URLS.save, {
        method: 'POST',
        headers: {'Content-Type': 'application/json', 'X-CSRFToken': getCSRF(), 'X-Requested-With': 'XMLHttpRequest'},
        body: JSON.stringify(payload)
    })
        .then(response => response.json())
        .then(res => {
            if (res.status === 'success') {
                Swal.fire('¡Guardado!', 'Los datos se aplicarán la próxima vez que generes el Rol de este periodo.', 'success')
                    .then(() => window.checkAndLoad());
            } else {
                Swal.fire('Error', res.message, 'error');
            }
        });
};

window.deleteAllNovelties = function () {
    const period_id = document.getElementById('period_id').value;
    const rubro_type = document.getElementById('rubro_type').value;
    let rubro_id = rubro_type === 'INCOME' ? document.getElementById('income_id').value : document.getElementById('deduction_id').value;

    if (!period_id || !rubro_type || !rubro_id) {
        Swal.fire('Atención', 'Primero selecciona el Periodo, el Tipo y el Rubro.', 'warning');
        return;
    }

    if (window.noveltyParsedData.length === 0) {
        Swal.fire('Atención', 'No hay datos cargados para eliminar.', 'info');
        return;
    }

    Swal.fire({
        title: '¿Estás seguro?',
        text: "Se eliminarán TODAS las novedades de este rubro para este periodo en la base de datos. ¡Esta acción no se puede deshacer!",
        icon: 'warning', showCancelButton: true, confirmButtonColor: '#ef4444',
        cancelButtonColor: '#64748b', confirmButtonText: '<i class="fas fa-trash-alt"></i> Sí, eliminar todo',
        cancelButtonText: 'Cancelar'
    }).then((result) => {
        if (result.isConfirmed) {
            const payload = {period_id: period_id, rubro_type: rubro_type, rubro_id: rubro_id, items: []};

            Swal.fire({title: 'Eliminando registros...', allowOutsideClick: false, didOpen: () => Swal.showLoading()});

            fetch(window.NOVELTY_URLS.save, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCSRF(),
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify(payload)
            })
                .then(response => response.json())
                .then(res => {
                    if (res.status === 'success') {
                        Swal.fire('¡Eliminado!', 'Se han limpiado todos los registros de este rubro.', 'success')
                            .then(() => window.checkAndLoad());
                    } else {
                        Swal.fire('Error', res.message, 'error');
                    }
                }).catch(err => Swal.fire('Error', 'Ocurrió un problema de conexión.', 'error'));
        }
    });
};

window.exportNoveltiesToExcel = function () {
    const periodSelect = document.getElementById('period_id');
    const period_name = periodSelect.options[periodSelect.selectedIndex]?.text || '';
    const rubro_type = document.getElementById('rubro_type').value;

    if (!rubro_type) {
        Swal.fire('Atención', 'Primero selecciona el Tipo y el Rubro para poder descargar.', 'warning');
        return;
    }

    const selectEl = rubro_type === 'INCOME' ? document.getElementById('income_id') : document.getElementById('deduction_id');
    const rubro_name = selectEl.options[selectEl.selectedIndex]?.text || 'Reporte';

    if (window.noveltyParsedData.length === 0) {
        Swal.fire('Atención', 'No hay datos en la tabla para exportar.', 'info');
        return;
    }

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
                        <th style="border: 1px solid #cbd5e1; padding: 6px; text-align: right;">Descuento ($)</th>
                    </tr>
                </thead>
                <tbody style="font-family: Arial, sans-serif; font-size: 9.5pt;">`;

    window.noveltyParsedData.forEach(row => {
        excelHtml += `
            <tr>
                <td style="border: 1px solid #e2e8f0; padding: 4px; mso-number-format:'\\@';">${row.cedula}</td>
                <td style="border: 1px solid #e2e8f0; padding: 4px;">${row.nombres}</td>
                <td style="border: 1px solid #e2e8f0; padding: 4px; text-align: right;">${parseFloat(row.valor).toFixed(2)}</td>
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
    const term = document.getElementById('searchTable').value.toLowerCase();
    const rows = document.querySelectorAll('#novelty_tbody tr');

    if (window.noveltyParsedData.length === 0) return;

    rows.forEach(row => {
        const text = row.textContent.toLowerCase();
        const inputs = row.querySelectorAll('input');
        let valStr = inputs.length > 0 ? inputs[0].value.toLowerCase() : '';

        if (text.includes(term) || valStr.includes(term)) row.style.display = '';
        else row.style.display = 'none';
    });
};