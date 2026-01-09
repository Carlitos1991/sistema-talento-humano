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
            // Estados de Control
            loading: false,
            step: 1,
            showWizard: false,
            showDetailModal: false,
            isEdit: false,

            // Datos de Búsqueda y Selección
            searchDoc: '',
            selectedContractType: {id: null, name: ''},
            selectedEmployee: {id: null, full_name: '', photo: '', budget_line: null},
            selectedPeriod: {}, // Para el modal de expediente

            // Formulario Paso 3
            form: {
                id: null,
                administrative_unit: '',
                budget_line: '',
                schedule: '',
                workplace: '',
                start_date: '',
                end_date: '',
                document_number: '',
                job_functions: '',
                institutional_need_memo: '',
                budget_certification: ''
            },

            // Estadísticas y Filtros
            stats: {
                total: parseInt(container?.dataset.total) || 0,
                active: parseInt(container?.dataset.active) || 0,
                losep: parseInt(container?.dataset.losep) || 0,
                ct: parseInt(container?.dataset.ct) || 0
            },
            filters: {name: '', status: ''},
            searchTimer: null
        }
    },

    mounted() {
        this.fetchTable();
    },

    methods: {
        // ==========================================
        // 1. GESTIÓN DEL WIZARD (CREACIÓN)
        // ==========================================
        startWizard() {
            this.step = 1;
            this.isEdit = false;
            this.resetWizard();
            this.showWizard = true;
            document.body.classList.add('no-scroll');
        },

        closeWizard() {
            this.showWizard = false;
            document.body.classList.remove('no-scroll');
        },

        resetWizard() {
            this.searchDoc = '';
            this.selectedContractType = {id: null, name: ''};
            this.selectedEmployee = {id: null, full_name: '', photo: '', budget_line: null};
            this.form = {
                administrative_unit: '',
                budget_line: '',
                schedule: '',
                workplace: '',
                start_date: '',
                end_date: '',
                document_number: '',
                job_functions: '',
                institutional_need_memo: '',
                budget_certification: ''
            };
        },

        selectContractType(id, name) {
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
                    if (data.has_active_contract) {
                        Swal.fire('Atención', 'Este empleado ya tiene un contrato activo.', 'warning');
                    } else {
                        this.selectedEmployee = data.employee;
                        this.form.budget_line = data.employee.budget_line.id;
                        this.step = 3;
                        this.$nextTick(() => {
                            this.initSelect2();
                        });
                    }
                } else {
                    Swal.fire('Validación', data.message, 'info');
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
                $(this).select2({
                    width: '100%',
                    dropdownParent: $('.modal-container-xl')
                }).on('change', function () {
                    vm.form[$(this).attr('name')] = $(this).val();
                });
            });
        },

        async saveManagementPeriod() {
            const f = this.form;
            if (!f.administrative_unit || !f.schedule || !f.start_date || !f.document_number) {
                Swal.fire('Atención', 'Complete los campos obligatorios.', 'warning');
                return;
            }

            this.loading = true;
            const formData = new FormData();
            formData.append('employee', this.selectedEmployee.id);
            formData.append('contract_type', this.selectedContractType.id);
            formData.append('budget_line', this.selectedEmployee.budget_line.id);

            Object.keys(this.form).forEach(key => {
                if (this.form[key] !== null && this.form[key] !== undefined) {
                    formData.append(key, this.form[key]);
                }
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
                    // --- MEJORA AQUÍ: Mostrar errores específicos del Backend ---
                    let errorContent = '';
                    if (result.errors) {
                        // Si Django devuelve errores por campo
                        for (const [field, messages] of Object.entries(result.errors)) {
                            errorContent += `<strong>${field}:</strong> ${messages.join(', ')}<br>`;
                        }
                    } else {
                        errorContent = result.message || 'Error desconocido al guardar.';
                    }

                    Swal.fire({
                        title: 'Error en Validación',
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
        // 2. GESTIÓN DE EXPEDIENTE (DETALLE Y EDICIÓN)
        // ==========================================
        async viewPeriodDetails(id) {
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
                this.showToast('error', 'No se pudo cargar el expediente');
            } finally {
                this.loading = false;
            }
        },

        closeDetailModal() {
            this.showDetailModal = false;
            document.body.classList.remove('no-scroll');
        },

        async editPeriodFields() {
            const p = this.selectedPeriod;
            // Construimos las opciones del select de horarios dinámicamente
            let scheduleOptions = '<option value="">Seleccione...</option>';
            window.allSchedules.forEach(s => {
                scheduleOptions += `<option value="${s.id}" ${s.id == p.schedule_id ? 'selected' : ''}>${s.name}</option>`;
            });

            const {value: formValues} = await Swal.fire({
                title: 'Modificar Datos Administrativos',
                width: '850px',
                html: `
                <div class="text-left container-fluid" style="font-family: inherit;">
                    <div class="row">
                        <div class="col-6 mb-3">
                            <label class="form-label font-weight-700 small">NRO. DOCUMENTO / ACCIÓN</label>
                            <input id="swal-doc" class="form-control" value="${p.document_number}">
                        </div>
                        <div class="col-6 mb-3">
                            <label class="form-label font-weight-700 small">LUGAR DE TRABAJO</label>
                            <input id="swal-workplace" class="form-control" value="${p.workplace}">
                        </div>
                        <div class="col-6 mb-3">
                            <label class="form-label font-weight-700 small">MEMO NECESIDAD</label>
                            <input id="swal-memo" class="form-control" value="${p.institutional_need_memo}">
                        </div>
                        <div class="col-6 mb-3">
                            <label class="form-label font-weight-700 small">CERT. PRESUPUESTARIA</label>
                            <input id="swal-cert" class="form-control" value="${p.budget_certification}">
                        </div>
                        <div class="col-4 mb-3">
                            <label class="form-label font-weight-700 small">FECHA INICIO</label>
                            <input type="date" id="swal-start" class="form-control" value="${p.start_date}">
                        </div>
                        <div class="col-4 mb-3">
                            <label class="form-label font-weight-700 small">FECHA FIN</label>
                            <input type="date" id="swal-end" class="form-control" value="${p.end_date}">
                        </div>
                        <div class="col-4 mb-3">
                            <label class="form-label font-weight-700 small">HORARIO</label>
                            <select id="swal-schedule" class="form-control">${scheduleOptions}</select>
                        </div>
                        <div class="col-12">
                            <label class="form-label font-weight-700 small">FUNCIONES DEL PUESTO</label>
                            <textarea id="swal-functions" class="form-control" rows="3">${p.job_functions}</textarea>
                        </div>
                    </div>
                </div>`,
                showCancelButton: true,
                confirmButtonText: 'Guardar Cambios',
                cancelButtonText: 'Cancelar',
                customClass: {confirmButton: 'btn-save', cancelButton: 'btn-cancel'},
                preConfirm: () => {
                    return {
                        doc: document.getElementById('swal-doc').value,
                        workplace: document.getElementById('swal-workplace').value,
                        memo: document.getElementById('swal-memo').value,
                        cert: document.getElementById('swal-cert').value,
                        start: document.getElementById('swal-start').value,
                        end: document.getElementById('swal-end').value,
                        schedule: document.getElementById('swal-schedule').value,
                        functions: document.getElementById('swal-functions').value,
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
                    this.viewPeriodDetails(id); // Recarga el modal de expediente
                    this.fetchTable(); // Recarga la tabla de fondo
                }
            } catch (e) {
                this.showToast('error', 'Error al actualizar');
            } finally {
                this.loading = false;
            }
        },

        // ==========================================
        // 3. FIRMA Y TERMINACIÓN
        // ==========================================
        async signPeriod(id) {
            const {isConfirmed} = await Swal.fire({
                title: '¿Legalizar Contrato?',
                text: "El estado cambiará a 'FIRMADO'.",
                icon: 'info', showCancelButton: true, confirmButtonText: 'Sí, Firmar'
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
                    this.showToast('error', 'Error al firmar');
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

        // ==========================================
        // 4. TABLA Y FILTROS
        // ==========================================
        async fetchTable() {
            const params = new URLSearchParams(this.filters).toString();
            try {
                const response = await fetch(`/contract/periods/partial-table/?${params}`);
                const data = await response.json();
                document.getElementById('table-content-wrapper').innerHTML = data.table_html;
                if (data.stats) this.stats = data.stats;
            } catch (e) {
                console.error("Error table:", e);
            }
        },

        filterByStatus(status) {
            this.filters.status = status;
            this.fetchTable();
        },

        debouncedSearch() {
            clearTimeout(this.searchTimer);
            this.searchTimer = setTimeout(() => this.fetchTable(), 400);
        },

        showToast(icon, title) {
            Swal.fire({icon, title, toast: true, position: 'top-end', showConfirmButton: false, timer: 3000});
        }
    }
});

// Exposición e inicio
window.periodInstance = periodApp.mount('#period-app');