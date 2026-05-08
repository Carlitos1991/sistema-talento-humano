document.addEventListener('DOMContentLoaded', function () {
    const urlList = document.getElementById('url-list').value;
    const notificationsWrapper = document.getElementById('latest-notifications-wrapper');
    const monthSelect = document.getElementById('notifications-month');
    const yearInput = document.getElementById('notifications-year');

    // 1. Escuchar cambios en los filtros
    if (monthSelect) monthSelect.addEventListener('change', () => fetchHistoryPage(1));
    if (yearInput) yearInput.addEventListener('change', () => fetchHistoryPage(1));

    // 2. Función principal de carga
    function fetchHistoryPage(page) {
        const params = new URLSearchParams();
        params.set('page', page);

        if (monthSelect && monthSelect.value) params.set('notifications_month', monthSelect.value);
        if (yearInput && yearInput.value) params.set('notifications_year', yearInput.value);

        fetch(`${urlList}?${params.toString()}`, {
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        })
            .then(res => res.json())
            .then(data => {
                if (notificationsWrapper && data.html) {
                    notificationsWrapper.innerHTML = data.html;
                    // Re-vincular eventos si es necesario
                    bindNotificationPagination();
                }
            })
            .catch(err => console.error('Error cargando historial:', err));
    }

    // 3. Paginación
    function bindNotificationPagination() {
        const paginationContainer = document.getElementById('notifications-js-pagination');
        if (!paginationContainer) return;

        paginationContainer.addEventListener('click', function (e) {
            const btn = e.target.closest('button');
            if (!btn || btn.disabled) return;

            let targetPage = 1;
            const currentPage = parseInt(document.getElementById('notifications-page-input').value);

            if (btn.id === 'notifications-btn-prev') targetPage = currentPage - 1;
            else if (btn.id === 'notifications-btn-next') targetPage = currentPage + 1;
            else if (btn.id === 'notifications-btn-first') targetPage = 1;
            else if (btn.id === 'notifications-btn-last') targetPage = parseInt(document.getElementById('notifications-page-input').max);

            fetchHistoryPage(targetPage);
        });
    }

    bindNotificationPagination();
});