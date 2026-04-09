document.addEventListener('DOMContentLoaded', function () {
    const fileInput = document.querySelector('input[type="file"][name="letterhead"]');
    const previewContainer = document.getElementById('uploadPreviewContainer');
    const previewImage = document.getElementById('uploadPreview');

    if (!fileInput || !previewContainer || !previewImage) {
        return;
    }

    fileInput.addEventListener('change', function (event) {
        const [file] = event.target.files || [];
        if (!file) {
            previewContainer.style.display = 'none';
            previewImage.src = '';
            return;
        }

        const reader = new FileReader();
        reader.onload = function (e) {
            previewImage.src = e.target.result;
            previewContainer.style.display = 'block';
        };
        reader.readAsDataURL(file);
    });
});
