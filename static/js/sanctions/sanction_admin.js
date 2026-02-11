document.addEventListener('DOMContentLoaded', function () {

    // --- REFERENCIAS ---
    const tableContainer = document.getElementById('table-content-wrapper');
    const searchInput = document.getElementById('table-search');
    const filterStatus = document.getElementById('filter-status');
    const filterSeverity = document.getElementById('filter-severity');
    const csrfToken = document.getElementById('csrf-token').value;
    const urlList = document.getElementById('url-list').value;

    // Referencias Modal
    const detailModal = document.getElementById('sanctionDetailModal');
    const detailContent = document.getElementById('modal-detail-content');

    // Referencias de paginación
    const pageInfo = document.getElementById('page-info');
    const btnPrev = document.getElementById('btn-prev');
    const btnNext = document.getElementById('btn-next');
    const currentPageDisplay = document.getElementById('current-page-display');

    // Estado de paginación y filtros
    let currentPage = window.initialPagination ? window.initialPagination.current_page : 1;
    let totalPages = window.initialPagination ? window.initialPagination.total_pages : 1;

    // Inicializar botones de paginación con datos del servidor
    if (window.initialPagination) {
        if (btnPrev) btnPrev.disabled = !window.initialPagination.has_previous;
        if (btnNext) btnNext.disabled = !window.initialPagination.has_next;
    }

    // --- EVENTOS ---

    // 1. Buscador
    let timeout = null;
    if (searchInput) {
        searchInput.addEventListener('keyup', (e) => {
            clearTimeout(timeout);
            timeout = setTimeout(() => {
                currentPage = 1;
                fetchTableData();
            }, 300);
        });
    }

    // 2. Filtros
    if (filterStatus) {
        filterStatus.addEventListener('change', () => {
            currentPage = 1;
            fetchTableData();
        });
    }

    if (filterSeverity) {
        filterSeverity.addEventListener('change', () => {
            currentPage = 1;
            fetchTableData();
        });
    }

    // 3. Botones de paginación
    if (btnPrev) {
        btnPrev.addEventListener('click', () => {
            if (currentPage > 1) {
                fetchTableData(currentPage - 1);
            }
        });
    }

    if (btnNext) {
        btnNext.addEventListener('click', () => {
            if (currentPage < totalPages) {
                fetchTableData(currentPage + 1);
            }
        });
    }

    // 4. Cerrar Modal de detalle
    if (detailModal) {
        detailModal.addEventListener('click', (e) => {
            if (e.target === detailModal || e.target.closest('.js-close-detail-modal')) {
                closeDetailModal();
            }
        });
    }

    // 5. DELEGACIÓN DE ACCIONES EN LA TABLA
    if (tableContainer) {
        tableContainer.addEventListener('click', function (e) {

            // A. VER DETALLE
            const detailBtn = e.target.closest('.js-view-detail');
            if (detailBtn) {
                e.preventDefault();
                openDetailModal(detailBtn.dataset.url);
                return;
            }

            // B. CAMBIAR ESTADO
            const statusBtn = e.target.closest('.js-change-status');
            if (statusBtn) {
                e.preventDefault();
                changeStatus(statusBtn.dataset.url, statusBtn.dataset.currentStatus);
                return;
            }
        });
    }

    // --- FUNCIONES ---

    function openDetailModal(url) {
        fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
            .then(res => res.text())
            .then(html => {
                if (detailContent) {
                    detailContent.innerHTML = html;
                    detailModal.classList.remove('hidden');
                }
            })
            .catch(err => {
                console.error('Error al abrir detalle:', err);
                Swal.fire('Error', 'No se pudo cargar el detalle de la sanción', 'error');
            });
    }

    function closeDetailModal() {
        detailModal.classList.add('hidden');
        if (detailContent) detailContent.innerHTML = '';
    }

    function changeStatus(url, currentStatus) {
        // Opciones de estado
        const statusOptions = {
            'REGISTERED': 'Registrada',
            'ACTIVE': 'Activa',
            'COMPLETED': 'Cumplida',
            'CANCELED': 'Anulada'
        };

        // Crear opciones HTML
        let optionsHtml = '';
        for (const [value, label] of Object.entries(statusOptions)) {
            const selected = value === currentStatus ? 'selected' : '';
            optionsHtml += `<option value="${value}" ${selected}>${label}</option>`;
        }

        Swal.fire({
            title: 'Cambiar Estado de Sanción',
            html: `
                <select id="new-status" class="swal2-input" style="width: 80%;">
                    ${optionsHtml}
                </select>
            `,
            showCancelButton: true,
            confirmButtonText: 'Cambiar Estado',
            cancelButtonText: 'Cancelar',
            confirmButtonColor: '#3085d6',
            cancelButtonColor: '#d33',
            preConfirm: () => {
                const newStatus = document.getElementById('new-status').value;
                if (!newStatus) {
                    Swal.showValidationMessage('Debe seleccionar un estado');
                    return false;
                }
                return newStatus;
            }
        }).then((result) => {
            if (result.isConfirmed) {
                const formData = new FormData();
                formData.append('status', result.value);

                fetch(url, {
                    method: 'POST',
                    body: formData,
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest',
                        'X-CSRFToken': csrfToken
                    }
                })
                    .then(res => res.json())
                    .then(data => {
                        if (data.success) {
                            const Toast = Swal.mixin({
                                toast: true,
                                position: 'top-end',
                                showConfirmButton: false,
                                timer: 3000,
                                timerProgressBar: true
                            });
                            Toast.fire({
                                icon: 'success',
                                title: data.message
                            });
                            fetchTableData();
                        } else {
                            Swal.fire('Error', data.message || 'No se pudo cambiar el estado', 'error');
                        }
                    })
                    .catch(err => {
                        console.error(err);
                        Swal.fire('Error', 'Error de comunicación con el servidor', 'error');
                    });
            }
        });
    }

    function fetchTableData(page = null) {
        if (page !== null) {
            currentPage = page;
        }

        const searchQuery = searchInput ? searchInput.value : '';
        const statusFilter = filterStatus ? filterStatus.value : '';
        const severityFilter = filterSeverity ? filterSeverity.value : '';

        let url = urlList + `?page=${currentPage}`;
        if (searchQuery) url += `&q=${searchQuery}`;
        if (statusFilter) url += `&status=${statusFilter}`;
        if (severityFilter) url += `&severity=${severityFilter}`;

        fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
            .then(res => res.json())
            .then(data => {
                tableContainer.innerHTML = data.html;
                
                if (data.pagination) {
                    updatePagination(data.pagination);
                }
            })
            .catch(err => {
                console.error('Error al cargar datos:', err);
            });
    }

    function updatePagination(paginationData) {
        currentPage = paginationData.current_page;
        totalPages = paginationData.total_pages;

        if (pageInfo) {
            pageInfo.textContent = `Mostrando ${paginationData.start_index} a ${paginationData.end_index} registros de ${paginationData.total_count} registros`;
        }

        if (currentPageDisplay) {
            currentPageDisplay.textContent = currentPage;
        }

        if (btnPrev) {
            btnPrev.disabled = !paginationData.has_previous;
        }
        if (btnNext) {
            btnNext.disabled = !paginationData.has_next;
        }
    }
});
