/**
 * Editor de Templates Dinámicos para Notificaciones
 * Maneja AJAX para crear/editar/eliminar/reordenar secciones
 * Renderiza vista previa en tiempo real
 */

class NotificationTemplateEditor {
    constructor(templateId) {
        this.templateId = templateId;
        this.csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
        this.currentEditSectionId = null;
        this.sectionsList = document.getElementById('sectionsList');
        this.emptyState = document.getElementById('emptyState');
    }

    init() {
        this.attachEventListeners();
        this.updatePreview();
    }

    attachEventListeners() {
        // Formulario agregar sección
        const form = document.getElementById('addSectionForm');
        if (form) {
            form.addEventListener('submit', (e) => this.handleAddSection(e));
        }

        // Botones delete/edit de secciones
        document.addEventListener('click', (e) => {
            if (e.target.closest('.btn-delete')) {
                const sectionId = e.target.closest('.btn-delete').dataset.sectionId;
                this.handleDeleteSection(sectionId);
            }
            if (e.target.closest('.btn-edit')) {
                const sectionId = e.target.closest('.btn-edit').dataset.sectionId;
                this.handleEditSection(sectionId);
            }
        });

        // Actualizar previa
        document.getElementById('refreshPreview')?.addEventListener('click', () => this.updatePreview());

        // Guardar cambios de edición
        document.getElementById('saveEditBtn')?.addEventListener('click', () => this.handleSaveEdit());

        // Herramientas de formato
        document.addEventListener('click', (e) => {
            const formatBtn = e.target.closest('.js-format-action');
            if (!formatBtn) return;
            const targetId = formatBtn.dataset.target;
            const textarea = document.getElementById(targetId);
            if (textarea) {
                this.wrapSelection(
                    textarea,
                    formatBtn.dataset.prefix || '',
                    formatBtn.dataset.suffix || '',
                );
            }
        });

        // Permite tabulaciones dentro del editor de contenido.
        document.addEventListener('keydown', (e) => {
            if (e.key !== 'Tab') return;
            if (!e.target || (e.target.id !== 'sectionContent' && e.target.id !== 'editSectionContent')) return;

            e.preventDefault();
            this.wrapSelection(e.target, '\t', '');
        });

        // Drag and drop
        this.initDragDrop();
    }

    wrapSelection(textarea, prefix, suffix) {
        const start = textarea.selectionStart || 0;
        const end = textarea.selectionEnd || 0;
        const selectedText = textarea.value.slice(start, end);
        const replacement = `${prefix}${selectedText || 'texto'}${suffix}`;

        textarea.setRangeText(replacement, start, end, 'end');
        textarea.focus();
    }

