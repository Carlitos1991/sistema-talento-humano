/**
 * SIGETH - MÓDULO MANUAL DE FUNCIONES (ESTANDARIZADO SIN VUE.JS)
 * Administra el Wizard de Perfiles, Valoración de Puestos, Actividades y Modales.
 */

// Utilidad CSRF compatible con el estándar main.js
const getCsrfToken = () => {
    return typeof getCSRF === 'function' ? getCSRF() : (document.querySelector('[name=csrfmiddlewaretoken]')?.value || '');
};

/* ==========================================================================
   1. WIZARD DE PERFILES DE PUESTOS (PASOS 1 A 4)
   ========================================================================== */
class JobProfileWizard {
    constructor(rootElement) {
        this.root = rootElement;
        this.urls = {
            units: this.root.dataset.urlUnits,
            nextCode: this.root.dataset.urlNextCode,
            valuationNodes: this.root.dataset.urlValuationNodes,
            matrix: this.root.dataset.urlMatrix,
            cancel: this.root.dataset.urlCancel,
            save: this.root.dataset.urlSaveAction
        };
        this.isEdit = this.root.dataset.isEdit === 'true';

        // Catálogos e inicialización
        this.catalogs = {
            instruction: [], decisions: [], impact: [], roles: [],
            verbs: [], frequency: [], complexity: [], matrix: [], competencies: []
        };
        this.allCompetencies = [];
        this.unitDeliverables = [];

        // Estado del formulario
        this.currentStep = 1;
        this.stepLabels = [
            'Estructura e Identificación',
            'Valoración Normativa',
            'Actividades Esenciales',
            'Definiciones y Competencias'
        ];

        this.selectedUnits = [];       // Array de IDs de unidades seleccionadas por nivel
        this.selectedNodes = [];       // Array de IDs de ValuationNode por nivel
        this.valuationLevels = [];     // Metadata de cada nivel de valoración cargado
        this.activities = [];          // Lista de objetos de actividades
        this.matchResult = null;       // Objeto de clasificación resultante

        this.selectedTechnical = ['', '', ''];
        this.selectedBehavioral = ['', '', ''];
        this.selectedTransversal = ['', ''];

        this.init();
    }

    async init() {
        // Cargar Catálogos desde Data Island
        const catTag = document.getElementById('catalogs-data');
        if (catTag) {
            try {
                this.catalogs = JSON.parse(catTag.textContent || '{}');
                this.allCompetencies = this.catalogs.competencies || [];
            } catch (e) {
                console.error("Error parseando catalogs-data:", e);
            }
        }

        this.bindEvents();
        this.renderStepNavigation();

        // Carga de Unidades Raíz y Niveles Iniciales de Valoración
        await this.fetchUnits(null, 0);
        await this.fetchValuationLevel(null, 0);

        // Si es edición, rehidratar
        const initTag = document.getElementById('initial-data');
        if (initTag) {
            try {
                const initData = JSON.parse(initTag.textContent || '{}');
                await this.loadInitialData(initData);
            } catch (e) {
                console.error("Error cargando datos de edición:", e);
            }
        } else {
            // Actividad inicial por defecto
            this.addActivity();
        }

        this.initCompetencySelects();
    }

