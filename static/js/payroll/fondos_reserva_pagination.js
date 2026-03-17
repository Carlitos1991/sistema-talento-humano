// JS para paginación y búsqueda rápida en Fondos de Reserva
(function(){
    const container = document.getElementById('fondos-reserva-container');
    if(!container) return;

    const tableContent = document.getElementById('fondos-table-content');
    const searchInput = document.getElementById('fondos-search-input');
    const prevBtn = document.getElementById('fondos-prev-btn');
    const nextBtn = document.getElementById('fondos-next-btn');
    const pageInfo = document.getElementById('fondos-page-info');

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
                pageInfo.innerHTML = `Página ${data.pagination.current_page} de ${totalPages} <br><small class="text-muted">Mostrando ${start}-${end} de ${total}</small>`;
                prevBtn.disabled = !data.pagination.has_previous;
                nextBtn.disabled = !data.pagination.has_next;
            }
        }).catch(err=>{
            console.error('Error cargando página:', err);
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

    prevBtn.addEventListener('click', function(){ if(currentPage>1) fetchPage(currentPage-1, lastQuery); });
    nextBtn.addEventListener('click', function(){ fetchPage(currentPage+1, lastQuery); });
    searchInput.addEventListener('input', onSearch);

    // Carga inicial usando parámetros si vienen en la página
    const urlParams = new URLSearchParams(window.location.search);
    const initialPage = parseInt(urlParams.get('page')||'1',10);
    const initialQ = urlParams.get('q')||'';
    if(initialQ) searchInput.value = initialQ;
    fetchPage(initialPage, initialQ);
})();
