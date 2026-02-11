document.addEventListener('DOMContentLoaded', function () {

    // --- REFERENCIAS ---
    const tableContainer = document.getElementById('table-content-wrapper');
    const searchInput = document.getElementById('table-search');
    const csrfToken = document.getElementById('csrf-token').value;
    const urlList = document.getElementById('url-list').value;

    // Referencias Modal
    const modalOverlay = document.getElementById('customModal');
    const modalContentContainer = document.getElementById('modal-dynamic-content');

    // Modal de historial
    // REMOVED - No longer needed as we redirect to admin page

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

    // 3. Cerrar Modal desde overlay o botón cerrar
    if (modalOverlay) {
        modalOverlay.addEventListener('click', (e) => {
            if (e.target === modalOverlay || e.target.closest('.btn-close-modal') || e.target.closest('.js-close-modal')) {
                closeModal();
            }
        });
    }

    // 4. REMOVED - History modal no longer needed

    // 5. DELEGACIÓN DE ACCIONES EN LA TABLA
    if (tableContainer) {
        tableContainer.addEventListener('click', function (e) {

            // A. GENERAR SANCIÓN
            const generateBtn = e.target.closest('.js-generate-sanction');
            if (generateBtn) {
                e.preventDefault();
                const employeeId = generateBtn.dataset.employeeId;
                openGenerateSanctionModal(employeeId);
                return;
            }

            // B. VER HISTORIAL - Redirect to admin page filtered by employee
            const historyBtn = e.target.closest('.js-view-history');
            if (historyBtn) {
                e.preventDefault();
                const employeeId = historyBtn.dataset.employeeId;
                window.location.href = `/sanctions/admin/employee/${employeeId}/`;
                return;
            }
        });
    }

    // --- FUNCIONES ---

    function openGenerateSanctionModal(employeeId) {
        const url = `/sanctions/generate/?employee_id=${employeeId}`;
        
        fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
            .then(res => res.text())
            .then(html => {
                modalContentContainer.innerHTML = html;
                modalOverlay.classList.remove('hidden');
                document.body.classList.add('modal-open'); // Block background scroll

                initModalPlugins();

                const form = modalContentContainer.querySelector('form');
                if (form) form.addEventListener('submit', handleSanctionFormSubmit);
            })
            .catch(err => {
                console.error('Error al abrir modal:', err);
                Swal.fire('Error', 'No se pudo cargar el formulario', 'error');
            });
    }

    // REMOVED - openHistoryModal function no longer needed

    function closeModal() {
        modalOverlay.classList.add('hidden');
        modalContentContainer.innerHTML = '';
        document.body.classList.remove('modal-open'); // Restore background scroll
    }

    // REMOVED - closeHistoryModal function no longer needed

    function initModalPlugins() {
        // Inicializar Select2
        if (typeof $ !== 'undefined' && $.fn.select2) {
            $('.select2').select2({
                width: '100%',
                dropdownParent: modalOverlay
            });
        }

        // Initialize custom accordion
        const accordionToggles = document.querySelectorAll('.accordion-toggle');
        accordionToggles.forEach(toggle => {
            toggle.addEventListener('click', function() {
                const targetId = this.getAttribute('data-target');
                const content = document.getElementById(targetId);
                
                if (content) {
                    const isOpen = content.style.display === 'block';
                    
                    if (isOpen) {
                        content.style.display = 'none';
                        content.classList.remove('show');
                        this.classList.add('collapsed');
                    } else {
                        content.style.display = 'block';
                        content.classList.add('show');
                        this.classList.remove('collapsed');
                    }
                }
            });
        });

        // Initialize custom file upload
        const fileInput = document.getElementById('id_attachment_file');
        if (fileInput) {
            fileInput.addEventListener('change', function() {
                const fileLabel = this.nextElementSibling;
                const fileNameSpan = fileLabel.querySelector('.file-name');
                const fileTextSpan = fileLabel.querySelector('.file-text');
                const container = this.parentElement;
                
                if (this.files && this.files.length > 0) {
                    fileNameSpan.textContent = this.files[0].name;
                    fileTextSpan.textContent = 'Archivo seleccionado:';
                    container.classList.add('has-file');
                } else {
                    fileNameSpan.textContent = 'Ningún archivo seleccionado';
                    fileTextSpan.textContent = 'Seleccionar archivo';
                    container.classList.remove('has-file');
                }
            });
        }
    }

    function handleSanctionFormSubmit(e) {
        e.preventDefault();
        const form = e.target;
        const formData = new FormData(form);

        // Limpiar errores previos
        form.querySelectorAll('.is-invalid').forEach(el => el.classList.remove('is-invalid'));
        form.querySelectorAll('.invalid-feedback').forEach(el => el.textContent = '');

        fetch(form.action, {
            method: 'POST',
            body: formData,
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        })
            .then(async res => {
                const contentType = res.headers.get('content-type');
                if (!contentType || !contentType.includes('application/json')) {
                    throw new Error('Respuesta no válida del servidor');
                }
                
                const data = await res.json();
                
                if (res.ok) {
                    closeModal();
                    const Toast = Swal.mixin({
                        toast: true,
                        position: 'top-end',
                        showConfirmButton: false,
                        timer: 3000,
                        timerProgressBar: true
                    });
                    Toast.fire({
                        icon: 'success',
                        title: data.message || 'Sanción registrada correctamente'
                    });
                } else {
                    if (res.status === 403) {
                        Swal.fire('Acceso denegado', data.message || 'No tiene permisos para realizar esta acción', 'error');
                    } else if (data.errors) {
                        showErrors(form, data.errors);
                    } else {
                        Swal.fire('Error', data.message || 'Ocurrió un error al guardar', 'error');
                    }
                }
            })
            .catch(err => {
                console.error(err);
                Swal.fire('Error', 'Error de comunicación con el servidor', 'error');
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

    function showErrors(form, errors) {
        for (const [field, msgs] of Object.entries(errors)) {
            const input = form.querySelector(`[name="${field}"]`);
            if (input) {
                input.classList.add('is-invalid');
                const feedback = input.parentNode.querySelector('.invalid-feedback');
                if (feedback) feedback.textContent = Array.isArray(msgs) ? msgs.join(', ') : msgs;
            }
        }
    }
});