    bindEvents() {
        // Navegación Stepper
        document.getElementById('btnWizardPrev')?.addEventListener('click', () => this.goToStep(this.currentStep - 1));
        document.getElementById('btnWizardNext')?.addEventListener('click', () => this.handleNextStep());
        document.getElementById('btnWizardCancel')?.addEventListener('click', () => {
            window.location.href = this.urls.cancel || '/function_manual/profiles/';
        });
        document.getElementById('btnWizardSave')?.addEventListener('click', () => this.handleFinalizeClick());

        // Botón agregar actividad
        document.getElementById('btnAddActivity')?.addEventListener('click', () => this.addActivity());

        // Eventos Popups de Información paso 4
        document.querySelectorAll('.btn-info-icon').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const key = btn.dataset.infoKey || btn.closest('label')?.textContent.trim();
                this.openInfoPopup(key);
            });
        });
    }

    // --- MANEJO DE PASOS ---
    goToStep(stepNumber) {
        if (stepNumber < 1 || stepNumber > 4) return;
        this.currentStep = stepNumber;

        // Alternar visualización de pasos
        document.querySelectorAll('.wizard-step-content').forEach(sec => {
            const stepId = parseInt(sec.dataset.stepContent, 10);
            if (stepId === this.currentStep) {
                sec.classList.remove('hidden');
            } else {
                sec.classList.add('hidden');
            }
        });

        // Actualizar Stepper Header
        document.querySelectorAll('.wizard-stepper .step-item').forEach(item => {
            const step = parseInt(item.dataset.step, 10);
            item.classList.remove('active', 'completed');
            if (step === this.currentStep) {
                item.classList.add('active');
            } else if (step < this.currentStep) {
                item.classList.add('completed');
            }
        });

        const subtitle = document.getElementById('wizardSubtitle');
        if (subtitle) {
            subtitle.textContent = `Paso ${this.currentStep}: ${this.stepLabels[this.currentStep - 1]}`;
        }

        this.renderStepNavigation();

        // Acciones específicas al entrar a un paso
        if (this.currentStep === 3) {
            this.refreshActivitiesSelect2();
        } else if (this.currentStep === 4) {
            this.generateMissionSuggestion();
            this.autofillStep4();
            this.initCompetencySelects();
        }

        window.scrollTo({top: 0, behavior: 'smooth'});
    }

    renderStepNavigation() {
        const btnPrev = document.getElementById('btnWizardPrev');
        const btnNext = document.getElementById('btnWizardNext');
        const btnSave = document.getElementById('btnWizardSave');

        if (btnPrev) btnPrev.classList.toggle('hidden', this.currentStep === 1);
        if (btnNext) btnNext.classList.toggle('hidden', this.currentStep === 4);
        if (btnSave) btnSave.classList.toggle('hidden', this.currentStep !== 4);
    }

    validateCurrentStep() {
        if (this.currentStep === 1) {
            const adminUnit = this.selectedUnits.filter(Boolean).pop();
            if (!adminUnit) {
                if (typeof showToast === 'function') {
                    showToast('Seleccione la unidad organizacional completa.', 'warning');
                } else {
                    Swal.fire({icon: 'warning', title: 'Atención', text: 'Seleccione la unidad organizacional.'});
                }
                return false;
            }
            return true;
        }

        if (this.currentStep === 2) {
            const validNodes = this.selectedNodes.filter(Boolean);
            if (validNodes.length < 6) {
                Swal.fire({
                    icon: 'warning',
                    title: 'Valoración incompleta',
                    text: 'Debe completar los 6 niveles de valoración normativa.'
                });
                return false;
            }
            return true;
        }

        if (this.currentStep === 3) {
            if (this.activities.length < 10) {
                Swal.fire({
                    icon: 'warning',
                    title: 'Actividades insuficientes',
                    text: 'El manual normativo exige describir al menos 10 actividades esenciales.'
                });
                return false;
            }

            for (let i = 0; i < this.activities.length; i++) {
                const act = this.activities[i];
                if (!act.action_verb || !act.description || !act.complexity || !act.contribution || !act.frequency) {
                    Swal.fire({
                        icon: 'warning',
                        title: 'Actividad Incompleta',
                        text: `Por favor complete todos los campos obligatorios en la actividad #${i + 1}.`
                    });
                    return false;
                }
            }
            return true;
        }

        return true;
    }

    handleNextStep() {
        if (this.validateCurrentStep()) {
            this.goToStep(this.currentStep + 1);
        }
    }

    // --- PASO 1: UNIDADES ORGANIZACIONALES ---
    async fetchUnits(parentId, index) {
        const url = parentId ? `${this.urls.units}${parentId}/children/` : this.urls.units;
        try {
            const res = await fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}});
            const data = await res.json();
            if (data && data.length > 0) {
                this.renderUnitSelect(index, data);
            }
        } catch (e) {
            console.error("Error consultando unidades:", e);
        }
    }

    renderUnitSelect(index, options) {
        const container = document.getElementById('unitLevelsContainer');
        if (!container) return;

        // Remover selectores de nivel superior a 'index'
        const existingBoxes = container.querySelectorAll('.unit-level-box');
        for (let i = index; i < existingBoxes.length; i++) {
            existingBoxes[i].remove();
        }

        const labels = ['Nivel Institucional', 'Dirección / Gerencia', 'Jefatura / Departamento', 'Unidad / Coordinación'];
        const labelText = labels[index] || `Subnivel ${index + 1}`;

        const box = document.createElement('div');
        box.className = 'unit-level-box';
        box.dataset.level = index;

        box.innerHTML = `
            <label class="form-label">${labelText}</label>
            <select class="form-control select2-unit" data-index="${index}">
                <option value="">Seleccione una opción...</option>
                ${options.map(u => `<option value="${u.id}">${u.name}</option>`).join('')}
            </select>
        `;

        container.appendChild(box);

        const $select = $(box).find('select');
        $select.select2({width: '100%', placeholder: 'Seleccione opción...'});

        $select.on('change', async (e) => {
            const selectedVal = e.target.value;
            this.selectedUnits = this.selectedUnits.slice(0, index);
            if (selectedVal) {
                this.selectedUnits[index] = selectedVal;
            }

            // Limpiar cajas de niveles posteriores en DOM
            const allBoxes = container.querySelectorAll('.unit-level-box');
            for (let i = index + 1; i < allBoxes.length; i++) {
                allBoxes[i].remove();
            }

            const currentAdminUnit = this.selectedUnits.filter(Boolean).pop();
            if (currentAdminUnit) {
                await this.fetchUnitDeliverables(currentAdminUnit);
                await this.fetchNextCode(currentAdminUnit);
                if (selectedVal) {
                    await this.fetchUnits(selectedVal, index + 1);
                }
            } else {
                document.getElementById('position_code').value = '';
                this.unitDeliverables = [];
            }
        });
    }

    async fetchUnitDeliverables(unitId) {
        try {
            const res = await fetch(`/institution/api/units/${unitId}/deliverables/`, {
                headers: {'X-Requested-With': 'XMLHttpRequest'}
            });
            const data = await res.json();
            this.unitDeliverables = data.success ? data.data : (Array.isArray(data) ? data : []);
            this.refreshActivitiesSelect2();
        } catch (e) {
            console.error("Error obteniendo entregables de unidad:", e);
            this.unitDeliverables = [];
        }
    }

    async fetchNextCode(unitId) {
        try {
            const res = await fetch(this.urls.nextCode.replace('0', unitId));
            const data = await res.json();
            const input = document.getElementById('position_code');
            if (input && data.next_code) {
                input.value = data.next_code;
            }
        } catch (e) {
            console.error("Error obteniendo código posicional:", e);
        }
    }

    // --- PASO 2: VALORACIÓN NORMATIVA ---
    getValuationLabel(type) {
        const labels = {
            'ROLE': '1. Rol de Puesto',
            'INSTRUCTION': '2. Instrucción Formal',
            'EXPERIENCE': '3. Experiencia Requerida',
            'DECISION': '4. Toma de Decisiones',
            'IMPACT': '5. Impacto Institucional',
            'COMPLEXITY': '6. Nivel de Complejidad',
            'RESULT': '7. Resultado / Grupo Ocupacional',
            'GENERIC_DENOMINATION': '8. Denominación Genérica'
        };
        return labels[type] || 'Nivel de Valoración';
    }

    async fetchValuationLevel(parentId, index) {
        const url = parentId ? `${this.urls.valuationNodes}?parent=${parentId}` : this.urls.valuationNodes;
        try {
            const res = await fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}});
            const data = await res.json();

            if (data && data.length > 0) {
                this.valuationLevels[index] = {type: data[0].type, options: data};
                this.renderValuationSelect(index, data[0].type, data);
            }
        } catch (e) {
            console.error("Error consultando nodos de valoración:", e);
        }
    }

    renderValuationSelect(index, type, options) {
        if (type === 'RESULT' || type === 'GENERIC_DENOMINATION') {
            return;
        }

        const container = document.getElementById('valuationLevelsContainer');
        if (!container) return;

        // Limpiar niveles superiores
        const existingBoxes = container.querySelectorAll('.valuation-node-box');
        for (let i = index; i < existingBoxes.length; i++) {
            existingBoxes[i].remove();
        }

        const box = document.createElement('div');
        box.className = 'valuation-node-box';
        box.dataset.level = index;

        box.innerHTML = `
            <label class="form-label">${this.getValuationLabel(type)}</label>
            <select class="form-control select2-valuation" data-index="${index}">
                <option value="">Seleccione una opción...</option>
                ${options.map(n => `<option value="${n.id}">${n.name}</option>`).join('')}
            </select>
        `;

        container.appendChild(box);

        const $select = $(box).find('select');
        $select.select2({width: '100%', placeholder: 'Seleccione opción...'});

        $select.on('change', async (e) => {
            const selectedVal = e.target.value;
            this.selectedNodes = this.selectedNodes.slice(0, index);

            // Eliminar selects posteriores del DOM
            const allBoxes = container.querySelectorAll('.valuation-node-box');
            for (let i = index + 1; i < allBoxes.length; i++) {
                allBoxes[i].remove();
            }

            this.hideMatchResult();

            if (selectedVal) {
                this.selectedNodes[index] = selectedVal;

                // Nivel 6 (Complejidad) es el último antes de RESULT
                if (index === 5) {
                    await this.fetchResultNodes(selectedVal);
                } else {
                    await this.fetchValuationLevel(selectedVal, index + 1);
                }
            }
        });
    }

    async fetchResultNodes(complexityNodeId) {
        try {
            const url = `${this.urls.valuationNodes}?parent=${complexityNodeId}`;
            const res = await fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}});
            const resultNodes = await res.json();

            const results = resultNodes.filter(n => n.type === 'RESULT' || n.node_type === 'RESULT');
            if (results.length > 0) {
                const resultNode = results[0];
                this.selectedNodes[6] = resultNode.id;

                if (resultNode.classification) {
                    this.showMatchResult(resultNode.classification);
                }

                // Buscar nietos para Denominación Genérica
                const gRes = await fetch(`${this.urls.valuationNodes}?parent=${resultNode.id}`);
                const grandchildren = await gRes.json();
                const genericNodes = grandchildren.filter(n => n.type === 'GENERIC_DENOMINATION' || n.node_type === 'GENERIC_DENOMINATION');
                if (genericNodes.length > 0) {
                    this.selectedNodes[7] = genericNodes[0].id;
                }
            }
        } catch (e) {
            console.error("Error obteniendo nodo resultado:", e);
        }
    }

    showMatchResult(classification) {
        this.matchResult = classification;
        const banner = document.getElementById('classificationResultBanner');
        if (banner) {
            document.getElementById('matchGroupName').textContent = classification.group || '---';
            document.getElementById('matchGradeText').textContent = `GRADO ESCALA: ${classification.grade || '---'}`;
            document.getElementById('matchRmuText').textContent = `$${classification.rmu || '0.00'}`;
            banner.classList.remove('hidden');
        }
    }

    hideMatchResult() {
        this.matchResult = null;
        const banner = document.getElementById('classificationResultBanner');
        if (banner) banner.classList.add('hidden');
    }

    // --- PASO 3: ACTIVIDADES ESENCIALES ---
    getFilteredVerbs() {
        const roleNodeId = this.selectedNodes[0];
        if (!roleNodeId) return this.catalogs.verbs;
        return this.catalogs.verbs.filter(v => !v.target_role || v.target_role == roleNodeId);
    }

    addActivity(data = null) {
        const activity = data || {
            action_verb: '',
            deliverables: [],
            description: '',
            additional_knowledge: '',
            complexity: '',
            contribution: '',
            frequency: '',
            points: 0
        };

        this.activities.unshift(activity);
        this.renderActivitiesTable();
    }

    renderActivitiesTable() {
        const tbody = document.getElementById('activitiesTableBody');
        if (!tbody) return;

        // Limpiar Select2 existentes antes de renderizar
        $(tbody).find('select').each(function () {
            if ($(this).hasClass('select2-hidden-accessible')) {
                $(this).select2('destroy');
            }
        });

        tbody.innerHTML = '';

        const verbs = this.getFilteredVerbs();
        const frequencies = (this.catalogs.frequency || []).filter(f => !f.name.toUpperCase().includes('MENSUAL'));

        this.activities.forEach((act, idx) => {
            const tr = document.createElement('tr');
            tr.className = 'row-animated';
            tr.dataset.index = idx;

            tr.innerHTML = `
                <td>
                    <select class="select2-act mb-1 select-verb" data-index="${idx}" data-field="action_verb">
                        <option value="">Seleccione Verbo...</option>
                        ${verbs.map(v => `<option value="${v.id}" ${act.action_verb == v.id ? 'selected' : ''}>${v.name}</option>`).join('')}
                    </select>
                    <select class="select2-act select-deliverables" data-index="${idx}" data-field="deliverables" multiple="multiple">
                        ${this.unitDeliverables.map(d => `<option value="${d.id}" ${(act.deliverables || []).includes(d.id) ? 'selected' : ''}>${d.name}</option>`).join('')}
                    </select>
                </td>
                <td>
                    <textarea class="form-textarea-inline input-desc" data-index="${idx}" placeholder="¿Qué hace? + ¿Sobre qué?...">${act.description || ''}</textarea>
                </td>
                <td>
                    <select class="select2-act mb-1 select-complexity" data-index="${idx}" data-field="complexity">
                        <option value="">Complejidad (C)...</option>
                        ${(this.catalogs.complexity || []).map(c => `<option value="${c.id}" ${act.complexity == c.id ? 'selected' : ''}>${c.name}</option>`).join('')}
                    </select>
                    <select class="select2-act mb-1 select-contribution" data-index="${idx}" data-field="contribution">
                        <option value="">Aporte Gestión (AG)...</option>
                        ${(this.catalogs.complexity || []).map(c => `<option value="${c.id}" ${act.contribution == c.id ? 'selected' : ''}>${c.name}</option>`).join('')}
                    </select>
                    <select class="select2-act select-frequency" data-index="${idx}" data-field="frequency">
                        <option value="">Frecuencia (F)...</option>
                        ${frequencies.map(f => `<option value="${f.id}" ${act.frequency == f.id ? 'selected' : ''}>${f.name}</option>`).join('')}
                    </select>
                </td>
                <td>
                    <textarea class="form-textarea-inline input-knowledge" data-index="${idx}" placeholder="Conocimientos adicionales...">${act.additional_knowledge || ''}</textarea>
                </td>
                <td class="cell-actions text-center">
                    <div class="actions-col">
                        <button type="button" class="btn-clone-icon" data-index="${idx}" title="Clonar actividad">
                            <i class="fa-solid fa-clone"></i>
                        </button>
                        <button type="button" class="btn-delete-icon" data-index="${idx}" title="Eliminar actividad">
                            <i class="fa-solid fa-trash-can"></i>
                        </button>
                    </div>
                </td>
            `;

            tbody.appendChild(tr);
        });

        this.bindActivityRowEvents();
        this.refreshActivitiesSelect2();
    }

    bindActivityRowEvents() {
        const tbody = document.getElementById('activitiesTableBody');
        if (!tbody) return;

        // Textareas sync
        tbody.querySelectorAll('.input-desc').forEach(textarea => {
            textarea.addEventListener('input', (e) => {
                const idx = parseInt(e.target.dataset.index, 10);
                this.activities[idx].description = e.target.value;
            });
        });

        tbody.querySelectorAll('.input-knowledge').forEach(textarea => {
            textarea.addEventListener('input', (e) => {
                const idx = parseInt(e.target.dataset.index, 10);
                this.activities[idx].additional_knowledge = e.target.value;
            });
        });

        // Botones Clonar y Eliminar
        tbody.querySelectorAll('.btn-clone-icon').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const idx = parseInt(btn.dataset.index, 10);
                this.cloneActivity(idx);
            });
        });

        tbody.querySelectorAll('.btn-delete-icon').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const idx = parseInt(btn.dataset.index, 10);
                this.removeActivity(idx);
            });
        });
    }

    refreshActivitiesSelect2() {
        const self = this;
        $('.select2-act').each(function () {
            const $el = $(this);
            const idx = parseInt($el.data('index'), 10);
            const field = $el.data('field');

            if ($el.hasClass('select2-hidden-accessible')) {
                $el.select2('destroy');
            }

            $el.select2({
                width: '100%',
                placeholder: field === 'deliverables' ? 'Productos/Servicios...' : 'Seleccione...'
            }).off('change.act').on('change.act', function () {
                const val = $(this).val();
                if (self.activities[idx]) {
                    self.activities[idx][field] = val;
                    if (['complexity', 'contribution', 'frequency'].includes(field)) {
                        self.activities[idx].points = self.calculateActivityPoints(self.activities[idx]);
                    }
                }
            });
        });
    }

    calculateActivityPoints(act) {
        if (!act.complexity || !act.contribution || !act.frequency) return 0;

        const getItemName = (id, list) => {
            const item = (list || []).find(i => i.id == id);
            return item ? item.name.toUpperCase() : '';
        };

        const nameC = getItemName(act.complexity, this.catalogs.complexity);
        const nameAG = getItemName(act.contribution, this.catalogs.complexity);
        const nameF = getItemName(act.frequency, this.catalogs.frequency);

        const mapVal = (name) => {
            if (name.includes('ALTO')) return 3;
            if (name.includes('MEDIO')) return 2;
            if (name.includes('BAJO')) return 1;
            return 0;
        };

        const mapFreq = (name) => {
            if (name.includes('DIARIO')) return 5;
            if (name.includes('SEMANAL')) return 4;
            if (name.includes('MENSUAL')) return 3;
            if (name.includes('SEMESTRAL') || name.includes('TRIMESTRAL')) return 2;
            if (name.includes('ANUAL')) return 1;
            return 0;
        };

        return mapVal(nameAG) * (mapFreq(nameF) + mapVal(nameC));
    }

    cloneActivity(idx) {
        const original = this.activities[idx];
        if (!original) return;

        const copy = {
            action_verb: original.action_verb || '',
            deliverables: [...(original.deliverables || [])],
            description: original.description || '',
            additional_knowledge: original.additional_knowledge || '',
            complexity: original.complexity || '',
            contribution: original.contribution || '',
            frequency: original.frequency || '',
            points: original.points || 0
        };

        this.activities.splice(idx + 1, 0, copy);
        this.renderActivitiesTable();
    }

    removeActivity(idx) {
        if (this.activities.length <= 1) {
            Swal.fire({icon: 'info', title: 'Atención', text: 'El perfil debe contener al menos una actividad.'});
            return;
        }

        Swal.fire({
            title: '¿Eliminar actividad?',
            text: 'Esta acción removerá la actividad de la lista.',
            icon: 'warning',
            showCancelButton: true,
            confirmButtonText: 'Sí, eliminar',
            cancelButtonText: 'Cancelar'
        }).then(res => {
            if (res.isConfirmed) {
                this.activities.splice(idx, 1);
                this.renderActivitiesTable();
            }
        });
    }

    // --- PASO 4: COMPLETAR PERFIL & COMPETENCIAS ---
    generateMissionSuggestion() {
        const missionEl = document.getElementById('mission');
        const hintEl = document.getElementById('missionHint');
        const firstAct = this.activities[0];

        if (firstAct && firstAct.action_verb && firstAct.description) {
            const verbObj = (this.catalogs.verbs || []).find(v => v.id == firstAct.action_verb);
            const verbName = verbObj ? verbObj.name : '';
            const suggestion = `${verbName} ${firstAct.description.toLowerCase()} para garantizar el cumplimiento de metas y objetivos institucionales.`;

            if (hintEl) hintEl.textContent = `Sugerencia: ${suggestion}`;
            if (missionEl && !missionEl.value.trim()) {
                missionEl.value = suggestion;
            }
        }
    }

    autofillStep4() {
        const instrNodeId = this.selectedNodes[1];
        const expNodeId = this.selectedNodes[2];

        const knowledgeAreaEl = document.getElementById('knowledge_area');
        const experienceDetailsEl = document.getElementById('experience_details');

        if (instrNodeId) {
            const instrLevel = this.valuationLevels[1];
            const node = instrLevel?.options?.find(o => o.id == instrNodeId);
            if (node) {
                const hint = document.getElementById('instructionHint');
                if (hint) hint.textContent = `Instrucción seleccionada: ${node.name}`;
                if (node.name.toLowerCase().includes('bachiller') && knowledgeAreaEl && !knowledgeAreaEl.value.trim()) {
                    knowledgeAreaEl.value = 'Bachillerato';
                }
            }
        }

        if (expNodeId) {
            const expLevel = this.valuationLevels[2];
            const node = expLevel?.options?.find(o => o.id == expNodeId);
            if (node) {
                const hint = document.getElementById('experienceHint');
                if (hint) hint.textContent = `Experiencia seleccionada: ${node.name}`;
                if (node.name.toLowerCase().includes('no requerida') && experienceDetailsEl && !experienceDetailsEl.value.trim()) {
                    experienceDetailsEl.value = 'No requerida';
                }
            }
        }
    }

    initCompetencySelects() {
        const setup = (selector, valuesArray, type) => {
            const list = this.allCompetencies.filter(c => c.type === type);
            $(selector).each((idx, el) => {
                const $el = $(el);
                const currentVal = valuesArray[idx];

                if ($el.hasClass('select2-hidden-accessible')) {
                    $el.select2('destroy');
                }

                $el.empty().append('<option value="">Seleccione...</option>');
                list.forEach(item => {
                    const isSelected = currentVal == item.id;
                    $el.append(new Option(item.name, item.id, isSelected, isSelected));
                });

                $el.select2({width: '100%', placeholder: 'Seleccione competencia...'})
                    .off('change.comp')
                    .on('change.comp', function () {
                        valuesArray[idx] = $(this).val();
                    });
            });
        };

        setup('.select2-comp-tech', this.selectedTechnical, 'TECHNICAL');
        setup('.select2-comp-beh', this.selectedBehavioral, 'BEHAVIORAL');
        setup('.select2-comp-trans', this.selectedTransversal, 'TRANSVERSAL');
    }

    openInfoPopup(labelName) {
        const messages = {
            'Misión del Puesto': 'La misión se define de las actividades asignadas al puesto, en función del portafolio de productos y/o servicios de las unidades y los procesos.',
            'Área de Conocimiento': 'Conjunto de conocimientos requeridos para el desempeño del puesto, adquiridos a través de estudios formales; competencia necesaria para que el servidor se desempeñe eficientemente en el puesto.',
            'Especificidad de la Experiencia': 'Se refiere al nivel de experticia necesaria para el desarrollo eficiente de las actividades asignadas al puesto, para el logro de los productos y/o servicios en los que interviene el mismo.',
            'Relaciones Internas/Externas': 'Relación que tiene el cargo con las unidades administrativas internas o externas de la institución, así como con entidades u organismos del sector público o privado.',
            'Temática de Capacitación': 'Temáticas de capacitaciones inherentes al cargo o unidad administrativa, orientadas al fortalecimiento de las competencias requeridas.'
        };

        const msg = messages[labelName] || `Definición correspondiente a ${labelName}.`;

        Swal.fire({
            title: labelName,
            text: msg,
            icon: 'info',
            confirmButtonText: 'Entendido'
        });
    }

    // --- REHIDRATACIÓN DE EDICIÓN ---
    async loadInitialData(initData) {
        // Asignar campos de texto
        ['position_code', 'mission', 'knowledge_area', 'experience_details', 'training_topic', 'interface_relations'].forEach(field => {
            const el = document.getElementById(field);
            if (el && initData[field]) el.value = initData[field];
        });

        // Rehidratar Unidades Paso 1
        if (initData.selectedUnits && initData.selectedUnits.length > 0) {
            for (let i = 0; i < initData.selectedUnits.length; i++) {
                const uId = initData.selectedUnits[i];
                this.selectedUnits[i] = uId;
                const select = document.querySelector(`.select2-unit[data-index="${i}"]`);
                if (select) $(select).val(uId).trigger('change');
                await this.fetchUnits(uId, i + 1);
            }
            const lastUnit = initData.selectedUnits[initData.selectedUnits.length - 1];
            await this.fetchUnitDeliverables(lastUnit);
        }

        // Rehidratar Valoración Paso 2
        if (initData.selectedNodes && initData.selectedNodes.length > 0) {
            for (let i = 0; i < initData.selectedNodes.length; i++) {
                const nId = initData.selectedNodes[i];
                this.selectedNodes[i] = nId;
                const select = document.querySelector(`.select2-valuation[data-index="${i}"]`);
                if (select) $(select).val(nId).trigger('change');
                await this.fetchValuationLevel(nId, i + 1);
            }
        }

        if (initData.matchResult) {
            this.showMatchResult(initData.matchResult);
        }

        // Rehidratar Actividades Paso 3
        if (initData.activities && initData.activities.length > 0) {
            this.activities = initData.activities.map(a => ({
                action_verb: a.action_verb || '',
                deliverables: a.deliverables || [],
                description: a.description || '',
                additional_knowledge: a.additional_knowledge || '',
                complexity: a.complexity || '',
                contribution: a.contribution || '',
                frequency: a.frequency || '',
                points: a.points || 0
            }));
            this.renderActivitiesTable();
        }

        // Rehidratar Competencias Paso 4
        if (initData.selectedTechnical) this.selectedTechnical = [...initData.selectedTechnical];
        if (initData.selectedBehavioral) this.selectedBehavioral = [...initData.selectedBehavioral];
        if (initData.selectedTransversal) this.selectedTransversal = [...initData.selectedTransversal];
        this.initCompetencySelects();
    }

    // --- GUARDADO FINAL ---
    handleFinalizeClick() {
        if (!this.validateCurrentStep()) return;

        Swal.fire({
            title: 'Confirmación de Información',
            html: `
                <div style="text-align: left; padding: 5px 10px;">
                    <label style="display: flex; align-items: center; gap: 10px; cursor: pointer; font-size: 0.92rem;">
                        <input type="checkbox" id="swalAcceptanceCheck" style="width: 18px; height: 18px; accent-color: #059669;">
                        <span>Declaro que la información ingresada es veraz y responde a las necesidades del puesto.</span>
                    </label>
                </div>
            `,
            icon: 'warning',
            showCancelButton: true,
            confirmButtonText: '<i class="fas fa-floppy-disk me-1"></i> Sí, Guardar Perfil',
            cancelButtonText: 'Cancelar',
            customClass: {
                confirmButton: 'swal2-confirm btn-swal-success',
                cancelButton: 'swal2-cancel btn-swal-cancel'
            },
            didOpen: () => {
                const confirmBtn = Swal.getConfirmButton();
                const checkbox = document.getElementById('swalAcceptanceCheck');
                if (confirmBtn && checkbox) {
                    confirmBtn.disabled = true;
                    checkbox.addEventListener('change', () => {
                        confirmBtn.disabled = !checkbox.checked;
                    });
                }
            }
        }).then((res) => {
            if (res.isConfirmed) {
                this.submitForm();
            }
        });
    }

    async submitForm() {
        const saveBtn = document.getElementById('btnWizardSave');
        if (saveBtn) {
            saveBtn.disabled = true;
            saveBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Guardando...';
        }

        const competencies = [
            ...this.selectedTechnical,
            ...this.selectedBehavioral,
            ...this.selectedTransversal
        ].filter(Boolean);

        const payload = {
            id: document.querySelector('#initial-data') ? JSON.parse(document.querySelector('#initial-data').textContent).id : null,
            position_code: document.getElementById('position_code')?.value || '',
            administrative_unit: this.selectedUnits.filter(Boolean).pop(),
            mission: document.getElementById('mission')?.value || '',
            knowledge_area: document.getElementById('knowledge_area')?.value || '',
            experience_details: document.getElementById('experience_details')?.value || '',
            training_topic: document.getElementById('training_topic')?.value || '',
            interface_relations: document.getElementById('interface_relations')?.value || '',
            role_node_id: this.selectedNodes[0] || null,
            instruction_node_id: this.selectedNodes[1] || null,
            experience_node_id: this.selectedNodes[2] || null,
            decision_node_id: this.selectedNodes[3] || null,
            impact_node_id: this.selectedNodes[4] || null,
            complexity_node_id: this.selectedNodes[5] || null,
            result_node_id: this.selectedNodes[6] || null,
            selected_generic_node_id: this.selectedNodes[7] || null,
            selectedNodes: this.selectedNodes,
            activities: this.activities,
            competencies: competencies
        };

        try {
            const response = await fetch(this.urls.save, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken(),
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify(payload)
            });

            const data = await response.json();

            if (response.ok && data.success) {
                if (typeof showToast === 'function') {
                    showToast(data.message || 'Perfil guardado con éxito.', 'success');
                }
                setTimeout(() => {
                    window.location.href = data.redirect || this.urls.cancel;
                }, 800);
            } else {
                throw new Error(data.error || data.message || 'Error en validación del servidor');
            }
        } catch (err) {
            console.error(err);
            Swal.fire({
                icon: 'error',
                title: 'Error al Guardar',
                text: err.message || 'Ocurrió un problema de comunicación.'
            });
            if (saveBtn) {
                saveBtn.disabled = false;
                saveBtn.innerHTML = '<i class="fa-solid fa-floppy-disk"></i> Finalizar y Guardar';
            }
        }
    }
}


