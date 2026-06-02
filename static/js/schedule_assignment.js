document.addEventListener('DOMContentLoaded', () => {
    const app = document.getElementById('employee-schedule-app');
    if (!app) return;

    const tableContainer = document.getElementById('table-content-wrapper');
    const searchInput = document.getElementById('table-search');
    const partialUrl = document.getElementById('url-partial')?.value || '/schedule/assignment/partial-table/';
    const modalOverlay = document.getElementById('customModal');
    const modalContent = document.getElementById('modal-dynamic-content');
    const pageInfo = document.getElementById('page-info');
    const btnFirst = document.getElementById('btn-first');
    const btnPrev = document.getElementById('btn-prev');
    const btnNext = document.getElementById('btn-next');
    const btnLast = document.getElementById('btn-last');
    const pageInput = document.getElementById('page-input');

    let currentPage = parseInt(app.dataset.currentPage || '1', 10);
    let totalPages = parseInt(app.dataset.totalPages || '1', 10);
    let searchTimer = null;
    let currentSort = { field: 'person__last_name', dir: 'asc' };

    const getCookie = (name) => {
        const cookies = document.cookie ? document.cookie.split('; ') : [];
        for (const cookie of cookies) {
            const [cookieName, ...cookieValue] = cookie.split('=');
            if (cookieName === name) {
                return decodeURIComponent(cookieValue.join('='));
            }
        }
        return '';
    };

    const bindTableManager = () => {
        const table = tableContainer?.querySelector('.managed-table');
        if (table && window.TableManager) {
            try {
                new TableManager(table);
            } catch (err) {
                console.warn('No se pudo inicializar TableManager', err);
            }
        }
    };

    const updatePagination = (pagination) => {
        if (!pagination) return;
        currentPage = pagination.current_page || currentPage;
        totalPages = pagination.total_pages || totalPages;

        if (pageInfo) {
            pageInfo.textContent = `Mostrando ${pagination.start_index || 0} a ${pagination.end_index || 0} de ${pagination.total_count || 0} registros`;
        }
        if (pageInput) {
            pageInput.value = currentPage;
            pageInput.max = totalPages;
        }
        if (btnFirst) btnFirst.disabled = !pagination.has_previous;
        if (btnPrev) btnPrev.disabled = !pagination.has_previous;
        if (btnNext) btnNext.disabled = !pagination.has_next;
        if (btnLast) btnLast.disabled = !pagination.has_next;
    };

    const fetchTable = async (page = 1) => {
        const q = (searchInput?.value || '').trim();
        const params = new URLSearchParams();
        params.set('page', page);
        if (q) params.set('q', q);
        params.set('sort_field', currentSort.field);
        params.set('sort_dir', currentSort.dir);

        try {
            const response = await fetch(`${partialUrl}?${params.toString()}`, {
                headers: {'X-Requested-With': 'XMLHttpRequest'}
            });
            const data = await response.json();
            if (data.table_html && tableContainer) {
                tableContainer.innerHTML = data.table_html;
                bindTableManager();
                updatePagination(data.pagination);
                updateSortUI();
            }
        } catch (error) {
            console.error('Error cargando tabla de asignación de horarios', error);
        }
    };

    const openModal = (html) => {
        if (!modalOverlay || !modalContent) return;
        modalContent.innerHTML = html;
        modalOverlay.classList.remove('hidden');
        document.body.classList.add('modal-open');

        const form = modalContent.querySelector('#employee-schedule-form');
        if (form) {
            form.addEventListener('submit', handleAssignSubmit);
        }
    };

    const closeModal = () => {
        if (!modalOverlay || !modalContent) return;
        modalOverlay.classList.add('hidden');
        modalContent.innerHTML = '';
        document.body.classList.remove('modal-open');
    };

    const openHistory = async (employeeId) => {
        try {
            const response = await fetch(`/schedule/assignment/history/${employeeId}/`, {
                headers: {'X-Requested-With': 'XMLHttpRequest'}
            });
            openModal(await response.text());
        } catch (error) {
            Swal.fire('Error', 'No se pudo cargar el historial', 'error');
        }
    };

    const openChangeModal = async (employeeId) => {
        try {
            const response = await fetch(`/schedule/assignment/change-modal/${employeeId}/`, {
                headers: {'X-Requested-With': 'XMLHttpRequest'}
            });
            openModal(await response.text());
        } catch (error) {
            Swal.fire('Error', 'No se pudo cargar el formulario', 'error');
        }
    };

    const handleAssignSubmit = async (e) => {
        e.preventDefault();
        const form = e.target;
        const formData = new FormData(form);

        try {
            const response = await fetch(form.action, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-CSRFToken': getCookie('csrftoken'),
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });
            const data = await response.json();
            if (response.ok && data.success) {
                closeModal();
                Swal.fire({toast: true, position: 'top-end', icon: 'success', title: data.message || 'Horario asignado correctamente', showConfirmButton: false, timer: 2500});
                fetchTable(currentPage);
            } else {
                const firstError = data.errors ? Object.values(data.errors)[0]?.[0] : 'No se pudo guardar';
                Swal.fire('Atención', firstError || 'No se pudo guardar', 'warning');
            }
        } catch (error) {
            Swal.fire('Error', 'Error de comunicación con el servidor', 'error');
        }
    };

    const updateSortUI = () => {
        document.querySelectorAll('.sortable').forEach(th => {
            th.classList.remove('sort-asc', 'sort-desc');
            if (th.dataset.sortField === currentSort.field) {
                th.classList.add(currentSort.dir === 'asc' ? 'sort-asc' : 'sort-desc');
            }
        });
    };

    if (searchInput) {
        searchInput.addEventListener('input', () => {
            clearTimeout(searchTimer);
            searchTimer = setTimeout(() => fetchTable(1), 300);
        });
    }

    btnFirst?.addEventListener('click', () => fetchTable(1));
    btnPrev?.addEventListener('click', () => {
        if (currentPage > 1) fetchTable(currentPage - 1);
    });
    btnNext?.addEventListener('click', () => {
        if (currentPage < totalPages) fetchTable(currentPage + 1);
    });
    btnLast?.addEventListener('click', () => fetchTable(totalPages));
    pageInput?.addEventListener('change', () => {
        const target = parseInt(pageInput.value, 10);
        if (!Number.isNaN(target)) fetchTable(Math.min(Math.max(target, 1), totalPages));
    });

    tableContainer?.addEventListener('click', (e) => {
        const historyBtn = e.target.closest('.js-view-schedule-history');
        if (historyBtn) {
            e.preventDefault();
            openHistory(historyBtn.dataset.employeeId);
            return;
        }

        const changeBtn = e.target.closest('.js-change-schedule');
        if (changeBtn) {
            e.preventDefault();
            openChangeModal(changeBtn.dataset.employeeId);
            return;
        }

        const sortableHeader = e.target.closest('.sortable');
        if (sortableHeader) {
            const field = sortableHeader.dataset.sortField;
            if (currentSort.field === field) {
                currentSort.dir = currentSort.dir === 'asc' ? 'desc' : 'asc';
            } else {
                currentSort.field = field;
                currentSort.dir = 'asc';
            }
            fetchTable(1);
        }
    });

    modalOverlay?.addEventListener('click', (e) => {
        if (e.target === modalOverlay || e.target.closest('.btn-close-modal') || e.target.closest('.js-close-modal') || e.target.closest('.btn-cancel')) {
            closeModal();
        }
    });

    bindTableManager();
    updateSortUI();
});
