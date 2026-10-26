/* static/js/documents/virtual_office.js */
(function () {
    'use strict';

    let draggedCard = null;

    /**
     * Obtiene el token CSRF desde cookies o función global
     */
    function getCsrfToken() {
        if (typeof window.getCSRF === 'function') {
            return window.getCSRF();
        }
        const cookie = document.cookie.split('; ').find(row => row.startsWith('csrftoken='));
        return cookie ? cookie.split('=')[1] : '';
    }

    /**
     * Inicializa eventos Drag & Drop entre tarjetas de trámites y áreas destino
     */
    function initDragAndDrop() {
        const cards = document.querySelectorAll('.procedure-card');
        const dropZones = document.querySelectorAll('.drop-zone-card');

        cards.forEach(card => {
            card.addEventListener('dragstart', (e) => {
                draggedCard = card;
                card.classList.add('dragging');
                e.dataTransfer.setData('text/plain', card.dataset.procedureId);
                e.dataTransfer.effectAllowed = 'move';
            });

            card.addEventListener('dragend', () => {
                card.classList.remove('dragging');
                draggedCard = null;
            });
        });

        dropZones.forEach(zone => {
            zone.addEventListener('dragover', (e) => {
                e.preventDefault();
                e.dataTransfer.dropEffect = 'move';
                zone.classList.add('drop-hover');
            });

            zone.addEventListener('dragleave', () => {
                zone.classList.remove('drop-hover');
            });

            zone.addEventListener('drop', (e) => {
                e.preventDefault();
                zone.classList.remove('drop-hover');

                if (!draggedCard) return;

                const procedureId = draggedCard.dataset.procedureId;
                const unitId = zone.dataset.unitId;

                if (procedureId && unitId) {
                    window.openAjaxModal(`/documents/delegate/modal/?procedure_id=${procedureId}&unit_id=${unitId}`);
                }
            });
        });
    }

    /**
     * Callback invocado tras confirmar la delegación y sumilla en el modal
     */
    window.onTaskDelegated = function (data) {
        if (draggedCard) {
            draggedCard.remove();
        }
        if (typeof window.showToast === 'function') {
            window.showToast(data.message || 'Trámite derivado exitosamente.', 'success');
        }
        setTimeout(() => {
            window.location.reload();
        }, 800);
    };

    /**
     * Legaliza la sumilla con firma electrónica (.p12 en memoria)
     */
    window.signSumillaElectronically = function (taskId, procedureCode) {
        Swal.fire({
            title: `Legalizar Sumilla - ${procedureCode}`,
            text: 'Ingrese la contraseña de su firma electrónica (.p12) para estampar la disposición oficial.',
            icon: 'info',
            input: 'password',
            inputPlaceholder: 'Contraseña de su certificado digital...',
            inputAttributes: {
                autocapitalize: 'off',
                autocorrect: 'off'
            },
            showCancelButton: true,
            confirmButtonText: 'Firmar y Legalizar',
            cancelButtonText: 'Cancelar',
            customClass: {
                confirmButton: 'swal2-confirm btn-swal-success',
                cancelButton: 'swal2-cancel btn-swal-cancel'
            },
            showLoaderOnConfirm: true,
            preConfirm: (password) => {
                if (!password) {
                    Swal.showValidationMessage('Debe ingresar la contraseña del certificado.');
                    return false;
                }

                const formData = new FormData();
                formData.append('password', password);

                return fetch(`/documents/task/sumilla/sign/${taskId}/`, {
                    method: 'POST',
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest',
                        'X-CSRFToken': getCsrfToken()
                    },
                    body: formData
                })
                    .then(response => {
                        if (!response.ok) {
                            return response.json().then(data => {
                                throw new Error(data.message || 'Error validando firma electrónica.');
                            });
                        }
                        return response.json();
                    })
                    .catch(error => {
                        Swal.showValidationMessage(error.message || 'Error de comunicación.');
                    });
            },
            allowOutsideClick: () => !Swal.isLoading()
        }).then((result) => {
            if (result.isConfirmed && result.value?.success) {
                Swal.fire({
                    icon: 'success',
                    title: 'Sumilla Legalizada',
                    text: result.value.message || 'La sumilla ha sido firmada electrónicamente.',
                    timer: 2000,
                    showConfirmButton: false
                }).then(() => {
                    window.location.reload();
                });
            }
        });
    };

    document.addEventListener('DOMContentLoaded', initDragAndDrop);
})();