(function() {
    'use strict';

    const tableContainer = document.getElementById('table-content-wrapper');
    const searchInput = document.getElementById('table-search-permits');
    const filterStatusSelect = document.getElementById('filter-status');
    const modalOverlay = document.getElementById('modal-overlay');
    const modalContentContainer = document.getElementById('modal-content-container');
    const modalResponseOverlay = document.getElementById('modal-response-overlay');
    const modalResponseContainer = document.getElementById('modal-response-container');
    
    const urlList = '/permitrequest/admin/';
    let currentPage = 1;
    let currentStatus = '';

    // ========================================================
    // FILTROS POR ESTADO (CARDS CLICLEABLES)
    // ========================================================
    window.filterPermitsByStatus = function(status) {
        currentStatus = status === 'all' ? '' : status;
        currentPage = 1;
        
        // Actualizar clases de las cards
        document.querySelectorAll('.stat-card').forEach(card => {
            card.classList.remove('color-one', 'color-two', 'color-three', 'color-four');
            card.classList.add('opacity-low');
        });
        
        const activeCard = document.getElementById(`card-filter-${status === 'all' ? 'all' : status.toLowerCase()}`);
        if (activeCard) {
            activeCard.classList.remove('opacity-low');
            if (status === 'all' || status === '') activeCard.classList.add('color-one');
            else if (status === 'REQUESTED') activeCard.classList.add('color-two');
            else if (status === 'APPROVED') activeCard.classList.add('color-three');
            else if (status === 'REJECTED') activeCard.classList.add('color-four');
        }
        
        // Actualizar select
        filterStatusSelect.value = currentStatus;
        
        fetchTableData();
    };

    // ========================================================
    // BÚSQUEDA
    // ========================================================
    let searchTimeout;
    if (searchInput) {
        searchInput.addEventListener('input', function() {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                currentPage = 1;
                fetchTableData();
            }, 500);
        });
    }

    if (filterStatusSelect) {
        filterStatusSelect.addEventListener('change', function() {
            currentStatus = this.value;
            currentPage = 1;
            fetchTableData();
        });
    }

    // ========================================================
    // PAGINACIÓN
    // ========================================================
    const btnPrev = document.getElementById('btn-prev');
    const btnNext = document.getElementById('btn-next');

    if (btnPrev) {
        btnPrev.addEventListener('click', () => {
            if (currentPage > 1) {
                currentPage--;
                fetchTableData();
            }
        });
    }

    if (btnNext) {
        btnNext.addEventListener('click', () => {
            currentPage++;
            fetchTableData();
        });
    }

    // ========================================================
    // FETCH TABLA
    // ========================================================
    function fetchTableData() {
        const searchQuery = searchInput ? searchInput.value : '';
        let url = `${urlList}?page=${currentPage}`;
        
        if (searchQuery) url += `&q=${encodeURIComponent(searchQuery)}`;
        if (currentStatus) url += `&status=${currentStatus}`;

        fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
            .then(res => res.json())
            .then(data => {
                tableContainer.innerHTML = data.html;
                updatePagination(data.pagination);
                attachEventListeners();
            })
            .catch(err => {
                console.error('Error al cargar datos:', err);
            });
    }

    function updatePagination(paginationData) {
        const pageInfo = document.getElementById('page-info');
        if (pageInfo) {
            pageInfo.textContent = `Mostrando ${paginationData.start_index}-${paginationData.end_index} de ${paginationData.total_count}`;
        }
        if (btnPrev) btnPrev.disabled = !paginationData.has_previous;
        if (btnNext) btnNext.disabled = !paginationData.has_next;
    }

    // ========================================================
    // EVENT LISTENERS DINÁMICOS
    // ========================================================
    function attachEventListeners() {
        // Ver detalle
        document.querySelectorAll('.js-view-detail').forEach(btn => {
            btn.addEventListener('click', function() {
                const permitId = this.dataset.permitId;
                openDetailModal(permitId);
            });
        });

        // Aprobar
        document.querySelectorAll('.js-approve-permit').forEach(btn => {
            btn.addEventListener('click', function() {
                const permitId = this.dataset.permitId;
                openResponseModal(permitId, 'approve');
            });
        });

        // Rechazar
        document.querySelectorAll('.js-reject-permit').forEach(btn => {
            btn.addEventListener('click', function() {
                const permitId = this.dataset.permitId;
                openResponseModal(permitId, 'reject');
            });
        });
    }

    // ========================================================
    // MODALES
    // ========================================================
    function openDetailModal(permitId) {
        const url = `/permitrequest/admin/${permitId}/detail/`;
        
        fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
            .then(res => res.text())
            .then(html => {
                modalContentContainer.innerHTML = html;
                modalOverlay.classList.remove('hidden');
                document.body.style.overflow = 'hidden';
                
                // Event listener para cerrar
                document.querySelectorAll('.js-close-modal').forEach(btn => {
                    btn.addEventListener('click', closeDetailModal);
                });
            })
            .catch(err => {
                console.error('Error al abrir modal:', err);
                Swal.fire('Error', 'No se pudo cargar el detalle', 'error');
            });
    }

    function closeDetailModal() {
        modalOverlay.classList.add('hidden');
        modalContentContainer.innerHTML = '';
        document.body.style.overflow = '';
    }

    function openResponseModal(permitId, action) {
        const url = `/permitrequest/admin/${permitId}/${action}/`;
        
        fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
            .then(res => res.text())
            .then(html => {
                modalResponseContainer.innerHTML = html;
                modalResponseOverlay.classList.remove('hidden');
                document.body.style.overflow = 'hidden';
                
                // Event listeners
                document.querySelectorAll('.js-close-response-modal').forEach(btn => {
                    btn.addEventListener('click', closeResponseModal);
                });
                
                const form = document.getElementById('responsePermitForm');
                if (form) {
                    form.addEventListener('submit', (e) => handleResponseSubmit(e, permitId, action));
                }
            })
            .catch(err => {
                console.error('Error al abrir modal:', err);
                Swal.fire('Error', 'No se pudo cargar el formulario', 'error');
            });
    }

    function closeResponseModal() {
        modalResponseOverlay.classList.add('hidden');
        modalResponseContainer.innerHTML = '';
        document.body.style.overflow = '';
    }

    function handleResponseSubmit(e, permitId, action) {
        e.preventDefault();
        const form = e.target;
        const formData = new FormData(form);
        const url = `/permitrequest/admin/${permitId}/${action}/`;

        fetch(url, {
            method: 'POST',
            body: formData,
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    closeResponseModal();
                    Swal.fire({
                        icon: 'success',
                        title: 'Éxito',
                        text: data.message,
                        timer: 2000,
                        showConfirmButton: false
                    });
                    fetchTableData();
                } else {
                    Swal.fire('Error', data.message || 'Ocurrió un error', 'error');
                }
            })
            .catch(err => {
                console.error(err);
                Swal.fire('Error', 'Error de comunicación con el servidor', 'error');
            });
    }

    // ========================================================
    // INICIALIZACIÓN
    // ========================================================
    attachEventListeners();

})();
