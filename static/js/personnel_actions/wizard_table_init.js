// Init TableManager for tables loaded after DOMContentLoaded, attach export fallbacks,
// and handle AJAX modal opening for action detail.
(function(){

    function initTables() {
        document.querySelectorAll('.managed-table').forEach(function(table){
            if (!table._tableManager) {
                try {
                    if (window.TableManager) {
                        // Use explicit window.TableManager to avoid scope issues
                        table._tableManager = new window.TableManager(table);
                    } else {
                        // try fallback to global identifier
                        table._tableManager = new TableManager ? new TableManager(table) : null;
                    }
                } catch(e){ console.warn('TableManager init failed', e); }
            }
        });
        if (window.addExportButtonsToTables) {
            try { addExportButtonsToTables(); } catch(e){ console.warn('addExportButtonsToTables failed', e); }
        }
        attachExportFallbacks();
        // initialization complete
    }

    // quick diagnostics removed in production

    // Ensure TableManager is ready: retry if script loaded later
    function ensureTableManagerInit(retries = 10, delay = 150) {
        let attempts = 0;
        const iv = setInterval(() => {
            attempts += 1;
            const tables = document.querySelectorAll('.managed-table');
            if (window.TableManager) {
                tables.forEach(t => { if (!t._tableManager) { try { new TableManager(t); } catch(e){ console.warn('TableManager init failed on retry', e); } } });
                if (window.addExportButtonsToTables) {
                    try { addExportButtonsToTables(); } catch(e){ console.warn('addExportButtonsToTables failed on retry', e); }
                }
                attachExportFallbacks();
                // ready
                clearInterval(iv);
                return;
            }
            if (attempts >= retries) {
                clearInterval(iv);
                console.warn('TableManager not available after retries');
            }
        }, delay);
    }

    // Global fallback: delegated handlers if per-table listeners weren't attached
    function attachGlobalFallbacks() {
        // Export buttons fallback
        document.addEventListener('click', function(e){
            const bex = e.target.closest('.btn-export-excel');
            const bpdf = e.target.closest('.btn-export-pdf');
            if (bex) {
                const wrapper = bex.closest('.content-table');
                const table = wrapper ? wrapper.querySelector('.exportable-table') : document.querySelector('.exportable-table');
                if (table) {
                    try { exportTableToExcel(table); } catch(err){ console.warn('Global fallback export excel failed', err); }
                }
            }
            if (bpdf) {
                const wrapper = bpdf.closest('.content-table');
                const table = wrapper ? wrapper.querySelector('.exportable-table') : document.querySelector('.exportable-table');
                if (table) {
                    try { exportTableToPDF(table); } catch(err){ console.warn('Global fallback export pdf failed', err); }
                }
            }
        });

        // Search input fallback: delegated input handler
        document.addEventListener('input', function(e){
            if (!e.target.matches || !e.target.matches('.table-search-input')) return;
            const input = e.target;
            const wrapper = input.closest('.content-table');
            const table = wrapper ? wrapper.querySelector('.managed-table') : document.querySelector('.managed-table');
            if (!table) return;
            let manager = table._tableManager;
            // If manager missing but constructor available, create it on-demand
            if (!manager && window.TableManager) {
                try { table._tableManager = new window.TableManager(table); manager = table._tableManager; } catch(err){ console.warn('create TableManager on-demand failed', err); }
            }
            if (manager) {
                manager.filterState.search = input.value.toLowerCase().trim();
                manager.applyGlobalFilters();
            }
        });
    }

    // Helper: attach close listeners to known selectors inside the injected modal (top-level)
    function attachModalCloseBindings(container) {
        try {
            // Delegated click handler on the container: covers many variants and dynamically-added controls
            const clickHandler = function(ev){
                try {
                    const target = ev.target;
                    const box = container.querySelector('.modal-box');
                    // If clicked an explicit close control
                    const closeSel = target.closest('.modal-close, .js-close-detail-modal, [data-dismiss="modal"], [data-bs-dismiss], .close, .btn-close, [aria-label="Close"]');
                    if (closeSel) {
                        ev.preventDefault();
                        container.innerHTML = '';
                        document.body.classList.remove('no-scroll');
                        cleanup();
                        return;
                    }
                    // If clicked outside the modal box but inside overlay → close
                    const overlay = target.closest('.modal-overlay');
                    if (overlay && box && !target.closest('.modal-box')) {
                        ev.preventDefault();
                        container.innerHTML = '';
                        document.body.classList.remove('no-scroll');
                        cleanup();
                        return;
                    }
                } catch(e){ console.warn('modal delegated click handler error', e); }
            };

            const escHandler = function(ev){ if (ev.key === 'Escape') { container.innerHTML = ''; document.body.classList.remove('no-scroll'); cleanup(); } };

            function cleanup(){
                try { container.removeEventListener('click', clickHandler); } catch(_){}
                try { document.removeEventListener('keydown', escHandler); } catch(_){}
            }

            // Attach
            container.addEventListener('click', clickHandler);
            document.addEventListener('keydown', escHandler);
        } catch (e) { console.warn('attachModalCloseBindings failed', e); }
    }

    // diagnostics removed


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
                        if (data && data.html) return data.html;
                        // If we didn't get JSON, fetch as text and attempt to recover
                        return fetch(url).then(r=>r.text()).then(t=>{
                            const trimmed = (t || '').trim();
                            // Some servers may return a JSON string even when requested without AJAX headers.
                            // Try to detect a JSON payload and extract `.html` if present.
                            if (trimmed.startsWith('{') || trimmed.startsWith('\"{')) {
                                try {
                                    const parsed = JSON.parse(trimmed);
                                    if (parsed && parsed.html) return parsed.html;
                                } catch(e){ /* fallthrough to return raw text */ }
                            }
                            return t;
                        });
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
                    container.innerHTML = `<div class="action-detail-overlay">${html}</div>`;
                    document.body.classList.add('no-scroll');
                    // Attach explicit close listeners to any close controls inside injected HTML
                    attachModalCloseBindings(container);
                }).catch(err=>{
                    console.error('Error cargando detalle de acción', err);
                    // Try fetch text fallback
                    fetch(url).then(r=>r.text()).then(t=>{
                        let container = document.getElementById('action-modal-employee');
                        if (!container) { container = document.createElement('div'); container.id='action-modal-employee'; document.body.appendChild(container); }
                        container.innerHTML = `<div class="action-detail-overlay">${t}</div>`;
                        document.body.classList.add('no-scroll');
                        attachModalCloseBindings(container);
                    });
                });
        });

        // Close handler: support multiple variants (.modal-close, [data-dismiss], .close)
        document.addEventListener('click', function(e){
            const clickedClose = e.target.closest('.modal-close') || e.target.closest('.js-close-detail-modal') || e.target.closest('[data-dismiss="modal"]') || e.target.closest('[data-bs-dismiss]') || e.target.closest('.close') || e.target.closest('.btn-close') || e.target.closest('.action-detail-close');
            const overlay = e.target.closest('.action-detail-overlay');
            const card  = e.target.closest('.action-detail-card');
            // Close when explicit close clicked OR when clicking outside the card
            if (clickedClose || (overlay && !card)){
                const cont = document.getElementById('action-modal-employee');
                if (cont) cont.innerHTML='';
                document.body.classList.remove('no-scroll');
            }
        });

        // (modal binding is implemented at top-level attachModalCloseBindings)
    }

    // Run on load (if DOMContentLoaded already passed, run immediately)
    if (document.readyState === 'complete' || document.readyState === 'interactive') {
        setTimeout(()=>{ initTables(); attachActionModalHandler(); ensureTableManagerInit(); attachGlobalFallbacks(); }, 50);
    } else {
        document.addEventListener('DOMContentLoaded', function(){ initTables(); attachActionModalHandler(); ensureTableManagerInit(); attachGlobalFallbacks(); });
    }
})();
