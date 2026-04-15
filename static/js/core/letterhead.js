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

    const bindImagePreview = (inputSelector, previewContainerId, previewImageId, previewEmptyId) => {
        const fileInput = document.querySelector(inputSelector);
        const previewContainer = document.getElementById(previewContainerId);
        const previewImage = document.getElementById(previewImageId);
        const previewEmpty = previewEmptyId ? document.getElementById(previewEmptyId) : null;

        if (!fileInput || !previewContainer || !previewImage) {
            return;
        }

        const originalSrc = previewImage.dataset.originalSrc || previewImage.getAttribute('src') || '';

        const showEmptyState = () => {
            if (previewEmpty) {
                previewEmpty.style.display = 'block';
            }
            previewImage.style.display = 'none';
            previewImage.src = originalSrc;
        };

        const showImage = (src) => {
            if (previewEmpty) {
                previewEmpty.style.display = 'none';
            }
            previewImage.style.display = 'block';
            previewImage.src = src;
        };

        fileInput.addEventListener('change', function (event) {
            const [file] = event.target.files || [];
            if (!file) {
                if (originalSrc) {
                    showImage(originalSrc);
                } else {
                    showEmptyState();
                }
                return;
            }

            const reader = new FileReader();
            reader.onload = function (e) {
                showImage(e.target.result);
            };
            reader.readAsDataURL(file);
        });

        if (originalSrc) {
            showImage(originalSrc);
        } else {
            showEmptyState();
        }
    };

    bindImagePreview('input[type="file"][name="letterhead"]', 'uploadPreviewContainer', 'uploadPreview');
    bindImagePreview('input[type="file"][name="logo"]', 'logoPreviewContainer', 'logoPreview', 'logoPreviewEmpty');
});
