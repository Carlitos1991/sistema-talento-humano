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

    // Si la celda tiene .person-details, extraer nombre y cédula directamente
    const personDetails = clone.querySelector('.person-details');
    if (personDetails) {
        const name = personDetails.querySelector('h4')?.innerText?.trim() || '';
        const doc = personDetails.querySelector('p')?.innerText?.trim().replace(/\s+/g, ' ') || '';
        return name + (doc ? ' - ' + doc : '');
    }

    // Caso general: eliminar íconos, flechas y botones
    const garbage = clone.querySelectorAll('.sort-arrow, i, svg, button, .btn, .avatar-wrapper, .person-avatar, .person-avatar-placeholder');
    garbage.forEach(el => el.remove());
    return clone.innerText.trim().replace(/\s+/g, ' ');
}

function getTableMetadata(table) {
    const title = table.getAttribute('data-title') || document.querySelector('h1')?.innerText || 'Reporte';
    let filename = table.getAttribute('data-filename');
    if (!filename) filename = title.replace(/[^a-zA-Z0-9]/g, '_').toLowerCase();
    return {title, filename};
}

// ─── OBTENER DATOS DE LA TABLA (solo filas visibles del DOM) ─────────────────
function getTableData(table) {
    const headers = [];
    const body = [];

    const ths = Array.from(table.querySelectorAll('thead th'));
    const headerRow = ths.slice(0, -1).map(th => getCleanText(th));
    headers.push(headerRow);

    let sourceRows = [];
    if (table._tableManager && table._tableManager.currentRows) {
        sourceRows = table._tableManager.currentRows;
    } else if (window.filteredRows && window.filteredRows.length > 0) {
        sourceRows = window.filteredRows;
    } else {
        sourceRows = Array.from(table.querySelectorAll('tbody tr')).filter(tr => tr.style.display !== 'none');
    }

    sourceRows.forEach(tr => {
        if (tr.innerText.includes('No se encontraron registros')) return;
        const tds = Array.from(tr.querySelectorAll('td'));
        if (tds.length > 0) {
            body.push(tds.slice(0, -1).map(td => getCleanText(td)));
        }
    });

    return {headers, body};
}

// ─── FETCH DE TODOS LOS DATOS (paginación backend) ───────────────────────────
async function getAllRowsFromServer(table) {
    // Solo si la tabla usa paginación externa (backend/Vue)
    if (table.dataset.externalPagination !== 'true') return null;
    if (!window._personExport || !window._personExport.listUrl) {
        console.warn("Exportación completa abortada: Falta listUrl en window._personExport");
        return null;
    }

    const filters = window._personExport.getFilters ? window._personExport.getFilters() : {};
    const params = new URLSearchParams(filters);
    params.set('page_size', '99999');  // pedir todo
    params.set('page', '1');

    try {
        const resp = await fetch(window._personExport.listUrl + '?' + params.toString(), {
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        });
        const json = await resp.json();
        if (!json.success) return null;

        // Parsear el HTML recibido y extraer filas
        const parser = new DOMParser();
        const doc = parser.parseFromString(json.html, 'text/html');
        const rows = Array.from(doc.querySelectorAll('tbody tr')).filter(tr =>
            !tr.innerText.includes('No se encontraron') && tr.querySelectorAll('td').length > 1
        );

        // Extraer headers del DOM actual
        const ths = Array.from(table.querySelectorAll('thead th'));
        const headers = [ths.slice(0, -1).map(th => getCleanText(th))];

        const body = rows.map(tr =>
            Array.from(tr.querySelectorAll('td')).slice(0, -1).map(td => getCleanText(td))
        );

        return {headers, body};
    } catch (e) {
        console.error('Error al obtener todos los datos:', e);
        return null;
    }
}

// ─── EXPORTAR EXCEL ───────────────────────────────────────────────────────────
async function exportTableToExcel(table) {
    if (!window.XLSX) {
        alert('Cargando dependencias, intente en un momento...');
        return;
    }

    const {filename} = getTableMetadata(table);

    // Mostrar indicador mientras carga
    const btn = document.querySelector('.btn-export-excel');
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Generando...';
    }

    // Intentar obtener todos los datos del servidor
    const allData = await getAllRowsFromServer(table);
    const {headers, body} = allData || getTableData(table);

    if (btn) {
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-file-excel"></i> Excel';
    }

    const ws = XLSX.utils.aoa_to_sheet([...headers, ...body]);
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, 'Datos');
    XLSX.writeFile(wb, filename + '.xlsx');
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
        styles: {fontSize: 7, cellPadding: 2},
        headStyles: {fillColor: [30, 64, 175]},
        alternateRowStyles: {fillColor: [245, 247, 250]}
    });
    doc.save(filename + '.pdf');
}

function addExportButtonsToTables() {
    const tables = document.querySelectorAll('.exportable-table');
    tables.forEach(table => {
        const wrapper = table.closest('.content-table');
        const controls = wrapper ? wrapper.querySelector('.table-controls') : null;
        if (!controls) return;

        // Eliminar botones viejos — tras AJAX apuntaban a tabla anterior
        const existing = controls.querySelector('.table-export-btns');
        if (existing) existing.remove();

        const btnContainer = document.createElement('div');
        btnContainer.className = 'table-export-btns';
        btnContainer.innerHTML =
            '<button type="button" class="btn-export-excel" title="Excel">' +
            '<i class="fas fa-file-excel"></i> Excel</button>' +
            '<button type="button" class="btn-export-pdf" title="PDF">' +
            '<i class="fas fa-file-pdf"></i> PDF</button>';

        // Closure sobre la tabla actual — no buscar en el DOM de nuevo
        (function (t) {
            const excelBtn = btnContainer.querySelector('.btn-export-excel');
            const pdfBtn = btnContainer.querySelector('.btn-export-pdf');
            if (excelBtn) {
                excelBtn.addEventListener('click', function (e) {
                    exportTableToExcel(t);
                });
            }
            if (pdfBtn) {
                pdfBtn.addEventListener('click', function (e) {
                    exportTableToPDF(t);
                });
            }
        })(table);
        controls.insertBefore(btnContainer, controls.firstChild);
    });
}

// Try to initialize export buttons safely: if DOMContentLoaded already passed, call immediately.
if (document.readyState === 'complete' || document.readyState === 'interactive') {
    try { addExportButtonsToTables(); } catch(e){ console.warn('table-export init failed', e); }
} else {
    document.addEventListener('DOMContentLoaded', function(){ try { addExportButtonsToTables(); } catch(e){ console.warn('table-export init failed', e); } });
}

// debug badge removed