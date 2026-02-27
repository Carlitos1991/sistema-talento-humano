// Init TableManager for tables loaded after DOMContentLoaded, attach export fallbacks,
// and handle AJAX modal opening for action detail.
(function(){
    function initTables() {
        document.querySelectorAll('.managed-table').forEach(function(table){
            if (!table._tableManager && window.TableManager) {
                try { new TableManager(table); } catch(e){ console.warn('TableManager init failed', e); }
            }
        });
        if (window.addExportButtonsToTables) {
            try { addExportButtonsToTables(); } catch(e){ console.warn('addExportButtonsToTables failed', e); }
        }
        attachExportFallbacks();
    }

    function getTableDataForCSV(table) {
        const rows = [];
        const ths = Array.from(table.querySelectorAll('thead th'));
        const headers = ths.map(th => th.innerText.trim());
        rows.push(headers);
        const trs = Array.from(table.querySelectorAll('tbody tr')).filter(tr => tr.querySelectorAll('td').length>0);
        trs.forEach(tr => {
            const cols = Array.from(tr.querySelectorAll('td')).map(td=> td.innerText.trim().replace(/\n/g,' '));
            rows.push(cols);
        });
        return rows;
    }

    function downloadCSV(filename, rows) {
        const csv = rows.map(r => r.map(c => '"'+(c||'').replace(/"/g,'""')+'"').join(',')).join('\n');
        const blob = new Blob([csv], {type: 'text/csv;charset=utf-8;'});
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename + '.csv';
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
    }

    function exportTableCSVFallback(table) {
        const meta = table.dataset.filename || 'export';
        const rows = getTableDataForCSV(table);
        downloadCSV(meta, rows);
    }

    function exportTablePDFFallback(table) {
        // Simple fallback: open printable window with table HTML
        const html = '<html><head><title>PDF Export</title>' +
            '<link rel="stylesheet" href="/static/css/style.css">' +
            '</head><body>' + table.outerHTML + '</body></html>';
        const w = window.open('', '_blank');
        if (!w) { alert('Permita ventanas emergentes para exportar PDF'); return; }
        w.document.write(html);
        w.document.close();
        w.focus();
        setTimeout(()=>{ w.print(); }, 600);
    }

    function attachExportFallbacks(){
        document.querySelectorAll('.exportable-table').forEach(function(table){
            const wrapper = table.closest('.content-table');
            if (!wrapper) return;
            const excelBtn = wrapper.querySelector('.btn-export-excel');
            const pdfBtn = wrapper.querySelector('.btn-export-pdf');
            if (excelBtn) {
                excelBtn.addEventListener('click', function(e){
                    if (!window.XLSX) {
                        exportTableCSVFallback(table);
                        e.preventDefault();
                    }
                });
            }
            if (pdfBtn) {
                pdfBtn.addEventListener('click', function(e){
                    if (!window.jspdf || !window.jspdf.jsPDF) {
                        exportTablePDFFallback(table);
                        e.preventDefault();
                    }
                });
            }
        });
    }

    // Delegated click: open action detail in modal via AJAX
    function attachActionModalHandler(){
        document.addEventListener('click', function(e){
            const btn = e.target.closest('.open-action-detail');
            if (!btn) return;
            e.preventDefault();
            const url = btn.dataset.url;
            if (!url) return;
            fetch(url, {headers: {'X-Requested-With':'XMLHttpRequest'}})
                .then(r=>r.json().catch(()=>null).then(j=> j || null))
                .then(data=>{
                    let html = null;
                    if (data && data.html) html = data.html;
                    else {
                        // If server returned full HTML (not JSON), fetch as text
                        return fetch(url).then(r=>r.text()).then(t=>t);
                    }
                    return html;
                })
                .then(html=>{
                    if (!html) return;
                    // Inject modal
                    let container = document.getElementById('action-modal-employee');
                    if (!container) {
                        container = document.createElement('div');
                        container.id = 'action-modal-employee';
                        document.body.appendChild(container);
                    }
                    container.innerHTML = `<div class="modal-overlay"><div class="modal-box">${html}<button class="modal-close">Cerrar</button></div></div>`;
                    document.body.classList.add('no-scroll');
                }).catch(err=>{
                    console.error('Error cargando detalle de acción', err);
                    // Try fetch text fallback
                    fetch(url).then(r=>r.text()).then(t=>{
                        let container = document.getElementById('action-modal-employee');
                        if (!container) { container = document.createElement('div'); container.id='action-modal-employee'; document.body.appendChild(container); }
                        container.innerHTML = `<div class="modal-overlay"><div class="modal-box">${t}<button class="modal-close">Cerrar</button></div></div>`;
                        document.body.classList.add('no-scroll');
                    });
                });
        });

        // Close handler: support multiple variants (.modal-close, [data-dismiss], .close)
        document.addEventListener('click', function(e){
            const clickedClose = e.target.closest('.modal-close') || e.target.closest('[data-dismiss="modal"]') || e.target.closest('.close');
            const overlay = e.target.closest('.modal-overlay');
            const box = e.target.closest('.modal-box');
            // Close when explicit close clicked OR when clicking overlay outside the box
            if (clickedClose || (overlay && !box)){
                const cont = document.getElementById('action-modal-employee');
                if (cont) cont.innerHTML='';
                document.body.classList.remove('no-scroll');
            }
        });
    }

    // Run on load (if DOMContentLoaded already passed, run immediately)
    if (document.readyState === 'complete' || document.readyState === 'interactive') {
        setTimeout(()=>{ initTables(); attachActionModalHandler(); }, 50);
    } else {
        document.addEventListener('DOMContentLoaded', function(){ initTables(); attachActionModalHandler(); });
    }
})();