/* ==========================================================================
   2. INICIALIZACIÓN GLOBAL DE COMPONENTES AL CARGAR DOM
   ========================================================================== */
document.addEventListener('DOMContentLoaded', () => {
    // A. Inicializar Wizard de Perfiles
    const wizardEl = document.getElementById('profileFormApp');
    if (wizardEl) {
        new JobProfileWizard(wizardEl);
    }
});


/* ==========================================================================
   3. ACCIONES DE MODALES Y LISTADO DE PERFILES
   ========================================================================== */

// 3.1 Asignar Empleado Referencial
window.openAssignReferentialModal = function (pk) {
    if (typeof openAjaxModal === 'function') {
        openAjaxModal(`/function_manual/profiles/assign-referential/${pk}/`);
    }
};

window.searchEmployeeReferential = async function () {
    const cedula = document.getElementById('search-cedula-ref')?.value?.trim();
    const resultCard = document.getElementById('search-result-card-ref');
    const btnSubmit = document.getElementById('btn-submit-assign-ref');
    const resName = document.getElementById('res-name-ref');
    const resEmail = document.getElementById('res-email-ref');
    const resPhoto = document.getElementById('res-photo-ref');
    const hiddenId = document.getElementById('selected-employee-id-ref');

    if (!cedula || cedula.length < 10) {
        Swal.fire('Atención', 'Ingrese un número de cédula válido.', 'warning');
        return;
    }

    if (btnSubmit) btnSubmit.disabled = true;
    if (resName) resName.textContent = 'Buscando empleado...';
    if (resultCard) resultCard.classList.remove('hidden');

    try {
        const res = await fetch(`/function_manual/api/search-employee-simple/?q=${cedula}`, {
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        });
        const data = await res.json();

        if (data.success && data.data) {
            const emp = data.data;
            if (resName) resName.textContent = emp.full_name;
            if (resEmail) resEmail.textContent = emp.cargo || 'Sin partida asignada';
            if (resPhoto) {
                resPhoto.innerHTML = `<img src="${emp.photo || '/static/img/avatar-placeholder.png'}" style="width:100%; height:100%; object-fit:cover; border-radius:50%;">`;
            }
            if (hiddenId) hiddenId.value = emp.id;
            if (btnSubmit) btnSubmit.disabled = false;
        } else {
            if (resName) resName.textContent = 'No encontrado';
            if (resEmail) resEmail.textContent = data.message || 'Empleado no registrado o inactivo';
            if (resPhoto) resPhoto.innerHTML = '<i class="fas fa-user-slash text-muted fa-lg"></i>';
            if (hiddenId) hiddenId.value = '';
            if (btnSubmit) btnSubmit.disabled = true;
        }
    } catch (e) {
        console.error(e);
        if (resName) resName.textContent = 'Error de conexión';
        if (btnSubmit) btnSubmit.disabled = true;
    }
};

