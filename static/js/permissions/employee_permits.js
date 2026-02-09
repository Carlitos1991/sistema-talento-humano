document.addEventListener('DOMContentLoaded', function () {

    // --- REFERENCIAS ---
    const tableContainer = document.getElementById('table-content-wrapper');
    const searchInput = document.getElementById('table-search');
    const csrfToken = document.getElementById('csrf-token').value;
    const urlList = document.getElementById('url-list').value;

    // Referencias Modal
    const modalOverlay = document.getElementById('customModal');
    const modalContentContainer = document.getElementById('modal-dynamic-content');

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

    // =========================================================
    // MODAL VUE: HISTORIAL DE PERMISOS
    // =========================================================
    const HISTORY_MOUNT = '#permit-history-app';

    if (document.querySelector(HISTORY_MOUNT)) {
        const {createApp} = Vue;
        const appHistory = createApp({
            delimiters: ['[[', ']]'],
            data() {
                return {
                    isVisible: false,
                    employeeId: null,
                    employeeName: '',
                    employeeIdentification: '',
                    permits: [],
                    searchQuery: '',
                    currentPage: 1,
                    pageSize: 10
                }
            },
            computed: {
                filteredPermits() {
                    const term = this.searchQuery.toLowerCase().trim();
                    if (!term) return this.permits;
                    return this.permits.filter(permit =>
                        permit.permit_type__name.toLowerCase().includes(term) ||
                        (permit.reason && permit.reason.toLowerCase().includes(term))
                    );
                },
                totalPages() {
                    return Math.ceil(this.filteredPermits.length / this.pageSize) || 1;
                },
                paginatedPermits() {
                    const start = (this.currentPage - 1) * this.pageSize;
                    const end = start + this.pageSize;
                    return this.filteredPermits.slice(start, end);
                },
                startIndex() {
                    return this.filteredPermits.length === 0 ? 0 : (this.currentPage - 1) * this.pageSize + 1;
                },
                endIndex() {
                    return Math.min(this.currentPage * this.pageSize, this.filteredPermits.length);
                }
            },
            methods: {
                async open(employeeId) {
                    this.employeeId = employeeId;
                    this.searchQuery = '';
                    this.currentPage = 1;
                    await this.fetchHistory();
                    this.isVisible = true;
                },
                closeModal() {
                    this.isVisible = false;
                    this.permits = [];
                },
                async fetchHistory() {
                    if (!this.employeeId) return;
                    try {
                        const url = `/permitrequest/employees/${this.employeeId}/history/`;
                        const res = await fetch(url);
                        
                        if (!res.ok) {
                            throw new Error(`HTTP error! status: ${res.status}`);
                        }
                        
                        const data = await res.json();
                        if (data.success) {
                            this.employeeName = data.employee_name;
                            this.employeeIdentification = data.employee_identification;
                            this.permits = data.permits;
                        } else {
                            Swal.fire('Error', data.message || 'No se pudo cargar el historial', 'error');
                        }
                    } catch (e) {
                        console.error('Error al cargar historial:', e);
                        Swal.fire('Error', 'No se pudo cargar el historial de permisos', 'error');
                    }
                },
                formatDate(dateString) {
                    if (!dateString) return '-';
                    const date = new Date(dateString + 'T00:00:00');
                    return date.toLocaleDateString('es-EC', {
                        year: 'numeric',
                        month: '2-digit',
                        day: '2-digit'
                    });
                },
                getStatusLabel(status) {
                    const labels = {
                        'PENDING': 'Pendiente',
                        'APPROVED': 'Aprobado',
                        'REJECTED': 'Rechazado',
                        'CANCELLED': 'Cancelado'
                    };
                    return labels[status] || status;
                },
                getStatusClass(status) {
                    const classes = {
                        'PENDING': 'inactive',
                        'APPROVED': 'active',
                        'REJECTED': 'inactive',
                        'CANCELLED': 'inactive'
                    };
                    return classes[status] || '';
                }
            }
        });

        window.vmPermitHistory = appHistory.mount(HISTORY_MOUNT);
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

    // 3. NO cargar tabla inicial por AJAX (ya viene del servidor en la primera carga)
    // Solo si hay búsqueda activa, recargar
    // fetchTableData(urlList + '?page=1');

    // 4. Cerrar Modal desde overlay o botón cerrar
    if (modalOverlay) {
        modalOverlay.addEventListener('click', (e) => {
            if (e.target === modalOverlay || e.target.closest('.btn-close-modal') || e.target.closest('.js-close-modal')) {
                closeModal();
            }
        });
    }

    // 5. DELEGACIÓN DE ACCIONES EN LA TABLA
    if (tableContainer) {
        tableContainer.addEventListener('click', function (e) {

            // A. Generar Permiso
            const generateBtn = e.target.closest('.js-generate-permit');
            if (generateBtn) {
                e.preventDefault();
                const employeeId = generateBtn.dataset.employeeId;
                const employeeName = generateBtn.dataset.employeeName;
                openGeneratePermitModal(employeeId, employeeName);
                return;
            }

            // B. Ver Historial
            const historyBtn = e.target.closest('.js-view-history');
            if (historyBtn) {
                e.preventDefault();
                const employeeId = historyBtn.dataset.employeeId;
                if (window.vmPermitHistory && employeeId) {
                    window.vmPermitHistory.open(employeeId);
                }
                return;
            }
        });
    }

    // --- FUNCIONES ---

    function openGeneratePermitModal(employeeId, employeeName) {
        const url = `/permitrequest/requests/generate/?employee=${employeeId}`;
        
        fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
            .then(res => res.text())
            .then(html => {
                modalContentContainer.innerHTML = html;
                modalOverlay.classList.remove('hidden');
                
                // Bloquear scroll del body
                document.body.style.overflow = 'hidden';

                initModalPlugins();
                
                // Inicializar la lógica del formulario de permisos
                initPermitForm();

                const form = modalContentContainer.querySelector('form');
                if (form) form.addEventListener('submit', handleFormSubmit);
            })
            .catch(err => {
                console.error('Error al abrir modal:', err);
                Swal.fire('Error', 'No se pudo cargar el formulario', 'error');
            });
    }

    function closeModal() {
        modalOverlay.classList.add('hidden');
        modalContentContainer.innerHTML = '';
        
        // Restaurar scroll del body
        document.body.style.overflow = '';
    }

    function initModalPlugins() {
        if (typeof $ !== 'undefined' && $.fn.select2) {
            $('.select2').select2({
                width: '100%',
                dropdownParent: modalOverlay
            });
        }
    }

    function handleFormSubmit(e) {
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
                    Swal.fire({
                        icon: 'success',
                        title: 'Guardado',
                        text: data.message || 'Permiso registrado correctamente',
                        timer: 2000,
                        showConfirmButton: false
                    });
                    // Recargar tabla
                    const searchQuery = searchInput ? searchInput.value : '';
                    fetchTableData(urlList + `?page=${currentPage}${searchQuery ? '&q=' + searchQuery : ''}`);
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

    // ========================================================
    // LÓGICA DEL FORMULARIO DE GENERACIÓN DE PERMISOS
    // ========================================================
    function initPermitForm() {
        const parentSelect = document.getElementById('id_permit_type_parent');
        const subtypeContainer = document.getElementById('subtype-container');
        const subtypeSelect = document.getElementById('id_permit_type');
        const reasonSection = document.getElementById('reason-section');
        const reasonTextarea = document.getElementById('id_reason');
        const attachmentSection = document.getElementById('attachment-section');
        const attachmentInput = document.getElementById('id_justification_file');
        
        if (!parentSelect || !subtypeContainer || !subtypeSelect) {
            console.error('ERROR: No se encontraron elementos del formulario de permisos');
            return;
        }
        
        const startDateInput = document.getElementById('id_start_date');
        const startTimeInput = document.getElementById('id_start_time');
        const daysInput = document.getElementById('id_days');
        const hoursInput = document.getElementById('id_hours');
        const minutesInput = document.getElementById('id_minutes');
        const calculatedEndSpan = document.getElementById('calculated-end');
        const endDateHidden = document.getElementById('id_end_date');
        const endTimeHidden = document.getElementById('id_end_time');

        // Cambio de tipo padre - Cargar subtipos dinámicamente
        parentSelect.addEventListener('change', async function() {
            const parentId = this.value;
            const selectedOption = this.options[this.selectedIndex];
            const needsJustification = selectedOption.dataset.needsJustification === 'true';
            const requiresAttachment = selectedOption.dataset.requiresAttachment === 'true';
            
            subtypeSelect.innerHTML = '<option value="">-- Cargando... --</option>';
            
            if (!parentId) {
                subtypeSelect.innerHTML = '<option value="">-- Primero seleccione tipo principal --</option>';
                subtypeContainer.style.display = 'none';
                reasonSection.style.display = 'none';
                attachmentSection.style.display = 'none';
                return;
            }
            
            try {
                const response = await fetch(`/permitrequest/api/subtypes/${parentId}/`);
                const data = await response.json();
                
                subtypeSelect.innerHTML = '<option value="">-- Seleccione --</option>';
                
                if (data.success && data.subtypes && data.subtypes.length > 0) {
                    data.subtypes.forEach(subtype => {
                        const option = document.createElement('option');
                        option.value = subtype.id;
                        option.textContent = subtype.name;
                        option.dataset.needsJustification = subtype.needs_justification;
                        option.dataset.requiresAttachment = subtype.requires_attachment;
                        subtypeSelect.appendChild(option);
                    });
                    
                    subtypeContainer.style.display = 'block';
                    subtypeSelect.required = true;
                    reasonSection.style.display = 'none';
                    attachmentSection.style.display = 'none';
                    reasonTextarea.required = false;
                    attachmentInput.required = false;
                } else {
                    subtypeContainer.style.display = 'none';
                    subtypeSelect.required = false;
                    subtypeSelect.innerHTML = '<option value="' + parentId + '" selected style="display:none;"></option>';
                    
                    if (needsJustification) {
                        reasonSection.style.display = 'block';
                        reasonTextarea.required = true;
                    } else {
                        reasonSection.style.display = 'none';
                        reasonTextarea.required = false;
                    }
                    
                    if (requiresAttachment) {
                        attachmentSection.style.display = 'block';
                        attachmentInput.required = true;
                    } else {
                        attachmentSection.style.display = 'none';
                        attachmentInput.required = false;
                    }
                }
            } catch (error) {
                console.error('Error al cargar subtipos:', error);
                subtypeSelect.innerHTML = '<option value="">-- Error al cargar --</option>';
                subtypeContainer.style.display = 'none';
            }
        });

        // Cambio de subtipo
        subtypeSelect.addEventListener('change', function() {
            const selectedOption = this.options[this.selectedIndex];
            if (!selectedOption || !selectedOption.value) return;
            
            const needsJustification = selectedOption.dataset.needsJustification === 'true';
            const requiresAttachment = selectedOption.dataset.requiresAttachment === 'true';
            
            if (needsJustification) {
                reasonSection.style.display = 'block';
                reasonTextarea.required = true;
            } else {
                reasonSection.style.display = 'none';
                reasonTextarea.required = false;
            }
            
            if (requiresAttachment) {
                attachmentSection.style.display = 'block';
                attachmentInput.required = true;
            } else {
                attachmentSection.style.display = 'none';
                attachmentInput.required = false;
            }
        });

        // Calcular fecha/hora de fin
        function calculateEndDateTime() {
            const startDate = startDateInput.value;
            const startTime = startTimeInput.value;
            const days = parseInt(daysInput.value) || 0;
            const hours = parseInt(hoursInput.value) || 0;
            const minutes = parseInt(minutesInput.value) || 0;

            if (!startDate || !startTime) {
                calculatedEndSpan.textContent = '--';
                return;
            }

            const startDateTime = new Date(`${startDate}T${startTime}`);
            startDateTime.setDate(startDateTime.getDate() + days);
            startDateTime.setHours(startDateTime.getHours() + hours);
            startDateTime.setMinutes(startDateTime.getMinutes() + minutes);

            const endDateStr = startDateTime.toLocaleDateString('es-EC', {
                year: 'numeric',
                month: '2-digit',
                day: '2-digit'
            });
            const endTimeStr = startDateTime.toLocaleTimeString('es-EC', {
                hour: '2-digit',
                minute: '2-digit',
                hour12: false
            });

            calculatedEndSpan.textContent = `${endDateStr} ${endTimeStr}`;

            const year = startDateTime.getFullYear();
            const month = String(startDateTime.getMonth() + 1).padStart(2, '0');
            const day = String(startDateTime.getDate()).padStart(2, '0');
            const hour = String(startDateTime.getHours()).padStart(2, '0');
            const minute = String(startDateTime.getMinutes()).padStart(2, '0');

            endDateHidden.value = `${year}-${month}-${day}`;
            endTimeHidden.value = `${hour}:${minute}`;
        }

        startDateInput.addEventListener('change', calculateEndDateTime);
        startTimeInput.addEventListener('change', calculateEndDateTime);
        daysInput.addEventListener('input', calculateEndDateTime);
        hoursInput.addEventListener('input', calculateEndDateTime);
        minutesInput.addEventListener('input', calculateEndDateTime);

        calculateEndDateTime();
    }
});
