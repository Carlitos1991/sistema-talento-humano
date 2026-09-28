(function loadDeps() {
    if (!window.XLSX) {
        const script = document.createElement('script');
        script.src = '/static/vendor/xlsx.full.min.js';
        document.head.appendChild(script);
    }
    if (!window.jspdf) {
        const script = document.createElement('script');
        script.src = '/static/vendor/jspdf.umd.min.js';
        script.onload = () => {
            if (!window.jspdf.plugin?.autotable) {
                const atScript = document.createElement('script');
                atScript.src = '/static/vendor/jspdf.plugin.autotable.min.js';
                document.head.appendChild(atScript);
            }
        };
        document.head.appendChild(script);
    }
})();

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

    // Normaliza el texto en una sola línea continua sin saltos de línea
    return clone.innerText.replace(/[\r\n\t]+/g, ' ').replace(/\s{2,}/g, ' ').trim();
}

function getTableMetadata(table) {
    const title = table.getAttribute('data-title') || document.querySelector('h1')?.innerText || 'Reporte';
    let filename = table.getAttribute('data-filename');
    if (!filename) filename = title.replace(/[^a-zA-Z0-9]/g, '_').toLowerCase();
    return {title, filename};
}

/**
 * Determina qué índices de columna deben incluirse en la exportación,
 * excluyendo 'Acciones', 'Estado' o celdas marcadas con 'no-export'.
 */
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