window.submitAssignReferential = async function (e, pk) {
    e.preventDefault();
    const form = e.target;
    const btn = document.getElementById('btn-submit-assign-ref');

    if (btn) {
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Guardando...';
        btn.disabled = true;
    }

    try {
        const formData = new FormData(form);
        const res = await fetch(`/function_manual/profiles/assign-referential/${pk}/`, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': getCsrfToken()
            }
        });
        const data = await res.json();

        if (data.success) {
            if (typeof closeModal === 'function') closeModal();
            if (typeof showToast === 'function') {
                showToast(data.message || 'Empleado referencial asignado.', 'success');
            }
            if (typeof window.fetchFunctionManualProfiles === 'function') {
                window.fetchFunctionManualProfiles();
            } else {
                location.reload();
            }
        } else {
            Swal.fire('Error', data.message || 'No se pudo asignar el empleado.', 'error');
            if (btn) {
                btn.innerHTML = '<i class="fas fa-save me-1"></i> Guardar Asignación';
                btn.disabled = false;
            }
        }
    } catch (err) {
        console.error(err);
        Swal.fire('Error', 'Fallo de comunicación con el servidor.', 'error');
        if (btn) {
            btn.innerHTML = '<i class="fas fa-save me-1"></i> Guardar Asignación';
            btn.disabled = false;
        }
    }
};

