/**
 * Biométricos - Reportes de Asistencia
 * Integración con TableManager y funciones centralizadas de main.js
 */

document.addEventListener('DOMContentLoaded', () => {
    initDefaultDates();
    loadUnitRoots();
    setupDelegations();
    setupSearchEvents();
    setupDownloadButtons();
});

// 1. Asignar fecha actual por defecto
function initDefaultDates() {
    const now = new Date();
    const currentMonth = now.getMonth() + 1;
    const currentYear = now.getFullYear();

    const elMonth = document.getElementById('monthly_month');
    const elYear = document.getElementById('monthly_year');
    const elUnitMonth = document.getElementById('unit_month');
    const elUnitYear = document.getElementById('unit_year');

    if (elMonth) elMonth.value = currentMonth;
    if (elYear) elYear.value = currentYear;
    if (elUnitMonth) elUnitMonth.value = currentMonth;
    if (elUnitYear) elUnitYear.value = currentYear;
}

// 2. Control de Búsqueda Servidor (Solo al pulsar botón o Enter)
async function executeSearch() {
    const input = document.getElementById('globalSearchInput');
    const query = input ? input.value.trim() : '';

    const params = new URLSearchParams();
    if (query) {
        params.append('q', query);
        params.append('name', query);
        params.append('dni', query);
    }

    const wrapper = document.getElementById('table-content-wrapper');
    if (!wrapper) return;

    wrapper.style.opacity = '0.4';
    wrapper.style.pointerEvents = 'none';

    try {
        const response = await fetch(`?${params.toString()}`, {
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        });
        const data = await response.json();

        wrapper.innerHTML = data.html || '';

        // Reinicializar TableManager en la nueva tabla recibida
        const newTable = wrapper.querySelector('.managed-table');
        if (newTable && typeof TableManager !== 'undefined') {
            new TableManager(newTable);
        }
    } catch (error) {
        console.error("Error al buscar empleados:", error);
        Swal.fire({
            icon: 'error',
            title: 'Error',
            text: 'Ocurrió un problema de comunicación al buscar.'
        });
    } finally {
        wrapper.style.opacity = '1';
        wrapper.style.pointerEvents = 'auto';
    }
}

function clearSearch() {
    const input = document.getElementById('globalSearchInput');
    if (input) input.value = '';
    executeSearch();
}

function setupSearchEvents() {
    const btnSearch = document.getElementById('btnBiometricSearch');
    const btnClear = document.getElementById('btnBiometricClear');
    const input = document.getElementById('globalSearchInput');

    btnSearch?.addEventListener('click', executeSearch);
    btnClear?.addEventListener('click', clearSearch);

    input?.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            executeSearch();
        }
    });
}

// 3. Delegación de clics en la tabla para poblar modales antes de abrirse
function setupDelegations() {
    document.addEventListener('click', (e) => {
        const btnMonthly = e.target.closest('.btn-trigger-monthly');
        if (btnMonthly) {
            e.preventDefault();
            document.getElementById('monthly_emp_id').value = btnMonthly.dataset.id || '';
            document.getElementById('monthly_emp_name').textContent = btnMonthly.dataset.name || 'N/A';
            document.getElementById('monthly_emp_dni').textContent = btnMonthly.dataset.dni || 'N/A';
            openModal('modalReportMonthly');
            return;
        }

        const btnSpecific = e.target.closest('.btn-trigger-specific');
        if (btnSpecific) {
            e.preventDefault();
            document.getElementById('specific_emp_id').value = btnSpecific.dataset.id || '';
            document.getElementById('specific_emp_name').textContent = btnSpecific.dataset.name || 'N/A';
            document.getElementById('specific_emp_dni').textContent = btnSpecific.dataset.dni || 'N/A';
            document.getElementById('specific_start').value = '';
            document.getElementById('specific_end').value = '';

            openModal('modalReportSpecific');
        }
    });

    // Cascada de Dependencias
    document.getElementById('unit_root_select')?.addEventListener('change', function () {
        loadUnitChildren(this.value);
    });
}