    handleAddSection(e) {
        e.preventDefault();

        const type = document.getElementById('sectionType').value;
        const content = document.getElementById('sectionContent').value.trim();

        if (!type || !content) {
            this.showNotification('Completa todos los campos', 'warning');
            return;
        }

        // Obtener máximo order actual
        const items = document.querySelectorAll('.section-item');
        const maxOrder = items.length;

        fetch(`/sanctions/templates/${this.templateId}/sections/create/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.csrfToken,
            },
            body: JSON.stringify({
                section_type: type,
                content: content,
                order: maxOrder,
            }),
        })
            .then((res) => res.json())
            .then((data) => {
                if (data.success) {
                    // Limpiar formulario
                    document.getElementById('addSectionForm').reset();
                    this.appendSection(data.section);
                    this.updateOrderLabels();
                    this.updatePreview();
                    this.showNotification('Sección agregada exitosamente', 'success');
                } else {
                    this.showNotification(data.error || 'Error al crear', 'danger');
                }
            })
            .catch((err) => {
                console.error(err);
                this.showNotification('Error de red', 'danger');
            });
    }

    handleDeleteSection(sectionId) {
        const executeDelete = () => {
            fetch(`/sanctions/templates/sections/${sectionId}/delete/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.csrfToken,
                },
            })
                .then((res) => res.json())
                .then((data) => {
                    if (data.success) {
                        const item = document.querySelector(`.section-item[data-section-id="${sectionId}"]`);
                        if (item) item.remove();
                        this.updateOrderLabels();
                        this.toggleEmptyState();
                        this.updatePreview();
                        this.showNotification('Sección eliminada', 'success');
                    } else {
                        this.showNotification(data.error || 'Error al eliminar', 'danger');
                    }
                })
                .catch((err) => {
                    console.error(err);
                    this.showNotification('Error de red', 'danger');
                });
        };

        if (typeof Swal !== 'undefined') {
            Swal.fire({
                title: '¿Eliminar sección?',
                text: 'Esta acción no se puede deshacer.',
                icon: 'warning',
                showCancelButton: true,
                confirmButtonText: 'Sí, eliminar',
                cancelButtonText: 'Cancelar',
                confirmButtonColor: '#d33',
            }).then((result) => {
                if (result.isConfirmed) {
                    executeDelete();
                }
            });
            return;
        }

        if (confirm('¿Eliminar esta sección?')) {
            executeDelete();
        }
    }

    handleEditSection(sectionId) {
        this.currentEditSectionId = sectionId;

        // Obtener datos de la sección
        const item = document.querySelector(`[data-section-id="${sectionId}"]`);
        if (!item) return;

        const type = item.dataset.sectionType || 'PARAGRAPH';
        const content = item.dataset.sectionContent || '';

        document.getElementById('editSectionType').value = type;
        document.getElementById('editSectionContent').value = content;

        // Mostrar modal
        const modal = new bootstrap.Modal(document.getElementById('editSectionModal'));
        modal.show();
    }

    handleSaveEdit() {
        const sectionId = this.currentEditSectionId;
        const type = document.getElementById('editSectionType').value;
        const content = document.getElementById('editSectionContent').value.trim();

        if (!content) {
            this.showNotification('El contenido no puede estar vacío', 'warning');
            return;
        }

        fetch(`/sanctions/templates/sections/${sectionId}/update/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.csrfToken,
            },
            body: JSON.stringify({
                section_type: type,
                content: content,
            }),
        })
            .then((res) => res.json())
            .then((data) => {
                if (data.success) {
                    bootstrap.Modal.getInstance(document.getElementById('editSectionModal')).hide();
                    this.updateSectionItem(data.section);
                    this.updateOrderLabels();
                    this.updatePreview();
                    this.showNotification('Sección actualizada', 'success');
                } else {
                    this.showNotification(data.error || 'Error al actualizar', 'danger');
                }
            })
            .catch((err) => {
                console.error(err);
                this.showNotification('Error de red', 'danger');
            });
    }

    loadSections() {
        this.updateOrderLabels();
        this.toggleEmptyState();
    }

    initDragDrop() {
        const list = document.getElementById('sectionsList');
        if (!list) return;

        let draggedElement = null;

        document.addEventListener('dragstart', (e) => {
            if (e.target.closest('.section-item')) {
                draggedElement = e.target.closest('.section-item');
                draggedElement.style.opacity = '0.5';
            }
        });

        document.addEventListener('dragend', (e) => {
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
                id: parseInt(item.dataset.sectionId),
                order: index,
            });
        });

        fetch(`/sanctions/templates/${this.templateId}/sections/reorder/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.csrfToken,
            },
            body: JSON.stringify({ sections: sections }),
        })
            .then((res) => res.json())
            .then((data) => {
                if (data.success) {
                    this.updateOrderLabels();
                    this.updatePreview();
                    this.showNotification('Orden actualizado', 'success');
                }
            })
            .catch((err) => console.error(err));
    }

    updatePreview() {
        fetch(`/sanctions/templates/${this.templateId}/preview/`)
            .then((res) => res.json())
            .then((data) => {
                const preview = document.getElementById('preview');
                if (data.preview) {
                    preview.innerHTML = data.preview;
                } else if (data.error) {
                    preview.innerHTML = `<div class="alert alert-danger">${data.error}</div>`;
                }
            })
            .catch((err) => {
                console.error(err);
                document.getElementById('preview').innerHTML =
                    '<div class="alert alert-danger">Error al cargar la previa</div>';
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
            const Toast = Swal.mixin({
                toast: true,
                position: 'top-end',
                showConfirmButton: false,
                timer: 2500,
                timerProgressBar: true,
            });
            Toast.fire({
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
        return rawType === 'TITLE' ? 'Título (izquierda)' : 'Párrafo (justificado)';
    }

    escapeHtml(value) {
        return String(value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/\"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    appendSection(section) {
        if (!this.sectionsList || !section) return;

        const rawType = section.section_type_code || (section.section_type && section.section_type.includes('Título') ? 'TITLE' : 'PARAGRAPH');
        const displayType = section.section_type || this.getSectionDisplayType(rawType);
        const safeContent = this.escapeHtml(section.content || '');

        const wrapper = document.createElement('div');
        wrapper.className = 'section-item card mb-2';
        wrapper.setAttribute('draggable', 'true');
        wrapper.dataset.sectionId = section.id;
        wrapper.dataset.sectionType = rawType;
        wrapper.dataset.sectionContent = section.content || '';

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

        const rawType = section.section_type_code || (section.section_type && section.section_type.includes('Título') ? 'TITLE' : 'PARAGRAPH');
        const displayType = section.section_type || this.getSectionDisplayType(rawType);

        item.dataset.sectionType = rawType;
        item.dataset.sectionContent = section.content || '';

        const badge = item.querySelector('.badge');
        if (badge) badge.textContent = displayType;

        const contentNode = item.querySelector('p.text-break');
        if (contentNode) {
            contentNode.innerHTML = this.escapeHtml(section.content || '').replace(/\n/g, '<br>');
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
