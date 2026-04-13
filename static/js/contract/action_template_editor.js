class ActionTemplateEditor {
    constructor(templateId) {
        this.templateId = templateId;
        this.csrfToken = this.getCsrfToken();
        this.debug = true;
    }

    // 🕵️‍♂️ BÚSQUEDA EN TIEMPO REAL: Evita los "DOM fantasmas" de Vue.js
    get fields() {
        return Array.from(document.querySelectorAll('.action-template-field'));
    }

    get saveButton() {
        return document.getElementById('btn-save-action-template');
    }

    log(message, extra = null) {
        if (!this.debug || typeof console === 'undefined') return;
        if (extra !== null) {
            console.log(`[ActionTemplateEditor] ${message}`, extra);
        } else {
            console.log(`[ActionTemplateEditor] ${message}`);
        }
    }

    getCsrfToken() {
        const hidden = document.querySelector('[name=csrfmiddlewaretoken]');
        if (hidden && hidden.value) return hidden.value;
        const match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : '';
    }

    async fetchJson(url, options = {}) {
        const response = await fetch(url, options);
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            throw new Error(data.error || data.message || `HTTP ${response.status}`);
        }
        return data;
    }

    getJsonScriptData(id) {
        const node = document.getElementById(id);
        if (!node) return [];
        try {
            const payload = JSON.parse(node.textContent || '[]');
            return Array.isArray(payload) ? payload : [];
        } catch (error) {
            return [];
        }
    }

    async init() {
        this.log('Iniciando ActionTemplateEditor...');

        // Le damos 150ms a Vue.js/Navegador para que termine de redibujar el DOM
        setTimeout(async () => {
            await this.ensureOptionsLoaded();

            if (this.saveButton) {
                // Limpiamos listeners previos por si acaso y agregamos el nuevo
                this.saveButton.removeEventListener('click', this.saveHandler);
                this.saveHandler = () => this.saveAllFields();
                this.saveButton.addEventListener('click', this.saveHandler);
            }
        }, 150);
    }

    async ensureOptionsLoaded() {
        let actionTypes = this.getJsonScriptData('actionTemplateTypesData');
        let authorities = this.getJsonScriptData('actionTemplateAuthoritiesData');

        if (!actionTypes.length || !authorities.length) {
            try {
                const payload = await this.fetchJson('/contract/templates/action-editor/options/');
                if (!actionTypes.length) actionTypes = Array.isArray(payload.action_types) ? payload.action_types : [];
                if (!authorities.length) authorities = Array.isArray(payload.authorities) ? payload.authorities : [];
            } catch (error) {
                this.log('Error cargando opciones por API', error);
            }
        }

        // Consultamos jQuery DIRECTO al DOM actual, nada de variables cacheadas
        const $selects = jQuery('.action-template-field');
        this.log(`Modificando ${$selects.length} nodos VISIBLES en pantalla`);

        $selects.each(function () {
            const $field = jQuery(this);

            if ($field.hasClass('select2-hidden-accessible')) {
                $field.select2('destroy');
            }

            // Vaciamos e inyectamos la opción por defecto
            $field.empty();
            $field.append(new Option('-- Seleccione --', '', true, true));

            let currentValue = String($field.attr('data-original') || '').trim();
            if (currentValue === 'None' || currentValue === 'null') {
                currentValue = '';
            }

            const isActionType = $field.attr('data-field-key') === 'action_type';
            const options = isActionType ? actionTypes : authorities;

            // Inyectamos las opciones reales
            options.forEach((item) => {
                const text = isActionType ? item.name : `${item.name} - ${item.position || ''}`.trim();
                const optionId = String(item.id);
                const isSelected = (currentValue === optionId);

                $field.append(new Option(text, optionId, false, isSelected));
            });

            // Levantamos Select2
            $field.select2({
                width: '100%',
                placeholder: '-- Seleccione --',
                allowClear: true
            });
        });

        this.log('✅ Select2 inyectado con éxito en los nodos frescos');
    }

    async saveAllFields() {
        // Al llamar a this.fields aquí, asegura leer los valores de la pantalla, no de fantasmas
        const payloads = this.fields.map((field) => ({
            sectionId: field.dataset.sectionId,
            content: field.value,
            original: field.dataset.original || '',
        }));

        try {
            if (this.saveButton) this.saveButton.disabled = true;

            for (const payload of payloads) {
                if ((payload.content || '').trim() === (payload.original || '').trim()) {
                    continue;
                }
                await this.fetchJson(`/contract/templates/sections/${payload.sectionId}/update/`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': this.csrfToken,
                    },
                    body: JSON.stringify({
                        content: payload.content,
                    }),
                });
            }

            this.fields.forEach((field) => {
                field.dataset.original = field.value;
            });

            if (typeof Swal !== 'undefined') {
                Swal.fire({
                    icon: 'success',
                    title: 'Plantilla actualizada',
                    toast: true,
                    position: 'top-end',
                    showConfirmButton: false,
                    timer: 2500
                });
            }
        } catch (error) {
            if (typeof Swal !== 'undefined') {
                Swal.fire('Error', error.message || 'No fue posible guardar la plantilla.', 'error');
            }
        } finally {
            if (this.saveButton) this.saveButton.disabled = false;
        }
    }
}