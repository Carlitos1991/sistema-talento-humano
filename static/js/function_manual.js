/* static/js/function_manual.js */
const {createApp} = Vue;

createApp({
    delimiters: ['[[', ']]'],
    data() {
        return {
            loading: false,
            isEdit: false,
            showModal: false, // <-- NUEVA VARIABLE DE CONTROL
            currentId: null,
            urls: {},
            complexityLevels: [],
            formData: {
                name: '',
                type: 'TECHNICAL',
                definition: '',
                suggested_level: ''
            }
        }
    },
    mounted() {
        const container = document.getElementById('competencyApp');
        if (container) {
            this.urls = {
                table: container.dataset.urlTable,
                create: container.dataset.urlCreate,
                updateBase: container.dataset.urlUpdateBase,
                toggleBase: container.dataset.urlToggleBase
            };
            try {
                this.complexityLevels = JSON.parse(container.dataset.levels);
            } catch (e) { console.error("Error niveles:", e); }
        }
    },
    methods: {
        async refreshTable() {
            const response = await fetch(this.urls.table);
            document.getElementById('tablePartialContainer').innerHTML = await response.text();
        },

        openModal(mode, data = null) {
            this.isEdit = mode === 'edit';
            if (this.isEdit && data) {
                this.currentId = data.id;
                this.formData = {
                    name: data.name,
                    type: data.type,
                    definition: data.definition,
                    suggested_level: data.suggested_level || ''
                };
            } else {
                this.resetForm();
            }
            this.showModal = true; // <-- ACTIVAR MODAL
            document.body.classList.add('no-scroll');
        },

        closeModal() {
            this.showModal = false; // <-- DESACTIVAR MODAL
            document.body.classList.remove('no-scroll');
            this.resetForm();
        },

        resetForm() {
            this.currentId = null;
            this.isEdit = false;
            this.formData = {name: '', type: 'TECHNICAL', definition: '', suggested_level: ''};
        },

        async toggleStatus(id) {
            const url = this.urls.toggleBase.replace('0', id);
            await fetch(url, {
                method: 'POST',
                headers: {'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value}
            });
            this.refreshTable();
            window.Toast.fire({icon: 'success', title: 'Estado actualizado'});
        },

        async saveCompetency() {
            this.loading = true;
            const url = this.isEdit ? this.urls.updateBase.replace('0', this.currentId) : this.urls.create;

            try {
                const response = await fetch(url, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(this.formData)
                });

                const result = await response.json();
                if (response.ok) {
                    window.Toast.fire({icon: 'success', title: result.message});
                    this.closeModal();
                    this.refreshTable();
                }
            } catch (error) {
                window.Toast.fire({icon: 'error', title: 'Error en el servidor'});
            } finally {
                this.loading = false;
            }
        }
    }
}).mount('#competencyApp');