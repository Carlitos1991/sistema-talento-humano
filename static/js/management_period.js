/* apps/contract/static/js/management_period.js */
const {createApp} = Vue;

/**
 * Helper: Obtiene el token CSRF para peticiones POST
 */
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

const periodApp = createApp({
    delimiters: ['[[', ']]'],
    data() {
        const container = document.getElementById('period-app');
        return {
            // --- ESTADOS DE CONTROL ---
            loading: true,
            step: 1,
            showWizard: false,
            showDetailModal: false,
            showAdvancedModal: false,
            isEdit: false, // <-- PROPIEDAD REQUERIDA POR EL WIZARD
            unitLevels: [],
            // --- FILTRADO Y PAGINACIÓN ---
            currentPage: 1,
            pageSize: 10,
            totalRows: 0,
            searchTerm: '',
            allDOMRows: [],
            isAdvancedSearch: false,
            advancedQuery: '',
            advancedFilters: {
                q: '', unit: '', regime: '', doc_number: '',
                status_code: '', date_from: '', date_to: '', regime_code: ''
            },

            // --- SELECCIÓN Y DATOS ---
            searchDoc: '',
            selectedContractType: {id: null, name: '', code: '', category: ''},
            selectedEmployee: {id: null, full_name: '', photo: '', budget_line: null},
            selectedPeriod: {},

            // --- FORMULARIO CREACIÓN ---
            form: {
                id: null, administrative_unit: '', budget_line: '', schedule: '',
                workplace: '', start_date: '', end_date: '', document_number: '',
                job_functions: '', institutional_need_memo: '', budget_certification: '',
                manual_position: '', manual_remuneration: '',
                elaboration_date: '', action_motivation: '', is_boss: false, action_explanation: ''
            },


            // --- ESTADÍSTICAS ---
            stats: {
                total: 0,
                regimes: [] // Lista vacía inicial
            },
            pagination: {start: 0, end: 0},
            filters: {status: ''}
        }
    },

    mounted() {
        setTimeout(() => {
            this.fetchTable();
        }, 100);
        this.fetchTable();
        this.initDelegatedListeners();
    },

    methods: {
        // ==========================================
        // 1. INICIALIZACIÓN Y EVENTOS DELEGADOS
        // ==========================================
        initDelegatedListeners() {
            // Buscador Frontend
            const searchInput = document.getElementById('table-search-input');
            if (searchInput) {
                let debounce;
                searchInput.addEventListener('input', (e) => {
                    clearTimeout(debounce);
                    debounce = setTimeout(() => {
                        this.advancedFilters.q = e.target.value.trim();
                        this.searchTerm = this.advancedFilters.q;
                        this.currentPage = 1;
                        this.fetchTable(false);
                    }, 450);
                });
            }

            // Delegación Única
            const tableWrapper = document.getElementById('table-content-wrapper');
            if (tableWrapper) {
                tableWrapper.addEventListener('click', (e) => {
                    const btn = e.target.closest('button');
                    if (!btn) return;

                    const action = btn.dataset.action;
                    const id = btn.dataset.id;
                    const contractCategory = btn.dataset.contractCategory;

                    if (action === 'sign') this.signPeriod(id, contractCategory);
                    if (action === 'view') this.viewPeriodDetails(id);
                    if (action === 'terminate') this.terminatePeriod(id);
                    if (action === 'upload') this.uploadContractFile(id);
                    if (action === 'print') this.printPeriodDocument(id);

                    // CORRECCIÓN: Llamar al nuevo nombre del método
                    if (action === 'advanced-search-empty') this.openSearchModal();
                });
            }
        },
        // --- MÉTODOS DE BÚSQUEDA ---
        openSearchModal() {
            // Forzamos la actualización del estado
            this.showAdvancedModal = true;
            document.body.classList.add('no-scroll');

            // TÉCNICA SENIOR: Forzamos un re-render mediante loading
            // para que Vue despierte al motor de dibujo del navegador
            this.loading = true;
            this.$nextTick(() => {
                this.loading = false;
            });
        },
        closeAdvancedModal() {
            this.showAdvancedModal = false;
            document.body.classList.remove('no-scroll');
        },

        async applyAdvancedSearch() {
            this.loading = true;
            // Activamos bandera para mostrar botón "Limpiar" en la lista
            this.isAdvancedSearch = true;

            // Cerramos el modal
            this.showAdvancedModal = false;
            document.body.classList.remove('no-scroll');

            // Ejecutamos la petición al servidor
            await this.fetchTable(true);

            this.showToast('success', 'Búsqueda avanzada aplicada');
        },
        async loadInitialUnits() {
            try {
                const res = await fetch('/institution/api/unit-children/');
                const data = await res.json();
                if (data.success) {
                    // Inicializamos con el nivel 1
                    this.unitLevels = [{options: data.units, selectedId: null}];
                }
            } catch (e) {
                console.error("Error cargando unidades:", e);
            }
        },

        async handleUnitChange(index) {
            const selectedId = this.unitLevels[index].selectedId;

            // Cortar el array para eliminar niveles inferiores si el usuario cambia un nivel superior
            this.unitLevels = this.unitLevels.slice(0, index + 1);

            // Actualizar el valor final que irá a la base de datos
            this.form.administrative_unit = selectedId;

            if (!selectedId) return;

            try {
                const res = await fetch(`/institution/api/unit-children/?parent_id=${selectedId}`);
                const data = await res.json();

                if (data.success && data.units.length > 0) {
                    // Agregar el siguiente nivel de combo
                    this.unitLevels.push({options: data.units, selectedId: null});
                }
            } catch (e) {
                console.error("Error cargando hijos:", e);
            }
        },
        async uploadContractFile(id) {
            const {value: file} = await Swal.fire({
                title: 'Subir Contrato Legalizado',
                text: 'Seleccione el archivo PDF (Máx. 2MB)',
                input: 'file',
                inputAttributes: {'accept': 'application/pdf', 'aria-label': 'Subir contrato PDF'},
                showCancelButton: true,
                confirmButtonText: 'Subir Archivo',
                cancelButtonText: 'Cancelar',
                customClass: {confirmButton: 'btn-save', cancelButton: 'btn-cancel'}
            });

            if (file) {
                // Validación rápida en cliente
                if (file.size > 2 * 1024 * 1024) {
                    Swal.fire('Error', 'El archivo es demasiado pesado (Máximo 2MB)', 'error');
                    return;
                }

                const formData = new FormData();
                formData.append('contract_file', file);

                this.loading = true;
                try {
                    const response = await fetch(`/contract/periods/upload-doc/${id}/`, {
                        method: 'POST',
                        body: formData,
                        headers: {'X-CSRFToken': getCookie('csrftoken')}
                    });
                    const data = await response.json();
                    if (data.success) {
                        this.showToast('success', data.message);
                        this.fetchTable(); // Recargar tabla para ver el cambio
                        if (this.showDetailModal) this.viewPeriodDetails(id); // Recargar expediente si está abierto
                    } else {
                        Swal.fire('Error', data.message, 'error');
                    }
                } catch (e) {
                    this.showToast('error', 'Fallo en la carga del archivo');
                } finally {
                    this.loading = false;
                }
            }
        },

        async deleteContractFile(id) {
            const {isConfirmed} = await Swal.fire({
                title: '¿Eliminar Documento?',
                text: 'Esta acción borrará el PDF físico del servidor.',
                icon: 'warning',
                showCancelButton: true,
                confirmButtonText: 'Sí, eliminar',
                cancelButtonText: 'Cancelar',
                customClass: {confirmButton: 'btn-danger-action', cancelButton: 'btn-cancel'}
            });

            if (isConfirmed) {
                try {
                    const response = await fetch(`/contract/periods/delete-doc/${id}/`, {
                        method: 'POST',
                        headers: {'X-CSRFToken': getCookie('csrftoken')}
                    });
                    const data = await response.json();
                    if (data.success) {
                        this.showToast('success', data.message);
                        this.fetchTable();
                        if (this.showDetailModal) this.viewPeriodDetails(id);
                    }
                } catch (e) {
                    this.showToast('error', 'Error al eliminar archivo');
                }
            }
        },

        printPeriodDocument(id) {
            if (!id) return;
            const period = this.selectedPeriod || {};
            if (period.personnel_action_pdf_url) {
                window.open(period.personnel_action_pdf_url, '_blank');
                return;
            }
            window.open(`/contract/periods/print/${id}/`, '_blank');
        },


        // ==========================================
        // GESTIÓN DE EXPEDIENTE (EDICIÓN)
        // ==========================================
        async editPeriodFields() {
            const p = this.selectedPeriod;

            if (p.status_code !== 'SIN_FIRMAR') {
                Swal.fire({
                    title: 'Acceso Denegado',
                    text: 'Solo se pueden modificar contratos en estado "SIN FIRMAR".',
                    icon: 'warning'
                });
                return;
            }

            let scheduleOptions = '<option value="">Seleccione un horario...</option>';
            if (window.allSchedules) {
                window.allSchedules.forEach(s => {
                    scheduleOptions += `<option value="${s.id}" ${s.id == p.schedule_id ? 'selected' : ''}>${s.name}</option>`;
                });
            }

            const {value: formValues} = await Swal.fire({
                title: 'Modificar Datos Administrativos',
                width: '800px', // Un poco más estrecho para que los inputs no se estiren de más
                padding: '2rem',
                html: `
        <div style="text-align: left; font-family: 'Inter', sans-serif;">
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem;">
                <!-- Columna 1 -->
                <div class="form-group">
                    <label class="form-label">Número de Documento</label>
                      <input id="swal-doc" type="text" class="input-field readonly-styled" 
                          value="${p.document_number || ''}" readonly 
                           placeholder="Generado automáticamente">
                    <small class="form-hint">Este código se asignará al finalizar la gestión.</small>
                </div>
                <!-- Columna 2 -->
                <div class="form-group">
                    <label class="form-label" style="font-weight: 700; font-size: 0.75rem; color: #475569; text-transform: uppercase; margin-bottom: 0.5rem; display: block;">Lugar de Trabajo</label>
                    <input id="swal-workplace" class="form-control" value="${p.workplace}" placeholder="Ej: Edificio Central">
                </div>
                <!-- Columna 1 -->
                <div class="form-group">
                    <label class="form-label" style="font-weight: 700; font-size: 0.75rem; color: #475569; text-transform: uppercase; margin-bottom: 0.5rem; display: block;">Memo Necesidad</label>
                    <input id="swal-memo" class="form-control" value="${p.institutional_need_memo}">
                </div>
                <!-- Columna 2 -->
                <div class="form-group">
                    <label class="form-label" style="font-weight: 700; font-size: 0.75rem; color: #475569; text-transform: uppercase; margin-bottom: 0.5rem; display: block;">Cert. Presupuestaria</label>
                    <input id="swal-cert" class="form-control" value="${p.budget_certification}">
                </div>
                <!-- Columna 1 -->
                <div class="form-group">
                    <label class="form-label" style="font-weight: 700; font-size: 0.75rem; color: #475569; text-transform: uppercase; margin-bottom: 0.5rem; display: block;">Fecha Inicio</label>
                    <input type="date" id="swal-start" class="form-control" value="${p.start_date}">
                </div>
                <!-- Columna 2 -->
                <div class="form-group">
                    <label class="form-label" style="font-weight: 700; font-size: 0.75rem; color: #475569; text-transform: uppercase; margin-bottom: 0.5rem; display: block;">Fecha Fin</label>
                    <input type="date" id="swal-end" class="form-control" value="${p.end_date || ''}">
                </div>
            </div>
            
            <!-- Campos de ancho completo -->
            <div class="form-group" style="margin-top: 1.5rem;">
                <label class="form-label" style="font-weight: 700; font-size: 0.75rem; color: #475569; text-transform: uppercase; margin-bottom: 0.5rem; display: block;">Horario Laboral</label>
                <select id="swal-schedule" class="form-control" style="width: 100%; height: 45px;">${scheduleOptions}</select>
            </div>

            <div class="form-group" style="margin-top: 1.5rem;">
                <label class="form-label" style="font-weight: 700; font-size: 0.75rem; color: #475569; text-transform: uppercase; margin-bottom: 0.5rem; display: block;">Funciones del Puesto</label>
                <textarea id="swal-functions" class="form-control" rows="3" style="width: 100%; resize: none; padding: 0.75rem;">${p.job_functions}</textarea>
            </div>
        </div>`,
                showCancelButton: true,
                confirmButtonText: 'Guardar Cambios',
                cancelButtonText: 'Cancelar',
                customClass: {
                    confirmButton: 'btn-save',
                    cancelButton: 'btn-cancel',
                    popup: 'rounded-12'
                },
                preConfirm: () => {
                    // Validación simple antes de enviar
                    const docInput = document.getElementById('swal-doc');
                    const doc = (docInput && docInput.value ? docInput.value : (p.document_number || '')).trim().toUpperCase();
                    const start = document.getElementById('swal-start').value;
                    if (!start) {
                        Swal.showValidationMessage('La Fecha Inicio es obligatoria');
                        return false;
                    }
                    return {
                        doc: doc,
                        workplace: document.getElementById('swal-workplace').value.trim().toUpperCase(),
                        memo: document.getElementById('swal-memo').value.trim().toUpperCase(),
                        cert: document.getElementById('swal-cert').value.trim().toUpperCase(),
                        start: start,
                        end: document.getElementById('swal-end').value,
                        schedule: document.getElementById('swal-schedule').value,
                        functions: document.getElementById('swal-functions').value.trim()
                    }
                }
            });

            if (formValues) {
                this.updatePeriodAPI(p.id, formValues);
            }
        },

        async updatePeriodAPI(id, data) {
            this.loading = true;
            const formData = new FormData();
            // Mapeo de datos para el Backend
            Object.keys(data).forEach(key => formData.append(key, data[key]));

            try {
                const response = await fetch(`/contract/periods/update-partial/${id}/`, {
                    method: 'POST',
                    body: formData,
                    headers: {'X-CSRFToken': getCookie('csrftoken')}
                });
                const result = await response.json();
                if (result.success) {
                    this.showToast('success', result.message);
                    this.viewPeriodDetails(id); // Recarga los datos en el modal abierto
                    this.fetchTable();          // Recarga la tabla de fondo
                } else {
                    Swal.fire('Error de Validación', result.message || 'Datos no válidos', 'error');
                }
            } catch (e) {
                this.showToast('error', 'Error crítico al actualizar');
            } finally {
                this.loading = false;
            }
        },

        // ==========================================
        // 2. LÓGICA DE TABLA, FILTRO Y PAGINACIÓN
        // ==========================================
        async fetchTable(advanced = false) {
            this.loading = true;
            this.isAdvancedSearch = advanced;

            // Construimos los parámetros incluyendo los de búsqueda avanzada y el código de régimen
            const params = new URLSearchParams({
                advanced: advanced,
                sort: this.sortField,
                order: this.sortOrder,
                q: this.advancedFilters.q || this.advancedQuery,
                regime_code: this.advancedFilters.regime_code, // <-- IMPORTANTE
                status: this.filters.status,
                page: this.currentPage,
                page_size: this.pageSize,
                ...this.advancedFilters // Esto expande el resto (unit, dates, etc.)
            }).toString();

            try {
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), 15000); // 15s timeout

                const response = await fetch(`/contract/periods/partial-table/?${params}`, {signal: controller.signal});
                clearTimeout(timeoutId);

                let data;
                try {
                    data = await response.json();
                } catch (e) {
                    // JSON parse error (server returned HTML or empty). Show generic message.
                    this.loading = false;
                    this.showToast('error', 'Error al procesar la respuesta del servidor');
                    console.error('JSON parse error:', e);
                    return;
                }

                if (!response.ok) {
                    this.loading = false;
                    const msg = (data && (data.message || (data.errors && Object.values(data.errors)[0]))) || 'Error en la petición al servidor';
                    this.showToast('error', msg);
                    console.error('Server error:', response.status, data);
                    return;
                }

                const container = document.getElementById('table-content-wrapper');
                if (container) {
                    container.innerHTML = data.table_html;
                }

                // Actualizamos los stats reactivamente
                if (data.stats) this.stats = data.stats;

                // Actualizamos paginación desde metadata del servidor
                if (data.pagination) {
                    this.totalRows = data.pagination.total;
                    this.currentPage = data.pagination.page;
                    this.pagination = data.pagination;
                    this.$nextTick(() => {
                        if (window.addExportButtonsToTables) window.addExportButtonsToTables();
                        const tbl = document.querySelector('.managed-table');
                        if (tbl && typeof TableManager === 'function') {
                            new TableManager(tbl);
                        }
                        setTimeout(() => {
                            this.indexRows();
                            // Mostrar/ocultar fila de 'no results'
                            const emptyRow = document.getElementById('frontend-no-results');
                            if (emptyRow) {
                                if (this.totalRows === 0) emptyRow.classList.remove('hidden');
                                else emptyRow.classList.add('hidden');
                            }
                            this.updatePaginationUI(data.pagination);
                        }, 100);
                    });
                } else {
                    // Fallback: comport. anterior
                    this.$nextTick(() => {
                        setTimeout(() => {
                            this.indexRows();
                            this.applyFrontendLogic();
                        }, 100);
                    });
                }

            } catch (e) {
                console.error("Fallo al cargar tabla:", e);
            } finally {
                this.loading = false;
            }
        },

        indexRows() {
            const container = document.getElementById('table-content-wrapper');
            if (container) {
                this.allDOMRows = Array.from(container.querySelectorAll('tr.period-row'));
            }
        },

        applyFrontendLogic() {
            const matches = this.allDOMRows.filter(row => {
                return row.innerText.toLowerCase().includes(this.searchTerm);
            });

            this.totalRows = matches.length;
            const totalPages = Math.ceil(this.totalRows / this.pageSize) || 1;

            const emptyRow = document.getElementById('frontend-no-results');
            if (emptyRow) {
                const showMsg = (this.allDOMRows.length > 0 && this.totalRows === 0 && this.searchTerm !== '');
                showMsg ? emptyRow.classList.remove('hidden') : emptyRow.classList.add('hidden');
            }

            this.allDOMRows.forEach(row => row.style.display = 'none');
            const start = (this.currentPage - 1) * this.pageSize;
            const end = start + this.pageSize;

            matches.forEach((row, index) => {
                if (index >= start && index < end) row.style.display = '';
            });

            this.updatePaginationUI(totalPages);
        },

        updatePaginationUI(pagination) {
            const start = pagination.total === 0 ? 0 : pagination.start;
            const pageInfo = document.getElementById('page-info');
            if (pageInfo) {
                pageInfo.textContent = `Mostrando ${start}-${pagination.end} de ${pagination.total} registros`;
            }
        },

        // ==========================================
        // 3. BÚSQUEDA AVANZADA Y LIMPIEZA
        // ==========================================
        triggerAdvancedSearch() {
            this.showAdvancedModal = true;
            document.body.classList.add('no-scroll');
        },

        closeAdvancedModal() {
            this.showAdvancedModal = false;
            document.body.classList.remove('no-scroll');
        },
        resetAdvancedFilters() {
            this.advancedFilters = {
                regime_code: '', q: '', unit: '', regime: '',
                doc_number: '', status_code: '', date_from: '', date_to: ''
            };
        },

        async applyAdvancedSearch() {
            this.loading = true;
            this.isAdvancedSearch = true;
            this.showAdvancedModal = false; // Cerramos
            document.body.classList.remove('no-scroll');
            await this.fetchTable(true);
            this.showToast('success', 'Búsqueda avanzada aplicada');
        },


        clearSearch() {
            this.advancedFilters = {
                regime_code: '', q: '', unit: '', regime: '',
                doc_number: '', status_code: '', date_from: '', date_to: ''
            };
            this.isAdvancedSearch = false;
            this.searchTerm = '';
            const input = document.getElementById('table-search-input');
            if (input) input.value = '';
            this.currentPage = 1;
            this.fetchTable(false); // Vuelve a los 50 originales
        },

        // ==========================================
        // 4. GESTIÓN DEL WIZARD (CREACIÓN)
        // ==========================================
        startWizard() {
            this.step = 1;
            this.isEdit = false;
            this.resetWizard();
            this.showWizard = true;
            document.body.classList.add('no-scroll');

            // INICIAR CARGA DE UNIDADES NIVEL 1 INMEDIATAMENTE
            this.loadInitialUnits();
        },


        closeWizard() {
            this.showWizard = false;
            document.body.classList.remove('no-scroll');
        },

        resetWizard() {
            this.searchDoc = '';
            this.unitLevels = []; // Limpiar niveles
            this.selectedContractType = {id: null, name: '', code: '', category: ''};
            this.selectedEmployee = {id: null, full_name: '', photo: '', budget_line: null};
            this.form = {
                administrative_unit: '', budget_line: '', schedule: '', workplace: '',
                start_date: '', end_date: '', document_number: '', job_functions: '',
                institutional_need_memo: '', budget_certification: '',
                manual_position: '', manual_remuneration: '',
                elaboration_date: '', action_motivation: '', action_explanation: '',
                is_boss: false
            };
        },

        selectContractType(id, name, code, category) { // <-- MÉTODO REQUERIDO
            this.selectedContractType = {id, name, code, category};
            this.step = 2;
        },

        async validateEmployee() {
            if (!this.searchDoc) return;
            this.loading = true;
            try {
                const response = await fetch(`/contract/api/validate-employee/${this.searchDoc}/?contract_type_id=${this.selectedContractType.id}`);
                const data = await response.json();
                if (data.success) {
                    const isProfessionalService = (this.selectedContractType.code || '').toUpperCase() === 'SERVICIOS_PROFESIONALES';
                    const hasBudgetLine = !!(data.employee && data.employee.budget_line && data.employee.budget_line.id);

                    if (!isProfessionalService && !hasBudgetLine) {
                        Swal.fire({
                            title: 'Atención',
                            text: 'La persona no tiene una partida presupuestaria asignada. Debe asignarle una partida antes de pasar al tercer paso.',
                            icon: 'warning',
                            confirmButtonText: 'Aceptar',
                            customClass: {
                                confirmButton: 'btn-save'
                            }
                        });
                        return;
                    }

                    this.selectedEmployee = data.employee;
                    this.form.budget_line = data.employee.budget_line ? data.employee.budget_line.id : '';
                    if (data.employee.contract_type_category) {
                        this.selectedContractType.category = data.employee.contract_type_category;
                    }
                    this.step = 3;
                    this.$nextTick(() => this.initSelect2());
                } else {
                    // --- CONFIGURACIÓN ESTÁNDAR SENIOR PARA VALIDACIONES ---
                    Swal.fire({
                        title: 'Atención',
                        text: data.message,
                        icon: 'info',
                        confirmButtonText: 'Aceptar',
                        cancelButtonText: 'Cancelar', // Traducción de "Cancel"
                        showCancelButton: false,      // Sugerencia: En avisos, un solo botón es más limpio
                        customClass: {
                            confirmButton: 'btn-save',
                            cancelButton: 'btn-cancel'
                        }
                    });
                }
            } catch (e) {
                this.showToast('error', 'Fallo de conexión');
            } finally {
                this.loading = false;
            }
        },

        initSelect2() {
            const vm = this;
            $('.select2-vue').each(function () {
                $(this).select2({width: '100%', dropdownParent: $('.modal-container-xl')})
                    .on('change', function () {
                        vm.form[$(this).attr('name')] = $(this).val();
                    });
            });
        },

        async saveManagementPeriod() {
            const f = this.form;
            if (this.selectedContractType.category === 'ACCION_PERSONAL') {
                if (!f.administrative_unit || !f.elaboration_date || !f.start_date || !f.action_motivation || !f.action_explanation) {
                    Swal.fire('Validación', 'Complete la unidad administrativa de destino, fecha de elaboración, rige desde, motivación y explicación.', 'warning');
                    return;
                }
            } else {
                if (!f.administrative_unit || !f.schedule || !f.start_date) {
                    Swal.fire('Validación', 'Complete los campos obligatorios (*).', 'warning');
                    return;
                }
            }

            if (this.selectedContractType.code === 'SERVICIOS_PROFESIONALES') {
                if (!f.manual_position || !f.manual_remuneration) {
                    Swal.fire('Validación', 'Para Servicios Profesionales debe registrar cargo y remuneración manual.', 'warning');
                    return;
                }
            }

            this.loading = true;
            const formData = new FormData();
            formData.append('employee', this.selectedEmployee.id);
            formData.append('contract_type', this.selectedContractType.id);
            if (this.selectedEmployee.budget_line && this.selectedEmployee.budget_line.id) {
                formData.append('budget_line', this.selectedEmployee.budget_line.id);
            }

            Object.keys(this.form).forEach(key => {
                if (this.form[key]) formData.append(key, this.form[key]);
            });
            // Siempre enviar explicitamente el flag is_boss (0/1)
            formData.append('is_boss', this.form.is_boss ? '1' : '0');

            try {
                const response = await fetch('/contract/periods/create/', {
                    method: 'POST',
                    body: formData,
                    headers: {'X-CSRFToken': getCookie('csrftoken')}
                });

                const result = await response.json();

                if (response.ok && result.success) {
                    Swal.fire('¡Éxito!', result.message, 'success').then(() => location.reload());
                } else {
                    // --- MEJORA ARQUITECTÓNICA: Mostrar errores reales del Backend ---
                    let errorContent = '';
                    if (result.errors) {
                        // Si Django devuelve errores por campo (ValidationError)
                        for (const [field, messages] of Object.entries(result.errors)) {
                            errorContent += `<strong>${field}:</strong> ${messages.join(', ')}<br>`;
                        }
                    } else {
                        errorContent = result.message || 'Error desconocido al guardar.';
                    }

                    Swal.fire({
                        title: 'Error de Validación',
                        html: `<div class="text-left">${errorContent}</div>`,
                        icon: 'error'
                    });
                }
            } catch (e) {
                this.showToast('error', 'Error crítico en el servidor');
            } finally {
                this.loading = false;
            }
        },

        // ==========================================
        // 5. EXPEDIENTE, FIRMA Y TERMINACIÓN
        // ==========================================
        async viewPeriodDetails(id) {
            if (!id) return;
            this.loading = true;
            try {
                const response = await fetch(`/contract/periods/detail/${id}/`);
                const data = await response.json();
                if (data.success) {
                    this.selectedPeriod = data.period;
                    this.showDetailModal = true;
                    document.body.classList.add('no-scroll');
                }
            } catch (e) {
                this.showToast('error', 'Fallo al cargar expediente');
            } finally {
                this.loading = false;
            }
        },

        closeDetailModal() {
            this.showDetailModal = false;
            this.selectedPeriod = {};
            document.body.classList.remove('no-scroll');
        },

        async signPeriod(id, contractCategory = '') {
            const isActionDocument = (contractCategory || '').toUpperCase() === 'ACCION_PERSONAL';
            const legalizeLabel = isActionDocument ? 'Acción' : 'Contrato';
            const {isConfirmed} = await Swal.fire({
                title: `¿Legalizar ${legalizeLabel}?`,
                text: 'El estado cambiará a FIRMADO.',
                icon: 'info',
                showCancelButton: true,
                confirmButtonText: 'Sí, Firmar',
                cancelButtonText: 'Cancelar',
                customClass: {confirmButton: 'btn-save', cancelButton: 'btn-cancel'}
            });

            if (isConfirmed) {
                try {
                    const response = await fetch(`/contract/periods/sign/${id}/`, {
                        method: 'POST',
                        headers: {'X-CSRFToken': getCookie('csrftoken')}
                    });
                    const data = await response.json();
                    if (data.success) {
                        this.showToast('success', data.message);
                        this.fetchTable();
                    }
                } catch (e) {
                    this.showToast('error', 'Fallo al firmar');
                }
            }
        },

        async terminatePeriod(id) {
            const {value: formValues, isConfirmed} = await Swal.fire({
                title: 'Finalizar Gestión',
                html: `
                    <div style="text-align:left; display:grid; gap:10px;">
                        <label style="font-weight:600;">Motivo de salida</label>
                        <textarea id="swal-terminate-reason" class="swal2-textarea" placeholder="Detalle el motivo"></textarea>
                        <label style="font-weight:600;">Fecha fin de gestión</label>
                        <input id="swal-terminate-end-date" type="date" class="swal2-input" style="margin:0; width:100%;" />
                    </div>
                `,
                focusConfirm: false,
                showCancelButton: true,
                confirmButtonText: 'Finalizar',
                preConfirm: () => {
                    const reasonEl = document.getElementById('swal-terminate-reason');
                    const endDateEl = document.getElementById('swal-terminate-end-date');
                    const reason = reasonEl ? reasonEl.value.trim() : '';
                    const endDate = endDateEl ? endDateEl.value : '';
                    if (!reason) {
                        Swal.showValidationMessage('El motivo de salida es obligatorio.');
                        return false;
                    }
                    if (!endDate) {
                        Swal.showValidationMessage('La fecha fin de gestión es obligatoria.');
                        return false;
                    }
                    return {reason, end_date: endDate};
                }
            });

            if (isConfirmed && formValues) {
                const formData = new FormData();
                formData.append('reason', formValues.reason);
                formData.append('end_date', formValues.end_date);
                try {
                    const response = await fetch(`/contract/periods/terminate/${id}/`, {
                        method: 'POST',
                        body: formData,
                        headers: {'X-CSRFToken': getCookie('csrftoken')}
                    });
                    const data = await response.json();
                    if (data.success) {
                        Swal.fire('Éxito', data.message, 'success');
                        this.fetchTable();
                    } else {
                        this.showToast('error', data.message || 'No se pudo finalizar la gestión');
                    }
                } catch (e) {
                    this.showToast('error', 'Error al terminar');
                }
            }
        },
        filterByRegime(regimeCode) {
            // Si hace clic en el mismo, limpiamos
            if (this.advancedFilters.regime_code === regimeCode) {
                this.advancedFilters.regime_code = '';
                this.isAdvancedSearch = false;
                this.fetchTable(false);
            } else {
                this.advancedFilters.regime_code = regimeCode;
                this.isAdvancedSearch = true;
                this.fetchTable(true);
            }
        },

        // ==========================================
        // 6. UTILITARIOS
        // ==========================================
        nextPage() {
            this.currentPage++;
            this.fetchTable(this.isAdvancedSearch);
        },
        prevPage() {
            if (this.currentPage > 1) {
                this.currentPage--;
                this.fetchTable(this.isAdvancedSearch);
            }
        },
        showToast(icon, title) {
            Swal.fire({icon, title, toast: true, position: 'top-end', showConfirmButton: false, timer: 3000});
        }
    }
});

window.periodInstance = periodApp.mount('#period-app');