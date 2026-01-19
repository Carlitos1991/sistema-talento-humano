/* static/js/function_manual.js */

const {createApp} = Vue;

const getCsrfToken = () => document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';

document.addEventListener('DOMContentLoaded', () => {
    const matrixElement = document.getElementById('matrixApp');
    if (matrixElement) {
        createApp({
            delimiters: ['[[', ']]'],
            data() {
                return {
                    showModal: false, loading: false, isEdit: false,
                    catalogs: {roles: [], instruction: [], complexity: []},
                    formData: {
                        id: null,
                        occupational_group: '',
                        grade: '',
                        remuneration: '',
                        required_role_id: '',
                        complexity_level_id: '',
                        minimum_instruction_id: '',
                        minimum_experience_months: 0
                    }
                }
            },
            mounted() {
                const tag = document.getElementById('catalogs-data');
                if (tag) this.catalogs = JSON.parse(tag.textContent);
            },
            methods: {
                openCreateModal() {
                    this.isEdit = false;
                    this.resetForm();
                    this.showModal = true;
                    document.body.classList.add('no-scroll');
                },
                async editEntry(id) {
                    this.loading = true;
                    try {
                        const res = await fetch(`/function_manual/api/matrix/detail/${id}/`);
                        const data = await res.json();
                        this.formData = {...data}; // Cargamos toda la data en el form
                        this.isEdit = true
                        ;
                        this.showModal = true;
                        document.body.classList.add('no-scroll');
                    } catch (e) {
                        window.Toast.fire({icon: 'error', title: 'Error al cargar datos'});
                    } finally {
                        this.loading = false;
                    }
                },
                async toggleEntry(id, name, isActive) {
                    const actionName = isActive ? "Inactivar" : "Activar";
                    const confirmText = isActive ? "Sí, inactivar" : "Sí, activar";
                    const message = isActive
                        ? "El registro no aparecerá en la valoración, pero no se eliminará."
                        : "El registro volverá a estar disponible para su uso.";

                    const result = await Swal.fire({
                        title: `¿${actionName} ${name}?`,
                        text: message,
                        icon: isActive ? 'warning' : 'info',
                        showCancelButton: true,
                        customClass: {
                            confirmButton: isActive ? 'btn-swal-danger' : 'btn-swal-success'
                        },
                        confirmButtonText: confirmText
                    });

                    if (result.isConfirmed) {
                        const res = await fetch(`/function_manual/api/matrix/toggle/${id}/`, {
                            method: 'POST',
                            headers: {'X-CSRFToken': getCsrfToken()}
                        });
                        if (res.ok) {
                            window.Toast.fire({icon: 'success', title: 'Estado actualizado'});
                            location.reload();
                        }
                    }
                },
                async saveMatrix() {
                    this.loading = true;
                    try {
                        const res = await fetch(matrixElement.dataset.urlSave, {
                            method: 'POST',
                            headers: {'X-CSRFToken': getCsrfToken(), 'Content-Type': 'application/json'},
                            body: JSON.stringify(this.formData)
                        });
                        if (res.ok) {
                            window.Toast.fire({icon: 'success', title: 'Registro guardado'});
                            location.reload();
                        }
                    } finally {
                        this.loading = false;
                    }
                },
                closeModal() {
                    this.showModal = false;
                    document.body.classList.remove('no-scroll');
                },
                resetForm() {
                    this.formData = {
                        id: null,
                        occupational_group: '',
                        grade: '',
                        remuneration: '',
                        required_role_id: '',
                        complexity_level_id: '',
                        minimum_instruction_id: '',
                        minimum_experience_months: 0
                    };
                }
            }
        }).mount('#matrixApp');
    }
    // =========================================================================
    // 1. GESTIÓN DE ESCALAS / ESTRUCTURA (#valuationApp)
    // =========================================================================
    const valuationElement = document.getElementById('valuationApp');
    if (valuationElement) {
        createApp({
            delimiters: ['[[', ']]'],
            data() {
                return {
                    parentId: valuationElement.dataset.parentId || null,
                    nextType: valuationElement.dataset.nextType || 'ROLE',
                    nextLevelName: valuationElement.dataset.nextLevelName || 'Nivel',
                    urlSave: valuationElement.dataset.urlSave,
                    urlDetailBase: valuationElement.dataset.urlDetail.replace('/0/', '/'),
                    workingType: '',
                    showModal: false, isEdit: false, loading: false,
                    catalogs: {instruction: [], decisions: [], impact: [], roles: [], matrix: [], complexity: []},
                    formData: {id: null, catalog_item_id: '', name_extra: '', occupational_classification_id: ''}
                }
            },
            computed: {
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
                    return names[this.workingType] || 'Nivel';
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
                    if (!id) {
                        window.Toast.fire({icon: 'error', title: 'ID de registro no válido'});
                        return;
                    }
                    this.loading = true;
                    try {
                        // CONSTRUCCIÓN DE RUTA ABSOLUTA
                        const response = await fetch(`${this.urlDetailBase}${id}/`);
                        if (!response.ok) throw new Error("Registro no encontrado");

                        const data = await response.json();
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
                        console.error("Error Fetch:", e);
                        window.Toast.fire({icon: 'error', title: 'Error al obtener datos del servidor'});
                    } finally {
                        this.loading = false;
                    }
                },
                closeModal() {
                    this.showModal = false;
                    document.body.classList.remove('no-scroll');
                    this.resetForm();
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
                            location.reload();
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
                        occupational_classification: '', mission: '', knowledge_area: '', experience_details: '',
                        training_topic: '', interface_relations: ''
                    },
                    unitLevels: [], selectedUnits: [],
                    valuationLevels: [], selectedNodes: [], // Paso 2 Jerárquico
                    matchResult: null,
                    activities: [{action_verb: '', description: '', additional_knowledge: ''}],
                    catalogs: {instruction: [], decisions: [], impact: [], roles: [], verbs: [], frequency: [], competencies: []},
                    allCompetencies: [],
                    selectedTechnical: ['', '', ''],
                    selectedBehavioral: ['', '', ''],
                    selectedTransversal: ['', ''],
                    urls: {}
                }
            },
            async mounted() {
                this.urls = {
                    units: wizEl.dataset.urlUnits,
                    nextCode: wizEl.dataset.urlNextCode,
                    valuationNodes: wizEl.dataset.urlValuationNodes,
                    matrix: wizEl.dataset.urlMatrix,
                    cancel: wizEl.dataset.urlCancel
                };
                const tag = document.getElementById('catalogs-data');
                if (tag) {
                    this.catalogs = JSON.parse(tag.textContent);
                    if (this.catalogs.competencies) this.allCompetencies = this.catalogs.competencies;
                }

                await this.fetchUnits(null, 0);
                await this.fetchValuationLevel(null);

                // --- LOGICA DE EDICIÓN ---
                const initTag = document.getElementById('initial-data');
                if (initTag) {
                    try {
                        const initData = JSON.parse(initTag.textContent);
                        this.isEdit = true;
                        await this.loadInitialData(initData);
                    } catch (e) {
                        console.error("Error cargando datos iniciales:", e);
                    }
                }

                this.$nextTick(() => {
                    if (window.jQuery && $.fn.select2) {
                        this.initSelect2();
                        this.initSelect2Valuation();
                        this.initSelect2Competencies();
                    }
                });
            },
            computed: {
                technicalList() { return this.allCompetencies.filter(c => c.type === 'TECHNICAL'); },
                behavioralList() { return this.allCompetencies.filter(c => c.type === 'BEHAVIORAL'); },
                transversalList() { return this.allCompetencies.filter(c => c.type === 'TRANSVERSAL'); },

                filteredVerbs() {
                    // matchResult viene de lo que seleccionaste en el paso 2 (ej: {group: 'SP1', ...})
                    if (!this.matchResult || !this.matchResult.group) return [];
                    const currentSP = this.matchResult.group; // Ej: "SP1"
                    const currentGroup = this.matchResult.group; // Ejemplo: "SP1"

                    // Filtramos el catálogo de verbos que viene del servidor
                    return this.catalogs.verbs.filter(verb => {
                        // Si no tiene grupos definidos o es TODOS, se muestra
                        if (!verb.target_groups || verb.target_groups === 'TODOS') return true;

                        // Convertimos la cadena "SP1,SP2" en array y buscamos
                        const allowed = verb.target_groups.split(',').map(s => s.trim());
                        return allowed.includes(currentSP);
                    });
                },
                missionPreview() {
                    const firstAct = this.activities[0];
                    if (firstAct && firstAct.action_verb && firstAct.description && !this.formData.mission) {
                        const verbObj = this.catalogs.verbs.find(v => v.id == firstAct.action_verb);
                        const verbName = verbObj ? verbObj.name : '';
                        return `Sugerencia: ${verbName} ${firstAct.description.toLowerCase()}...`;
                    }
                    return "Complete las actividades para generar una sugerencia.";
                },
                firstUnitSelected() {
                    return this.selectedUnits && this.selectedUnits.length > 0 && !!this.selectedUnits[0];
                },
                hasBasicData() {
                     return this.firstUnitSelected && this.formData.specific_job_title;
                },
                isNextDisabled() {
                    if (this.currentStep === 1) return !this.hasBasicData;
                    if (this.currentStep === 2) return !this.formData.occupational_classification;
                    if (this.currentStep === 3) {
                        if (this.activities.length < 5) return true;
                        return !this.activities.every(a => a.action_verb && a.description && a.additional_knowledge);
                    }
                    return false;
                }
            },
            methods: {
                async loadInitialData(initData) {
                    // 1. Campos Básicos
                    this.formData = {
                        ...this.formData,
                        id: initData.id,
                        position_code: initData.position_code,
                        specific_job_title: initData.specific_job_title,
                        mission: initData.mission,
                        knowledge_area: initData.knowledge_area,
                        experience_details: initData.experience_details,
                        training_topic: initData.training_topic,
                        interface_relations: initData.interface_relations
                    };

                    // 2. Arrays de Complejidad/Competencias
                    this.activities = initData.activities && initData.activities.length ? initData.activities : [{action_verb: '', description: '', additional_knowledge: ''}];
                    if (initData.selectedTechnical) this.selectedTechnical = initData.selectedTechnical;
                    if (initData.selectedBehavioral) this.selectedBehavioral = initData.selectedBehavioral;
                    if (initData.selectedTransversal) this.selectedTransversal = initData.selectedTransversal;

                    // 3. Rehidratar Unidades (Paso 1)
                    // Reiniciamos para cargar en orden
                    this.unitLevels = [];
                    this.selectedUnits = [];
                    await this.fetchUnits(null, 0); // Carga Raíz

                    const units = initData.selectedUnits;
                    if (units && units.length > 0) {
                        for (let i = 0; i < units.length; i++) {
                            const unitId = units[i];
                            // El fetchUnits anterior ya pusheó el slot para este nivel
                            this.selectedUnits[i] = unitId;
                            
                            // Cargar hijos del seleccionado para preparar el siguiente nivel (o llenar las options)
                            await this.fetchUnits(unitId, i + 1);
                        }
                        // Setear la unidad final seleccionada
                        this.formData.administrative_unit = units[units.length - 1];
                    }

                    // 4. Rehidratar Valoración (Paso 2)
                    this.valuationLevels = [];
                    this.selectedNodes = [];
                    await this.fetchValuationLevel(null); // Carga Raíz

                    const nodes = initData.selectedNodes;
                    if (nodes && nodes.length > 0) {
                        for (let i = 0; i < nodes.length; i++) {
                            const nodeId = nodes[i];
                            this.selectedNodes[i] = nodeId;
                            await this.fetchValuationLevel(nodeId);
                        }
                    }

                    // 5. Match Result
                    if (initData.matchResult) {
                        this.matchResult = initData.matchResult;
                        this.formData.occupational_classification = initData.matchResult.id;
                    }
                },

                cancelProcess() {
                    window.location.href = this.urls.cancel || this.urls.matrix;
                },
                validateCurrentStep() {
                    if (this.currentStep === 1) {
                        if (!this.formData.administrative_unit || !this.formData.specific_job_title) {
                            window.Toast.fire({icon: 'warning', title: 'Complete la unidad y el cargo.'});
                            return false;
                        }
                    }
                    if (this.currentStep === 2) {
                        if (!this.formData.occupational_classification) {
                            window.Toast.fire({
                                icon: 'warning',
                                title: 'Debe completar la valoración hasta el nivel de Resultado.'
                            });
                            return false;
                        }
                    }
                    if (this.currentStep === 3) {
                        if (this.activities.length < 5) {
                            window.Toast.fire({icon: 'warning', title: 'Debe registrar al menos 5 actividades esenciales.'});
                            return false;
                        }
                        const allComplete = this.activities.every(a => a.action_verb && a.description && a.additional_knowledge);
                        if (!allComplete) {
                            window.Toast.fire({icon: 'warning', title: 'Todas las actividades deben tener verbo, descripción y conocimientos.'});
                            return false;
                        }
                    }
                    return true;
                },
                nextStep() {
                    if (this.validateCurrentStep()) {
                        if (this.currentStep === 3) this.generateMissionSuggestion();
                        this.currentStep++;
                    }
                },
                generateMissionSuggestion() {
                    // MDT-2025: Verbo + Objeto + Condición (Sugerencia)
                    const firstAct = this.activities[0];
                    if (firstAct && firstAct.action_verb && firstAct.description && !this.formData.mission) {
                        const verbText = this.catalogs.verbs.find(v => v.id == firstAct.action_verb)?.name || '';
                        this.formData.mission = `${verbText} ${firstAct.description.toLowerCase()} para asegurar el cumplimiento de los objetivos institucionales.`;
                    }
                },


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
                    this.formData.occupational_classification = ''; // Reset classification on change

                    if (id) {
                        const sel = this.valuationLevels[index].options.find(n => n.id == id);
                        if (sel.type === 'RESULT') {
                            this.matchResult = sel.classification;
                            this.formData.occupational_classification = sel.classification_id;
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
                    $('.select2-unit').select2({width: '100%'});
                    
                    $('.select2-unit').off('change.vue').on('change.vue', function () {
                        const idx = $(this).data('index');
                        const val = $(this).val();
                        if (self.selectedUnits[idx] !== val) {
                            self.selectedUnits[idx] = val;
                            self.handleUnitChange(idx);
                        }
                    });
                },
                initSelect2Valuation() {
                    const self = this;
                    $('.select2-valuation').select2({
                        width: '100%',
                        placeholder: 'Seleccione...'
                    });
                    
                    $('.select2-valuation').off('change.vue').on('change.vue', function () {
                        const idx = $(this).data('index');
                        const val = $(this).val();
                        // Solo procesar si el valor realmente cambió para evitar bucles
                        if (self.selectedNodes[idx] !== val) {
                            self.selectedNodes[idx] = val;
                            self.handleNodeChange(idx);
                        }
                    });
                },
                initSelect2Competencies() {
                    const self = this;
                    // Helper genérico para init select2
                    const setup = (cls, arrayRef) => {
                        $(cls).select2({width: '100%', placeholder: 'Seleccione...'})
                            .off('change.vue')
                            .on('change.vue', function() {
                                const idx = $(this).data('index');
                                const val = $(this).val();
                                if (arrayRef[idx] !== val) {
                                    arrayRef[idx] = val;
                                }
                            });
                    };
                    setup('.select2-comp-tech', this.selectedTechnical);
                    setup('.select2-comp-beh', this.selectedBehavioral);
                    setup('.select2-comp-trans', this.selectedTransversal);
                },
                addActivity() {
                    // Validar que la ultima actividad tenga datos completos antes de crear otra
                    if (this.activities.length > 0) {
                        const last = this.activities[this.activities.length - 1];
                        if (!last.action_verb || !last.description || !last.additional_knowledge) {
                            window.Toast.fire({
                                icon: 'warning',
                                title: 'Complete todos los campos de la actividad actual antes de agregar otra.'
                            });
                            return;
                        }
                    }
                    this.activities.push({action_verb: '', description: '', additional_knowledge: ''});
                },
                removeActivity(idx) {
                    if (this.activities.length > 1) this.activities.splice(idx, 1);
                },
                async submitForm() {
                    if (!this.validateCurrentStep()) return;

                    this.loading = true;
                    // Recopilar IDs de competencias (filtrando vacíos)
                    const competencies = [
                        ...this.selectedTechnical,
                        ...this.selectedBehavioral,
                        ...this.selectedTransversal
                    ].filter(id => id && id !== '');
                    
                    const payload = {
                        ...this.formData,
                        activities: this.activities,
                        competencies: competencies
                    };

                    try {
                        const res = await fetch(wizEl.dataset.urlSaveAction, { // Debes agregar este data-attr al HTML
                            method: 'POST',
                            headers: {
                                'X-CSRFToken': getCsrfToken(),
                                'Content-Type': 'application/json'
                            },
                            body: JSON.stringify(payload)
                        });
                        const data = await res.json();
                        if (data.success) {
                            Swal.fire('¡Éxito!', data.message, 'success').then(() => {
                                window.location.href = data.redirect;
                            });
                        } else {
                            throw new Error(data.error);
                        }
                    } catch (e) {
                        window.Toast.fire({icon: 'error', title: e.message});
                    } finally {
                        this.loading = false;
                    }
                },
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
                },
                closeModal() {
                    this.showModal = false;
                    document.body.classList.remove('no-scroll');
                    this.resetForm();
                },
                resetForm() {
                    this.isEdit = false;
                    this.formData = {id: null, name: '', type: 'TECHNICAL', definition: '', suggested_level: ''};
                    this.currentErrors = {};
                },
                async saveCompetency() {
                    this.loading = true;
                    this.currentErrors = {};
                    const url = this.isEdit
                        ? this.urls.update.replace('0', this.formData.id)
                        : this.urls.create;

                    try {
                        const res = await fetch(url, {
                            method: 'POST',
                            headers: {'X-CSRFToken': getCsrfToken(), 'Content-Type': 'application/json'},
                            body: JSON.stringify(this.formData)
                        });
                        const data = await res.json();

                        if (data.success) {
                            window.Toast.fire({icon: 'success', title: 'Guardado correctamente'});
                            this.closeModal();
                            this.fetchTable();
                        } else {
                            if (data.errors) {
                                this.currentErrors = data.errors;
                                window.Toast.fire({icon: 'error', title: 'Verifique los campos'});
                            } else {
                                throw new Error('Error desconocido');
                            }
                        }
                    } catch (e) {
                        window.Toast.fire({icon: 'error', title: 'Error al guardar'});
                    } finally {
                        this.loading = false;
                    }
                },
                async fetchTable() {
                    // Se recarga vía partial HTML o simplemente AJAX y se inyecta
                    const res = await fetch(this.urls.table);
                    const html = await res.text();
                    document.querySelector('#table-content-wrapper').innerHTML = html;
                },
                // Auxiliares para botones de tabla (ya que Vue no controla el HTML inyectado vía AJAX a menos que usemos componentes)
                // En este caso híbrido, onclick en HTML llama funciones globales o dispara eventos
                // Simplificación: recargar página si se prefiere
                reloadPage() {
                    location.reload();
                }

            },
            mounted() {
                // Leer configuración inicial
                if (compEl.dataset.levels) {
                    this.levels = JSON.parse(compEl.dataset.levels.replace(/'/g, '"'));
                }
                this.urls = {
                    table: compEl.dataset.urlTable,
                    create: compEl.dataset.urlCreate,
                    update: compEl.dataset.urlUpdateBase,
                    toggle: compEl.dataset.urlToggleBase
                };

                // Exponer app para llamadas externas desde el HTML inyectado (si fuera necesario)
                window.competencyApp = this;

                // Cargar tabla inicial
                this.fetchTable();
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

    // =========================================================================
    // 5. FUNCIONES GLOBALES: ASIGNAR EMPLEADO REFERENCIAL (Fuera de Vue)
    // =========================================================================

    window.openAssignReferentialModal = (pk) => {
        fetch(`/function_manual/profiles/assign-referential/${pk}/`)
            .then(res => res.text())
            .then(html => {
                const container = document.getElementById('modal-inject-container');
                if (container) {
                    container.innerHTML = html;
                    const overlay = container.querySelector('.modal-overlay');
                    if (overlay) overlay.style.display = 'flex';
                    document.body.classList.add('no-scroll');
                }
            });
    };

    window.closeManualModal = () => {
        const container = document.getElementById('modal-inject-container');
        if (container) {
            container.innerHTML = '';
            document.body.classList.remove('no-scroll');
        }
    };

    window.searchEmployeeReferential = async () => {
        const cedula = document.getElementById('search-cedula-ref').value;
        const resultCard = document.getElementById('search-result-card-ref'),
            btnSubmit = document.getElementById('btn-submit-assign-ref'),
            resName = document.getElementById('res-name-ref'),
            resEmail = document.getElementById('res-email-ref'),
            resPhoto = document.getElementById('res-photo-ref'),
            hiddenId = document.getElementById('selected-employee-id-ref');

        if (!cedula || cedula.length < 10) return Swal.fire('Error', 'Cédula no válida (mínimo 10 dígitos)', 'warning');

        // Estado de carga
        btnSubmit.disabled = true;
        resName.textContent = 'Buscando...';
        resultCard.classList.remove('hidden');

        try {
            const res = await fetch(`/function_manual/api/search-employee-simple/?q=${cedula}`);
            const data = await res.json();

            if (data.success) {
                const emp = data.data;
                resName.textContent = emp.full_name;
                resEmail.textContent = emp.email;
                
                // Foto
                const photoUrl = emp.photo ? emp.photo : '/static/img/avatar-placeholder.png';
                resPhoto.innerHTML = `<img src="${photoUrl}" style="width:100%; height:100%; object-fit:cover;">`;
                
                hiddenId.value = emp.id;
                
                btnSubmit.disabled = false;
                resultCard.classList.remove('hidden');
            } else {
                resName.textContent = 'No encontrado';
                resEmail.textContent = data.message;
                resPhoto.innerHTML = '<i class="fas fa-user-slash fa-lg text-muted"></i>';
                hiddenId.value = '';
                
                // Opcionalmente ocultar card o mostrar error style
                btnSubmit.disabled = true;
            }

        } catch (e) {
            console.error(e);
            resName.textContent = 'Error de conexión';
        }
    };

    window.submitAssignReferential = async (e, pk) => {
        e.preventDefault();
        const form = e.target;
        const btn = document.getElementById('btn-submit-assign-ref');
        
        // Bloqueo
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Guardando...';
        btn.disabled = true;

        try {
            const formData = new FormData(form);
            const res = await fetch(`/function_manual/profiles/assign-referential/${pk}/`, {
                method: 'POST',
                body: formData,
                headers: {'X-Requested-With': 'XMLHttpRequest'}
            });
            const data = await res.json();
            
            if (data.success) {
                Swal.fire({
                    icon: 'success',
                    title: '¡Asignado!',
                    text: data.message,
                    timer: 1500,
                    showConfirmButton: false
                }).then(() => {
                    location.reload();
                });
            } else {
                Swal.fire('Error', data.message, 'error');
                btn.innerHTML = '<i class="fas fa-save me-2"></i> Guardar Asignación';
                btn.disabled = false;
            }
        } catch (err) {
            console.error(err);
            Swal.fire('Error', 'Fallo de conexión', 'error');
            btn.innerHTML = '<i class="fas fa-save me-2"></i> Guardar Asignación';
            btn.disabled = false;
        }
    };

    // =========================================================================
    // LEGALIZACIÓN (FIRMAS)
    // =========================================================================

    window.openLegalizeModal = (pk) => {
        fetch(`/function_manual/profiles/legalize/${pk}/`)
            .then(res => res.text())
            .then(html => {
                const container = document.getElementById('modal-inject-container');
                if (container) {
                    container.innerHTML = html;
                    const overlay = container.querySelector('.modal-overlay');
                    if (overlay) {
                        // Forzamos estilos para garantizar overlay
                        overlay.style.position = 'fixed';
                        overlay.style.display = 'flex';
                        overlay.style.zIndex = '999999';
                    }
                    document.body.classList.add('no-scroll');
                    setTimeout(validateLegalizeSelects, 200);
                }
            });
    };

    window.validateLegalizeSelects = () => {
        const selects = document.querySelectorAll('.select-authority');
        const selectedValues = Array.from(selects).map(s => s.value).filter(v => v);

        selects.forEach(select => {
            const currentVal = select.value;
            Array.from(select.options).forEach(opt => {
                if (!opt.value) return; // Skip placeholder
                
                // Si el valor está en la lista de seleccionados y NO es el valor de este select
                if (selectedValues.includes(opt.value) && opt.value !== currentVal) {
                    opt.disabled = true;
                    opt.textContent = opt.textContent.replace(' (Seleccionado)', '') + ' (Seleccionado)';
                } else {
                    opt.disabled = false;
                    opt.textContent = opt.textContent.replace(' (Seleccionado)', '');
                }
            });
        });
    };

    window.submitLegalizeProfile = async (e, pk) => {
        e.preventDefault();
        const form = e.target;
        const btn = document.getElementById('btn-submit-legalize');
        
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Guardando...';
        btn.disabled = true;

        try {
            const formData = new FormData(form);
            const res = await fetch(`/function_manual/profiles/legalize/${pk}/`, {
                method: 'POST',
                body: formData,
                headers: {'X-Requested-With': 'XMLHttpRequest'}
            });
            const data = await res.json();
            
            if (data.success) {
                Swal.fire({
                    icon: 'success',
                    title: '¡Legalizado!',
                    text: data.message,
                    timer: 1500,
                    showConfirmButton: false
                }).then(() => {
                     window.closeManualModal();
                     location.reload();
                });
            } else {
                Swal.fire('Error', data.message, 'error');
                btn.innerHTML = '<i class="fas fa-save"></i> Guardar Legalización';
                btn.disabled = false;
            }

        } catch (e) {
            console.error(e);
            Swal.fire('Error', 'Fallo de conexión', 'error');
            btn.innerHTML = '<i class="fas fa-save"></i> Guardar Legalización';
            btn.disabled = false;
        }
    };

    // =========================================================================
    // SUBIDA Y DETALLE (LEGALIZADOS)
    // =========================================================================

    window.openUploadLegalizedModal = (pk) => {
        fetch(`/function_manual/profiles/upload-legalized/${pk}/`)
            .then(res => res.text())
            .then(html => {
                const container = document.getElementById('modal-inject-container');
                if (container) {
                    container.innerHTML = html;
                    const overlay = container.querySelector('.modal-overlay');
                    if (overlay) overlay.style.display = 'flex';
                    document.body.classList.add('no-scroll');
                }
            });
    };

    window.submitUploadLegalized = async (e, pk) => {
        e.preventDefault();
        const form = e.target;
        const btn = document.getElementById('btn-submit-upload');
        
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Subiendo...';
        btn.disabled = true;

        try {
            const formData = new FormData(form);
            const res = await fetch(`/function_manual/profiles/upload-legalized/${pk}/`, {
                method: 'POST',
                body: formData,
                headers: {'X-Requested-With': 'XMLHttpRequest'}
            });
            const data = await res.json();
            
            if (data.success) {
                Swal.fire({
                    icon: 'success',
                    title: '¡Subido!',
                    text: data.message,
                    timer: 1500,
                    showConfirmButton: false
                }).then(() => {
                     window.closeManualModal();
                     // Opcional: recargar solo fila o página
                     location.reload();
                });
            } else {
                Swal.fire('Error', data.message, 'error');
                btn.innerHTML = '<i class="fas fa-upload"></i> Subir Documento';
                btn.disabled = false;
            }

        } catch (e) {
            console.error(e);
            Swal.fire('Error', 'Fallo de conexión', 'error');
            btn.innerHTML = '<i class="fas fa-upload"></i> Subir Documento';
            btn.disabled = false;
        }
    };

    window.openProfileDetailModal = (pk) => {
        fetch(`/function_manual/profiles/detail/${pk}/`)
            .then(res => res.text())
            .then(html => {
                const container = document.getElementById('modal-inject-container');
                if (container) {
                    container.innerHTML = html;
                    const overlay = container.querySelector('.modal-overlay');
                    if (overlay) overlay.style.display = 'flex';
                    document.body.classList.add('no-scroll');
                }
            });
    };
});