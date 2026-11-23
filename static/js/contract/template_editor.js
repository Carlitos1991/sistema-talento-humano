/**
 * SIGETH - Editor Enriquecido de Plantillas Contractuales
 */
(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', () => {
        const app = document.getElementById('contract-template-editor-app');
        if (!app) return;

        const saveUrl = app.dataset.saveUrl;
        const previewUrl = app.dataset.previewUrl;
        const editor = document.getElementById('contractTemplateRichEditor');
        const btnSave = document.getElementById('btn-save-template-body');
        const toolbar = document.getElementById('wysiwyg-toolbar');
        const variablesBar = document.getElementById('template-variables-bar');
        const previewBox = document.getElementById('preview');

        let savedRange = null;
        let previewTimer = null;

        function getCsrfToken() {
            if (typeof window.getCSRF === 'function') return window.getCSRF();
            const hidden = document.querySelector('[name=csrfmiddlewaretoken]');
            if (hidden && hidden.value) return hidden.value;
            const match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
            return match ? decodeURIComponent(match[1]) : '';
        }

        function notify(message, icon = 'success') {
            if (typeof window.showToast === 'function') {
                window.showToast(message, icon);
            }
        }

        function saveSelection() {
            const sel = window.getSelection();
            if (sel && sel.rangeCount > 0) {
                const range = sel.getRangeAt(0);
                if (editor && editor.contains(range.commonAncestorContainer)) {
                    savedRange = range.cloneRange();
                }
            }
        }

        function insertTextAtCursor(text) {
            if (!editor) return;
            editor.focus();
            const sel = window.getSelection();
            if (savedRange && sel) {
                sel.removeAllRanges();
                sel.addRange(savedRange);
            }

            if (sel && sel.rangeCount > 0) {
                const range = sel.getRangeAt(0);
                range.deleteContents();
                const textNode = document.createTextNode(text);
                range.insertNode(textNode);
                range.setStartAfter(textNode);
                range.setEndAfter(textNode);
                sel.removeAllRanges();
                sel.addRange(range);
                savedRange = range.cloneRange();
            } else {
                editor.appendChild(document.createTextNode(text));
            }
        }

        async function refreshPreview() {
            if (!previewBox || !previewUrl) return;
            try {
                const response = await fetch(previewUrl, {
                    headers: {'X-Requested-With': 'XMLHttpRequest'}
                });
                const data = await response.json();
                if (data.preview) {
                    previewBox.innerHTML = data.preview;
                }
            } catch (error) {
                console.error('Error cargando vista previa:', error);
            }
        }

        async function saveTemplateBody(silent = false) {
            if (!editor || !saveUrl) return;
            const htmlContent = editor.innerHTML.trim();
            const originalBtnHtml = btnSave ? btnSave.innerHTML : '';

            if (btnSave) {
                btnSave.disabled = true;
                btnSave.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Guardando...';
            }

            try {
                const response = await fetch(saveUrl, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken(),
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    body: JSON.stringify({content: htmlContent})
                });
                const data = await response.json();

                if (response.ok && data.success) {
                    if (!silent) {
                        notify(data.message || 'Guardado correctamente.', 'success');
                    }
                    await refreshPreview();
                } else {
                    notify(data.error || 'No se pudo guardar.', 'error');
                }
            } catch (error) {
                notify('Error de comunicación con el servidor.', 'error');
            } finally {
                if (btnSave) {
                    btnSave.disabled = false;
                    btnSave.innerHTML = originalBtnHtml;
                }
            }
        }

        if (editor) {
            editor.addEventListener('keyup', saveSelection);
            editor.addEventListener('mouseup', saveSelection);
            editor.addEventListener('blur', saveSelection);
            editor.addEventListener('input', () => {
                const bodyPreview = previewBox?.querySelector('.contract-preview-body');
                if (bodyPreview) {
                    bodyPreview.innerHTML = editor.innerHTML;
                }
                clearTimeout(previewTimer);
                previewTimer = setTimeout(() => {
                    saveTemplateBody(true);
                }, 4000);
            });
        }

        if (toolbar) {
            toolbar.addEventListener('click', (e) => {
                const btn = e.target.closest('.wysiwyg-btn');
                if (!btn || !editor) return;
                e.preventDefault();
                editor.focus();
                document.execCommand(btn.dataset.cmd, false, null);
                saveSelection();
            });
        }

        if (variablesBar) {
            variablesBar.addEventListener('click', (e) => {
                const chip = e.target.closest('.js-insert-variable');
                if (!chip) return;
                const placeholder = chip.dataset.placeholder || '';
                if (placeholder) {
                    insertTextAtCursor(placeholder);
                }
            });
        }

        if (btnSave) {
            btnSave.addEventListener('click', (e) => {
                e.preventDefault();
                clearTimeout(previewTimer);
                saveTemplateBody();
            });
        }

        refreshPreview();
    });
})();