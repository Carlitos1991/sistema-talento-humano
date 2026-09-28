document.addEventListener('DOMContentLoaded', () => {
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

    // Navegación por input numérico de página
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

    // Delegación para modales vía openAjaxModal de main.js
    document.addEventListener('click', (e) => {
        const btnModal = e.target.closest('.btn-vacation-action');
        if (!btnModal) return;

        e.preventDefault();
        const targetUrl = btnModal.dataset.url;

        if (targetUrl && typeof window.openAjaxModal === 'function') {
            window.openAjaxModal(targetUrl);
        }
    });

    // Guardado AJAX para modales
    document.addEventListener('submit', (e) => {
        const form = e.target;
        if (form.matches('#firstVacationForm, #periodForm, .ajax-vacation-form')) {
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