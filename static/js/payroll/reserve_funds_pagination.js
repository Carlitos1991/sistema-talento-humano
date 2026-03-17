// JS for pagination and quick search in Reserve Funds
(function(){
    const container = document.getElementById('reserve-container');
    if(!container) return;

    const tableContent = document.getElementById('reserve-table-content');
    const searchInput = document.getElementById('reserve-search-input');
    const prevBtn = document.getElementById('reserve-prev-btn');
    const nextBtn = document.getElementById('reserve-next-btn');
    const pageInfo = document.getElementById('reserve-page-info');

    let currentPage = 1;
    let lastQuery = '';
    let isLoading = false;

    function getCSRF() {
        const cookieName = 'csrftoken';
        const cookies = document.cookie.split(';').map(c=>c.trim());
        for(const c of cookies){
            if(c.startsWith(cookieName+'=')) return decodeURIComponent(c.split('=')[1]);
        }
        return '';
    }

    function fetchPage(page, query){
        if(isLoading) return;
        isLoading = true;
        const url = new URL(window.location.href);
        url.searchParams.set('page', page);
        if(query) url.searchParams.set('q', query);
        fetch(url.toString(), {
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            },
            credentials: 'same-origin'
        }).then(r=>r.json())
        .then(data=>{
            if(data.html) tableContent.innerHTML = data.html;
                if(data.pagination){
                currentPage = data.pagination.current_page;
                const totalPages = data.pagination.total_pages || data.pagination.num_pages || 1;
                const start = data.pagination.start_index || data.pagination.start || 0;
                const end = data.pagination.end_index || data.pagination.end || 0;
                const total = data.pagination.total_count || data.pagination.total || 0;

                // Build a pagination-container compatible with TableManager styles
                let tableApp = document.querySelector('#table-app') || document.body;
                let pagContainer = document.querySelector('.pagination-container[data-tm-for]');
                if(!pagContainer){
                    pagContainer = document.createElement('div');
                    pagContainer.className = 'pagination-container';
                    // place after the nearest .content-table if exists
                    const contentTable = document.querySelector('.content-table');
                    if(contentTable && contentTable.parentNode){
                        contentTable.parentNode.insertBefore(pagContainer, contentTable.nextSibling);
                    } else {
                        document.body.appendChild(pagContainer);
                    }
                    // Persist current state so it survives modal close or navigation
                    try{
                        sessionStorage.setItem('reserve_funds_q', lastQuery || '');
                        sessionStorage.setItem('reserve_funds_page', String(currentPage));
                    }catch(e){/* ignore */}
                }

                // Associate the pagination container explicitly to this table so TableManager recognizes it
                try{
                    const table = document.querySelector('.managed-table');
                    if(table && table.dataset.tmId){
                        pagContainer.dataset.tmFor = table.dataset.tmId;
                    } else if (table) {
                        // ensure table has tmId similar to TableManager behavior
                        table.dataset.tmId = 'tm-' + Math.random().toString(36).slice(2,8);
                        pagContainer.dataset.tmFor = table.dataset.tmId;
                    }
                }catch(e){/* ignore */}

                const prevDisabled = !data.pagination.has_previous;
                const nextDisabled = !data.pagination.has_next;
                const showControls = totalPages > 1 && total > 0;

                pagContainer.innerHTML = `\
                    <div class="pagination-info">\
                        Mostrando ${start}-${end} de ${total}\
                    </div>\
                    <div class="pagination-controls" style="${!showControls ? 'visibility:hidden;' : ''}">\
                        <button class="page-btn btn-first" title="Primera" ${prevDisabled ? 'disabled' : ''}>\
                            <i class="fas fa-angle-double-left"></i>\
                        </button>\
                        <button class="page-btn btn-prev" title="Anterior" ${prevDisabled ? 'disabled' : ''}>\
                            <i class="fas fa-angle-left"></i>\
                        </button>\
                        <div class="page-input-wrapper">\
                            <input type="number" class="page-input" value="${data.pagination.current_page}" min="1" max="${totalPages}">\
                            <span class="total-pages-badge">de ${totalPages}</span>\
                        </div>\
                        <button class="page-btn btn-next" title="Siguiente" ${nextDisabled ? 'disabled' : ''}>\
                            <i class="fas fa-angle-right"></i>\
                        </button>\
                        <button class="page-btn btn-last" title="Última" ${nextDisabled ? 'disabled' : ''}>\
                            <i class="fas fa-angle-double-right"></i>\
                        </button>\
                    </div>`;

                // Attach events to the new controls
                const btnPrev = pagContainer.querySelector('.btn-prev');
                const btnNext = pagContainer.querySelector('.btn-next');
                const btnFirst = pagContainer.querySelector('.btn-first');
                const btnLast = pagContainer.querySelector('.btn-last');
                const input = pagContainer.querySelector('.page-input');

                if(btnPrev) btnPrev.onclick = () => { if(currentPage>1) fetchPage(currentPage-1, lastQuery); };
                if(btnNext) btnNext.onclick = () => { if(currentPage<totalPages) fetchPage(currentPage+1, lastQuery); };
                if(btnFirst) btnFirst.onclick = () => { fetchPage(1, lastQuery); };
                if(btnLast) btnLast.onclick = () => { fetchPage(totalPages, lastQuery); };
                if(input) input.onchange = () => {
                    let p = parseInt(input.value||'1',10);
                    if(isNaN(p) || p<1) p = 1;
                    if(p>totalPages) p = totalPages;
                    fetchPage(p, lastQuery);
                };
            }
        }).catch(err=>{
            console.error('Error loading page:', err);
        }).finally(()=>{ isLoading=false; });
    }

    let debounceTimer = null;
    function onSearch(){
        const q = searchInput.value.trim();
        if(q === lastQuery) return;
        lastQuery = q;
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(()=>{
            fetchPage(1, q);
        }, 350);
    }

    if(prevBtn) prevBtn.addEventListener('click', function(){ if(currentPage>1) fetchPage(currentPage-1, lastQuery); });
    if(nextBtn) nextBtn.addEventListener('click', function(){ fetchPage(currentPage+1, lastQuery); });
    if(searchInput) searchInput.addEventListener('input', onSearch);

    // Restore from sessionStorage first (keeps filter after modal close), fallback to URL params
    const storedQ = (function(){ try { return sessionStorage.getItem('reserve_funds_q')||'' } catch(e){ return ''; } })();
    const storedPage = (function(){ try { return parseInt(sessionStorage.getItem('reserve_funds_page')||'1',10) } catch(e){ return 1 } })();
    const urlParams = new URLSearchParams(window.location.search);
    const urlPage = parseInt(urlParams.get('page')||'1',10);
    const urlQ = urlParams.get('q')||'';

    const initialQ = storedQ || urlQ || '';
    const initialPage = storedQ ? (storedPage || 1) : (urlPage || 1);

    if(searchInput && initialQ) searchInput.value = initialQ;
    lastQuery = initialQ;
    fetchPage(initialPage, initialQ);
})();