// ─── EXPORTAR EXCEL CON FORMATO XML NATIVO (COLORES, BORDES Y SIN ADVERTENCIA) ───
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

    // 1. Separar columna 'Empleado' en Cédula, Apellidos y Nombres si viene agrupada
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

    const escapeXml = (str) => {
        if (str === null || str === undefined) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&apos;');
    };

    // Anchos proporcionales de columnas en puntos
    const colWidths = [95, 150, 150, 85, 120, 120, 250];

    // 2. Construcción de libro XML Spreadsheet 2003 compatible al 100% con Excel
    let xml = `<?xml version="1.0"?>
<?mso-application progid="Excel.Sheet"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:o="urn:schemas-microsoft-com:office:office"
 xmlns:x="urn:schemas-microsoft-com:office:excel"
 xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:html="http://www.w3.org/TR/REC-html40">
 <Styles>
  <Style ss:ID="Default" ss:Name="Normal">
   <Alignment ss:Vertical="Center"/>
   <Borders/>
   <Font ss:FontName="Arial" ss:Size="10"/>
   <Interior/>
   <NumberFormat/>
   <Protection/>
  </Style>
  <!-- Estilo del Título Institucional -->
  <Style ss:ID="sHeaderTitle">
   <Alignment ss:Horizontal="Center" ss:Vertical="Center"/>
   <Font ss:FontName="Arial" ss:Size="14" ss:Bold="1" ss:Color="#203C7D"/>
  </Style>
  <!-- Estilo del Subtítulo -->
  <Style ss:ID="sHeaderSubtitle">
   <Alignment ss:Horizontal="Center" ss:Vertical="Center"/>
   <Font ss:FontName="Arial" ss:Size="11" ss:Bold="1" ss:Color="#334155"/>
  </Style>
  <!-- Estilo de Fecha a la derecha -->
  <Style ss:ID="sHeaderDate">
   <Alignment ss:Horizontal="Right" ss:Vertical="Center"/>
   <Font ss:FontName="Arial" ss:Size="8.5" ss:Color="#64748B"/>
  </Style>
  <!-- Estilo de Cabecera de Tabla (Fondo azul institucional, texto blanco y borde negro fino) -->
  <Style ss:ID="sTableHeader">
   <Alignment ss:Horizontal="Center" ss:Vertical="Center"/>
   <Borders>
    <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#000000"/>
    <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#000000"/>
    <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#000000"/>
    <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#000000"/>
   </Borders>
   <Font ss:FontName="Arial" ss:Size="10" ss:Bold="1" ss:Color="#FFFFFF"/>
   <Interior ss:Color="#203C7D" ss:Pattern="Solid"/>
  </Style>
  <!-- Estilo de Celdas de Texto (Alineadas a la izquierda con borde negro fino) -->
  <Style ss:ID="sCellLeft">
   <Alignment ss:Horizontal="Left" ss:Vertical="Center"/>
   <Borders>
    <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#000000"/>
    <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#000000"/>
    <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#000000"/>
    <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#000000"/>
   </Borders>
   <Font ss:FontName="Arial" ss:Size="9"/>
   <NumberFormat ss:Format="@"/>
  </Style>
  <!-- Estilo de Celdas Centradas con borde negro fino -->
  <Style ss:ID="sCellCenter">
   <Alignment ss:Horizontal="Center" ss:Vertical="Center"/>
   <Borders>
    <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#000000"/>
    <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#000000"/>
    <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#000000"/>
    <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#000000"/>
   </Borders>
   <Font ss:FontName="Arial" ss:Size="9"/>
   <NumberFormat ss:Format="@"/>
  </Style>
 </Styles>
 <Worksheet ss:Name="Datos">
  <Table>`;

    // Ancho por columna
    for (let c = 0; c < totalCols; c++) {
        const w = colWidths[c] || 120;
        xml += `\n   <Column ss:Width="${w}"/>`;
    }

    // Fila 1: Título MUNICIPIO DE LOJA
    xml += `\n   <Row ss:Height="28">
    <Cell ss:MergeAcross="${totalCols - 1}" ss:StyleID="sHeaderTitle"><Data ss:Type="String">MUNICIPIO DE LOJA</Data></Cell>
   </Row>`;

    // Fila 2: Subtítulo de Reporte
    xml += `\n   <Row ss:Height="20">
    <Cell ss:MergeAcross="${totalCols - 1}" ss:StyleID="sHeaderSubtitle"><Data ss:Type="String">Reporte: ${escapeXml(title.toUpperCase())}</Data></Cell>
   </Row>`;

    // Fila 3: Fecha a la derecha
    xml += `\n   <Row ss:Height="18">
    <Cell ss:MergeAcross="${totalCols - 1}" ss:StyleID="sHeaderDate"><Data ss:Type="String">Fecha de generación: ${today}</Data></Cell>
   </Row>`;

    // Fila 4: Encabezados de Columna (Inmediatamente tras la fecha, sin fila vacía)
    xml += `\n   <Row ss:Height="24">`;
    headers[0].forEach(thText => {
        xml += `\n    <Cell ss:StyleID="sTableHeader"><Data ss:Type="String">${escapeXml(thText)}</Data></Cell>`;
    });
    xml += `\n   </Row>`;

    // Filas de Datos con 22pt de altura
    body.forEach(row => {
        xml += `\n   <Row ss:Height="22">`;
        row.forEach((cellText, colIdx) => {
            const isCenter = colIdx === 0 || colIdx === 3 || colIdx === 4 || colIdx === 5;
            const styleId = isCenter ? 'sCellCenter' : 'sCellLeft';
            xml += `\n    <Cell ss:StyleID="${styleId}"><Data ss:Type="String">${escapeXml(cellText || '')}</Data></Cell>`;
        });
        xml += `\n   </Row>`;
    });

    xml += `\n  </Table>
  <WorksheetOptions xmlns="urn:schemas-microsoft-com:office:excel">
   <DisplayGridlines/>
  </WorksheetOptions>
 </Worksheet>
</Workbook>`;

    // 3. Descarga oficial en formato SpreadsheetML (se abre directamente sin mensajes de advertencia)
    const blob = new Blob([xml], {
        type: 'application/vnd.ms-excel;charset=utf-8'
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${filename}.xls`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
}

// ─── EXPORTAR PDF ─────────────────────────────────────────────────────────────
async function exportTableToPDF(table) {
    if (!window.jspdf || !window.jspdf.jsPDF) {
        alert('Cargando dependencias, intente en un momento...');
        return;
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