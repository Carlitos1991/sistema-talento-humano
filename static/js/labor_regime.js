/* apps/contract/static/js/labor_regime.js */
const {createApp} = Vue;

const regimeApp = createApp({
    delimiters: ['[[', ']]'],
    data() {
        const container = document.getElementById('regime-app');
        return {
            // Estado Principal (Regímenes)
            loading: false,
            showModal: false,
            isEdit: false,
            searchTimer: null,
            stats: {
                total: parseInt(container?.dataset.total) || 0,
                active: parseInt(container?.dataset.active) || 0,
                inactive: parseInt(container?.dataset.inactive) || 0
            },
            filters: {name: '', is_active: ''},
            form: {id: null, code: '', name: '', description: '', is_active: true},

            // Estado Sub-módulo (Tipos de Contrato)
            showContractModal: false,
            currentRegime: {id: null, name: ''},
            contractTypes: [],
            loadingContracts: false
        }
    },
    methods: {
        // --- GESTIÓN DE REGÍMENES ---
        openCreateModal() {
            this.isEdit = false;
            this.resetForm();
            this.showModal = true;
            document.body.classList.add('no-scroll');
        },
        async openCreateContractType() {
            const {value: formValues} = await Swal.fire({
                title: 'Nueva Modalidad Laboral',
                html: `
            <div class="text-left" style="padding: 1rem">
                <div class="form-group mb-3">
                    <label class="form-label font-weight-700">Código Único</label>
                    <input id="swal-code" class="form-control uppercase-input" placeholder="EJ: CT_OCASIONAL">
                </div>
               <div class="form-group mb-3">
                    <label class="form-label font-weight-700">Nombre de la Modalidad</label>
                    <input id="swal-name" class="form-control uppercase-input" placeholder="EJ: CONTRATO OCASIONAL">
                </div>editContractType
                <div class="form-group">
                    <label class="form-label font-weight-700">Categoría de Documento</label>
                    <select id="swal-cat" class="form-control">
                        <option value="CONTRATO">Contrato</option>
                        <option value="ACCION_PERSONAL">Acción de Personal</option>
                    </select>
                </div>
            </div>`,
                showCancelButton: true,
                confirmButtonText: 'Guardar Modalidad',
                cancelButtonText: 'Cancelar',
                customClass: {confirmButton: 'btn-swal-success', cancelButton: 'btn-swal-cancel'},
                preConfirm: () => {
                    const code = document.getElementById('swal-code').value;
                    const name = document.getElementById('swal-name').value;
                    if (!code || !name) return Swal.showValidationMessage('Código y Nombre son obligatorios');
                    return {
                        code: code,
                        name: name,
                        category: document.getElementById('swal-cat').value,
                        regime: this.currentRegime.id
                    }
                }
            });

            if (formValues) this.saveContractTypeAPI(formValues);
        },

        async saveContractTypeAPI(data) {
            const formData = new FormData();
            formData.append('code', data.code);
            formData.append('name', data.name);
            formData.append('contract_type_category', data.category);
            formData.append('labor_regime', data.regime);
            formData.append('is_active', 'true'); // Forzado por negocio

            try {
                const response = await fetch('/contract/contract-types/create/', {
                    method: 'POST',
                    body: formData,
                    headers: {'X-CSRFToken': getCookie('csrftoken')}
                });
                const result = await response.json();
                if (result.success) {
                    this.showToast('success', result.message);
                    this.fetchContractTypes(); // Refresca el modal de lista
                    this.fetchTable();         // Refresca el contador azul de la tabla principal
                } else {
                    Swal.fire('Atención', result.errors?.code?.[0] || 'Error al guardar', 'warning');
                }
            } catch (error) {
                this.showToast('error', 'Error de red');
            }
        },

        async toggleContractTypeStatus(id) {
            try {
                const response = await fetch(`/contract/contract-types/toggle-status/${id}/`, {
                    method: 'POST',
                    headers: {'X-CSRFToken': getCookie('csrftoken')}
                });
                const result = await response.json();
                if (result.success) {
                    this.showToast('success', result.message);
                    this.fetchContractTypes();
                }
            } catch (error) {
                this.showToast('error', 'Error al cambiar estado');
            }
        },
        async openEditModal(id) {
            this.loading = true;
            this.isEdit = true;
            try {
                const response = await fetch(`/contract/regimes/detail/${id}/`);
                const data = await response.json();
                if (data.success) {
                    this.form = data.regime;
                    this.showModal = true;
                    document.body.classList.add('no-scroll');
                }
            } catch (error) {
                this.showToast('error', 'Error al cargar datos');
            } finally {
                this.loading = false;
            }
        },

        async saveRegime() {
            this.loading = true;
            const formData = new FormData();
            formData.append('id', this.form.id || '');
            formData.append('code', this.form.code.toUpperCase().trim());
            formData.append('name', this.form.name.toUpperCase().trim());
            formData.append('description', this.form.description);
            formData.append('is_active', this.form.is_active);
            Object.keys(this.form).forEach(key => formData.append(key, this.form[key]));

            const url = this.isEdit ? `/contract/regimes/update/${this.form.id}/` : '/contract/regimes/create/';

            try {
                const response = await fetch(url, {
                    method: 'POST',
                    body: formData,
                    headers: {'X-CSRFToken': getCookie('csrftoken')}
                });
                const result = await response.json();
                if (result.success) {
                    this.showToast('success', result.message);
                    this.closeModal();
                    this.fetchTable();
                } else {
                    Swal.fire('Atención', 'Revise los campos obligatorios o códigos duplicados', 'warning');
                }
            } catch (error) {
                this.showToast('error', 'Error de servidor');
            } finally {
                this.loading = false;
            }
        },

        async toggleStatus(id, currentStatus) {
            const status = String(currentStatus) === 'true';
            const action = status ? 'DAR DE BAJA' : 'RESTAURAR';

            const result = await Swal.fire({
                title: `¿${action}?`,
                icon: 'warning',
                showCancelButton: true,
                confirmButtonText: 'Sí, confirmar'
            });

            if (result.isConfirmed) {
                const response = await fetch(`/contract/regimes/toggle-status/${id}/`, {
                    method: 'POST',
                    headers: {'X-CSRFToken': getCookie('csrftoken')}
                });
                if (response.ok) {
                    this.fetchTable();
                    this.showToast('success', 'Estado actualizado');
                }
            }
        },
        async editContractType(type) {
            const {value: formValues} = await Swal.fire({
                title: 'Editar Modalidad Laboral',
                html: `
                     <div class="text-left" style="padding: 1rem">
                        <div class="form-group mb-3">
                            <label class="form-label font-weight-700">Código Único (No editable)</label>
                            <input id="swal-code" class="form-control bg-readonly" readonly value="${type.code}">
                        </div>
                        <div class="form-group mb-3">
                            <label class="form-label font-weight-700">Nombre de la Modalidad</label>
                            <input id="swal-name" class="form-control uppercase-input" value="${type.name}">
                        </div>
                        <div class="form-group">
                            <label class="form-label font-weight-700">Categoría de Documento</label>
                            <select id="swal-cat" class="form-control">
                                <option value="CONTRATO" ${type.category === 'CONTRATO' ? 'selected' : ''}>Contrato</option>
                                <option value="ACCION_PERSONAL" ${type.category === 'ACCION_PERSONAL' ? 'selected' : ''}>Acción de Personal</option>
                            </select>
                        </div>
                    </div>`,
                showCancelButton: true,
                confirmButtonText: 'Guardar Cambios',
                cancelButtonText: 'Cancelar',
                customClass: {confirmButton: 'btn-swal-success', cancelButton: 'btn-swal-cancel'},
                preConfirm: () => {
                    const code = document.getElementById('swal-code').value;
                    const name = document.getElementById('swal-name').value;
                    if (!code || !name) return Swal.showValidationMessage('Código y Nombre son obligatorios');
                    return {
                        id: type.id,
                        code: code,
                        name: name,
                        category: document.getElementById('swal-cat').value,
                        regime: this.currentRegime.id
                    }
                }
            });

            if (formValues) {
                this.updateContractTypeAPI(formValues);
            }
        },

        async updateContractTypeAPI(data) {
            this.loadingContracts = true;
            const formData = new FormData();
            formData.append('code', data.code);
            formData.append('name', data.name);
            formData.append('contract_type_category', data.category);
            formData.append('labor_regime', data.regime);

            try {
                const response = await fetch(`/contract/contract-types/update/${data.id}/`, {
                    method: 'POST',
                    body: formData,
                    headers: {'X-CSRFToken': getCookie('csrftoken')}
                });
                const result = await response.json();

                if (result.success) {
                    this.showToast('success', result.message);
                    this.fetchContractTypes(); // Recarga la lista del modal
                } else {
                    Swal.fire('Atención', result.message || 'Error al actualizar', 'warning');
                }
            } catch (error) {
                this.showToast('error', 'Error de comunicación');
            } finally {
                this.loadingContracts = false;
            }
        },
        // --- GESTIÓN ANIDADA (TIPOS DE CONTRATO) ---
        async viewContractTypes(regimeId, regimeName) {
            this.currentRegime = {id: regimeId, name: regimeName};
            this.showContractModal = true;
            document.body.classList.add('no-scroll');
            this.fetchContractTypes();
        },

        async fetchContractTypes() {
            this.loadingContracts = true;
            try {
                const response = await fetch(`/contract/regimes/${this.currentRegime.id}/contract-types/`);
                const data = await response.json();
                this.contractTypes = data.contract_types;
            } catch (error) {
                this.showToast('error', 'No se pudieron cargar los tipos de contrato');
            } finally {
                this.loadingContracts = false;
            }
        },

        // --- UTILITARIOS ---
        filterByStatus(status) {
            this.filters.is_active = status;
            this.fetchTable();
        },

        async fetchTable() {
            const params = new URLSearchParams(this.filters).toString();
            const response = await fetch(`/contract/regimes/partial-table/?${params}`);
            const data = await response.json();
            document.getElementById('table-content-wrapper').innerHTML = data.table_html;
            if (data.stats) this.stats = data.stats;
        },

        debouncedSearch() {
            clearTimeout(this.searchTimer);
            this.searchTimer = setTimeout(() => this.fetchTable(), 400);
        },

        resetForm() {
            this.form = {id: null, code: '', name: '', description: '', is_active: true};
        },

        closeModal() {
            this.showModal = false;
            this.showContractModal = false;
            document.body.classList.remove('no-scroll');
        },

        showToast(icon, title) {
            Swal.fire({icon, title, toast: true, position: 'top-end', showConfirmButton: false, timer: 3000});
        }
    },
    mounted() {
        // Sincronización inicial
        this.fetchTable();
    }
});

// Exposición global para los botones onclick del Partial Table
window.regimeInstance = regimeApp.mount('#regime-app');

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