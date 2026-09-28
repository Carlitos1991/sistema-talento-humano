/**
 * SIGETH - Catálogo de Tipos de Acción de Personal
 * Conectado con main.js (openAjaxModal, submitAjaxForm, deleteRecordAjax, refreshCurrentTable)
 */
document.addEventListener('DOMContentLoaded', () => {

    // 1. Botón Nuevo Tipo
    const btnNew = document.getElementById('btnNewActionType');
    if (btnNew) {
        btnNew.addEventListener('click', (e) => {
            e.preventDefault();
            if (typeof window.openAjaxModal === 'function') {
                window.openAjaxModal('/personnel_actions/types/create/');
            }
        });
    }

    // 2. Buscador en tiempo real con debounce
    const searchInput = document.getElementById('table-search');
    if (searchInput) {
        let debounceTimer;
        searchInput.addEventListener('input', (e) => {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(() => {
                const query = e.target.value.trim();
                const currentUrl = new URL(window.location.href);

                if (query) {
                    currentUrl.searchParams.set('q', query);
                } else {
                    currentUrl.searchParams.delete('q');
                }
                currentUrl.searchParams.set('page', 1);

                window.history.pushState({}, '', currentUrl.toString());

                if (typeof window.refreshCurrentTable === 'function') {
                    window.refreshCurrentTable({q: query, page: 1});
                }
            }, 350);
        });
    }

    // 3. Navegación por input numérico de página
    const handlePageInput = (inputEl) => {
        let pageVal = parseInt(inputEl.value, 10);
        const maxPage = parseInt(inputEl.dataset.maxPage || 1, 10);

        if (isNaN(pageVal) || pageVal < 1) pageVal = 1;
        if (pageVal > maxPage) pageVal = maxPage;

        inputEl.value = pageVal;

        const currentUrl = new URL(window.location.href);
        currentUrl.searchParams.set('page', pageVal);
        window.history.pushState({}, '', currentUrl.toString());

        if (typeof window.refreshCurrentTable === 'function') {
            window.refreshCurrentTable({page: pageVal});
        }
    };

    document.addEventListener('change', (e) => {
        if (e.target.matches('.page-input')) {
            handlePageInput(e.target);
        }
    });

    document.addEventListener('keydown', (e) => {
        if (e.target.matches('.page-input') && e.key === 'Enter') {
            e.preventDefault();
            handlePageInput(e.target);
        }
    });

    // 4. Delegación de Edición y Eliminación
    document.addEventListener('click', (e) => {
        // Editar
        const btnEdit = e.target.closest('.btn-edit-action-type');
        if (btnEdit) {
            e.preventDefault();
            const url = btnEdit.dataset.url;
            if (url && typeof window.openAjaxModal === 'function') {
                window.openAjaxModal(url);
            }
            return;
        }

        // Eliminar
        const btnDelete = e.target.closest('.btn-delete-action-type');
        if (btnDelete) {
            e.preventDefault();
            const url = btnDelete.dataset.url;
            const name = btnDelete.dataset.name || 'este registro';
            if (url && typeof window.deleteRecordAjax === 'function') {
                window.deleteRecordAjax(url, name, () => {
                    if (typeof window.refreshCurrentTable === 'function') {
                        window.refreshCurrentTable();
                    }
                });
            }
        }
    });

    // 5. Envío AJAX del formulario del modal
    document.addEventListener('submit', (e) => {
        const form = e.target;
        if (form.matches('#actionTypeForm')) {
            if (typeof window.submitAjaxForm === 'function') {
                window.submitAjaxForm(e, () => {
                    if (typeof window.refreshCurrentTable === 'function') {
                        window.refreshCurrentTable();
                    }
                });
            }
        }
    });

});