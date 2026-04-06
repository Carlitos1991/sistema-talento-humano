(function () {
    function bindSearchAutoSubmit(formId) {
        const form = document.getElementById(formId);
        if (!form) {
            return;
        }

        const input = form.querySelector('input[name="q"]');
        if (!input) {
            return;
        }

        let timer = null;
        input.addEventListener('input', function () {
            clearTimeout(timer);
            timer = setTimeout(function () {
                form.submit();
            }, 450);
        });
    }

    function bindUploadButtonState() {
        const forms = document.querySelectorAll('.archive-upload-form');
        forms.forEach(function (form) {
            form.addEventListener('submit', function () {
                const button = form.querySelector('button[type="submit"]');
                if (button) {
                    button.disabled = true;
                    button.textContent = 'Subiendo...';
                }
            });
        });
    }

    function bindLoanFilterAutoSubmit() {
        const form = document.getElementById('archiveLoanFilterForm');
        if (!form) {
            return;
        }

        const searchInput = form.querySelector('input[name="q"]');
        const statusSelect = form.querySelector('select[name="status"]');

        if (statusSelect) {
            statusSelect.addEventListener('change', function () {
                form.submit();
            });
        }

        if (searchInput) {
            let timer = null;
            searchInput.addEventListener('input', function () {
                clearTimeout(timer);
                timer = setTimeout(function () {
                    form.submit();
                }, 450);
            });
        }
    }

    document.addEventListener('DOMContentLoaded', function () {
        bindSearchAutoSubmit('archiveTypeSearchForm');
        bindLoanFilterAutoSubmit();
        bindUploadButtonState();
    });
})();
