document.addEventListener('DOMContentLoaded', function () {

    // --- REFERENCIAS ---
    const tableContainer = document.getElementById('table-content-wrapper');
    const searchInput = document.getElementById('table-search');
    const csrfToken = document.getElementById('csrf-token').value;
    const urlList = document.getElementById('url-list').value;

    // Referencias Modal
    const detailModal = document.getElementById('actionDetailModal');
    const detailContent = document.getElementById('modal-detail-content');

    // Referencias de paginación
    const pageInfo = document.getElementById('page-info');
    const btnPrev = document.getElementById('btn-prev');
    const btnNext = document.getElementById('btn-next');
    const currentPageDisplay = document.getElementById('current-page-display');

    // Estado de paginación
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

    // 2. Botones de paginación
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

    // 3. Cerrar Modal de detalle
    if (detailModal) {
        detailModal.addEventListener('click', (e) => {
            if (e.target === detailModal || e.target.closest('.js-close-detail-modal') || e.target.closest('.btn-close-modal')) {
                closeDetailModal();
            }
        });
    }

    // 4. DELEGACIÓN DE ACCIONES EN LA TABLA
    if (tableContainer) {
        tableContainer.addEventListener('click', function (e) {

            // A. VER DETALLE
            const detailBtn = e.target.closest('.js-view-detail');
            if (detailBtn) {
                e.preventDefault();
                openDetailModal(detailBtn.dataset.url);
                return;
            }

            // B. EDITAR ACCIÓN
            const editBtn = e.target.closest('.js-edit-action');
            if (editBtn) {
                e.preventDefault();
                const actionId = editBtn.dataset.actionId;
                window.location.href = `/personnel_actions/${actionId}/edit/`;
                return;
            }

            // C. REGISTRAR ACCIÓN
            const registerBtn = e.target.closest('.js-register-action');
            if (registerBtn) {
                e.preventDefault();
                const actionId = registerBtn.dataset.actionId;
                confirmRegisterAction(actionId);
                return;
            }

            // D. IMPRIMIR PDF
            const printBtn = e.target.closest('.js-print-action');
            if (printBtn) {
                e.preventDefault();
                const actionId = printBtn.dataset.actionId;
                window.open(`/personnel_actions/${actionId}/pdf/`, '_blank');
                return;
            }
        });
    }

    // --- FUNCIONES AUXILIARES ---

    /**
     * Fetch actualizado de la tabla con paginación y búsqueda
     */
    function fetchTableData(page = null) {
        const searchQuery = searchInput ? searchInput.value : '';
        const pageNumber = page || currentPage;

        let url = `${urlList}?page=${pageNumber}`;
        if (searchQuery) {
            url += `&q=${encodeURIComponent(searchQuery)}`;
        }

        fetch(url, {
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        })
            .then(res => res.json())
            .then(data => {
                if (data.html) {
                    tableContainer.innerHTML = data.html;
                }

                // Actualizar paginación
                currentPage = data.page_number || 1;
                totalPages = data.num_pages || 1;

                if (pageInfo) {
                    const start = ((currentPage - 1) * 10) + 1;
                    const end = Math.min(currentPage * 10, data.total_records || 0);
                    pageInfo.textContent = `Mostrando ${start} a ${end} registros de ${data.total_records} registros`;
                }

                if (currentPageDisplay) {
                    currentPageDisplay.textContent = currentPage;
                }

                if (btnPrev) {
                    btnPrev.disabled = !data.has_previous;
                }
                if (btnNext) {
                    btnNext.disabled = !data.has_next;
                }
            })
            .catch(err => {
                console.error('Error al cargar datos:', err);
            });
    }

    /**
     * Abrir modal de detalle
     */
    function openDetailModal(url) {
        fetch(url, {
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        })
            .then(res => res.text())
            .then(html => {
                detailContent.innerHTML = html;
                detailModal.classList.remove('hidden');
                document.body.classList.add('modal-open');
            })
            .catch(err => {
                console.error('Error al cargar detalle:', err);
                if (typeof Swal !== 'undefined') {
                    Swal.fire('Error', 'No se pudo cargar el detalle', 'error');
                }
            });
    }

    /**
     * Cerrar modal de detalle
     */
    function closeDetailModal() {
        detailModal.classList.add('hidden');
        detailContent.innerHTML = '';
        document.body.classList.remove('modal-open');
    }

    /**
     * Confirmar registro de acción
     */
    function confirmRegisterAction(actionId) {
        if (typeof Swal === 'undefined') {
            alert('¿Está seguro de registrar esta acción?');
            registerAction(actionId);
            return;
        }

        Swal.fire({
            title: '¿Registrar Acción?',
            text: 'Una vez registrada, no podrá ser editada.',
            icon: 'warning',
            showCancelButton: true,
            confirmButtonColor: '#3b82f6',
            cancelButtonColor: '#6b7280',
            confirmButtonText: 'Sí, registrar',
            cancelButtonText: 'Cancelar'
        }).then((result) => {
            if (result.isConfirmed) {
                registerAction(actionId);
            }
        });
    }

    /**
     * Registrar acción vía AJAX
     */
    function registerAction(actionId) {
        fetch(`/personnel_actions/${actionId}/register/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrfToken,
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    if (typeof Swal !== 'undefined') {
                        Swal.fire('¡Registrada!', data.message || 'Acción registrada correctamente', 'success');
                    }
                    fetchTableData();
                } else {
                    if (typeof Swal !== 'undefined') {
                        Swal.fire('Error', data.message || 'No se pudo registrar', 'error');
                    }
                }
            })
            .catch(err => {
                console.error('Error:', err);
                if (typeof Swal !== 'undefined') {
                    Swal.fire('Error', 'Error de conexión', 'error');
                }
            });
    }

});
