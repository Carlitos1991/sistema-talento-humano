/**
 * SIGETH - Manejo de Configuración General e Identidad Gráfica
 * Vanilla JS: Modal interactivo y Drag & Drop con preview instantáneo.
 */

document.addEventListener('DOMContentLoaded', () => {
    initConfigurationModal();
    initDropzone('dropzoneLogo', 'placeholderLogo', 'previewBoxLogo', 'imgPreviewLogo', 'filenameLogo');
    initDropzone('dropzoneLetterhead', 'placeholderLetterhead', 'previewBoxLetterhead', 'imgPreviewLetterhead', 'filenameLetterhead');
});

function initConfigurationModal() {
    const modal = document.getElementById('configGeneralModal');
    const openBtn = document.getElementById('btn-open-config-modal');
    const closeBtns = document.querySelectorAll('.js-close-config-modal');

    if (!modal) return;

    if (openBtn) {
        openBtn.addEventListener('click', (e) => {
            e.preventDefault();
            modal.classList.remove('hidden');
        });
    }

    closeBtns.forEach((btn) => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            modal.classList.add('hidden');
        });
    });

    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.classList.add('hidden');
        }
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && !modal.classList.contains('hidden')) {
            modal.classList.add('hidden');
        }
    });
}

function initDropzone(dropzoneId, placeholderId, previewBoxId, imgPreviewId, filenameId) {
    const dropzone = document.getElementById(dropzoneId);
    if (!dropzone) return;

    const input = dropzone.querySelector('input[type="file"]');
    const placeholder = document.getElementById(placeholderId);
    const previewBox = document.getElementById(previewBoxId);
    const imgPreview = document.getElementById(imgPreviewId);
    const filename = document.getElementById(filenameId);

    if (!input || !placeholder || !previewBox || !imgPreview) return;

    input.addEventListener('change', (e) => {
        const file = e.target.files && e.target.files[0];
        if (file) {
            const reader = new FileReader();
            reader.onload = (event) => {
                imgPreview.src = event.target.result;
                if (filename) filename.textContent = file.name;
                placeholder.classList.add('d-none');
                previewBox.classList.remove('d-none');
            };
            reader.readAsDataURL(file);
        }
    });

    // Feedback visual al arrastrar archivos
    ['dragenter', 'dragover'].forEach(eventName => {
        dropzone.addEventListener(eventName, () => dropzone.classList.add('dragover'), false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropzone.addEventListener(eventName, () => dropzone.classList.remove('dragover'), false);
    });
}