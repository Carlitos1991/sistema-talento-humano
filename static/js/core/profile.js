/* static/js/core/profile.js */

document.addEventListener('DOMContentLoaded', () => {
    initAvatarPreview();
    initSignatureUploadForm();
});

/**
 * Muestra la vista previa de la fotografía seleccionada antes de guardar.
 */
function initAvatarPreview() {
    const fileInput = document.getElementById('id_photo');
    if (!fileInput) return;

    fileInput.addEventListener('change', function () {
        if (!this.files || !this.files[0]) return;

        const reader = new FileReader();
        reader.onload = (event) => {
            const preview = document.getElementById('avatarPreview');
            const placeholder = document.getElementById('avatarPlaceholder');

            if (preview) {
                preview.src = event.target.result;
                preview.classList.remove('hidden');
            }

            if (placeholder) {
                placeholder.classList.add('hidden');
            }
        };

        reader.readAsDataURL(this.files[0]);
    });
}

/**
 * Vincula el envío AJAX del certificado de firma electrónica sin atributos onsubmit inline.
 */
function initSignatureUploadForm() {
    const signatureForm = document.getElementById('signatureProfileForm');
    if (!signatureForm || typeof submitAjaxForm !== 'function') return;

    signatureForm.addEventListener('submit', (event) => {
        submitAjaxForm(event, () => location.reload());
    });
}