document.addEventListener('DOMContentLoaded', function () {
    // Referencias importantes para búsqueda y paginación
    const tableContainer = document.getElementById('table-content-wrapper');
    const searchInput = document.getElementById('table-search');
    const csrfToken = document.getElementById('csrf-token') ? document.getElementById('csrf-token').value : '';
    const urlList = document.getElementById('url-list') ? document.getElementById('url-list').value : '';
    // Prefer the server-included overlay `modalContentContainer` when present,
    // otherwise fall back to dynamic containers used by other flows.
    const modalOverlay = document.getElementById('customModal') || document.getElementById('modalContentContainer') || document.getElementById('modal-dynamic-content') || document.getElementById('bitacoraModal') || document.getElementById('bitacoraListModal') || null;
    const modalContentContainer = document.getElementById('modalContentContainer') || document.getElementById('modal-dynamic-content') || null;
    const pageInfo = document.querySelector('.pagination-info');
    const currentPageDisplay = document.querySelector('.page-input') || null;
    const btnPrev = document.querySelector('.pagination-controls .page-btn[title="Anterior"]') || null;
    const btnNext = document.querySelector('.pagination-controls .page-btn[title="Siguiente"]') || null;

    let currentPage = (window.initialPagination && window.initialPagination.current_page) ? window.initialPagination.current_page : 1;
    let totalPages = (window.initialPagination && window.initialPagination.total_pages) ? window.initialPagination.total_pages : 1;

    let timeout = null;
    if (searchInput) {
        searchInput.addEventListener('keyup', (e) => {
            clearTimeout(timeout);
            timeout = setTimeout(() => {
                currentPage = 1;
                fetchTableData(urlList + `?q=${encodeURIComponent(e.target.value)}&page=1`);
            }, 300);
        });
    }

    // 2. Botones de paginación
    if (btnPrev) {
        btnPrev.addEventListener('click', () => {
            if (currentPage > 1) {
                const searchQuery = searchInput ? searchInput.value : '';
                const url = urlList + `?page=${currentPage - 1}${searchQuery ? '&q=' + encodeURIComponent(searchQuery) : ''}`;
                fetchTableData(url);
            }
        });
    }

    if (btnNext) {
        btnNext.addEventListener('click', () => {
            if (currentPage < totalPages) {
                const searchQuery = searchInput ? searchInput.value : '';
                const url = urlList + `?page=${currentPage + 1}${searchQuery ? '&q=' + encodeURIComponent(searchQuery) : ''}`;
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
            if (e.target === modalOverlay || e.target.closest('.btn-close-modal') || e.target.closest('.js-close-modal') || e.target.closest('.js-close-bitacora-modal') || e.target.closest('.btn-cancel')) {
                closeModal();
            }
        });
    }

    // Delegated close handler on modalContentContainer so close buttons
    // work even if Vue re-renders/replaces inner nodes.
    if (modalContentContainer && !modalContentContainer._closeDelegateAttached) {
        modalContentContainer.addEventListener('click', function (e) {
            const btn = e.target.closest('.js-close-bitacora-modal, .js-close-modal, .btn-cancel, .btn-close-modal');
            if (btn) {
                e.preventDefault();
                closeModal();
            }
        });
        modalContentContainer._closeDelegateAttached = true;
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

                // Si el template ya está incluido en la página, mostrarlo y montarlo.
                if (modalContentContainer && document.getElementById('bitacora-history-container')) {
                    modalContentContainer.dataset.historyUrl = url;
                    modalContentContainer.classList.remove('hidden');
                    document.body.style.overflow = 'hidden';

                    // Asegurar que los botones de cierre dentro del modal funcionen
                    modalContentContainer.querySelectorAll('.js-close-modal, .js-close-bitacora-modal, .btn-cancel, .btn-close-modal').forEach(btn => btn.addEventListener('click', closeModal));

                    // Montar la app Vue si está disponible, o inicializar el manejador clásico
                    try {
                        if (typeof Vue !== 'undefined' && typeof mountBitacoraHistory === 'function') {
                            mountBitacoraHistory(employeeId);
                        } else if (typeof initBitacoraHistoryModal === 'function') {
                            initBitacoraHistoryModal();
                        }
                    } catch (err) {
                        console.warn('No se pudo inicializar history Vue app desde template incluido', err);
                    }

                    return;
                }

                // Fallback: solicitar HTML al servidor (comportamiento previo)
                fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
                    .then(res => {
                        if (!res.ok) {
                            return res.text().then(text => {
                                throw new Error(text || 'Error al obtener historial');
                            });
                        }
                        return res.text();
                    })
                    .then(html => {
                        modalContentContainer.innerHTML = html;
                        modalContentContainer.dataset.historyUrl = url;
                        modalOverlay.classList.remove('hidden');
                        document.body.style.overflow = 'hidden';
                        modalContentContainer.querySelectorAll('.js-close-modal, .js-close-bitacora-modal, .btn-cancel, .btn-close-modal').forEach(btn => btn.addEventListener('click', closeModal));
                        if (typeof initBitacoraHistoryModal === 'function') initBitacoraHistoryModal();
                        if (typeof Vue !== 'undefined' && typeof mountBitacoraHistory === 'function') mountBitacoraHistory(employeeId);
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
        if (modalOverlay && modalOverlay.classList) modalOverlay.classList.add('hidden');
        if (modalContentContainer && modalContentContainer.classList) modalContentContainer.classList.add('hidden');
        // NO desmontar la app Vue de historial: Vue 3 deja nodos internos (comentarios)
        // al desmontar y un remontaje posterior falla con "Cannot read properties of null
        // (reading 'nextSibling')". Si el nodo #bitacora-history-container persiste en el
        // DOM, la instancia se reutiliza en la próxima apertura vía mountBitacoraHistory.
        // Solo limpiamos innerHTML cuando el contenido fue cargado dinámicamente (sin ese nodo).
        try {
            if (modalContentContainer && modalContentContainer.querySelector && !modalContentContainer.querySelector('#bitacora-history-container')) {
                // Contenido dinámico: sí podemos limpiar (Vue no está montado aquí)
                if (window._bitacoraHistoryApp) {
                    try {
                        window._bitacoraHistoryApp.unmount();
                    } catch (e) { /* ignore */
                    }
                    window._bitacoraHistoryApp = null;
                }
                modalContentContainer.innerHTML = '';
            }
            // Si #bitacora-history-container está presente: solo ocultar, NO desmontar Vue
        } catch (e) {
            try {
                modalContentContainer.innerHTML = '';
            } catch (ee) { /* ignore */
            }
        }

        // Restaurar scroll del body
        document.body.style.overflow = '';
    }

    function initModalPlugins() {
        if (typeof $ !== 'undefined' && $.fn.select2) {
            $('.select2').select2({
                width: '100%', dropdownParent: modalOverlay
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
            method: 'POST', body: formData, headers: {'X-Requested-With': 'XMLHttpRequest'}
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
                    fetchTableData(urlList + `?page=${currentPage}${searchQuery ? '&q=' + encodeURIComponent(searchQuery) : ''}`);
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
        const baseUrl = modalContentContainer.dataset.historyUrl || null;
        const fromInput = document.getElementById('bitacora-history-from');
        const toInput = document.getElementById('bitacora-history-to');
        const clearBtn = document.getElementById('bitacora-history-clear');
        const pageInput = document.getElementById('bitacora-history-current');
        const pageSizeSelect = document.getElementById('bitacora-history-pagesize-select');
        const prevBtn = document.getElementById('bitacora-history-prev');
        const nextBtn = document.getElementById('bitacora-history-next');
        const totalBadge = document.getElementById('bitacora-history-total');

        let currentPage = parseInt(pageInput ? pageInput.value : 1) || 1;
        let pageSize = parseInt(pageSizeSelect ? pageSizeSelect.value : 100) || 100;
        let sort = modalContentContainer.dataset.sort || '-start_date';

        function fetchAndRender(params = {}) {
            if (!baseUrl) return;
            const qs = new URLSearchParams();
            qs.set('page', params.page || currentPage);
            qs.set('page_size', params.page_size || pageSize);
            // Date range filter
            if (params.from !== undefined) qs.set('from', params.from); else if (fromInput && fromInput.value) qs.set('from', fromInput.value);
            if (params.to !== undefined) qs.set('to', params.to); else if (toInput && toInput.value) qs.set('to', toInput.value);

            const url = `${baseUrl}?${qs.toString()}`;
            fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
                .then(res => res.text())
                .then(html => {
                    modalContentContainer.innerHTML = html;
                    modalContentContainer.dataset.historyUrl = baseUrl;
                    // re-init modal handlers
                    initBitacoraHistoryModal();
                })
                .catch(err => console.error('Error cargando historial:', err));
        }


        // Date range listeners
        if (fromInput) {
            fromInput.addEventListener('change', function (e) {
                e.preventDefault();
                e.stopImmediatePropagation(); // Bloquea otros scripts (como JQuery)
                currentPage = 1;
                fetchAndRender({page: 1});
                return false;
            }, true); // El 'true' usa la fase de captura para actuar antes que nadie
        }

        if (toInput) {
            toInput.addEventListener('change', function (e) {
                e.preventDefault();
                e.stopImmediatePropagation();
                currentPage = 1;
                fetchAndRender({page: 1});
                return false;
            }, true);
        }

        if (clearBtn) {
            clearBtn.addEventListener('click', function (e) {
                e.preventDefault();
                e.stopImmediatePropagation();
                if (fromInput) fromInput.value = '';
                if (toInput) toInput.value = '';
                currentPage = 1;
                fetchAndRender({page: 1, from: '', to: ''});
            }, true);
        }

        if (pageSizeSelect) {
            pageSizeSelect.addEventListener('change', function (e) {
                pageSize = parseInt(e.target.value);
                currentPage = 1;
                fetchAndRender({page: 1, page_size: pageSize});
            });
        }

        // Prevent accidental form submission from inputs inside the modal (some browsers/forms auto-submit on enter)
        modalContentContainer.querySelectorAll('form').forEach(f => {
            f.addEventListener('submit', function (ev) {
                ev.preventDefault();
                ev.stopPropagation();
                // if form should be handled via AJAX, developer can wire it explicitly
                console.debug('Prevented native submit in bitacora history modal form');
            });
        });

        if (prevBtn) prevBtn.addEventListener('click', function () {
            const p = Math.max(1, currentPage - 1);
            currentPage = p;
            fetchAndRender({page: p});
        });
        if (nextBtn) nextBtn.addEventListener('click', function () {
            const p = (parseInt(pageInput ? pageInput.max || 1 : 1) || currentPage) + 1;
            currentPage = p;
            fetchAndRender({page: p});
        });

        if (pageInput) {
            pageInput.addEventListener('change', function () {
                let p = parseInt(this.value) || 1;
                currentPage = p;
                fetchAndRender({page: p});
            });
        }

        // No client-side sorting for historial; server-side pagination only (no headers clickable)

        // Ensure close buttons work
        modalContentContainer.querySelectorAll('.js-close-modal, .js-close-bitacora-modal, .btn-cancel').forEach(btn => btn.addEventListener('click', closeModal));
        modalContentContainer.querySelectorAll('.btn-close-modal').forEach(btn => btn.addEventListener('click', closeModal));
    };

    // Montar app Vue para historial de bitácoras (separado para reutilizar cuando
    // el modal ya esté incluido en el template del servidor)
    function mountBitacoraHistory(empId) {
        try {
            const emp = empId || (modalContentContainer && modalContentContainer.dataset && modalContentContainer.dataset.employeeId) || null;
            if (!emp) return;
            const mountEl = document.getElementById('bitacora-history-container');
            if (!mountEl || typeof Vue === 'undefined') return;

            const canEditFlag = (mountEl && mountEl.dataset && mountEl.dataset.canEdit === '1') ? true : false;

            // ── REUTILIZAR instancia existente ──────────────────────────────
            // Si Vue ya está montado sobre este nodo, NO desmontar ni remontar:
            // hacerlo causa "Cannot read properties of null (reading 'nextSibling')"
            // porque Vue deja nodos de comentario internos al desmontar.
            // Simplemente actualizamos los datos reactivos y pedimos los datos nuevos.
            if (window._bitacoraHistoryApp) {
                try {
                    window._bitacoraHistoryApp.employeeId = emp;
                    window._bitacoraHistoryApp.can_edit = canEditFlag;
                    window._bitacoraHistoryApp.page = 1;
                    window._bitacoraHistoryApp.from = '';
                    window._bitacoraHistoryApp.to = '';
                    window._bitacoraHistoryApp.fetchData();
                } catch (e) {
                    console.warn('mountBitacoraHistory: error reutilizando app existente', e);
                }
                return;
            }

            const {createApp} = Vue;
            const historyApp = createApp({
                delimiters: ['[[', ']]'],
                data() {
                    return {
                        employeeId: emp,
                        employee_name: '',
                        can_edit: canEditFlag,
                        bitacoras: [],
                        from: '',
                        to: '',
                        page: 1,
                        page_size: 100,
                        total_pages: 1,
                        total_count: 0
                    };
                },
                computed: {
                    startIndex() {
                        return this.total_count === 0 ? 0 : ((this.page - 1) * this.page_size) + 1;
                    },
                    endIndex() {
                        return Math.min(this.total_count, this.page * this.page_size);
                    }
                },
                watch: {
                    page(newVal, oldVal) {
                        if (newVal !== oldVal) this.fetchData();
                    }
                },
                methods: {
                    formatDate(s) {
                        if (!s) return '--';
                        try {
                            // Extraemos el texto "2026-02-24" sin usar new Date() para evitar el desfase de zona horaria
                            const partes = s.split('T')[0].split('-');
                            if (partes.length === 3) {
                                // parts[0] = año, parts[1] = mes, parts[2] = día
                                return `${parseInt(partes[2], 10)}/${parseInt(partes[1], 10)}/${partes[0]}`;
                            }
                            return s;
                        } catch (e) {
                            return s;
                        }
                    },
                    formatDateTimeShort(dt) {
                        if (!dt) return '';
                        try {
                            const d = new Date(dt);
                            const day = String(d.getDate()).padStart(2, '0');
                            const month = String(d.getMonth() + 1).padStart(2, '0');
                            const year = d.getFullYear();
                            const hours = String(d.getHours()).padStart(2, '0');
                            const minutes = String(d.getMinutes()).padStart(2, '0');
                            return `${day}/${month}/${year} ${hours}:${minutes}`;
                        } catch (e) {
                            return dt;
                        }
                    },
                    async fetchData() {
                        try {
                            const qs = new URLSearchParams();
                            qs.set('page', this.page || 1);
                            qs.set('page_size', this.page_size || 10);
                            if (this.from) qs.set('from', this.from);
                            if (this.to) qs.set('to', this.to);
                            const resp = await fetch(`/permitrequest/bitacora/history/${this.employeeId}/?format=json&${qs.toString()}`);
                            if (!resp.ok) throw new Error('HTTP ' + resp.status);
                            const data = await resp.json();
                            this.bitacoras = data.bitacoras || [];
                            this.employee_name = data.employee_name || '';
                            this.can_edit = !!data.can_edit;
                            this.page = data.page || this.page;
                            this.total_count = data.total_count || 0;
                            this.total_pages = data.total_pages || 1;
                        } catch (err) {
                            console.error('Error fetching history JSON', err);
                            this.bitacoras = [];
                            this.page = 1;
                            this.total_pages = 1;
                            this.total_count = 0;
                        }
                    },
                    goTo(p) {
                        this.page = Math.max(1, Math.min(p, this.total_pages || 1));
                    },
                    prev() {
                        this.goTo(this.page - 1);
                    }, next() {
                        this.goTo(this.page + 1);
                    }, first() {
                        this.goTo(1);
                    }, last() {
                        this.goTo(this.total_pages);
                    },
                    clearDates() {
                        this.from = '';
                        this.to = '';
                        document.getElementById('bitacora-history-from').value = '';
                        document.getElementById('bitacora-history-to').value = '';
                        this.page = 1;
                        this.fetchData();
                    }
                }
            });

            // Ensure the mount element is connected; if not, retry a few times
            const mountElConnected = mountEl.isConnected;
            if (!mountElConnected) {
                const retries = parseInt((modalContentContainer && modalContentContainer.dataset && modalContentContainer.dataset.mountRetry) || '0');
                if (retries >= 5) {
                    console.warn('mountBitacoraHistory: mount element not connected after retries');
                    return;
                }
                if (modalContentContainer && modalContentContainer.dataset) modalContentContainer.dataset.mountRetry = String(retries + 1);
                setTimeout(() => mountBitacoraHistory(empId), 60);
                return;
            }

            try {
                const proxy = historyApp.mount(mountEl);
                window._bitacoraHistoryApp = proxy;
                window.appBitacoraHistory = proxy;

                // inicial fetch
                if (window._bitacoraHistoryApp && typeof window._bitacoraHistoryApp.fetchData === 'function') {
                    window._bitacoraHistoryApp.fetchData();
                }
            } catch (mountErr) {
                console.warn('mountBitacoraHistory: Vue mount failed, falling back to initBitacoraHistoryModal', mountErr);
                if (typeof initBitacoraHistoryModal === 'function') {
                    try {
                        initBitacoraHistoryModal();
                    } catch (e) {
                        console.error('Fallback initBitacoraHistoryModal failed', e);
                    }
                }
            }

        } catch (err) {
            console.warn('mountBitacoraHistory error', err);
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
        parentSelect.addEventListener('change', async function () {
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
        subtypeSelect.addEventListener('change', function () {
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
                year: 'numeric', month: '2-digit', day: '2-digit'
            });
            const endTimeStr = startDateTime.toLocaleTimeString('es-EC', {
                hour: '2-digit', minute: '2-digit', hour12: false
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
    document.addEventListener('click', function (e) {
        // Event clicks handled below

        // Botón: Registrar Bitácora
        if (e.target.closest('.js-register-bitacora')) {
            const btn = e.target.closest('.js-register-bitacora');
            const employeeId = btn.dataset.employeeId;
            const employeeName = btn.dataset.employeeName;
            // abrir modal de registro de bitácora
            openBitacoraModal(employeeId, employeeName);
        }

        // Botón: Listar Bitácoras
        if (e.target.closest('.js-list-bitacoras')) {
            const btn = e.target.closest('.js-list-bitacoras');
            const employeeId = btn.dataset.employeeId;
            // abrir listado de bitácoras
            openBitacoraList(employeeId);
        }

        // Cerrar modal bitácora
        if (e.target.closest('.js-close-bitacora-modal')) {
            closeBitacoraModal();
        }
    });

    // Abrir listado de bitácoras
    function openBitacoraList(employeeId) {
        console.debug('openBitacoraList called for employeeId=', employeeId, 'appBitacoraList=', !!window.appBitacoraList);
        if (window.appBitacoraList) {
            bitacoraListModal.classList.remove('hidden');
            document.body.style.overflow = 'hidden';
            try {
                window.appBitacoraList.open(employeeId);
            } catch (err) {
                console.error('Error calling appBitacoraList.open', err);
            }
        } else {
            console.warn('appBitacoraList not initialized — attempting to initialize');
            tryInitBitacoraListApp().then((ok) => {
                if (window.appBitacoraList) {
                    try {
                        bitacoraListModal.classList.remove('hidden');
                        document.body.style.overflow = 'hidden';
                        window.appBitacoraList.open(employeeId);
                        return;
                    } catch (err) {
                        console.error('Error calling appBitacoraList.open after init', err);
                    }
                }
                // Fallback: show modal with included HTML
                if (bitacoraListModal) {
                    bitacoraListModal.classList.remove('hidden');
                    document.body.style.overflow = 'hidden';
                }
            }).catch(() => {
                if (bitacoraListModal) {
                    bitacoraListModal.classList.remove('hidden');
                    document.body.style.overflow = 'hidden';
                }
            });
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
        // No desmontar la instancia Vue del listado para permitir reaperturas rápidas
        // (evita que `appBitacoraList` quede null y provoque fallback en la segunda apertura)
    }

    // Ensure we unmount the list app when the list modal is closed to avoid Vue trying
    // to patch a DOM node that was removed (insertBefore null errors).
    function ensureUnmountBitacoraList() {
        try {
            if (window._bitacoraListAppInstance) {
                try {
                    window._bitacoraListAppInstance.unmount();
                } catch (e) {
                }
                window._bitacoraListAppInstance = null;
            }
            window.appBitacoraList = null;
            window._bitacoraListInitPromise = null;  // ← LÍNEA CRÍTICA
        } catch (e) {
            console.warn('Error during unmounting bitacora list app', e);
        }
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
        let file = null;
        if (fileInput && fileInput.files && fileInput.files.length > 0) {
            file = fileInput.files[0];
            if (file.size > 500 * 1024) {
                Swal.fire('Error', 'El archivo no debe superar los 500 KB', 'error');
                return;
            }
            if (!file.name.toLowerCase().endsWith('.pdf')) {
                Swal.fire('Error', 'Solo se permiten archivos PDF', 'error');
                return;
            }
        }

        const formData = new FormData(form);
        const employeeId = formData.get('employee_id');
        const url = `/permitrequest/bitacora/register/${employeeId}/`;

        fetch(url, {
            method: 'POST', body: formData, headers: {
                'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': csrfToken
            }
        })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    closeBitacoraModal();
                    Swal.fire({
                        icon: 'success', title: 'Éxito', text: data.message, timer: 2000, showConfirmButton: false
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

    function tryInitBitacoraListApp() {
        // Return existing promise if initialization already in progress
        if (window._bitacoraListAppInstance && window.appBitacoraList) {
            return Promise.resolve(true);
        }
        if (window._bitacoraListInitPromise) return window._bitacoraListInitPromise;

        window._bitacoraListInitPromise = new Promise((resolve, reject) => {
            if (!document.querySelector(BITACORA_LIST_MOUNT)) {
                console.warn('Bitacora mount element not present');
                resolve(false);
                return;
            }
            // Avoid creating multiple app instances if already initialized (protect against duplicate bundles)
            if (window._bitacoraListAppInstance) {
                console.debug('bitacora list app already initialized, skipping createApp');
                resolve(true);
                return;
            }
            if (typeof Vue === 'undefined') {
                console.warn('Vue not available, cannot mount bitacora list app');
                resolve(false);
                return;
            }
            const {createApp} = Vue;
            // create the app instance and keep a reference for unmounting later
            const _bitacoraListApp = createApp({
                delimiters: ['[[', ']]'], data() {
                    return {
                            isVisible: false,
                            employeeId: null,
                            employeeName: '',
                            employeeIdentification: '',
                            bitacoras: [],
                            selectedBitacoras: [],
                            selectAll: false,
                            fromDate: '',
                            toDate: '',
                            currentPage: 1,
                            perPage: 100
                        }
                }, computed: {
                    filteredBitacoras() {
                        // Filtrar por rango de fechas (start_date)
                        if (!this.fromDate && !this.toDate) return this.bitacoras;
                        const from = this.fromDate ? new Date(this.fromDate) : null;
                        const to = this.toDate ? new Date(this.toDate) : null;
                        // Normalize to compare dates only
                        return this.bitacoras.filter(b => {
                            if (!b.start_date) return false;
                            const d = new Date(b.start_date);
                            if (from && d < from) return false;
                            if (to) {
                                // include entire 'to' day
                                const toEnd = new Date(to);
                                toEnd.setHours(23, 59, 59, 999);
                                if (d > toEnd) return false;
                            }
                            return true;
                        });
                    }, totalPages() {
                        return Math.ceil(this.filteredBitacoras.length / this.perPage) || 1;
                    }, paginatedBitacoras() {
                        const start = (this.currentPage - 1) * this.perPage;
                        const end = start + this.perPage;
                        return this.filteredBitacoras.slice(start, end);
                    }, startIndex() {
                        return this.filteredBitacoras.length === 0 ? 0 : (this.currentPage - 1) * this.perPage + 1;
                    }, endIndex() {
                        return Math.min(this.currentPage * this.perPage, this.filteredBitacoras.length);
                    }
                }, methods: {
                    async open(employeeId) {
                        this.employeeId = employeeId;
                        this.fromDate = '';
                        this.toDate = '';
                        this.currentPage = 1;
                        this.selectedBitacoras = [];
                        this.selectAll = false;
                        await this.fetchBitacoras();
                        this.isVisible = true;
                    }, clearDates() {
                        this.fromDate = '';
                        this.toDate = '';
                        this.currentPage = 1;
                    }, closeModal() {
                        this.isVisible = false;
                        this.bitacoras = [];
                        this.selectedBitacoras = [];
                        this.selectAll = false;
                        if (bitacoraListModal) {
                            bitacoraListModal.classList.add('hidden');
                            document.body.style.overflow = '';
                        }
                        // NO desmontar Vue: el nodo #bitacora-list-app persiste en el DOM
                        // y un remontaje posterior falla con "Cannot read properties of null
                        // (reading 'nextSibling')". La instancia se reutiliza en open().
                    }, async fetchBitacoras() {
                        if (this._loading) {
                            console.debug('fetchBitacoras: already loading, skipping concurrent call');
                            return;
                        }
                        this._loading = true;
                        try {
                            const url = `/permitrequest/bitacora/list/${this.employeeId}/`;
                            console.debug('fetchBitacoras ->', url);
                            const res = await fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}});
                            const text = await res.text();
                            let data = null;
                            try {
                                data = JSON.parse(text);
                            } catch (e) {
                                console.warn('fetchBitacoras: response not JSON', text);
                            }

                            if (data && data.success) {
                                // Ensure the root element still exists before updating reactive state
                                const rootEl = document.getElementById('bitacora-list-app');
                                if (!rootEl) {
                                    console.warn('bitacora root element removed; skipping state update');
                                    return;
                                }
                                this.employeeName = data.employee_name;
                                this.employeeIdentification = data.employee_identification;
                                this.bitacoras = data.bitacoras || [];
                            } else {
                                console.warn('fetchBitacoras: no success', data);
                                this.bitacoras = [];
                            }
                        } catch (err) {
                            console.error('fetchBitacoras error:', err);
                            this.bitacoras = [];
                        } finally {
                            this._loading = false;
                        }
                    }, toggleAll() {
                        if (this.selectAll) {
                            this.selectedBitacoras = this.paginatedBitacoras.map(b => b.id);
                        } else {
                            this.selectedBitacoras = [];
                        }
                    }, async approveSelected() {
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
                                    method: 'POST', headers: {
                                        'Content-Type': 'application/json', 'X-CSRFToken': csrfToken
                                    }, body: JSON.stringify({ids: this.selectedBitacoras})
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
                    }, async rejectSelected() {
                        if (this.selectedBitacoras.length === 0) return;

                        const {value: reason} = await Swal.fire({
                            title: 'Rechazar bitácoras',
                            input: 'textarea',
                            inputLabel: `Ingrese motivo de rechazo para ${this.selectedBitacoras.length} bitácora(s)`,
                            inputPlaceholder: 'Motivo de rechazo...',
                            showCancelButton: true,
                            confirmButtonText: 'Rechazar',
                            cancelButtonText: 'Cancelar',
                            inputAttributes: {maxlength: 1000},
                        });

                        if (!reason) return;

                        try {
                            const res = await fetch('/permitrequest/bitacora/reject/', {
                                method: 'POST', headers: {
                                    'Content-Type': 'application/json', 'X-CSRFToken': csrfToken
                                }, body: JSON.stringify({ids: this.selectedBitacoras, reason})
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
                    }, async deleteSelected() {
                        if (this.selectedBitacoras.length === 0) return;

                        const result = await Swal.fire({
                            title: '¿Marcar bitácoras como inactivas?',
                            text: `Se marcarán como inactivas ${this.selectedBitacoras.length} bitácora(s)`,
                            icon: 'warning',
                            showCancelButton: true,
                            confirmButtonText: 'Sí, marcar inactivas',
                            cancelButtonText: 'Cancelar',
                            confirmButtonColor: '#ef4444'
                        });

                        if (result.isConfirmed) {
                            try {
                                const res = await fetch('/permitrequest/bitacora/delete/', {
                                    method: 'POST', headers: {
                                        'Content-Type': 'application/json', 'X-CSRFToken': csrfToken
                                    }, body: JSON.stringify({ids: this.selectedBitacoras})
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
                    }, async deleteSingle(id) {
                        // Reuse same confirmation as bulk delete
                        const result = await Swal.fire({
                            title: '¿Eliminar bitácora? ',
                            text: `Se eliminará la bitácora seleccionada. Esta acción es irreversible.`,
                            icon: 'warning',
                            showCancelButton: true,
                            confirmButtonText: 'Sí, eliminar',
                            cancelButtonText: 'Cancelar',
                            confirmButtonColor: '#ef4444'
                        });
                        if (!result.isConfirmed) return;
                        try {
                            const res = await fetch('/permitrequest/bitacora/delete/', {
                                method: 'POST', headers: {
                                    'Content-Type': 'application/json', 'X-CSRFToken': csrfToken
                                }, body: JSON.stringify({ids: [id]})
                            });
                            const data = await res.json();
                            if (data.success) {
                                Swal.fire('Éxito', data.message, 'success');
                                await this.fetchBitacoras();
                            } else {
                                Swal.fire('Error', data.message, 'error');
                            }
                        } catch (err) {
                            Swal.fire('Error', 'Error de comunicación', 'error');
                        }
                    },

                    async openEdit(bitacora) {
                        // Preload start/end times into SweetAlert inputs
                        const {value: formValues} = await Swal.fire({
                            title: 'Editar hora (Inicio / Fin)', html: `<div style="display:flex;gap:8px;align-items:center;justify-content:center;">
                                    <input id="swal-start" type="time" class="swal2-input" value="${bitacora.start_time || ''}" />
                                    <input id="swal-end" type="time" class="swal2-input" value="${bitacora.end_time || ''}" />
                                </div>`, focusConfirm: false, showCancelButton: true, preConfirm: () => {
                                const start = document.getElementById('swal-start').value;
                                const end = document.getElementById('swal-end').value;
                                if (!start && !end) {
                                    Swal.showValidationMessage('Debe ingresar al menos una hora');
                                    return false;
                                }
                                return {start, end};
                            }
                        });

                        if (formValues) {
                            try {
                                const res = await fetch(`/permitrequest/bitacora/edit/${bitacora.id}/`, {
                                    method: 'POST', headers: {
                                        'Content-Type': 'application/json', 'X-CSRFToken': csrfToken
                                    }, body: JSON.stringify({start_time: formValues.start, end_time: formValues.end})
                                });
                                const data = await res.json();
                                if (data.success) {
                                    Swal.fire('Éxito', data.message, 'success');
                                    await this.fetchBitacoras();
                                } else {
                                    Swal.fire('Error', data.message || 'No se pudo actualizar', 'error');
                                }
                            } catch (err) {
                                Swal.fire('Error', 'Error de comunicación', 'error');
                            }
                        }
                    }, async openEditSwal(bitacora) {
                        const {value: response} = await Swal.fire({
                            title: 'Editar bitácora',
                            html: `
                                <div style="display:flex;gap:8px;align-items:center;justify-content:center;margin-bottom:8px;">
                                    <input id="swal-start" type="time" class="swal2-input" value="${bitacora.start_time || ''}" />
                                    <input id="swal-end" type="time" class="swal2-input" value="${bitacora.end_time || ''}" />
                                </div>
                                <div style="text-align:left;margin-bottom:8px;">
                                    <label style="font-weight:600;">Agregar mensaje (se añadirá al historial)</label>
                                    <textarea id="swal-note" class="swal2-textarea" rows="3" placeholder="Ingrese el nuevo mensaje..."></textarea>
                                </div>
                                <div style="text-align:left;">
                                    <label style="font-weight:600;">Adjuntar PDF (opcional, máximo 2MB)</label>
                                    <div id="swal-upload" style="border:1px dashed #cbd5e1;border-radius:6px;padding:10px;display:flex;align-items:center;gap:10px;cursor:pointer;background:#f8fafc;">
                                        <i class="fas fa-file-pdf" style="font-size:26px;color:#dc2626"></i>
                                        <div style="display:flex;flex-direction:column;">
                                            <span style="font-weight:600;color:#0f172a">Seleccionar archivo PDF</span>
                                            <span style="font-size:12px;color:#6b7280">Haz click para elegir un archivo</span>
                                        </div>
                                        <span id="swal-file-name" style="margin-left:auto;font-size:12px;color:#374151"></span>
                                        <input id="swal-file" type="file" accept="application/pdf" style="display:none" onchange="(function(el){ const n = document.getElementById('swal-file-name'); n.textContent = el.files && el.files[0] ? el.files[0].name : ''; })(this)" />
                                    </div>
                                </div>
                            `,
                            focusConfirm: false,
                            showCancelButton: true,
                            showLoaderOnConfirm: true,
                            didOpen: () => {
                                const up = document.getElementById('swal-upload');
                                const fileEl = document.getElementById('swal-file');
                                if (up && fileEl) up.addEventListener('click', () => fileEl.click());
                            },
                            preConfirm: () => {
                                const start = document.getElementById('swal-start').value;
                                const end = document.getElementById('swal-end').value;
                                const note = document.getElementById('swal-note').value.trim();
                                const fileEl = document.getElementById('swal-file');
                                const file = fileEl && fileEl.files && fileEl.files[0] ? fileEl.files[0] : null;

                                if (file) {
                                    if (!file.name.toLowerCase().endsWith('.pdf')) {
                                        Swal.showValidationMessage('Solo se permiten archivos PDF');
                                        return false;
                                    }
                                    if (file.size > 500 * 1024) {
                                        Swal.showValidationMessage('El archivo no debe superar los 500 KB');
                                        return false;
                                    }
                                }

                                // Concatenar mensaje nuevo al historial existente, sin precargarlo en el textarea
                                // Send only the new note; server will format and prepend to history
                                const formData = new FormData();
                                formData.append('start_time', start || '');
                                formData.append('end_time', end || '');
                                formData.append('response_note', note || '');
                                if (file) formData.append('justification_file', file);

                                return fetch(`/permitrequest/bitacora/edit/${bitacora.id}/`, {
                                    method: 'POST', headers: {'X-CSRFToken': csrfToken}, body: formData
                                }).then(res => res.json()).catch(() => {
                                    Swal.showValidationMessage('Error de comunicación');
                                });
                            }
                        });

                        if (response) {
                            if (response.success) {
                                Swal.fire('Éxito', response.message, 'success');
                                await this.fetchBitacoras();
                            } else {
                                Swal.fire('Error', response.message || 'No se pudo actualizar', 'error');
                            }
                        }
                    }, formatDate(dateStr) {
                        if (!dateStr) return '--';
                        try {
                            // Separamos el string exacto que viene de la BD para evitar zonas horarias
                            const partes = dateStr.split('T')[0].split('-');
                            if (partes.length === 3) {
                                return `${parseInt(partes[2], 10)}/${parseInt(partes[1], 10)}/${partes[0]}`;
                            }
                            return dateStr;
                        } catch (e) {
                            return dateStr;
                        }
                    }, formatDateShort(dateTimeStr) {
                        if (!dateTimeStr) return '--';
                        const date = new Date(dateTimeStr);
                        return date.toLocaleDateString('es-EC', {
                            month: '2-digit', day: '2-digit', year: '2-digit'
                        });
                    }, formatTime(timeStr) {
                        return timeStr || '--:--';
                    }, formatDateTime(dateTimeStr) {
                        if (!dateTimeStr) return '--';
                        const date = new Date(dateTimeStr);
                        return date.toLocaleString('es-EC', {
                            year: 'numeric',
                            month: '2-digit',
                            day: '2-digit',
                            hour: '2-digit',
                            minute: '2-digit',
                            hour12: false
                        });
                    }, truncateText(text, maxLength) {
                        if (!text) return '';
                        if (text.length <= maxLength) return text;
                        return text.substring(0, maxLength) + '...';
                    }, getStatusLabel(status) {
                        const labels = {
                            'REQUESTED': 'Pendiente', 'APPROVED': 'Aprobado', 'REJECTED': 'Rechazado'
                        };
                        return labels[status] || status;
                    }, getStatusClass(status) {
                        const classes = {
                            'REQUESTED': 'badge-secondary', 'APPROVED': 'badge-success', 'REJECTED': 'badge-danger'
                        };
                        return classes[status] || '';
                    }, // Rich note helpers
                    getFirstSegmentHtml(html) {
                        if (!html) return '';
                        const parts = html.split('\n\n');
                        return parts[0] || '';
                    },
                    stripHtml(html) {
                        if (!html) return '';
                        const d = document.createElement('div');
                        d.innerHTML = html;
                        return d.textContent || d.innerText || '';
                    },
                    joinHtmlSegments(html) {
                        if (!html) return '';
                        const parts = html.split('\n\n').map(p => p.trim()).filter(Boolean);
                        if (parts.length === 0) return '';
                        const mapped = parts.map(p => {
                            // If segment already contains an HTML span label, keep as is
                            if (/\<span[^>]*class=["']?note-label/.test(p)) {
                                return p;
                            }
                            // otherwise escape and wrap
                            return `<span class="note-text">${this.escapeHtml(p)}</span>`;
                        });
                        return mapped.join(' ');
                    },
                    escapeHtml(text) {
                        if (!text) return '';
                        return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
                    },
                    truncateHtmlFirst(html, maxLength) {
                        const seg = this.getFirstSegmentHtml(html);
                        if (!seg) return '';
                        const wrapper = document.createElement('div');
                        wrapper.innerHTML = seg;
                        const labelEl = wrapper.querySelector('.note-label');
                        // Caso: todo el texto está dentro del label (ej. <span class="note-label">Rechazo: texto</span>)
                        if (labelEl) {
                            const full = (labelEl.textContent || '').trim();
                            const idx = full.indexOf(':');
                            if (idx !== -1) {
                                const labelText = full.substring(0, idx + 1);
                                const msg = full.substring(idx + 1).trim();
                                let truncatedMsg = msg;
                                if (msg.length > maxLength) truncatedMsg = msg.substring(0, maxLength) + '...';
                                const cls = this.escapeHtml(labelEl.getAttribute('class') || 'note-label');
                                return `<span class="${cls}">${this.escapeHtml(labelText)} ${this.escapeHtml(truncatedMsg)}</span>`;
                            }
                            // Si no se puede separar, devolver el outerHTML truncado
                            const labelHtml = labelEl.outerHTML;
                            // remove label to get any extra text (rare)
                            labelEl.remove();
                            const msgText = (wrapper.textContent || '').trim();
                            const truncated = msgText.length > maxLength ? msgText.substring(0, maxLength) + '...' : msgText;
                            return labelHtml + ' ' + this.escapeHtml(truncated);
                        }
                        // Si no hay label, devolver texto truncado
                        const textOnly = (wrapper.textContent || '').trim();
                        const truncated = textOnly.length > maxLength ? textOnly.substring(0, maxLength) + '...' : textOnly;
                        return this.escapeHtml(truncated);
                    }
                }
            });

            try {
                const proxy = _bitacoraListApp.mount(BITACORA_LIST_MOUNT);
                // store both the app instance and the proxy so we can unmount safely later
                window._bitacoraListAppInstance = _bitacoraListApp;
                window.appBitacoraList = proxy;
                console.debug('bitacora list app mounted');
                resolve(true);
            } catch (mountErr) {
                console.error('Error mounting bitacora list app', mountErr);
                resolve(false);
            }

            // safety timeout: resolve false after 2s if nothing happened
            setTimeout(() => {
                if (!window.appBitacoraList) {
                    console.warn('tryInitBitacoraListApp: timing out');
                    resolve(false);
                }
            }, 2000);
        });

        return window._bitacoraListInitPromise;
    }

    // Intentar inicializar la app de bitácoras al cargar el DOM
    tryInitBitacoraListApp();
});

// --- PREVENCIÓN GLOBAL DE RECARGAS EN MODALES ---
$(document).on('submit', '#bitacora-history-container form, #bitacora-list-app form', function (e) {
    e.preventDefault();
    return false;
});

// NOTE: removed a global click handler that prevented clicks on
// buttons inside #bitacora-history-container. That handler called
// e.preventDefault() on all buttons (except close), which blocked
// Vue-managed controls (like pagination). Buttons are now handled
// by their respective components/handlers.

/* Global helper used by server-side paginator in modal_bitacora_history.html */
function bitacoraHistoryChangePage(page) {
    try {
        if (window._bitacoraHistoryApp && typeof window._bitacoraHistoryApp.goTo === 'function') {
            window._bitacoraHistoryApp.goTo(page);
            return;
        }
        // fallback: fetch JSON via dataset historyUrl if available
        const container = document.getElementById('modal-dynamic-content') || document.getElementById('modalContentContainer');
        const baseUrl = container && container.dataset && container.dataset.historyUrl ? container.dataset.historyUrl : null;
        if (baseUrl) {
            const url = new URL(baseUrl, window.location.origin);
            url.searchParams.set('page', page);
            fetch(url.toString(), {headers: {'X-Requested-With': 'XMLHttpRequest'}})
                .then(res => res.text())
                .then(html => {
                    if (container) container.innerHTML = html;
                }).catch(err => console.error('Error fetching page:', err));
        }
    } catch (e) {
        console.error('bitacoraHistoryChangePage error', e);
    }
}