// 3.2 Completar Denominación
window.openCompleteDenominationModal = function (pk) {
    if (typeof openAjaxModal === 'function') {
        openAjaxModal(`/function_manual/profiles/complete-denomination/${pk}/`);
    }
};

window.submitCompleteDenomination = async function (e, pk) {
    e.preventDefault();
    const currentDenom = document.getElementById('current-denomination')?.value || '';
    const complement = document.getElementById('denomination-complement')?.value.trim() || '';
    const finalDenom = complement ? `${currentDenom} ${complement}` : currentDenom;

    const result = await Swal.fire({
        title: '¿Confirmar Denominación?',
        html: `
            <div style="text-align: left; background: #f8fafc; padding: 15px; border-radius: 8px;">
                <p style="margin: 0 0 10px; color: #475569;">Se asignará la denominación definitiva:</p>
                <div style="font-weight: 700; color: #1e3a8a; padding: 10px; background: white; border-radius: 6px; border-left: 4px solid #3b82f6;">
                    ${finalDenom}
                </div>
            </div>
        `,
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: 'Sí, confirmar',
        cancelButtonText: 'Cancelar'
    });

    if (!result.isConfirmed) return;

    try {
        const res = await fetch('/function_manual/api/profile/complete-denomination/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken(),
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify({profile_id: pk, complement: complement})
        });
        const data = await res.json();

        if (data.success) {
            if (typeof closeModal === 'function') closeModal();
            if (typeof showToast === 'function') {
                showToast(data.message || 'Denominación actualizada.', 'success');
            }
            if (typeof window.fetchFunctionManualProfiles === 'function') {
                window.fetchFunctionManualProfiles();
            } else {
                location.reload();
            }
        } else {
            Swal.fire('Atención', data.message || 'No se pudo actualizar la denominación.', 'warning');
        }
    } catch (err) {
        console.error(err);
        Swal.fire('Error', 'Problema al procesar la solicitud.', 'error');
    }
};

