/* static/js/function_manual.js */
const {createApp} = Vue;

createApp({
    delimiters: ['[[', ']]'],
    data() {
        return {
            loading: false,
            isEdit: false,
            showModal: false,
            currentId: null,
            searchQuery: '',
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
                const levelsData = container.dataset.levels;
                this.complexityLevels = JSON.parse(levelsData);
            } catch (e) { 
                console.error("Error al parsear niveles:", e); 
                this.complexityLevels = [];
            }
        }
        
        // Configurar búsqueda frontend
        this.setupSearch();
    },
    methods: {
        setupSearch() {
            const searchInput = document.getElementById('table-search');
            if (searchInput) {
                searchInput.addEventListener('input', (e) => {
                    this.searchQuery = e.target.value.toLowerCase();
                    this.filterTable();
                });
            }
        },

        filterTable() {
            const rows = document.querySelectorAll('#table-content-wrapper tbody tr');
            let visibleCount = 0;
            
            rows.forEach(row => {
                const text = row.textContent.toLowerCase();
                if (text.includes(this.searchQuery)) {
                    row.style.display = '';
                    visibleCount++;
                } else {
                    row.style.display = 'none';
                }
            });
            
            // Actualizar info de paginación si existe
            const pageInfo = document.getElementById('page-info');
            if (pageInfo) {
                pageInfo.textContent = `Mostrando ${visibleCount} de ${rows.length} registros`;
            }
        },

        async refreshTable() {
            try {
                const response = await fetch(this.urls.table);
                const html = await response.text();
                document.getElementById('table-content-wrapper').innerHTML = html;
                
                // Reaplica el filtro si hay búsqueda activa
                if (this.searchQuery) {
                    this.filterTable();
                }
                
                // Actualizar estadísticas
                await this.updateStats();
            } catch (error) {
                console.error('Error al refrescar tabla:', error);
            }
        },

        async updateStats() {
            // Aquí podrías hacer un fetch para obtener las estadísticas actualizadas
            // Por ahora, recuenta desde la tabla
            const rows = document.querySelectorAll('#table-content-wrapper tbody tr');
            let total = 0, behavioral = 0, technical = 0, transversal = 0;
            
            rows.forEach(row => {
                const typeCell = row.querySelector('[data-type]');
                if (typeCell) {
                    total++;
                    const type = typeCell.dataset.type;
                    if (type === 'BEHAVIORAL') behavioral++;
                    else if (type === 'TECHNICAL') technical++;
                    else if (type === 'TRANSVERSAL') transversal++;
                }
            });
            
            // Actualizar números en las tarjetas
            const statTotal = document.getElementById('stat-total');
            const statBehavioral = document.getElementById('stat-behavioral');
            const statTechnical = document.getElementById('stat-technical');
            const statTransversal = document.getElementById('stat-transversal');
            
            if (statTotal) statTotal.textContent = total;
            if (statBehavioral) statBehavioral.textContent = behavioral;
            if (statTechnical) statTechnical.textContent = technical;
            if (statTransversal) statTransversal.textContent = transversal;
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
            this.showModal = true;
            document.body.classList.add('no-scroll');
        },

        closeModal() {
            this.showModal = false;
            document.body.classList.remove('no-scroll');
            this.resetForm();
        },

        resetForm() {
            this.currentId = null;
            this.isEdit = false;
            this.formData = {
                name: '', 
                type: 'TECHNICAL', 
                definition: '', 
                suggested_level: ''
            };
        },

        async toggleStatus(id) {
            try {
                const url = this.urls.toggleBase.replace('0', id);
                const response = await fetch(url, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': this.getCsrfToken(),
                        'Content-Type': 'application/json'
                    }
                });
                
                if (response.ok) {
                    await this.refreshTable();
                    window.Toast.fire({icon: 'success', title: 'Estado actualizado'});
                }
            } catch (error) {
                console.error('Error al cambiar estado:', error);
                window.Toast.fire({icon: 'error', title: 'Error al actualizar'});
            }
        },

        async saveCompetency() {
            this.loading = true;
            const url = this.isEdit 
                ? this.urls.updateBase.replace('0', this.currentId) 
                : this.urls.create;

            try {
                const response = await fetch(url, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': this.getCsrfToken(),
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(this.formData)
                });

                const result = await response.json();
                
                if (response.ok) {
                    window.Toast.fire({
                        icon: 'success', 
                        title: result.message || 'Operación exitosa'
                    });
                    this.closeModal();
                    await this.refreshTable();
                } else {
                    // Mostrar errores de validación
                    if (result.errors) {
                        const errorMessages = Object.values(result.errors).flat().join(', ');
                        window.Toast.fire({icon: 'error', title: errorMessages});
                    } else {
                        window.Toast.fire({icon: 'error', title: 'Error al guardar'});
                    }
                }
            } catch (error) {
                console.error('Error al guardar:', error);
                window.Toast.fire({icon: 'error', title: 'Error en el servidor'});
            } finally {
                this.loading = false;
            }
        },

        getCsrfToken() {
            const tokenElement = document.querySelector('[name=csrfmiddlewaretoken]');
            return tokenElement ? tokenElement.value : '';
        }
    }
}).mount('#competencyApp');