document.addEventListener('DOMContentLoaded', function () {

    // --- REFERENCIAS ---
    const tableContainer = document.getElementById('table-content-wrapper');
    const searchInput = document.getElementById('table-search');
    const csrfInput = document.getElementById('csrf-token');
    const urlListInput = document.getElementById('url-list');
    const csrfToken = csrfInput ? csrfInput.value : '';
    const urlList = urlListInput ? urlListInput.value : '';

    // Salir silenciosamente cuando el script se carga fuera de su vista objetivo.
    if (!tableContainer || !urlList) {
        return;
    }

    // Referencias Modal
    const detailModal = document.getElementById('actionDetailModal');
    const detailContent = document.getElementById('modal-detail-content');
    const editModal = document.getElementById('actionEditModal');
    const editContent = document.getElementById('modal-edit-content');

    // Referencias de paginación
    const pageInfo = document.getElementById('page-info');
    const btnPrev = document.getElementById('btn-prev');
    const btnNext = document.getElementById('btn-next');
    const currentPageDisplay = document.getElementById('current-page-display');

    // Estado de paginación
    let currentPage = window.initialPagination ? window.initialPagination.current_page : 1;
    let totalPages = window.initialPagination ? window.initialPagination.total_pages : 1;

    // Inicializar botones de paginación
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

    // 3. Cerrar modales
    if (detailModal) {
        detailModal.addEventListener('click', (e) => {
            if (e.target === detailModal || e.target.closest('.js-close-detail-modal') || e.target.closest('.btn-close-modal')) {
                closeDetailModal();
            }
        });
    }
    
    if (editModal) {
        editModal.addEventListener('click', (e) => {
            if (e.target === editModal || e.target.closest('.btn-close-modal')) {
                closeEditModal();
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
                openEditModal(actionId);
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

                if (btnPrev) btnPrev.disabled = !data.has_previous;
                if (btnNext) btnNext.disabled = !data.has_next;
            })
            .catch(err => console.error('Error:', err));
    }

    function openDetailModal(url) {
        if (!detailModal || !detailContent) {
            console.error('Modal de detalle no disponible en el DOM.');
            return;
        }

        fetch(url, {
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        })
            .then(async (res) => {
                const contentType = (res.headers.get('content-type') || '').toLowerCase();
                if (contentType.includes('application/json')) {
                    const data = await res.json();
                    return data && data.html ? data.html : '';
                }
                return await res.text();
            })
            .then((html) => {
                detailContent.innerHTML = html || '<div class="modal-body">No se pudo cargar el detalle.</div>';
                detailModal.classList.remove('hidden');
                document.body.classList.add('modal-open');
            })
            .catch(err => {
                console.error('Error:', err);
                if (typeof Swal !== 'undefined') {
                    Swal.fire('Error', 'No se pudo cargar el detalle', 'error');
                }
            });
    }

    function closeDetailModal() {
        if (!detailModal || !detailContent) {
            return;
        }

        detailModal.classList.add('hidden');
        detailContent.innerHTML = '';
        document.body.classList.remove('modal-open');
    }
    
    function openEditModal(actionId) {
        fetch(`/personnel_actions/${actionId}/edit/`, {
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        })
            .then(res => res.text())
            .then(html => {
                editContent.innerHTML = html;
                editModal.classList.remove('hidden');
                document.body.classList.add('modal-open');
                initEditModalPlugins();
            })
            .catch(err => {
                console.error('Error:', err);
                if (typeof Swal !== 'undefined') {
                    Swal.fire('Error', 'No se pudo cargar el formulario', 'error');
                }
            });
    }
    
    function closeEditModal() {
        // Destruir Select2 antes de cerrar (solo si está inicializado)
        if (typeof $ !== 'undefined' && $.fn.select2) {
            $('#modal-edit-content .select2').each(function() {
                if ($(this).hasClass('select2-hidden-accessible')) {
                    $(this).select2('destroy');
                }
            });
        }
        editModal.classList.add('hidden');
        editContent.innerHTML = '';
        document.body.classList.remove('modal-open');
    }
    
    window.closeModal = closeEditModal;
    
    function initEditModalPlugins() {
        // Inicializar Select2
        if (typeof $ !== 'undefined' && $.fn.select2) {
            $('#modal-edit-content .select2').select2({
                dropdownParent: $('#modal-edit-content'),
                width: '100%',
                language: 'es'
            });
        }

        // Manejar submit del formulario
        const form = editContent.querySelector('form');
        if (form) {
            form.addEventListener('submit', handleEditFormSubmit);
        }

        // Botón cancelar
        const btnCancel = editContent.querySelector('.btn-cancel');
        if (btnCancel) {
            btnCancel.addEventListener('click', closeEditModal);
        }
    }
    
    function handleEditFormSubmit(e) {
        e.preventDefault();
        const form = e.target;
        const formData = new FormData(form);

        fetch(form.action, {
            method: 'POST',
            body: formData,
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    if (typeof Swal !== 'undefined') {
                        Swal.fire('¡Actualizado!', data.message, 'success');
                    }
                    closeEditModal();
                    fetchTableData();
                } else {
                    if (typeof Swal !== 'undefined') {
                        Swal.fire('Error', 'No se pudo actualizar', 'error');
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
                        Swal.fire('¡Registrada!', data.message, 'success');
                    }
                    fetchTableData();
                } else {
                    if (typeof Swal !== 'undefined') {
                        Swal.fire('Error', data.message, 'error');
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