// 3.3 Legalización (Firmas)
window.openLegalizeModal = function (pk) {
    if (typeof openAjaxModal === 'function') {
        openAjaxModal(`/function_manual/profiles/legalize/${pk}/`, () => {
            initLegalizeSelects();
        });
    }
};

function initLegalizeSelects() {
    const selects = document.querySelectorAll('.select-authority');
    selects.forEach(select => {
        const $select = $(select);
        const ajaxUrl = select.dataset.ajaxUrl || '/function_manual/api/users/search/';

        $select.select2({
            width: '100%',
            placeholder: 'Buscar usuario...',
            allowClear: true,
            ajax: {
                url: ajaxUrl,
                dataType: 'json',
                delay: 250,
                data: params => ({term: params.term}),
                processResults: data => ({results: data.results || []}),
                cache: true
            }
        });
    });
}

window.submitLegalizeProfile = async function (e, pk) {
    e.preventDefault();
    const form = e.target;
    const btn = document.getElementById('btn-submit-legalize');

    if (btn) {
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Guardando...';
        btn.disabled = true;
    }

    try {
        const formData = new FormData(form);
        const res = await fetch(`/function_manual/profiles/legalize/${pk}/`, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': getCsrfToken()
            }
        });
        const data = await res.json();

        if (data.success) {
            if (typeof closeModal === 'function') closeModal();
            if (typeof showToast === 'function') {
                showToast(data.message || 'Perfil legalizado correctamente.', 'success');
            }
            if (typeof window.fetchFunctionManualProfiles === 'function') {
                window.fetchFunctionManualProfiles();
            } else {
                location.reload();
            }
        } else {
            Swal.fire('Error', data.message || 'No se pudo guardar la legalización.', 'error');
            if (btn) {
                btn.innerHTML = '<i class="fas fa-save"></i> Guardar Legalización';
                btn.disabled = false;
            }
        }
    } catch (e) {
        console.error(e);
        Swal.fire('Error', 'Fallo de conexión.', 'error');
        if (btn) {
            btn.innerHTML = '<i class="fas fa-save"></i> Guardar Legalización';
            btn.disabled = false;
        }
    }
};

