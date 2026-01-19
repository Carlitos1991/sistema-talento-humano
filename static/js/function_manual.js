/* static/js/function_manual.js */

const {createApp} = Vue;

const getCsrfToken = () => document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';

document.addEventListener('DOMContentLoaded', () => {

    // =========================================================================
    // 1. GESTIÓN DE ESCALAS / ESTRUCTURA (#valuationApp)
    // =========================================================================
    const valEl = document.getElementById('valuationApp');
    if (valEl) {
        createApp({
            delimiters: ['[[', ']]'],
            data() {
                return {
                    parentId: valEl.dataset.parentId || null,
                    nextType: valEl.dataset.nextType || 'ROLE',
                    urlSave: valEl.dataset.urlSave,
                    urlDetailBase: valEl.dataset.urlDetailBase, // URL con el '0' de placeholder
                    workingType: '',
                    showModal: false, isEdit: false, loading: false,
                    catalogs: {instruction: [], decisions: [], impact: [], roles: [], matrix: [], complexity: []},
                    formData: {id: null, catalog_item_id: '', name_extra: '', occupational_classification_id: ''}
                }
            },
            computed: {
                nextLevelName() {
                    const names = {
                        'ROLE': 'Rol',
                        'INSTRUCTION': 'Instrucción',
                        'EXPERIENCE': 'Experiencia',
                        'DECISION': 'Decisión',
                        'IMPACT': 'Impacto',
                        'COMPLEXITY': 'Complejidad',
                        'RESULT': 'Resultado'
                    };
                    return names[this.nextType] || 'Nivel';
                },
                currentNodeTypeName() {
                    const names = {
                        'ROLE': 'Rol',
                        'INSTRUCTION': 'Instrucción',
                        'EXPERIENCE': 'Experiencia',
                        'DECISION': 'Decisión',
                        'IMPACT': 'Impacto',
                        'COMPLEXITY': 'Complejidad',
                        'RESULT': 'Resultado'
                    };
                    return names[this.workingType] || this.nextLevelName;
                },
                filteredCatalogItems() {
                    const mapping = {
                        'ROLE': 'roles',
                        'INSTRUCTION': 'instruction',
                        'DECISION': 'decisions',
                        'IMPACT': 'impact',
                        'COMPLEXITY': 'complexity'
                    };
                    const key = mapping[this.workingType];
                    return (this.catalogs && this.catalogs[key]) ? this.catalogs[key] : [];
                }
            },
            mounted() {
                const tag = document.getElementById('catalogs-data');
                if (tag) {
                    try {
                        this.catalogs = JSON.parse(tag.textContent);
                    } catch (e) {
                        console.error("Error catálogos:", e);
                    }
                }
                this.workingType = this.nextType;
            },
            methods: {
                openCreateModal() {
                    this.isEdit = false;
                    this.workingType = this.nextType;
                    this.resetForm();
                    this.showModal = true;
                    document.body.classList.add('no-scroll');
                },
                async editNode(id) {
                    if (!id) return;
                    this.loading = true;
                    try {
                        // Construir URL dinámica reemplazando el 0 del placeholder
                        const url = this.urlDetailBase.replace('0', id);
                        const res = await fetch(url);

                        if (!res.ok) throw new Error("Registro no encontrado");

                        const data = await res.json();
                        this.formData = {
                            id: data.id,
                            catalog_item_id: data.catalog_item_id || '',
                            name_extra: data.name_extra || '',
                            occupational_classification_id: data.occupational_classification_id || ''
                        };
                        this.workingType = data.node_type;
                        this.isEdit = true;
                        this.showModal = true;
                        document.body.classList.add('no-scroll');
                    } catch (e) {
                        window.Toast.fire({icon: 'error', title: 'Error al cargar los datos'});
                        console.error(e);
                    } finally {
                        this.loading = false;
                    }
                },
                closeModal() {
                    this.showModal = false;
                    document.body.classList.remove('no-scroll');
                },
                async saveNode() {
                    this.loading = true;
                    const payload = {...this.formData, parent_id: this.parentId, node_type: this.workingType};
                    try {
                        const res = await fetch(this.urlSave, {
                            method: 'POST',
                            headers: {'X-CSRFToken': getCsrfToken(), 'Content-Type': 'application/json'},
                            body: JSON.stringify(payload)
                        });
                        if (res.ok) {
                            window.Toast.fire({icon: 'success', title: 'Registro guardado'});
                            setTimeout(() => location.reload(), 800);
                        }
                    } finally {
                        this.loading = false;
                    }
                },
                resetForm() {
                    this.formData = {id: null, catalog_item_id: '', name_extra: '', occupational_classification_id: ''};
                }
            }
        }).mount('#valuationApp');
    }

    // =========================================================================
    // 2. WIZARD DE PERFILES (#profileFormApp)
    // =========================================================================
    const wizEl = document.getElementById('profileFormApp');
    if (wizEl) {
        createApp({
            delimiters: ['[[', ']]'],
            data() {
                return {
                    currentStep: 1, stepLabels: ['Estructura', 'Valoración', 'Actividades', 'Finalización'],
                    loading: false, isEdit: false,
                    formData: {
                        position_code: '', specific_job_title: '', administrative_unit: '',
                        occupational_classification: '', mission: '', knowledge_area: '', experience_details: ''
                    },
                    unitLevels: [], selectedUnits: [],
                    valuationLevels: [], selectedNodes: [], // Paso 2 Jerárquico
                    matchResult: null,
                    activities: [{action_verb: '', description: '', frequency: ''}],
                    catalogs: {instruction: [], decisions: [], impact: [], roles: [], verbs: [], frequency: []},
                    urls: {}
                }
            },
            async mounted() {
                this.urls = {
                    units: wizEl.dataset.urlUnits,
                    nextCode: wizEl.dataset.urlNextCode,
                    valuationNodes: wizEl.dataset.urlValuationNodes
                };
                const tag = document.getElementById('catalogs-data');
                if (tag) {
                    this.catalogs = JSON.parse(tag.textContent);
                }

                await this.fetchUnits(null, 0);
                await this.fetchValuationLevel(null);

                this.$nextTick(() => {
                    if (window.jQuery && $.fn.select2) {
                        this.initSelect2();
                        this.initSelect2Valuation();
                    }
                });
            },
            computed: {
                missionPreview() {
                    return (this.activities.length > 0 && this.activities[0].description)
                        ? `Sugerencia: Ejecutar procesos de ${this.activities[0].description}...`
                        : "Defina las actividades para generar la misión.";
                }
            },
            methods: {
                // --- UNIDADES PASO 1 ---
                async fetchUnits(parentId, index) {
                    const url = parentId ? `${this.urls.units}${parentId}/children/` : this.urls.units;
                    const res = await fetch(url);
                    const data = await res.json();
                    if (data.length > 0) {
                        this.unitLevels.push({options: data});
                        this.selectedUnits.push('');
                    }
                },
                async handleUnitChange(index) {
                    const id = this.selectedUnits[index];
                    this.unitLevels = this.unitLevels.slice(0, index + 1);
                    this.selectedUnits = this.selectedUnits.slice(0, index + 1);
                    if (id) {
                        await this.fetchUnits(id, index + 1);
                        this.formData.administrative_unit = id;
                        const codeRes = await fetch(this.urls.nextCode.replace('0', id));
                        const codeData = await codeRes.json();
                        this.formData.position_code = codeData.next_code;
                    }
                    this.$nextTick(() => this.initSelect2());
                },
                // --- VALORACIÓN PASO 2 ---
                async fetchValuationLevel(parentId) {
                    const url = parentId ? `${this.urls.valuationNodes}?parent=${parentId}` : this.urls.valuationNodes;
                    const res = await fetch(url);
                    const data = await res.json();
                    if (data.length > 0) {
                        this.valuationLevels.push({type: data[0].type, options: data});
                        this.selectedNodes.push('');
                    }
                },
                async handleNodeChange(index) {
                    const id = this.selectedNodes[index];
                    this.valuationLevels = this.valuationLevels.slice(0, index + 1);
                    this.selectedNodes = this.selectedNodes.slice(0, index + 1);
                    this.matchResult = null;
                    if (id) {
                        const sel = this.valuationLevels[index].options.find(n => n.id == id);
                        if (sel.type === 'RESULT') {
                            this.matchResult = sel.classification;
                            this.formData.occupational_classification = sel.id;
                        } else {
                            await this.fetchValuationLevel(id);
                        }
                    }
                    this.$nextTick(() => this.initSelect2Valuation());
                },
                // --- OTROS MÉTODOS ---
                getValuationLabel(type) {
                    const labels = {
                        'ROLE': '1. Rol',
                        'INSTRUCTION': '2. Instrucción',
                        'EXPERIENCE': '3. Experiencia',
                        'DECISION': '4. Decisiones',
                        'IMPACT': '5. Impacto',
                        'COMPLEXITY': '6. Complejidad',
                        'RESULT': '7. Resultado'
                    };
                    return labels[type] || 'Nivel';
                },
                getLevelLabel(index) {
                    return ['Nivel Institucional', 'Dirección', 'Jefatura', 'Unidad'][index] || 'Subnivel';
                },
                initSelect2() {
                    const self = this;
                    $('.select2-unit').select2({width: '100%'}).on('change', function () {
                        const idx = $(this).data('index');
                        self.selectedUnits[idx] = $(this).val();
                        self.handleUnitChange(idx);
                    });
                },
                initSelect2Valuation() {
                    const self = this;
                    $('.select2-valuation').select2({
                        width: '100%',
                        placeholder: 'Seleccione...'
                    }).on('change', function () {
                        const idx = $(this).data('index');
                        self.selectedNodes[idx] = $(this).val();
                        self.handleNodeChange(idx);
                    });
                },
                addActivity() {
                    this.activities.push({action_verb: '', description: '', frequency: ''});
                },
                removeActivity(idx) {
                    if (this.activities.length > 1) this.activities.splice(idx, 1);
                },
                async submitForm() {
                    this.loading = true;
                    window.Toast.fire({icon: 'success', title: 'Procesando Perfil...'});
                    // Aquí iría el fetch POST del formulario completo
                }
            }
        }).mount('#profileFormApp');
    }

    // =========================================================================
    // 3. COMPETENCIAS (#competencyApp)
    // =========================================================================
    const compEl = document.getElementById('competencyApp');
    if (compEl) {
        createApp({
            delimiters: ['[[', ']]'],
            data() {
                return {
                    loading: false, isEdit: false, showModal: false,
                    currentId: null, searchQuery: '', urls: {}, complexityLevels: [],
                    formData: {name: '', type: 'TECHNICAL', definition: '', suggested_level: ''}
                }
            },
            mounted() {
                this.urls = {
                    table: compEl.dataset.urlTable,
                    create: compEl.dataset.urlCreate,
                    updateBase: compEl.dataset.urlUpdateBase,
                    toggleBase: compEl.dataset.urlToggleBase
                };
                try {
                    this.complexityLevels = JSON.parse(compEl.dataset.levels || '[]');
                } catch (e) {
                    console.error("Error niveles:", e);
                }
            },
            methods: {
                async refreshTable() {
                    const res = await fetch(this.urls.table);
                    document.getElementById('table-content-wrapper').innerHTML = await res.text();
                },
                openModal(mode, data = null) {
                    this.isEdit = mode === 'edit';
                    if (this.isEdit && data) {
                        this.currentId = data.id;
                        this.formData = {...data};
                    } else {
                        this.formData = {name: '', type: 'TECHNICAL', definition: '', suggested_level: ''};
                    }
                    this.showModal = true;
                    document.body.classList.add('no-scroll');
                }
                // ... resto de lógica de competencias
            }
        }).mount('#competencyApp');
    }

    // =========================================================================
    // 4. LISTADO DE PERFILES (#profileApp)
    // =========================================================================
    const profListEl = document.getElementById('profileApp');
    if (profListEl) {
        createApp({
            delimiters: ['[[', ']]'],
            data() {
                return {searchQuery: '', timeout: null, urls: {}}
            },
            mounted() {
                this.urls = {table: profListEl.dataset.urlTable};
            },
            methods: {
                debounceSearch() {
                    clearTimeout(this.timeout);
                    this.timeout = setTimeout(() => this.fetchTable(), 500);
                },
                async fetchTable() {
                    const url = new URL(this.urls.table, window.location.origin);
                    url.searchParams.append('partial', '1');
                    if (this.searchQuery) url.searchParams.append('q', this.searchQuery);
                    const res = await fetch(url);
                    document.getElementById('tablePartialContainer').innerHTML = await res.text();
                }
            }
        }).mount('#profileApp');
    }
});