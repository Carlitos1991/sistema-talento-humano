/**
 * Editor de Templates Dinamicos para Notificaciones
 * - Modal unico para agregar/editar parrafos
 * - Modal de variables
 * - CRUD + reordenamiento por drag & drop
 */

class NotificationTemplateEditor {
    constructor(templateId) {
        this.templateId = templateId;
        this.csrfToken = this.getCsrfToken();

        this.sectionsList = document.getElementById('sectionsList');
        this.emptyState = document.getElementById('emptyState');

        this.sectionEditorModal = document.getElementById('sectionEditorModal');

        this.btnOpenVariablesSwal = document.getElementById('btn-open-variables-swal');
        this.btnOpenAddSectionModal = document.getElementById('btn-open-add-section-modal');
        this.saveSectionBtn = document.getElementById('saveSectionBtn');

        this.sectionEditorTitle = document.getElementById('sectionEditorTitle');
        this.sectionEditorContent = document.getElementById('sectionEditorContent');
        this.availableMappings = this.getAvailableMappings();

        this.sectionEditorMode = 'create';
        this.currentEditSectionId = null;
    }

    getAvailableMappings() {
        const dataNode = document.getElementById('templateEditorMappingsData');
        if (!dataNode) return [];

        try {
            const parsed = JSON.parse(dataNode.textContent || '[]');
            return Array.isArray(parsed) ? parsed : [];
        } catch (error) {
            console.error('Error leyendo variables disponibles:', error);
            return [];
        }
    }

    getCsrfToken() {
        const hidden = document.querySelector('[name=csrfmiddlewaretoken]');
        if (hidden && hidden.value) {
            return hidden.value;
        }

        const match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : '';
    }

