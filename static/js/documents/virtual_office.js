/* static/js/documents/virtual_office.js */
(function () {
    'use strict';

    let draggedCard = null;

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

    window.onTaskDelegated = function (data) {
        if (draggedCard) {
            draggedCard.remove();
        }
        window.location.reload();
    };

    document.addEventListener('DOMContentLoaded', initDragAndDrop);
})();