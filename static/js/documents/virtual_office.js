/**
 * Inicializa CKEditor 4 con todas las herramientas de formato en español
 */
window.initCKEditorModal = function () {
    setTimeout(function () {
        const editorTextarea = document.getElementById('documentEditor');
        if (!editorTextarea) return;

        // Si ya había una instancia previa, destruirla limpiamente
        if (typeof CKEDITOR !== 'undefined' && CKEDITOR.instances['documentEditor']) {
            CKEDITOR.instances['documentEditor'].destroy(true);
        }

        if (typeof CKEDITOR !== 'undefined') {
            CKEDITOR.replace('documentEditor', {
                language: 'es',
                height: 'calc(88vh - 280px)',
                versionCheck: false,
                toolbar: [
                    {name: 'document', items: ['Source', '-', 'Print']},
                    {name: 'clipboard', items: ['Undo', 'Redo', '-', 'Cut', 'Copy', 'Paste', 'PasteText']},
                    {name: 'editing', items: ['Find', 'Replace', '-', 'SelectAll']},
                    '/',
                    {
                        name: 'basicstyles',
                        items: ['Bold', 'Italic', 'Underline', 'Strike', 'Subscript', 'Superscript', '-', 'RemoveFormat']
                    },
                    {
                        name: 'paragraph',
                        items: ['NumberedList', 'BulletedList', '-', 'Outdent', 'Indent', '-', 'Blockquote', '-', 'JustifyLeft', 'JustifyCenter', 'JustifyRight', 'JustifyBlock']
                    },
                    {name: 'insert', items: ['Table', 'HorizontalRule', 'SpecialChar']},
                    '/',
                    {name: 'styles', items: ['Styles', 'Format', 'Font', 'FontSize']},
                    {name: 'colors', items: ['TextColor', 'BGColor']},
                    {name: 'tools', items: ['Maximize']}
                ],
                removePlugins: 'elementspath',
                resize_enabled: false
            });
        }

        // Conectar eventos del formulario de respuesta
        const form = document.getElementById('createResponseDocForm');
        if (!form) return;

        // Toggle del campo de contraseña para firma electrónica
        const radios = form.querySelectorAll('input[name="sign_mode"]');
        const certAuthBox = document.getElementById('certAuthBox');
        radios.forEach(radio => {
            radio.addEventListener('change', (e) => {
                if (e.target.value === 'ELECTRONIC') {
                    certAuthBox.classList.remove('hidden');
                } else {
                    certAuthBox.classList.add('hidden');
                }
            });
        });

        // Recálculo dinámico de radicado según nivel y tipo
        const emissionLevel = document.getElementById('emissionLevelSelect');
        const docCategory = document.getElementById('docCategorySelect');
        const filingInput = document.getElementById('filingCodeInput');
        const procedureId = form.dataset.procedureId;

        const updateFilingCode = () => {
            if (!docCategory || !emissionLevel || !filingInput) return;
            const catId = docCategory.value;
            const level = emissionLevel.value;

            fetch(`/documents/next-code/${catId}/?procedure_id=${procedureId}&level=${level}`)
                .then(res => res.json())
                .then(data => {
                    if (data.code) filingInput.value = data.code;
                })
                .catch(err => console.error('Error calculando radicado:', err));
        };

        if (emissionLevel) emissionLevel.addEventListener('change', updateFilingCode);
        if (docCategory) docCategory.addEventListener('change', updateFilingCode);

        // Envío AJAX con actualización previa del contenido desde CKEditor
        form.onsubmit = function (e) {
            e.preventDefault();

            if (typeof CKEDITOR !== 'undefined' && CKEDITOR.instances['documentEditor']) {
                CKEDITOR.instances['documentEditor'].updateElement();
            }

            const formData = new FormData(form);
            const submitBtn = document.getElementById('btnSubmitResponseDoc');
            if (submitBtn) submitBtn.disabled = true;

            const csrfToken = (typeof getCSRF === 'function') ? getCSRF() : '';

            fetch(form.action, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': csrfToken
                }
            })
                .then(res => res.json())
                .then(data => {
                    if (data.success) {
                        if (typeof window.closeModal === 'function') window.closeModal();
                        if (typeof window.showToast === 'function') {
                            window.showToast(data.message, 'success');
                        }

                        if (formData.get('sign_mode') === 'MANUAL' && data.document_id) {
                            window.open(`/documents/detail/${data.document_id}/print/`, '_blank');
                        }

                        setTimeout(() => window.location.reload(), 900);
                    } else {
                        Swal.fire({icon: 'warning', title: 'Atención', text: data.message});
                    }
                })
                .catch(() => {
                    Swal.fire({icon: 'error', title: 'Error', text: 'Error procesando el documento.'});
                })
                .finally(() => {
                    if (submitBtn) submitBtn.disabled = false;
                });
        };
    }, 50);
};