// 3.4 Subir PDF Legalizado y Reporte
window.openUploadLegalizedModal = function (pk) {
    if (typeof openAjaxModal === 'function') {
        openAjaxModal(`/function_manual/profiles/upload-legalized/${pk}/`);
    }
};

window.submitUploadLegalized = async function (e, pk) {
    e.preventDefault();
    const form = e.target;
    const btn = document.getElementById('btn-submit-upload');

    if (btn) {
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Subiendo...';
        btn.disabled = true;
    }

    try {
        const formData = new FormData(form);
        const res = await fetch(`/function_manual/profiles/upload-legalized/${pk}/`, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': getCsrfToken()
            }
        });
        const data = await res.json();

        if (data.success) {
            if (typeof closeModal === 'function') closeModal();
            if (typeof showToast === 'function') {
                showToast(data.message || 'Documento cargado con éxito.', 'success');
            }
            if (typeof window.fetchFunctionManualProfiles === 'function') {
                window.fetchFunctionManualProfiles();
            } else {
                location.reload();
            }
        } else {
            Swal.fire('Error', data.message || 'No se pudo subir el archivo.', 'error');
            if (btn) {
                btn.innerHTML = '<i class="fas fa-upload"></i> Subir Documento';
                btn.disabled = false;
            }
        }
    } catch (e) {
        console.error(e);
        Swal.fire('Error', 'Error de comunicación.', 'error');
        if (btn) {
            btn.innerHTML = '<i class="fas fa-upload"></i> Subir Documento';
            btn.disabled = false;
        }
    }
};

window.openProfileDetailModal = function (pk) {
    if (typeof openAjaxModal === 'function') {
        openAjaxModal(`/function_manual/profiles/detail/${pk}/`);
    }
};

window.openReportPdfModal = function (pk) {
    if (typeof openAjaxModal === 'function') {
        openAjaxModal(`/function_manual/profiles/report_pdf_modal/${pk}/`);
    }
};

/* ==========================================================================
   4. MODALES DINÁMICOS Y AJAX (CATÁLOGOS, MATRIZ Y ASIGNACIÓN DE GRUPO)
   ========================================================================== */

/* ==========================================================================
   GESTOR: ASIGNAR GRUPO OCUPACIONAL (VANILLA JS + SELECT2)
   ========================================================================== */

window.openAssignGroupModal = async function (profileId) {
    const modal = document.getElementById('modalAssignGroup');
    if (!modal) return;

    const inputId = document.getElementById('assign_group_profile_id');
    const loading = document.getElementById('assignGroupLoading');
    const chainContainer = document.getElementById('assignGroupChainContainer');
    const btnSubmit = document.getElementById('btnSubmitAssignGroup');

    inputId.value = profileId;
    btnSubmit.disabled = true;
    loading.classList.remove('hidden');
    chainContainer.classList.add('hidden');
    chainContainer.innerHTML = '';

    // Abrir modal usando la API de main.js
    if (typeof openModal === 'function') {
        openModal('modalAssignGroup');
    } else {
        modal.classList.remove('hidden');
        document.body.classList.add('no-scroll');
    }

    try {
        // 1. Obtener la cadena del perfil desde el backend
        const res = await fetch(`/function_manual/api/profile/${profileId}/valuation-chain/`, {
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        });
        const data = await res.json();

        if (!data.success) {
            throw new Error(data.message || 'No se pudo cargar la cadena de valoración.');
        }

        const selected = data.selected_values;
        let parentId = null;

        // Función auxiliar para consultar y avanzar en el árbol de valoración
        const fetchLevel = async (parent, expectedType) => {
            const url = parent ? `/function_manual/api/valuation-nodes/?parent=${parent}` : '/function_manual/api/valuation-nodes/';
            const r = await fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}});
            const list = await r.json();
            return list.filter(n => (n.type === expectedType || n.node_type === expectedType));
        };

        // Recorrer árbol hasta COMPLEXITY para encontrar los RESULT hijos
        const roles = await fetchLevel(null, 'ROLE');
        const roleNode = roles.find(n => n.catalog_item_id == selected.role_id) || roles[0];
        if (roleNode) {
            parentId = roleNode.id;
            const instructions = await fetchLevel(parentId, 'INSTRUCTION');
            const instNode = instructions.find(n => n.catalog_item_id == selected.instruction_id) || instructions[0];
            if (instNode) {
                parentId = instNode.id;
                const experiences = await fetchLevel(parentId, 'EXPERIENCE');
                const expNode = experiences.find(n => (n.name_extra || n.name) === selected.experience_text) || experiences[0];
                if (expNode) {
                    parentId = expNode.id;
                    const decisions = await fetchLevel(parentId, 'DECISION');
                    const decNode = decisions.find(n => n.catalog_item_id == selected.decision_id) || decisions[0];
                    if (decNode) {
                        parentId = decNode.id;
                        const impacts = await fetchLevel(parentId, 'IMPACT');
                        const impNode = impacts.find(n => n.catalog_item_id == selected.impact_id) || impacts[0];
                        if (impNode) {
                            parentId = impNode.id;
                            const complexities = await fetchLevel(parentId, 'COMPLEXITY');
                            const compNode = complexities.find(n => n.catalog_item_id == selected.complexity_id) || complexities[0];
                            if (compNode) {
                                parentId = compNode.id;
                            }
                        }
                    }
                }
            }
        }

        if (!parentId) {
            throw new Error('La cadena de valoración previa está incompleta o no coincide.');
        }

        // 2. Obtener los nodos RESULT finales bajo la complejidad obtenida
        const results = await fetchLevel(parentId, 'RESULT');

        if (!results || results.length === 0) {
            throw new Error('No se encontraron grupos ocupacionales (RESULT) para esta configuración.');
        }

        // Renderizar selector
        chainContainer.innerHTML = `
            <div class="valuation-node-box w-100">
                <label class="form-label font-weight-700">7. Grupo Ocupacional (Resultado Final) (*)</label>
                <select class="form-control select2-modal" id="assign_result_node_select" name="result_node_id" required>
                    <option value="">Seleccione grupo ocupacional...</option>
                    ${results.map(r => `<option value="${r.id}">${r.name}</option>`).join('')}
                </select>
                <p class="form-hint mt-1">Seleccione la clasificación salarial correspondiente.</p>
            </div>
        `;

        const $select = $(chainContainer).find('#assign_result_node_select');
        $select.select2({
            width: '100%',
            dropdownParent: $(modal)
        }).on('change', function () {
            btnSubmit.disabled = !this.value;
        });

        loading.classList.add('hidden');
        chainContainer.classList.remove('hidden');

    } catch (err) {
        console.error(err);
        loading.classList.add('hidden');
        closeModal('modalAssignGroup');
        Swal.fire({
            icon: 'error',
            title: 'Error de Valoración',
            text: err.message || 'No se pudo obtener la cadena de nodos.'
        });
    }
};

