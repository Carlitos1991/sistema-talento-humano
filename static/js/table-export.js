// ─── CARGA ASÍNCRONA DE DEPENDENCIAS (LAZY LOADING) ──────────────────────────
async function ensureExcelJS() {
    if (window.ExcelJS) return;
    await new Promise((resolve, reject) => {
        const s = document.createElement('script');
        s.src = 'https://cdnjs.cloudflare.com/ajax/libs/exceljs/4.4.0/exceljs.min.js';
        s.onload = resolve;
        s.onerror = () => reject(new Error('No se pudo cargar la librería ExcelJS'));
        document.head.appendChild(s);
    });
}

function getCleanText(element) {
    const clone = element.cloneNode(true);

    const personDetails = clone.querySelector('.person-details');
    if (personDetails) {
        const name = personDetails.querySelector('h4')?.innerText?.trim() || '';
        const doc = personDetails.querySelector('p')?.innerText?.trim().replace(/\s+/g, ' ') || '';
        return (name + (doc ? ' - ' + doc : '')).replace(/[\r\n\t]+/g, ' ').trim();
    }

    const garbage = clone.querySelectorAll('.sort-arrow, i, svg, button, .btn, .avatar-wrapper, .person-avatar, .person-avatar-placeholder');
    garbage.forEach(el => el.remove());

    return clone.innerText.replace(/[\r\n\t]+/g, ' ').replace(/\s{2,}/g, ' ').trim();
}

function getTableMetadata(table) {
    const title = table.getAttribute('data-title') || document.querySelector('h1')?.innerText || 'Reporte';
    let filename = table.getAttribute('data-filename');
    if (!filename) filename = title.replace(/[^a-zA-Z0-9]/g, '_').toLowerCase();
    return {title, filename};
}

function getExportableColumnIndices(table) {
    const ths = Array.from(table.querySelectorAll('thead th'));
    const validIndices = [];

    ths.forEach((th, index) => {
        const text = getCleanText(th).toLowerCase();
        const isActions = th.classList.contains('actions') || text.includes('accion') || text.includes('acciones');
        const isStatus = th.classList.contains('no-export') || th.dataset.noExport === 'true' || text === 'estado';

        if (!isActions && !isStatus) {
            validIndices.push(index);
        }
    });

    return validIndices;
}

// ─── OBTENER DATOS DE LA TABLA (DOM) ─────────────────────────────────────────
function getTableData(table) {
    const validIndices = getExportableColumnIndices(table);
    const ths = Array.from(table.querySelectorAll('thead th'));
    const headers = [validIndices.map(idx => getCleanText(ths[idx]))];
    const body = [];

    let sourceRows = [];
    if (table._tableManager && table._tableManager.currentRows) {
        sourceRows = table._tableManager.currentRows;
    } else if (window.filteredRows && window.filteredRows.length > 0) {
        sourceRows = window.filteredRows;
    } else {
        sourceRows = Array.from(table.querySelectorAll('tbody tr')).filter(tr => tr.style.display !== 'none');
    }

    sourceRows.forEach(tr => {
        if (tr.innerText.includes('No se encontraron registros') || tr.classList.contains('empty-results-row')) return;
        const tds = Array.from(tr.querySelectorAll('td'));
        if (tds.length > 0) {
            body.push(validIndices.map(idx => tds[idx] ? getCleanText(tds[idx]) : ''));
        }
    });

    return {headers, body};
}

// ─── FETCH DE TODOS LOS DATOS (BACKEND) ───────────────────────────────────────
async function getAllRowsFromServer(table) {
    const listUrl = table.getAttribute('data-list-url');
    if (listUrl) {
        const params = new URLSearchParams(window.location.search);

        const permitFiltersForm = document.getElementById('filtersForm');
        if (permitFiltersForm) {
            new FormData(permitFiltersForm).forEach((value, key) => {
                params.delete(key);
                if (value) params.set(key, value);
            });
        }

        if (typeof currentFilters !== 'undefined') {
            if (currentFilters.q) params.set('q', currentFilters.q);
            if (currentFilters.status && currentFilters.status !== 'all') params.set('status', currentFilters.status);
        }

        if (typeof currentProfileFilters !== 'undefined' && currentProfileFilters.q) {
            params.set('q', currentProfileFilters.q);
        }

        if (window._personExport && typeof window._personExport.getFilters === 'function') {
            const filters = window._personExport.getFilters();
            Object.entries(filters).forEach(([key, val]) => {
                if (val) params.set(key, val);
            });
        }

        params.set('partial', 'true');
        params.set('export', 'true');

        try {
            const resp = await fetch(listUrl + '?' + params.toString(), {
                headers: {'X-Requested-With': 'XMLHttpRequest'}
            });
            const html = await resp.text();

            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');
            const rows = Array.from(doc.querySelectorAll('tbody tr')).filter(tr =>
                !tr.innerText.includes('No se encontraron') && tr.querySelectorAll('td').length > 1
            );

            const validIndices = getExportableColumnIndices(table);
            const ths = Array.from(table.querySelectorAll('thead th'));
            const headers = [validIndices.map(idx => getCleanText(ths[idx]))];

            const body = rows.map(tr => {
                const tds = Array.from(tr.querySelectorAll('td'));
                return validIndices.map(idx => tds[idx] ? getCleanText(tds[idx]) : '');
            });

            return {headers, body};
        } catch (e) {
            console.error('Error al obtener datos del servidor:', e);
            return null;
        }
    }

    return null;
}