    async fetchJson(url, options = {}) {
        const response = await fetch(url, options);
        const contentType = (response.headers.get('content-type') || '').toLowerCase();

        if (!contentType.includes('application/json')) {
            const text = await response.text();
            if (response.status === 403) {
                throw new Error('No tiene permisos para realizar esta accion.');
            }
            if (response.status === 500) {
                throw new Error('Error interno del servidor.');
            }
            throw new Error(`Respuesta invalida del servidor (HTTP ${response.status}).`);
        }

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || data.message || `HTTP ${response.status}`);
        }

        return data;
    }

    init() {
        this.attachEventListeners();
        this.updatePreview();
    }

    attachEventListeners() {
        if (this.btnOpenVariablesSwal) {
            this.btnOpenVariablesSwal.addEventListener('click', () => this.openVariablesAlert());
        }

        if (this.btnOpenAddSectionModal) {
            this.btnOpenAddSectionModal.addEventListener('click', () => this.openSectionEditorModal('create'));
        }

        if (this.saveSectionBtn) {
            this.saveSectionBtn.addEventListener('click', () => this.handleSaveSection());
        }

        document.getElementById('refreshPreview')?.addEventListener('click', () => this.updatePreview());

        document.addEventListener('click', (e) => {
            if (e.target.closest('.btn-delete')) {
                const sectionId = e.target.closest('.btn-delete').dataset.sectionId;
                this.handleDeleteSection(sectionId);
                return;
            }

            if (e.target.closest('.btn-edit')) {
                const sectionId = e.target.closest('.btn-edit').dataset.sectionId;
                this.handleEditSection(sectionId);
                return;
            }

            if (e.target.closest('.js-close-section-editor-modal')) {
                this.closeModal(this.sectionEditorModal);
                return;
            }

            const formatBtn = e.target.closest('.js-format-action');
            if (!formatBtn) return;

            const targetId = formatBtn.dataset.target;
            const textarea = document.getElementById(targetId);
            if (textarea) {
                this.wrapSelection(
                    textarea,
                    formatBtn.dataset.prefix || '',
                    formatBtn.dataset.suffix || ''
                );
            }
        });

        this.sectionEditorModal?.addEventListener('click', (e) => {
            if (e.target === this.sectionEditorModal) {
                e.preventDefault();
            }
        });

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.closeModal(this.sectionEditorModal);
                return;
            }

            if (e.key !== 'Tab') return;
            if (!e.target || e.target.id !== 'sectionEditorContent') return;

            e.preventDefault();
            this.wrapSelection(e.target, '\t', '');
        });

        this.initDragDrop();
    }

    openModal(modal) {
        if (!modal) return;
        modal.classList.remove('hidden');
        document.body.classList.add('modal-open');
    }

    openVariablesAlert() {
        const mappings = this.availableMappings || [];

        if (typeof Swal === 'undefined') {
            if (!mappings.length) {
                this.showNotification('No hay variables globales configuradas.', 'warning');
                return;
            }

            const fallbackText = mappings
                .map((item) => `${item.placeholder || ''} - ${item.label || ''}`)
                .join('\n');
            alert(`Variables disponibles:\n\n${fallbackText}`);
            return;
        }

        const rows = mappings
            .map((item) => {
                const placeholder = this.escapeHtml(item.placeholder || '');
                const label = this.escapeHtml(item.label || '');
                return `
                    <div class="template-editor-var-item">
                        <code>${placeholder}</code>
                        <span>${label}</span>
                    </div>
                `;
            })
            .join('');

        const content = rows || '<div class="template-editor-var-empty">No hay variables globales configuradas.</div>';

        Swal.fire({
            title: 'Variables disponibles',
            html: `<div class="template-editor-var-grid">${content}</div>`,
            icon: 'info',
            width: 705,
            showCloseButton: false,
            showCancelButton: false,
            confirmButtonText: 'Cerrar',
            allowOutsideClick: true,
            allowEscapeKey: true,
            customClass: {
                popup: 'template-editor-vars-swal',
                confirmButton: 'btn btn-primary template-editor-swal-confirm-btn',
            },
            buttonsStyling: false,
        });
    }

    closeModal(modal) {
        if (!modal) return;
        modal.classList.add('hidden');

        const anyOpen = Array.from(document.querySelectorAll('.modal-overlay')).some((m) => !m.classList.contains('hidden'));
        if (!anyOpen) {
            document.body.classList.remove('modal-open');
        }
    }

    openSectionEditorModal(mode, sectionId = null) {
        this.sectionEditorMode = mode;
        this.currentEditSectionId = sectionId;

        if (!this.sectionEditorTitle || !this.sectionEditorContent) return;

        if (mode === 'edit' && sectionId) {
            const item = document.querySelector(`.section-item[data-section-id="${sectionId}"]`);
            const content = item ? this.decodeEscapedContent(item.dataset.sectionContent || '') : '';
            this.sectionEditorTitle.textContent = 'Editar Parrafo';
            this.sectionEditorContent.value = content;
            if (this.saveSectionBtn) this.saveSectionBtn.innerHTML = '<i class="fa-solid fa-save"></i> Guardar';
        } else {
            this.sectionEditorTitle.textContent = 'Agregar Nuevo Parrafo';
            this.sectionEditorContent.value = '';
            if (this.saveSectionBtn) this.saveSectionBtn.innerHTML = '<i class="fas fa-plus"></i> Agregar Parrafo';
        }

        this.openModal(this.sectionEditorModal);
        window.setTimeout(() => this.sectionEditorContent.focus(), 30);
    }

    wrapSelection(textarea, prefix, suffix) {
        const start = textarea.selectionStart || 0;
        const end = textarea.selectionEnd || 0;
        const selectedText = textarea.value.slice(start, end);
        const replacement = `${prefix}${selectedText || 'texto'}${suffix}`;

        textarea.setRangeText(replacement, start, end, 'end');
        textarea.focus();
    }

    handleSaveSection() {
        const content = this.decodeEscapedContent((this.sectionEditorContent?.value || '').trim());
        if (!content) {
            this.showNotification('El contenido no puede estar vacio', 'warning');
            return;
        }

        if (this.sectionEditorMode === 'edit' && this.currentEditSectionId) {
            this.updateSection(this.currentEditSectionId, content);
            return;
        }

        this.createSection(content);
    }

    createSection(content) {
        const maxOrder = document.querySelectorAll('.section-item').length;

        this.fetchJson(`/sanctions/templates/${this.templateId}/sections/create/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.csrfToken,
            },
            body: JSON.stringify({
                section_type: 'PARAGRAPH',
                content: content,
                order: maxOrder,
            }),
        })
            .then((data) => {
                if (data.success) {
                    this.appendSection(data.section);
                    this.updateOrderLabels();
                    this.toggleEmptyState();
                    this.updatePreview();
                    this.closeModal(this.sectionEditorModal);
                    this.showNotification('Parrafo agregado exitosamente', 'success');
                } else {
                    this.showNotification(data.error || 'Error al crear', 'danger');
                }
            })
            .catch((err) => {
                console.error(err);
                this.showNotification(err.message || 'Error de red', 'danger');
            });
    }

    updateSection(sectionId, content) {
        this.fetchJson(`/sanctions/templates/sections/${sectionId}/update/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.csrfToken,
            },
            body: JSON.stringify({
                section_type: 'PARAGRAPH',
                content: content,
            }),
        })
            .then((data) => {
                if (data.success) {
                    this.updateSectionItem(data.section);
                    this.updateOrderLabels();
                    this.updatePreview();
                    this.closeModal(this.sectionEditorModal);
                    this.showNotification('Parrafo actualizado', 'success');
                } else {
                    this.showNotification(data.error || 'Error al actualizar', 'danger');
                }
            })
            .catch((err) => {
                console.error(err);
                this.showNotification(err.message || 'Error de red', 'danger');
            });
    }

    handleEditSection(sectionId) {
        this.openSectionEditorModal('edit', sectionId);
    }

    handleDeleteSection(sectionId) {
        const executeDelete = () => {
            this.fetchJson(`/sanctions/templates/sections/${sectionId}/delete/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.csrfToken,
                },
            })
                .then((data) => {
                    if (data.success) {
                        const item = document.querySelector(`.section-item[data-section-id="${sectionId}"]`);
                        if (item) item.remove();
                        this.updateOrderLabels();
                        this.toggleEmptyState();
                        this.updatePreview();
                        this.showNotification('Parrafo eliminado', 'success');
                    } else {
                        this.showNotification(data.error || 'Error al eliminar', 'danger');
                    }
                })
                .catch((err) => {
                    console.error(err);
                    this.showNotification(err.message || 'Error de red', 'danger');
                });
        };

        if (typeof Swal !== 'undefined') {
            Swal.fire({
                title: '¿Eliminar parrafo?',
                text: 'Esta accion no se puede deshacer.',
                icon: 'warning',
                showCancelButton: true,
                confirmButtonText: 'Si, eliminar',
                cancelButtonText: 'Cancelar',
                confirmButtonColor: '#d33',
            }).then((result) => {
                if (result.isConfirmed) {
                    executeDelete();
                }
            });
            return;
        }

        if (confirm('¿Eliminar este parrafo?')) {
            executeDelete();
        }
    }

    initDragDrop() {
        if (!this.sectionsList) return;

        let draggedElement = null;

        document.addEventListener('dragstart', (e) => {
            if (e.target.closest('.section-item')) {
                draggedElement = e.target.closest('.section-item');
                draggedElement.style.opacity = '0.5';
            }
        });

        document.addEventListener('dragend', () => {
            if (draggedElement) {
                draggedElement.style.opacity = '1';
            }
        });

        document.addEventListener('dragover', (e) => {
            e.preventDefault();
            const item = e.target.closest('.section-item');
            if (item && item !== draggedElement) {
                const rect = item.getBoundingClientRect();
                if (e.clientY < rect.top + rect.height / 2) {
                    item.parentNode.insertBefore(draggedElement, item);
                } else {
                    item.parentNode.insertBefore(draggedElement, item.nextSibling);
                }
            }
        });

        document.addEventListener('drop', (e) => {
            e.preventDefault();
            if (draggedElement) {
                this.saveReorder();
            }
        });
    }

    saveReorder() {
        const items = document.querySelectorAll('.section-item');
        const sections = [];

        items.forEach((item, index) => {
            sections.push({
                id: parseInt(item.dataset.sectionId, 10),
                order: index,
            });
        });

        this.fetchJson(`/sanctions/templates/${this.templateId}/sections/reorder/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.csrfToken,
            },
            body: JSON.stringify({ sections: sections }),
        })
            .then((data) => {
                if (data.success) {
                    this.updateOrderLabels();
                    this.updatePreview();
                    this.showNotification('Orden actualizado', 'success');
                }
            })
            .catch((err) => {
                console.error(err);
                this.showNotification(err.message || 'Error al guardar el orden', 'danger');
            });
    }

    updatePreview() {
        this.fetchJson(`/sanctions/templates/${this.templateId}/preview/`)
            .then((data) => {
                const preview = document.getElementById('preview');
                if (!preview) return;

                if (data.preview) {
                    preview.innerHTML = data.preview;
                } else if (data.error) {
                    preview.innerHTML = `<div class="alert alert-danger">${data.error}</div>`;
                }
            })
            .catch((err) => {
                console.error(err);
                const preview = document.getElementById('preview');
                if (preview) {
                    preview.innerHTML = `<div class="alert alert-danger">${this.escapeHtml(err.message || 'Error al cargar la previa')}</div>`;
                }
            });
    }

    showNotification(message, type = 'info') {
        const iconByType = {
            success: 'success',
            danger: 'error',
            warning: 'warning',
            info: 'info',
        };

        if (typeof Swal !== 'undefined') {
            const toast = Swal.mixin({
                toast: true,
                position: 'top-end',
                showConfirmButton: false,
                timer: 2500,
                timerProgressBar: true,
            });
            toast.fire({
                icon: iconByType[type] || 'info',
                title: message,
            });
            return;
        }

        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type} alert-dismissible fade show position-fixed top-0 start-50 translate-middle-x mt-3`;
        alertDiv.style.zIndex = '9999';
        alertDiv.innerHTML = `${message}<button type="button" class="btn-close" data-bs-dismiss="alert"></button>`;
        document.body.appendChild(alertDiv);
        setTimeout(() => alertDiv.remove(), 3000);
    }

    getSectionDisplayType(rawType) {
        return rawType === 'TITLE' ? 'Titulo' : 'Parrafo';
    }

    escapeHtml(value) {
        return String(value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/\"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    decodeEscapedContent(value) {
        if (!value) return '';

        return String(value)
            .replace(/\\r\\n/g, '\n')
            .replace(/\\n/g, '\n')
            .replace(/\\r/g, '\n')
            .replace(/\\t/g, '\t')
            .replace(/\\u([0-9a-fA-F]{4})/g, (_, hex) => String.fromCharCode(parseInt(hex, 16)));
    }

    appendSection(section) {
        if (!this.sectionsList || !section) return;

        const rawType = section.section_type_code || 'PARAGRAPH';
        const displayType = section.section_type || this.getSectionDisplayType(rawType);
        const normalizedContent = this.decodeEscapedContent(section.content || '');
        const safeContent = this.escapeHtml(normalizedContent);

        const wrapper = document.createElement('div');
        wrapper.className = 'section-item card mb-2';
        wrapper.setAttribute('draggable', 'true');
        wrapper.dataset.sectionId = section.id;
        wrapper.dataset.sectionType = rawType;
        wrapper.dataset.sectionContent = normalizedContent;

        wrapper.innerHTML = `
            <div class="card-body p-3">
                <div class="d-flex justify-content-between align-items-start mb-2">
                    <div class="flex-grow-1">
                        <span class="badge bg-info mb-2">${displayType}</span>
                        <p class="mb-0 small text-muted"><small class="js-section-order">Orden: ${section.order ?? 0}</small></p>
                    </div>
                    <div class="btn-group btn-group-sm" role="group">
                        <button type="button" class="btn btn-outline-primary btn-edit" data-section-id="${section.id}" title="Editar">
                            <i class="fas fa-pencil"></i>
                        </button>
                        <button type="button" class="btn btn-outline-danger btn-delete" data-section-id="${section.id}" title="Eliminar">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                </div>
                <p class="mb-0 small text-break">${safeContent.replace(/\n/g, '<br>')}</p>
            </div>
        `;

        this.sectionsList.appendChild(wrapper);
        this.toggleEmptyState();
    }

    updateSectionItem(section) {
        if (!section) return;

        const item = document.querySelector(`.section-item[data-section-id="${section.id}"]`);
        if (!item) return;

        const rawType = section.section_type_code || 'PARAGRAPH';
        const displayType = section.section_type || this.getSectionDisplayType(rawType);
        const normalizedContent = this.decodeEscapedContent(section.content || '');

        item.dataset.sectionType = rawType;
        item.dataset.sectionContent = normalizedContent;

        const badge = item.querySelector('.badge');
        if (badge) badge.textContent = displayType;

        const contentNode = item.querySelector('p.text-break');
        if (contentNode) {
            contentNode.innerHTML = this.escapeHtml(normalizedContent).replace(/\n/g, '<br>');
        }
    }

    updateOrderLabels() {
        const items = document.querySelectorAll('.section-item');
        items.forEach((item, index) => {
            const orderNode = item.querySelector('.js-section-order');
            if (orderNode) {
                orderNode.textContent = `Orden: ${index}`;
            }
        });
    }

    toggleEmptyState() {
        if (!this.emptyState) return;
        const count = document.querySelectorAll('.section-item').length;
        this.emptyState.classList.toggle('d-none', count > 0);
    }
}
