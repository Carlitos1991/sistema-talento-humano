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
                        'REQUESTED': 'Pendiente',
                        'PENDING': 'Pendiente',
                        'APPROVED': 'Aprobado',
                        'REJECTED': 'Rechazado',
                        'CANCELLED': 'Cancelado'
                    };
                    return labels[status] || status;
                },
                getStatusClass(status) {
                    const classes = {
                        'REQUESTED': 'inactive',
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

            // C. Historial Bitácoras Aprobadas
            const approvedHistoryBtn = e.target.closest('.js-approved-bitacoras');
            if (approvedHistoryBtn) {
                e.preventDefault();
                const employeeId = approvedHistoryBtn.dataset.employeeId;
                if (!employeeId) return;

                const url = `/permitrequest/bitacora/history/${employeeId}/`;
                fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
                    .then(res => {
                        if (!res.ok) throw new Error('Error al obtener historial');
                        return res.text();
                    })
                    .then(html => {
                        modalContentContainer.innerHTML = html;
                        modalOverlay.classList.remove('hidden');
                        document.body.style.overflow = 'hidden';
                        // Inicializar lógica del modal de historial de bitácoras aprobadas
                        if (typeof initBitacoraHistoryModal === 'function') {
                            initBitacoraHistoryModal();
                        }
                    })
                    .catch(err => {
                        console.error('Error al cargar historial aprobado:', err);
                        Swal.fire('Error', 'No se pudo cargar el historial de bitácoras aprobadas', 'error');
                    });
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

    // Inicializador para modal de historial de bitácoras aprobadas
    window.initBitacoraHistoryModal = function () {
        const searchInput = document.getElementById('bitacora-history-search');
        const table = modalContentContainer.querySelector('.custom-table');
        if (!table) return;

        const tbody = table.querySelector('tbody');
        const rows = Array.from(tbody.querySelectorAll('tr'));
        const pageInfo = document.getElementById('bitacora-history-info');
        const prevBtn = document.getElementById('bitacora-history-prev');
        const nextBtn = document.getElementById('bitacora-history-next');
        const currentDisplay = document.getElementById('bitacora-history-current');
        const pageSizeSelect = document.getElementById('bitacora-history-pagesize-select');

        let currentPage = 1;
        let pageSize = parseInt(pageSizeSelect ? pageSizeSelect.value : 10);

        function render() {
            const term = searchInput ? searchInput.value.trim().toLowerCase() : '';
            const filtered = rows.filter(r => {
                if (term === '') return true;
                return r.textContent.toLowerCase().includes(term);
            });

            const total = filtered.length;
            const totalPages = Math.max(1, Math.ceil(total / pageSize));
            if (currentPage > totalPages) currentPage = totalPages;

            const start = (currentPage - 1) * pageSize;
            const end = start + pageSize;

            rows.forEach(r => r.style.display = 'none');
            filtered.slice(start, end).forEach(r => r.style.display = 'table-row');

            const startIndex = total === 0 ? 0 : start + 1;
            const endIndex = Math.min(end, total);
            if (pageInfo) pageInfo.textContent = `Mostrando ${startIndex} a ${endIndex} de ${total}`;
            if (currentDisplay) currentDisplay.textContent = currentPage;

            prevBtn.disabled = currentPage <= 1;
            nextBtn.disabled = currentPage >= totalPages;
        }

        if (searchInput) {
            searchInput.addEventListener('input', () => { currentPage = 1; render(); });
        }
        if (pageSizeSelect) {
            pageSizeSelect.addEventListener('change', (e) => { pageSize = parseInt(e.target.value); currentPage = 1; render(); });
        }
        if (prevBtn) prevBtn.addEventListener('click', () => { if (currentPage > 1) { currentPage--; render(); } });
        if (nextBtn) nextBtn.addEventListener('click', () => { currentPage++; render(); });

        // Reemplazar texto 'APPROVED' por 'APROBADAS' en la columna de estado (por si vino sin traducir)
        rows.forEach(r => {
            const badge = r.querySelector('.badge');
            if (badge && badge.textContent.trim() === 'APPROVED') badge.textContent = 'APROBADAS';
        });

        render();

        // Asegurar que los botones cerrar del modal funcionen (delegación existente ya maneja .btn-close-modal y .js-close-modal)
        modalContentContainer.querySelectorAll('.js-close-modal').forEach(btn => btn.addEventListener('click', closeModal));
        modalContentContainer.querySelectorAll('.btn-close-modal').forEach(btn => btn.addEventListener('click', closeModal));
    };

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

    // =========================================================
    // BIT\u00c1CORAS: REGISTRAR E LISTAR
    // =========================================================
    
    // Referencias modales bitácora
    const bitacoraModal = document.getElementById('bitacoraModal');
    const bitacoraModalContent = document.getElementById('bitacora-modal-content');
    
    // Referencias modales listado
    const bitacoraListModal = document.getElementById('bitacoraListModal');
    
    // Event delegation para botones de bitácora
    document.addEventListener('click', function(e) {
        // Botón: Registrar Bitácora
        if (e.target.closest('.js-register-bitacora')) {
            const btn = e.target.closest('.js-register-bitacora');
            const employeeId = btn.dataset.employeeId;
            const employeeName = btn.dataset.employeeName;
            openBitacoraModal(employeeId, employeeName);
        }
        
        // Botón: Listar Bitácoras
        if (e.target.closest('.js-list-bitacoras')) {
            const btn = e.target.closest('.js-list-bitacoras');
            const employeeId = btn.dataset.employeeId;
            openBitacoraList(employeeId);
        }
        
        // Cerrar modal bitácora
        if (e.target.closest('.js-close-bitacora-modal')) {
            closeBitacoraModal();
        }
    });
    
    // Abrir listado de bitácoras
    function openBitacoraList(employeeId) {
        if (window.appBitacoraList) {
            bitacoraListModal.classList.remove('hidden');
            document.body.style.overflow = 'hidden';
            window.appBitacoraList.open(employeeId);
        }
    }
    
    // Abrir modal de registro de bitácora
    function openBitacoraModal(employeeId, employeeName) {
        const url = `/permitrequest/bitacora/register/${employeeId}/`;
        
        fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
            .then(res => res.text())
            .then(html => {
                bitacoraModalContent.innerHTML = html;
                bitacoraModal.classList.remove('hidden');
                document.body.style.overflow = 'hidden';
                
                // Agregar event listener al formulario
                const form = document.getElementById('bitacoraRegisterForm');
                if (form) {
                    form.addEventListener('submit', handleBitacoraSubmit);
                }
            })
            .catch(err => {
                console.error('Error:', err);
                Swal.fire('Error', 'No se pudo cargar el formulario', 'error');
            });
    }
    
    // Cerrar modal bitácora
    function closeBitacoraModal() {
        bitacoraModal.classList.add('hidden');
        bitacoraModalContent.innerHTML = '';
        document.body.style.overflow = '';
    }
    
    // Manejar submit del formulario de bitácora
    function handleBitacoraSubmit(e) {
        e.preventDefault();
        const form = e.target;
        
        // Validar que al menos una jornada esté completa
        const firstStart = form.querySelector('#first_start').value;
        const firstEnd = form.querySelector('#first_end').value;
        const secondStart = form.querySelector('#second_start').value;
        const secondEnd = form.querySelector('#second_end').value;
        
        const hasFirst = firstStart && firstEnd;
        const hasSecond = secondStart && secondEnd;
        
        if (!hasFirst && !hasSecond) {
            Swal.fire('Error', 'Debe ingresar al menos una jornada completa (entrada y salida)', 'error');
            return;
        }
        
        // Validar archivo PDF
        const fileInput = form.querySelector('#attachment');
        if (!fileInput.files || fileInput.files.length === 0) {
            Swal.fire('Error', 'Debe adjuntar un documento PDF', 'error');
            return;
        }
        
        const file = fileInput.files[0];
        if (file.size > 2 * 1024 * 1024) {
            Swal.fire('Error', 'El archivo no debe superar los 2MB', 'error');
            return;
        }
        
        if (!file.name.toLowerCase().endsWith('.pdf')) {
            Swal.fire('Error', 'Solo se permiten archivos PDF', 'error');
            return;
        }
        
        const formData = new FormData(form);
        const employeeId = formData.get('employee_id');
        const url = `/permitrequest/bitacora/register/${employeeId}/`;
        
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
                    closeBitacoraModal();
                    Swal.fire({
                        icon: 'success',
                        title: 'Éxito',
                        text: data.message,
                        timer: 2000,
                        showConfirmButton: false
                    });
                } else {
                    Swal.fire('Error', data.message || 'Ocurrió un error', 'error');
                }
            })
            .catch(err => {
                console.error(err);
                Swal.fire('Error', 'Error de comunicación con el servidor', 'error');
            });
    }
    
    // =========================================================
    // MODAL VUE: LISTADO DE BIT\u00c1CORAS
    // =========================================================
    const BITACORA_LIST_MOUNT = '#bitacora-list-app';
    
    if (document.querySelector(BITACORA_LIST_MOUNT)) {
        const {createApp} = Vue;
        window.appBitacoraList = createApp({
            delimiters: ['[[', ']]'],
            data() {
                return {
                    isVisible: false,
                    employeeId: null,
                    employeeName: '',
                    employeeIdentification: '',
                    bitacoras: [],
                    selectedBitacoras: [],
                    selectAll: false,
                    searchQuery: '',
                    currentPage: 1,
                    perPage: 10
                }
            },
            computed: {
                filteredBitacoras() {
                    const term = this.searchQuery.toLowerCase().trim();
                    if (!term) return this.bitacoras;
                    return this.bitacoras.filter(b =>
                        b.start_date.toLowerCase().includes(term)
                    );
                },
                totalPages() {
                    return Math.ceil(this.filteredBitacoras.length / this.perPage) || 1;
                },
                paginatedBitacoras() {
                    const start = (this.currentPage - 1) * this.perPage;
                    const end = start + this.perPage;
                    return this.filteredBitacoras.slice(start, end);
                },
                startIndex() {
                    return this.filteredBitacoras.length === 0 ? 0 : (this.currentPage - 1) * this.perPage + 1;
                },
                endIndex() {
                    return Math.min(this.currentPage * this.perPage, this.filteredBitacoras.length);
                }
            },
            methods: {
                async open(employeeId) {
                    this.employeeId = employeeId;
                    this.searchQuery = '';
                    this.currentPage = 1;
                    this.selectedBitacoras = [];
                    this.selectAll = false;
                    await this.fetchBitacoras();
                    this.isVisible = true;
                },
                closeModal() {
                    this.isVisible = false;
                    this.bitacoras = [];
                    this.selectedBitacoras = [];
                    // Cerrar overlay padre
                    if (bitacoraListModal) {
                        bitacoraListModal.classList.add('hidden');
                        document.body.style.overflow = '';
                    }
                },
                async fetchBitacoras() {
                    try {
                        const url = `/permitrequest/bitacora/list/${this.employeeId}/`;
                        const res = await fetch(url);
                        const data = await res.json();
                        if (data.success) {
                            this.employeeName = data.employee_name;
                            this.employeeIdentification = data.employee_identification;
                            this.bitacoras = data.bitacoras;
                        }
                    } catch (err) {
                        console.error('Error:', err);
                    }
                },
                toggleAll() {
                    if (this.selectAll) {
                        this.selectedBitacoras = this.paginatedBitacoras.map(b => b.id);
                    } else {
                        this.selectedBitacoras = [];
                    }
                },
                async approveSelected() {
                    if (this.selectedBitacoras.length === 0) return;
                    
                    const result = await Swal.fire({
                        title: '¿Aprobar bitácoras?',
                        text: `Se aprobarán ${this.selectedBitacoras.length} bitácora(s)`,
                        icon: 'question',
                        showCancelButton: true,
                        confirmButtonText: 'Sí, aprobar',
                        cancelButtonText: 'Cancelar'
                    });
                    
                    if (result.isConfirmed) {
                        try {
                            const res = await fetch('/permitrequest/bitacora/approve/', {
                                method: 'POST',
                                headers: {
                                    'Content-Type': 'application/json',
                                    'X-CSRFToken': csrfToken
                                },
                                body: JSON.stringify({ids: this.selectedBitacoras})
                            });
                            const data = await res.json();
                            if (data.success) {
                                Swal.fire('Éxito', data.message, 'success');
                                this.selectedBitacoras = [];
                                this.selectAll = false;
                                await this.fetchBitacoras();
                            } else {
                                Swal.fire('Error', data.message, 'error');
                            }
                        } catch (err) {
                            Swal.fire('Error', 'Error de comunicación', 'error');
                        }
                    }
                },
                async deleteSelected() {
                    if (this.selectedBitacoras.length === 0) return;
                    
                    const result = await Swal.fire({
                        title: '¿Eliminar bitácoras?',
                        text: `Se eliminarán ${this.selectedBitacoras.length} bitácora(s)`,
                        icon: 'warning',
                        showCancelButton: true,
                        confirmButtonText: 'Sí, eliminar',
                        cancelButtonText: 'Cancelar',
                        confirmButtonColor: '#ef4444'
                    });
                    
                    if (result.isConfirmed) {
                        try {
                            const res = await fetch('/permitrequest/bitacora/delete/', {
                                method: 'POST',
                                headers: {
                                    'Content-Type': 'application/json',
                                    'X-CSRFToken': csrfToken
                                },
                                body: JSON.stringify({ids: this.selectedBitacoras})
                            });
                            const data = await res.json();
                            if (data.success) {
                                Swal.fire('Éxito', data.message, 'success');
                                this.selectedBitacoras = [];
                                this.selectAll = false;
                                await this.fetchBitacoras();
                            } else {
                                Swal.fire('Error', data.message, 'error');
                            }
                        } catch (err) {
                            Swal.fire('Error', 'Error de comunicación', 'error');
                        }
                    }
                },
                formatDate(dateStr) {
                    if (!dateStr) return '--';
                    const date = new Date(dateStr + 'T00:00:00');
                    return date.toLocaleDateString('es-EC', {
                        year: 'numeric',
                        month: '2-digit',
                        day: '2-digit'
                    });
                },
                formatDateShort(dateTimeStr) {
                    if (!dateTimeStr) return '--';
                    const date = new Date(dateTimeStr);
                    return date.toLocaleDateString('es-EC', {
                        month: '2-digit',
                        day: '2-digit',
                        year: '2-digit'
                    });
                },
                formatTime(timeStr) {
                    return timeStr || '--:--';
                },
                formatDateTime(dateTimeStr) {
                    if (!dateTimeStr) return '--';
                    const date = new Date(dateTimeStr);
                    return date.toLocaleString('es-EC', {
                        year: 'numeric',
                        month: '2-digit',
                        day: '2-digit',
                        hour: '2-digit',
                        minute: '2-digit'
                    });
                },
                truncateText(text, maxLength) {
                    if (!text) return '';
                    if (text.length <= maxLength) return text;
                    return text.substring(0, maxLength) + '...';
                },
                getStatusLabel(status) {
                    const labels = {
                        'REQUESTED': 'Pendiente',
                        'APPROVED': 'Aprobado',
                        'REJECTED': 'Rechazado'
                    };
                    return labels[status] || status;
                },
                getStatusClass(status) {
                    const classes = {
                        'REQUESTED': 'inactive',
                        'APPROVED': 'active',
                        'REJECTED': 'inactive'
                    };
                    return classes[status] || '';
                }
            }
        }).mount(BITACORA_LIST_MOUNT);
    }
});