// Descarga Reporte Mensual con los 3 parámetros de los switches
function setupDownloadButtons() {
    document.getElementById('btnDownloadMonthly')?.addEventListener('click', () => {
        const empId = document.getElementById('monthly_emp_id').value;
        const month = document.getElementById('monthly_month').value;
        const year = document.getElementById('monthly_year').value;

        // Lectura de los 3 switches
        const showSummary = document.getElementById('sw_show_summary').checked ? '1' : '0';
        const showObservations = document.getElementById('sw_show_observations').checked ? '1' : '0';
        const deduplicate = document.getElementById('sw_deduplicate').checked ? '1' : '0';

        if (!empId || !month || !year) {
            Swal.fire({
                icon: 'warning',
                title: 'Datos incompletos',
                text: 'Verifique el mes y año ingresados.'
            });
            return;
        }

        const url = `/biometric/reports/monthly-pdf/?emp_id=${empId}&month=${month}&year=${year}&show_summary=${showSummary}&show_observations=${showObservations}&deduplicate=${deduplicate}`;
        window.open(url, '_blank');
        closeModal('modalReportMonthly');
    });

    // Descarga Reporte Específico
    document.getElementById('btnDownloadSpecific')?.addEventListener('click', () => {
        const empId = document.getElementById('specific_emp_id').value;
        const start = document.getElementById('specific_start').value;
        const end = document.getElementById('specific_end').value;

        if (!start || !end) {
            Swal.fire({
                icon: 'warning',
                title: 'Rango incompleto',
                text: 'Seleccione fecha de inicio y fin.'
            });
            return;
        }

        if (new Date(start) > new Date(end)) {
            Swal.fire({
                icon: 'warning',
                title: 'Fechas incorrectas',
                text: 'La fecha de inicio no puede ser posterior a la de fin.'
            });
            return;
        }

        const url = `/biometric/reports/specific-pdf/?emp_id=${empId}&start=${start}&end=${end}`;
        window.open(url, '_blank');
        closeModal('modalReportSpecific');
    });

    // Descarga Reporte por Dependencia
    document.getElementById('btnDownloadUnit')?.addEventListener('click', () => {
        const rootId = document.getElementById('unit_root_select').value;
        const childId = document.getElementById('unit_child_select').value;
        const month = document.getElementById('unit_month').value;
        const year = document.getElementById('unit_year').value;

        const unitId = childId || rootId;

        if (!unitId) {
            Swal.fire({
                icon: 'warning',
                title: 'Atención',
                text: 'Seleccione al menos una dependencia raíz.'
            });
            return;
        }

        const url = `/biometric/reports/department-pdf/?unit_id=${unitId}&month=${month}&year=${year}`;
        window.open(url, '_blank');
        closeModal('modalReportUnit');
    });
}

// 5. Dependencias Organizacionales
async function loadUnitRoots() {
    const rootSelect = document.getElementById('unit_root_select');
    if (!rootSelect) return;

    try {
        const res = await fetch('/personnel_actions/api/unit-children/', {
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        });
        const json = await res.json();
        const units = json.units || [];

        rootSelect.innerHTML = '<option value="">-- Seleccione una dependencia --</option>';
        units.forEach(u => {
            rootSelect.innerHTML += `<option value="${u.id}">${u.name}</option>`;
        });
    } catch (e) {
        console.error('Error cargando dependencias:', e);
    }
}

async function loadUnitChildren(parentId) {
    const childGroup = document.getElementById('subUnitGroup');
    const childSelect = document.getElementById('unit_child_select');
    if (!childGroup || !childSelect) return;

    if (!parentId) {
        childGroup.style.display = 'none';
        childSelect.innerHTML = '<option value="">-- Todas las dependencias hijas --</option>';
        return;
    }

    try {
        const res = await fetch(`/personnel_actions/api/unit-children/?parent_id=${parentId}`, {
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        });
        const json = await res.json();
        const units = json.units || [];

        if (units.length > 0) {
            childSelect.innerHTML = '<option value="">-- Todas las dependencias hijas --</option>';
            units.forEach(u => {
                childSelect.innerHTML += `<option value="${u.id}">${u.name}</option>`;
            });
            childGroup.style.display = 'block';
        } else {
            childGroup.style.display = 'none';
            childSelect.innerHTML = '<option value="">-- Todas las dependencias hijas --</option>';
        }
    } catch (e) {
        console.error('Error cargando subunidades:', e);
    }
}