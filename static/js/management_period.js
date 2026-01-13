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
            loading: false,
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
            selectedContractType: {id: null, name: ''},
            selectedEmployee: {id: null, full_name: '', photo: '', budget_line: null},
            selectedPeriod: {},

            // --- FORMULARIO CREACIÓN ---
            form: {
                id: null, administrative_unit: '', budget_line: '', schedule: '',
                workplace: '', start_date: '', end_date: '', document_number: '',
                job_functions: '', institutional_need_memo: '', budget_certification: ''
            },

            // --- ESTADÍSTICAS ---
            stats: {
                total: 0,
                regimes: [] // Lista vacía inicial
            },
            filters: {status: ''}
        }
    },

    mounted() {
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
                searchInput.addEventListener('input', (e) => {
                    this.searchTerm = e.target.value.toLowerCase().trim();
                    this.currentPage = 1;
                    this.applyFrontendLogic();
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

                    if (action === 'sign') this.signPeriod(id);
                    if (action === 'view') this.viewPeriodDetails(id);
                    if (action === 'terminate') this.terminatePeriod(id);
                    if (action === 'upload') this.uploadContractFile(id);

                    // CORRECCIÓN: Llamar al nuevo nombre del método
                    if (action === 'advanced-search-empty') this.openSearchModal();
                });
            }
        },
        // --- MÉTODOS DE BÚSQUEDA ---
        openSearchModal() {
            console.log("Iniciando secuencia de apertura...");

            // Forzamos la actualización del estado
            this.showAdvancedModal = true;
            document.body.classList.add('no-scroll');

            // TÉCNICA SENIOR: Forzamos un re-render mediante loading
            // para que Vue despierte al motor de dibujo del navegador
            this.loading = true;
            this.$nextTick(() => {
                this.loading = false;
                console.log("DOM actualizado: Modal de búsqueda debería ser visible.");
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
                    <input type="text" class="input-field readonly-styled" 
                           value="ML-DTH-XXX-REGIME" readonly 
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
                    const doc = document.getElementById('swal-doc').value;
                    const start = document.getElementById('swal-start').value;
                    if (!doc || !start) {
                        Swal.showValidationMessage('Nro. Documento y Fecha Inicio son obligatorios');
                        return false;
                    }
                    return {
                        doc: doc.trim().toUpperCase(),
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
                q: this.advancedQuery,
                regime_code: this.advancedFilters.regime_code, // <-- IMPORTANTE
                status: this.filters.status,
                ...this.advancedFilters // Esto expande el resto (unit, dates, etc.)
            }).toString();

            try {
                const response = await fetch(`/contract/periods/partial-table/?${params}`);
                const data = await response.json();

                const container = document.getElementById('table-content-wrapper');
                if (container) container.innerHTML = data.table_html;

                // Actualizamos los stats reactivamente (esto cambiará los 0s por los números reales)
                if (data.stats) {
                    this.stats = data.stats;
                }

                this.$nextTick(() => {
                    setTimeout(() => {
                        this.indexRows();
                        this.applyFrontendLogic();
                    }, 100);
                });

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

        updatePaginationUI(totalPages) {
            const pageInfo = document.getElementById('page-info');
            const pageDisplay = document.getElementById('current-page-display');
            const btnPrev = document.getElementById('btn-prev');
            const btnNext = document.getElementById('btn-next');

            if (pageInfo) {
                if (this.totalRows > 0) {
                    const start = (this.currentPage - 1) * this.pageSize + 1;
                    const end = Math.min(this.currentPage * this.pageSize, this.totalRows);
                    pageInfo.textContent = `Mostrando ${start}-${end} de ${this.totalRows} registros`;
                } else {
                    pageInfo.textContent = "Sin registros para mostrar";
                }
            }
            if (pageDisplay) pageDisplay.textContent = this.currentPage;
            if (btnPrev) btnPrev.disabled = (this.currentPage === 1);
            if (btnNext) btnNext.disabled = (this.currentPage >= totalPages || this.totalRows === 0);
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
            this.selectedContractType = {id: null, name: ''};
            this.selectedEmployee = {id: null, full_name: '', photo: '', budget_line: null};
            this.form = {
                administrative_unit: '', budget_line: '', schedule: '', workplace: '',
                start_date: '', end_date: '', document_number: '', job_functions: '',
                institutional_need_memo: '', budget_certification: ''
            };
        },

        selectContractType(id, name) { // <-- MÉTODO REQUERIDO
            this.selectedContractType = {id, name};
            this.step = 2;
        },

        async validateEmployee() {
            if (!this.searchDoc) return;
            this.loading = true;
            try {
                const response = await fetch(`/contract/api/validate-employee/${this.searchDoc}/`);
                const data = await response.json();
                if (data.success) {
                    this.selectedEmployee = data.employee;
                    this.form.budget_line = data.employee.budget_line.id;
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
            if (!f.administrative_unit || !f.schedule || !f.start_date) {
                CustomSwal.fire('Validación', 'Complete los campos obligatorios (*).', 'warning');
                return;
            }

            this.loading = true;
            const formData = new FormData();
            formData.append('employee', this.selectedEmployee.id);
            formData.append('contract_type', this.selectedContractType.id);
            formData.append('budget_line', this.selectedEmployee.budget_line.id);

            Object.keys(this.form).forEach(key => {
                if (this.form[key]) formData.append(key, this.form[key]);
            });

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

        async signPeriod(id) {
            const {isConfirmed} = await Swal.fire({
                title: '¿Legalizar Contrato?',
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
            const {value: reason, isConfirmed} = await Swal.fire({
                title: 'Finalizar Gestión',
                input: 'textarea',
                inputLabel: 'Motivo de salida',
                showCancelButton: true, confirmButtonText: 'Finalizar'
            });

            if (isConfirmed && reason) {
                const formData = new FormData();
                formData.append('reason', reason);
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
            if (this.currentPage < Math.ceil(this.totalRows / this.pageSize)) {
                this.currentPage++;
                this.applyFrontendLogic();
            }
        },
        prevPage() {
            if (this.currentPage > 1) {
                this.currentPage--;
                this.applyFrontendLogic();
            }
        },
        showToast(icon, title) {
            Swal.fire({icon, title, toast: true, position: 'top-end', showConfirmButton: false, timer: 3000});
        }
    }
});

window.periodInstance = periodApp.mount('#period-app');