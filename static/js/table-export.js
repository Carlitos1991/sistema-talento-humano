/* static/js/table-export.js */

(function loadDeps() {
    if (!window.XLSX) {
        const script = document.createElement('script');
        script.src = 'https://cdn.jsdelivr.net/npm/xlsx@0.18.5/dist/xlsx.full.min.js';
        document.head.appendChild(script);
    }
    if (!window.jspdf) {
        const script = document.createElement('script');
        script.src = 'https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js';
        script.onload = () => {
            if (!window.jspdf.plugin?.autotable) {
                const atScript = document.createElement('script');
                atScript.src = 'https://cdnjs.cloudflare.com/ajax/libs/jspdf-autotable/3.7.1/jspdf.plugin.autotable.min.js';
                document.head.appendChild(atScript);
            }
        };
        document.head.appendChild(script);
    }
})();

function getCleanText(element) {
    const clone = element.cloneNode(true);
    const garbage = clone.querySelectorAll('.sort-arrow, i, svg, .fa, .fas, .far, button, .btn');
    garbage.forEach(el => el.remove());
    return clone.innerText.trim();
}

function getTableMetadata(table) {
    const title = table.getAttribute('data-title') || document.querySelector('h1')?.innerText || 'Reporte';
    let filename = table.getAttribute('data-filename');
    if (!filename) filename = title.replace(/[^a-zA-Z0-9]/g, '_').toLowerCase();
    return {title, filename};
}

// --- FUNCIÓN CLAVE MODIFICADA ---
function getTableData(table) {
    const headers = [];
    const body = [];

    // Header
    const ths = Array.from(table.querySelectorAll('thead th'));
    const headerRow = ths.slice(0, -1).map(th => getCleanText(th));
    headers.push(headerRow);

    // Body: Intentar obtener datos del TableManager Global
    let sourceRows = [];

    if (table._tableManager && table._tableManager.currentRows) {
        // CASO 1: Tabla gestionada por table-manager.js (Tiene TODOS los datos)
        sourceRows = table._tableManager.currentRows;
    } else if (window.filteredRows && window.filteredRows.length > 0) {
        // CASO 2: Compatibilidad antigua con levels.js
        sourceRows = window.filteredRows;
    } else {
        // CASO 3: Tabla HTML estática (Solo lo visible)
        sourceRows = Array.from(table.querySelectorAll('tbody tr')).filter(tr => tr.style.display !== 'none');
    }

    sourceRows.forEach(tr => {
        // Ignorar filas de "No resultados"
        if (tr.innerText.includes('No se encontraron registros')) return;

        const tds = Array.from(tr.querySelectorAll('td'));
        if (tds.length > 0) {
            const rowData = tds.slice(0, -1).map(td => getCleanText(td));
            body.push(rowData);
        }
    });

    return {headers, body};
}

// (Las funciones exportTableToExcel, exportTableToPDF y addExportButtonsToTables
//  se mantienen IGUAL que en tu versión anterior, solo usan el nuevo getTableData)

function exportTableToExcel(table) {
    if (!window.XLSX) {
        alert("Cargando Excel...");
        return;
    }
    const {filename} = getTableMetadata(table);
    const {headers, body} = getTableData(table);
    const data = [...headers, ...body];
    const ws = XLSX.utils.aoa_to_sheet(data);
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, "Datos");
    XLSX.writeFile(wb, `${filename}.xlsx`);
}

function exportTableToPDF(table) {
    if (!window.jspdf || !window.jspdf.jsPDF) {
        alert("Cargando PDF...");
        return;
    }
    const {jsPDF} = window.jspdf;
    const doc = new jsPDF();
    const {title, filename} = getTableMetadata(table);
    const {headers, body} = getTableData(table);
    doc.text(title, 14, 15);
    doc.setFontSize(10);
    doc.text(`Generado el: ${new Date().toLocaleDateString()}`, 14, 22);
    doc.autoTable({
        head: headers,
        body: body,
        startY: 26,
        theme: 'grid',
        styles: {fontSize: 8, cellPadding: 2},
        headStyles: {fillColor: [22, 163, 74]}
    });
    doc.save(`${filename}.pdf`);
}

function addExportButtonsToTables() {
    const tables = document.querySelectorAll('.exportable-table');
    tables.forEach(table => {
        const wrapper = table.closest('.content-table');
        const controls = wrapper ? wrapper.querySelector('.table-controls') : null;
        if (controls) {
            if (controls.querySelector('.table-export-btns')) return;
            const btnContainer = document.createElement('div');
            btnContainer.className = 'table-export-btns';
            btnContainer.innerHTML = `
                <button type="button" class="btn-export-excel" title="Excel"><i class="fas fa-file-excel"></i> Excel</button>
                <button type="button" class="btn-export-pdf" title="PDF"><i class="fas fa-file-pdf"></i> PDF</button>
            `;
            btnContainer.querySelector('.btn-export-excel').onclick = () => exportTableToExcel(table);
            btnContainer.querySelector('.btn-export-pdf').onclick = () => exportTableToPDF(table);
            controls.insertBefore(btnContainer, controls.firstChild);
        }
    });
}

document.addEventListener('DOMContentLoaded', addExportButtonsToTables);