window.submitAssignGroup = async function (e) {
    e.preventDefault();
    const form = e.target;
    const profileId = document.getElementById('assign_group_profile_id').value;
    const resultNodeId = document.getElementById('assign_result_node_select')?.value;
    const btn = document.getElementById('btnSubmitAssignGroup');

    if (!resultNodeId) {
        Swal.fire('Atención', 'Seleccione un grupo ocupacional final.', 'warning');
        return;
    }

    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i> Guardando...';

    try {
        const res = await fetch('/function_manual/api/profile/assign-group/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken(),
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify({
                profile_id: profileId,
                result_node_id: resultNodeId
            })
        });

        const data = await res.json();

        if (data.success) {
            closeModal('modalAssignGroup');
            showToast(data.message || 'Grupo ocupacional asignado con éxito.', 'success');
            if (typeof fetchFunctionManualProfiles === 'function') {
                fetchFunctionManualProfiles();
            } else {
                setTimeout(() => location.reload(), 600);
            }
        } else {
            throw new Error(data.message || 'Error al asignar el grupo.');
        }
    } catch (err) {
        Swal.fire({
            icon: 'error',
            title: 'Error',
            text: err.message || 'Error de comunicación con el servidor.'
        });
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-check me-1"></i> Asignar Grupo';
    }
};

async function initAssignGroupWorkflow(profileId, modalEl) {
    const inputId = modalEl.querySelector('#assign_group_profile_id');
    if (inputId) inputId.value = profileId;

    const loading = modalEl.querySelector('#assignGroupLoading');
    const content = modalEl.querySelector('#assignGroupContent');
    const select = modalEl.querySelector('#assign_result_node_id');
    const btnSubmit = modalEl.querySelector('#btnSubmitAssignGroup');

    try {
        const res = await fetch(`/function_manual/api/profile/${profileId}/valuation-chain/`, {
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        });
        const data = await res.json();
        if (!data.success) throw new Error(data.message);

        // Nivel 6 (Complejidad) es el padre directo de RESULT
        const complexityId = data.selected_values?.complexity_id;
        if (complexityId) {
            const nodeRes = await fetch(`/function_manual/api/valuation-nodes/?parent=${complexityId}`);
            const nodes = await nodeRes.json();
            const resultNodes = nodes.filter(n => n.type === 'RESULT' || n.node_type === 'RESULT');

            $(select).empty().append('<option value="">Seleccione grupo...</option>');
            resultNodes.forEach(n => {
                $(select).append(new Option(n.name, n.id));
            });

            $(select).select2({width: '100%', dropdownParent: $(modalEl)});
            $(select).on('change', () => {
                btnSubmit.disabled = !select.value;
            });

            loading.classList.add('hidden');
            content.classList.remove('hidden');
        }
    } catch (e) {
        Swal.fire({icon: 'error', title: 'Error', text: 'No se pudo cargar la cadena de valoración.'});
    }
}

window.submitAssignGroup = async function (e) {
    e.preventDefault();
    const form = e.target;
    const profileId = form.querySelector('#assign_group_profile_id').value;
    const resultNodeId = form.querySelector('#assign_result_node_id').value;
    const btn = form.querySelector('#btnSubmitAssignGroup');

    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i> Guardando...';

    try {
        const res = await fetch('/function_manual/api/profile/assign-group/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken(),
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify({profile_id: profileId, result_node_id: resultNodeId})
        });
        const data = await res.json();
        if (data.success) {
            closeModal();
            showToast(data.message || 'Grupo asignado correctamente.', 'success');
            if (typeof fetchFunctionManualProfiles === 'function') fetchFunctionManualProfiles();
        } else {
            throw new Error(data.message);
        }
    } catch (err) {
        Swal.fire({icon: 'error', title: 'Error', text: err.message || 'Error al asignar grupo.'});
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-check me-1"></i> Asignar';
    }
};

// 4.2 Guardar Competencias
window.submitCompetencyForm = async function (e, pk) {
    e.preventDefault();
    const form = e.target;
    const payload = {
        name: form.querySelector('#comp_name').value.trim(),
        type: form.querySelector('#comp_type').value,
        suggested_level: form.querySelector('#comp_level').value || null,
        definition: form.querySelector('#comp_definition').value.trim()
    };

    const url = pk ? `/function_manual/competencies/update/${pk}/` : '/function_manual/competencies/create/';

    try {
        const res = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken(),
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.status === 'success') {
            closeModal();
            showToast(data.message, 'success');
            setTimeout(() => location.reload(), 600);
        } else {
            Swal.fire({icon: 'warning', title: 'Atención', text: data.message});
        }
    } catch (err) {
        Swal.fire({icon: 'error', title: 'Error', text: 'Error de comunicación con el servidor.'});
    }
};

// 4.3 Guardar Matriz Escalar Ocupacional
window.submitMatrixForm = async function (e, pk) {
    e.preventDefault();
    const form = e.target;
    const payload = {
        id: pk || null,
        occupational_group: form.querySelector('#matrix_group').value.trim(),
        grade: form.querySelector('#matrix_grade').value,
        remuneration: form.querySelector('#matrix_rmu').value
    };

    try {
        const res = await fetch('/function_manual/api/matrix/save/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken(),
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.success) {
            closeModal();
            showToast(data.message, 'success');
            setTimeout(() => location.reload(), 600);
        } else {
            Swal.fire({icon: 'error', title: 'Error', text: data.message});
        }
    } catch (err) {
        Swal.fire({icon: 'error', title: 'Error', text: 'Error de comunicación con el servidor.'});
    }
};