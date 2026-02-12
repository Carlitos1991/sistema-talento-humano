document.addEventListener('DOMContentLoaded', function () {

    // --- REFERENCIAS ---
    const tableContainer = document.getElementById('table-content-wrapper');
    const searchInput = document.getElementById('table-search');
    const csrfToken = document.getElementById('csrf-token').value;
    const urlList = document.getElementById('url-list').value;

    // Referencias Modal
    const modalOverlay = document.getElementById('modal-create-action');
    const modalContentContainer = document.getElementById('modal-body-content');

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
                fetchTableData(urlList + `?q=${e.target.value}&page=1`);
            }, 300);
        });
    }

    // 2. Botones de paginación
    if (btnPrev) {
        btnPrev.addEventListener('click', () => {
            if (currentPage > 1) {
                const searchQuery = searchInput ? searchInput.value : '';
                const url = urlList + `?page=${currentPage - 1}${searchQuery ? '&q=' + searchQuery : ''}`;
                fetchTableData(url);
            }
        });
    }

    if (btnNext) {
        btnNext.addEventListener('click', () => {
            if (currentPage < totalPages) {
                const searchQuery = searchInput ? searchInput.value : '';
                const url = urlList + `?page=${currentPage + 1}${searchQuery ? '&q=' + searchQuery : ''}`;
                fetchTableData(url);
            }
        });
    }

    // 3. Cerrar Modal
    if (modalOverlay) {
        modalOverlay.addEventListener('click', (e) => {
            if (e.target === modalOverlay) {
                closeModal();
            }
        });
    }

    // 4. DELEGACIÓN DE ACCIONES EN LA TABLA
    if (tableContainer) {
        tableContainer.addEventListener('click', function (e) {

            // A. GENERAR ACCIÓN
            const generateBtn = e.target.closest('.js-generate-action');
            if (generateBtn) {
                e.preventDefault();
                const employeeId = generateBtn.dataset.employeeId;
                openGenerateActionModal(employeeId);
                return;
            }
            
            // B. VER HISTORIAL
            const historyBtn = e.target.closest('.js-view-history');
            if (historyBtn) {
                e.preventDefault();
                const historyEmployeeId = historyBtn.dataset.employeeId;
                window.location.href = `/personnel_actions/history/${historyEmployeeId}/`;
                return;
            }
        });
    }

    // --- FUNCIONES AUXILIARES ---

    function openGenerateActionModal(employeeId) {
        // Cargar el formulario de creación de acción con el empleado preseleccionado
        const url = `/personnel_actions/create/?employee_id=${employeeId}`;
        
        fetch(url, {
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        })
        .then(res => {
            if (!res.ok) {
                throw new Error(`HTTP error! status: ${res.status}`);
            }
            return res.text();
        })
        .then(html => {
            modalContentContainer.innerHTML = html;
            modalOverlay.classList.remove('hidden');
            document.body.classList.add('modal-open');
            // Inicializar plugins del formulario
            initModalPlugins();
        })
        .catch(err => {
            console.error('Error al abrir modal:', err);
            if (typeof Swal !== 'undefined') {
                Swal.fire('Error', 'No se pudo cargar el formulario', 'error');
            }
        });
    }

    function closeModal() {
        modalOverlay.classList.add('hidden');
        modalContentContainer.innerHTML = '';
        document.body.classList.remove('modal-open');
    }

    // Exponer closeModal globalmente para que funcione con onclick
    window.closeModal = closeModal;

    function initModalPlugins() {
        // Inicializar Select2 para selects con clase .select2
        if (typeof $ !== 'undefined' && $.fn.select2) {
            $('.select2').select2({
                dropdownParent: modalOverlay,
                width: '100%'
            });
        }

        // Inicializar el manejo del formulario
        const form = modalContentContainer.querySelector('form');
        if (form) {
            form.addEventListener('submit', handleFormSubmit);
        }

        // Manejador para botón cancelar
        const btnCancel = modalContentContainer.querySelector('.btn-cancel');
        if (btnCancel) {
            btnCancel.addEventListener('click', closeModal);
        }
    }

    function handleFormSubmit(e) {
        e.preventDefault();
        const form = e.target;
        const formData = new FormData(form);

        fetch(form.action, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                Swal.fire({
                    icon: 'success',
                    title: 'Éxito',
                    text: data.message || 'Acción creada correctamente',
                    showConfirmButton: false,
                    timer: 1500
                }).then(() => {
                    closeModal();
                    // Recargar la tabla
                    const searchQuery = searchInput ? searchInput.value : '';
                    fetchTableData(urlList + `?page=${currentPage}${searchQuery ? '&q=' + searchQuery : ''}`);
                });
            } else if (data.errors) {
                // Mostrar errores del formulario
                let errorHtml = '<ul style="text-align: left;">';
                for (const [field, errors] of Object.entries(data.errors)) {
                    errorHtml += `<li>${errors.join(', ')}</li>`;
                }
                errorHtml += '</ul>';
                
                Swal.fire({
                    icon: 'error',
                    title: 'Errores en el formulario',
                    html: errorHtml
                });
            } else {
                Swal.fire('Error', data.message || 'Error al guardar', 'error');
            }
        })
        .catch(err => {
            console.error('Error al enviar formulario:', err);
            Swal.fire('Error', 'Ocurrió un error al procesar la solicitud', 'error');
        });
    }

    function fetchTableData(url) {
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
            pageInfo.textContent = `Mostrando ${paginationData.start_index} a ${paginationData.end_index} de ${paginationData.total_count} empleados`;
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
