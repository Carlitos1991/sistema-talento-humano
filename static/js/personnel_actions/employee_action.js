document.addEventListener('DOMContentLoaded', function () {

    // --- REFERENCIAS ---
    const tableContainer = document.getElementById('table-content-wrapper');
    const searchInput = document.getElementById('table-search');
    const searchButton = document.getElementById('table-search-btn');
    const csrfToken = document.getElementById('csrf-token').value;
    const urlList = document.getElementById('url-list').value;

    // Referencias Modal
    const modalOverlay = document.getElementById('modal-create-action');
    const modalContentContainer = document.getElementById('modal-body-content');

    // Referencias de paginación
    const pageInfo = document.getElementById('page-info');
    const paginationControls = document.getElementById('pagination-controls');
    const btnFirst = document.getElementById('btn-first');
    const btnPrev = document.getElementById('btn-prev');
    const btnNext = document.getElementById('btn-next');
    const btnLast = document.getElementById('btn-last');
    const pageInput = document.getElementById('page-input');
    const totalPagesDisplay = document.getElementById('total-pages-display');

    // Estado de paginación
    let currentPage = window.initialPagination ? window.initialPagination.current_page : 1;
    let totalPages = window.initialPagination ? window.initialPagination.total_pages : 1;

    // Inicializar botones de paginación con datos del servidor
    if (window.initialPagination) {
        if (btnFirst) btnFirst.disabled = !window.initialPagination.has_previous;
        if (btnPrev) btnPrev.disabled = !window.initialPagination.has_previous;
        if (btnNext) btnNext.disabled = !window.initialPagination.has_next;
        if (btnLast) btnLast.disabled = !window.initialPagination.has_next;

        if (pageInput) {
            pageInput.value = window.initialPagination.current_page || 1;
            pageInput.max = window.initialPagination.total_pages || 1;
        }

        if (totalPagesDisplay) {
            totalPagesDisplay.textContent = `de ${window.initialPagination.total_pages || 1}`;
        }

        if (paginationControls) {
            paginationControls.style.visibility = (window.initialPagination.total_pages || 1) <= 1 ? 'hidden' : 'visible';
        }
    }

    // --- EVENTOS ---

    function getSearchQuery() {
        return searchInput ? (searchInput.value || '').trim() : '';
    }

    function buildListUrl(page, query) {
        const safePage = Number(page) || 1;
        const safeQuery = (query || '').trim();
        if (safeQuery) {
            return urlList + `?page=${safePage}&q=${encodeURIComponent(safeQuery)}`;
        }
        return urlList + `?page=${safePage}`;
    }

    function triggerSearch() {
        currentPage = 1;
        fetchTableData(buildListUrl(1, getSearchQuery()));
    }

    function goToPage(page) {
        const targetPage = Math.max(1, Math.min(Number(page) || 1, totalPages || 1));
        fetchTableData(buildListUrl(targetPage, getSearchQuery()));
    }

    // 1. Buscador: solo Enter o click en lupa
    if (searchInput) {
        searchInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                triggerSearch();
            }
        });
    }

    if (searchButton) {
        searchButton.addEventListener('click', (e) => {
            e.preventDefault();
            triggerSearch();
        });
    }

    // 2. Botones de paginación
    if (btnFirst) {
        btnFirst.addEventListener('click', () => {
            if (currentPage !== 1) {
                goToPage(1);
            }
        });
    }

    if (btnPrev) {
        btnPrev.addEventListener('click', () => {
            if (currentPage > 1) {
                goToPage(currentPage - 1);
            }
        });
    }

    if (btnNext) {
        btnNext.addEventListener('click', () => {
            if (currentPage < totalPages) {
                goToPage(currentPage + 1);
            }
        });
    }

    if (btnLast) {
        btnLast.addEventListener('click', () => {
            if (currentPage !== totalPages) {
                goToPage(totalPages);
            }
        });
    }

    if (pageInput) {
        const commitPageInput = () => {
            goToPage(pageInput.value);
        };

        pageInput.addEventListener('change', commitPageInput);
        pageInput.addEventListener('keydown', (event) => {
            if (event.key === 'Enter') {
                event.preventDefault();
                commitPageInput();
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

        if (window.PersonnelActionModal && typeof window.PersonnelActionModal.init === 'function') {
            window.PersonnelActionModal.init();
        }

        // Inicializar el manejo del formulario
        const form = modalContentContainer.querySelector('form');
        if (form) {
            clearFormErrors(form);
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

        clearFormErrors(form);

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
                    fetchTableData(buildListUrl(currentPage, getSearchQuery()));
                });
            } else if (data.errors) {
                showFormErrors(form, data.errors);
            } else {
                if (typeof Swal !== 'undefined') {
                    Swal.fire('Error', data.message || 'Error al guardar', 'error');
                }
            }
        })
        .catch(err => {
            console.error('Error al enviar formulario:', err);
            if (typeof Swal !== 'undefined') {
                Swal.fire('Error', 'Ocurrió un error al procesar la solicitud', 'error');
            }
        });
    }

    function clearFormErrors(form) {
        const invalidFields = form.querySelectorAll('.is-invalid');
        invalidFields.forEach((field) => field.classList.remove('is-invalid'));

        const errorBoxes = form.querySelectorAll('.invalid-feedback');
        errorBoxes.forEach((box) => {
            box.textContent = '';
            box.classList.remove('show');
        });

        const errorGroups = form.querySelectorAll('.form-group.has-error');
        errorGroups.forEach((group) => group.classList.remove('has-error'));
    }

    function showFormErrors(form, errors) {
        Object.entries(errors).forEach(([fieldName, messages]) => {
            const messageText = Array.isArray(messages) ? messages.join(' ') : String(messages);

            const field = form.querySelector(`[name="${fieldName}"]`);
            const feedback = field ? field.parentElement.querySelector('.invalid-feedback') : null;
            const group = field ? field.closest('.form-group') : null;

            if (field) {
                field.classList.add('is-invalid');
            }

            if (feedback) {
                feedback.textContent = messageText;
                feedback.classList.add('show');
            }

            if (group) {
                group.classList.add('has-error');
            }
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

        if (totalPagesDisplay) {
            totalPagesDisplay.textContent = `de ${totalPages}`;
        }

        if (pageInput) {
            pageInput.value = currentPage;
            pageInput.max = totalPages;
        }

        if (paginationControls) {
            paginationControls.style.visibility = totalPages <= 1 ? 'hidden' : 'visible';
        }

        if (btnFirst) {
            btnFirst.disabled = !paginationData.has_previous;
        }
        if (btnPrev) {
            btnPrev.disabled = !paginationData.has_previous;
        }
        if (btnNext) {
            btnNext.disabled = !paginationData.has_next;
        }
        if (btnLast) {
            btnLast.disabled = !paginationData.has_next;
        }
    }
});
