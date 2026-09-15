document.addEventListener('DOMContentLoaded', function () {
    const tableContainer = document.getElementById('table-content-wrapper');
    const modalOverlay = document.getElementById('modal-create-action');
    const modalContentContainer = document.getElementById('modal-body-content');

    // Delegación de eventos de la tabla
    if (tableContainer) {
        tableContainer.addEventListener('click', function (e) {
            const generateBtn = e.target.closest('.js-generate-action');
            if (generateBtn) {
                e.preventDefault();
                openGenerateActionModal(generateBtn.dataset.employeeId);
                return;
            }

            const historyBtn = e.target.closest('.js-view-history');
            if (historyBtn) {
                e.preventDefault();
                window.location.href = `/personnel_actions/history/${historyBtn.dataset.employeeId}/`;
            }
        });
    }

    function openGenerateActionModal(employeeId) {
        fetch(`/personnel_actions/create/?employee_id=${employeeId}`, {
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        })
            .then(res => res.text())
            .then(html => {
                if (modalContentContainer && modalOverlay) {
                    modalContentContainer.innerHTML = html;
                    modalOverlay.classList.remove('hidden');
                    document.body.classList.add('modal-open');
                    initModalPlugins();
                }
            })
            .catch(err => {
                console.error('Error al abrir modal:', err);
                if (typeof Swal !== 'undefined') Swal.fire('Error', 'No se pudo cargar el formulario', 'error');
            });
    }

    function closeModal() {
        if (modalOverlay) modalOverlay.classList.add('hidden');
        if (modalContentContainer) modalContentContainer.innerHTML = '';
        document.body.classList.remove('modal-open');
    }

    window.closeModal = closeModal;

    if (modalOverlay) {
        modalOverlay.addEventListener('click', (e) => {
            if (e.target === modalOverlay) closeModal();
        });
    }

    function initModalPlugins() {
        if (typeof $ !== 'undefined' && $.fn.select2) {
            $('.select2').select2({dropdownParent: $('#modal-create-action'), width: '100%'});
        }
        if (window.PersonnelActionModal && typeof window.PersonnelActionModal.init === 'function') {
            window.PersonnelActionModal.init();
        }
        const form = modalContentContainer?.querySelector('form');
        if (form) {
            form.addEventListener('submit', handleFormSubmit);
        }
        modalContentContainer?.querySelectorAll('.btn-cancel, .btn-close-circle').forEach(btn => {
            btn.addEventListener('click', closeModal);
        });
    }

    function handleFormSubmit(e) {
        e.preventDefault();
        const form = e.target;
        const formData = new FormData(form);

        fetch(form.action, {
            method: 'POST',
            body: formData,
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    Swal.fire({
                        icon: 'success',
                        title: 'Éxito',
                        text: data.message || 'Acción guardada correctamente',
                        timer: 1500,
                        showConfirmButton: false
                    }).then(() => {
                        closeModal();
                        window.location.reload();
                    });
                } else {
                    Swal.fire('Atención', data.message || 'Error al procesar el formulario', 'warning');
                }
            })
            .catch(err => console.error(err));
    }
});