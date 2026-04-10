document.addEventListener('DOMContentLoaded', function () {
    const configModal = document.getElementById('configGeneralModal');
    const openConfigBtn = document.getElementById('btn-open-config-modal');
    const closeConfigButtons = document.querySelectorAll('.js-close-config-modal');

    if (configModal && openConfigBtn) {
        openConfigBtn.addEventListener('click', function () {
            configModal.classList.remove('hidden');
            document.body.classList.add('modal-open');
        });

        closeConfigButtons.forEach((button) => {
            button.addEventListener('click', function () {
                configModal.classList.add('hidden');
                document.body.classList.remove('modal-open');
            });
        });

        configModal.addEventListener('click', function (event) {
            if (event.target === configModal) {
                configModal.classList.add('hidden');
                document.body.classList.remove('modal-open');
            }
        });

        document.addEventListener('keydown', function (event) {
            if (event.key === 'Escape' && !configModal.classList.contains('hidden')) {
                configModal.classList.add('hidden');
                document.body.classList.remove('modal-open');
            }
        });

        if (configModal.dataset.openOnLoad === '1') {
            configModal.classList.remove('hidden');
            document.body.classList.add('modal-open');
        }
    }

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