// ─── EXPORTACIÓN A EXCEL NATIVO CON EXCELJS (CERO ADVERTENCIAS) ───────────────
async function exportTableToExcel(table) {
    const {filename, title} = getTableMetadata(table);

    const btn = document.querySelector('.btn-export-excel');
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Generando...';
    }

    const allData = await getAllRowsFromServer(table);
    let {headers, body} = allData || getTableData(table);

    if (btn) {
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-file-excel"></i> Excel';
    }

    // Separar columna 'Empleado' en Cédula, Apellidos y Nombres si viene agrupada
    if (headers && headers[0] && headers[0][0] && headers[0][0].toLowerCase().includes('empleado')) {
        headers[0].splice(0, 1, 'Cédula', 'Apellidos', 'Nombres');
        body = body.map(row => {
            const empStr = row[0] || '';
            let cedula = '';
            let fullName = empStr;

            if (empStr.includes('CI:')) {
                const parts = empStr.split('CI:');
                fullName = parts[0].trim();
                cedula = parts[1].trim();
            } else if (empStr.includes('-')) {
                const parts = empStr.split('-');
                fullName = parts[0].trim();
                cedula = parts[1].trim();
            }

            const tokens = fullName.split(' ').filter(t => t.trim().length > 0);
            let apellidos = '';
            let nombres = '';
            if (tokens.length >= 4) {
                apellidos = tokens.slice(0, 2).join(' ');
                nombres = tokens.slice(2).join(' ');
            } else if (tokens.length === 3) {
                apellidos = tokens.slice(0, 2).join(' ');
                nombres = tokens[2];
            } else if (tokens.length === 2) {
                apellidos = tokens[0];
                nombres = tokens[1];
            } else {
                apellidos = fullName;
                nombres = '';
            }

            return [cedula, apellidos, nombres, ...row.slice(1)];
        });
    }

    const totalCols = (headers && headers[0]) ? headers[0].length : 7;
    const today = new Date().toLocaleDateString();
    const BLUE = 'FF203C7D';

    // Carga de ExcelJS bajo demanda
    await ensureExcelJS();

    const wb = new ExcelJS.Workbook();
    wb.creator = 'SIGETH - Municipio de Loja';
    wb.created = new Date();

    const ws = wb.addWorksheet('Datos', {
        views: [{showGridLines: true}]
    });

    // Anchos en caracteres
    const colWidths = [17, 27, 27, 15, 22, 22, 45];
    ws.columns = Array.from({length: totalCols}, (_, i) => ({
        width: colWidths[i] || 22
    }));

    const thin = {style: 'thin', color: {argb: 'FF000000'}};
    const allBorders = {top: thin, left: thin, bottom: thin, right: thin};

    // Filas 1-3: Banner Institucional
    const addBanner = (rowNum, text, font, align, height) => {
        ws.mergeCells(rowNum, 1, rowNum, totalCols);
        const cell = ws.getCell(rowNum, 1);
        cell.value = text;
        cell.font = font;
        cell.alignment = {horizontal: align, vertical: 'middle'};
        ws.getRow(rowNum).height = height;
    };

    addBanner(1, 'MUNICIPIO DE LOJA', {
        name: 'Arial', size: 14, bold: true, color: {argb: BLUE}
    }, 'center', 28);

    addBanner(2, 'Reporte: ' + (title ? title.toUpperCase() : 'REPORTE GENERAL'), {
        name: 'Arial', size: 11, bold: true, color: {argb: 'FF334155'}
    }, 'center', 20);

    addBanner(3, 'Fecha de generación: ' + today, {
        name: 'Arial', size: 8.5, color: {argb: 'FF64748B'}
    }, 'right', 18);

    // Fila 4: Encabezados de Tabla
    const headerRow = ws.getRow(4);
    headerRow.height = 24;
    headers[0].forEach((text, i) => {
        const cell = headerRow.getCell(i + 1);
        cell.value = text;
        cell.font = {name: 'Arial', size: 10, bold: true, color: {argb: 'FFFFFFFF'}};
        cell.fill = {type: 'pattern', pattern: 'solid', fgColor: {argb: BLUE}};
        cell.alignment = {horizontal: 'center', vertical: 'middle', wrapText: true};
        cell.border = allBorders;
    });

    // Filas de Datos
    body.forEach((row, r) => {
        const excelRow = ws.getRow(5 + r);
        excelRow.height = 22;

        row.forEach((text, c) => {
            const cell = excelRow.getCell(c + 1);
            cell.value = text !== null && text !== undefined ? String(text) : '';
            cell.numFmt = '@'; // Formato de texto para preservar ceros a la izquierda en cédulas
            cell.font = {name: 'Arial', size: 9};
            cell.border = allBorders;

            const isCenter = (c === 0 || c === 3 || c === 4 || c === 5);
            cell.alignment = {
                horizontal: isCenter ? 'center' : 'left',
                vertical: 'middle'
            };
        });
    });

    // Generar buffer .xlsx binario real
    const buffer = await wb.xlsx.writeBuffer();
    const blob = new Blob([buffer], {
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    });

    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${filename}.xlsx`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    setTimeout(() => URL.revokeObjectURL(url), 1000);
}

// ─── EXPORTAR PDF ─────────────────────────────────────────────────────────────
async function exportTableToPDF(table) {
    if (!window.jspdf) {
        await new Promise((resolve) => {
            const s = document.createElement('script');
            s.src = 'https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js';
            s.onload = () => {
                const atScript = document.createElement('script');
                atScript.src = 'https://cdnjs.cloudflare.com/ajax/libs/jspdf-autotable/3.5.31/jspdf.plugin.autotable.min.js';
                atScript.onload = resolve;
                document.head.appendChild(atScript);
            };
            document.head.appendChild(s);
        });
    }

    const {jsPDF} = window.jspdf;
    const {title, filename} = getTableMetadata(table);

    const btn = document.querySelector('.btn-export-pdf');
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Generando...';
    }

    const allData = await getAllRowsFromServer(table);
    const {headers, body} = allData || getTableData(table);

    if (btn) {
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-file-pdf"></i> PDF';
    }

    const doc = new jsPDF({orientation: body.length > 20 ? 'landscape' : 'portrait'});
    doc.setFontSize(13);
    doc.text(title, 14, 15);
    doc.setFontSize(9);
    doc.text('Generado el: ' + new Date().toLocaleDateString(), 14, 22);
    doc.autoTable({
        head: headers,
        body: body,
        startY: 27,
        theme: 'grid',
        styles: {fontSize: 8, cellPadding: 3},
        headStyles: {fillColor: [32, 60, 125]},
        alternateRowStyles: {fillColor: [248, 250, 252]}
    });
    doc.save(filename + '.pdf');
}

function addExportButtonsToTables() {
    const tables = document.querySelectorAll('.exportable-table');
    tables.forEach(table => {
        const wrapper = table.closest('.content-table');
        const controls = wrapper ? wrapper.querySelector('.table-controls') : null;
        if (!controls) return;
        if (controls.dataset.manualExport === 'true') return;

        const existing = controls.querySelector('.table-export-btns');
        if (existing) existing.remove();

        const btnContainer = document.createElement('div');
        btnContainer.className = 'table-export-btns';
        btnContainer.innerHTML =
            '<button type="button" class="btn-export-excel" title="Excel">' +
            '<i class="fas fa-file-excel"></i> Excel</button>' +
            '<button type="button" class="btn-export-pdf" title="PDF">' +
            '<i class="fas fa-file-pdf"></i> PDF</button>';

        const resolveCurrentTable = () => {
            const currentWrapper = table.closest('.content-table');
            return currentWrapper ? currentWrapper.querySelector('.exportable-table') : table;
        };

        const excelBtn = btnContainer.querySelector('.btn-export-excel');
        const pdfBtn = btnContainer.querySelector('.btn-export-pdf');
        if (excelBtn) {
            excelBtn.addEventListener('click', function () {
                exportTableToExcel(resolveCurrentTable());
            });
        }
        if (pdfBtn) {
            pdfBtn.addEventListener('click', function () {
                exportTableToPDF(resolveCurrentTable());
            });
        }
        controls.insertBefore(btnContainer, controls.firstChild);
    });
}

window.addExportButtonsToTables = addExportButtonsToTables;

if (document.readyState === 'complete' || document.readyState === 'interactive') {
    try {
        addExportButtonsToTables();
    } catch (e) {
        console.warn('table-export init failed', e);
    }
} else {
    document.addEventListener('DOMContentLoaded', function () {
        try {
            addExportButtonsToTables();
        } catch (e) {
            console.warn('table-export init failed', e);
        }
    });
}