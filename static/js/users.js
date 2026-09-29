/**
 * SIGETH - Módulo de Usuarios (Security)
 * Controlador Vanilla JavaScript basado en el estándar de person.js.
 */

document.addEventListener('DOMContentLoaded', () => {
    initUserSearch();
    initUserPagination();
    initCredentialsModalHandler();
});

let currentPage = 1;

function initUserSearch() {
    const form = document.getElementById('userFilterForm');
    const btnToggle = document.getElementById('btn-toggle-advanced');
    const btnClear = document.getElementById('btn-clear-search');
    const searchInput = document.getElementById('table-search-user');

    if (btnToggle) {
        btnToggle.addEventListener('click', () => {
            const container = document.getElementById('advanced-search-container');
            const icon = document.getElementById('icon-toggle-advanced');
            if (!container) return;

            const isHidden = container.classList.toggle('hidden');
            if (icon) {
                icon.classList.toggle('fa-chevron-up', !isHidden);
                icon.classList.toggle('fa-chevron-down', isHidden);
            }
        });
    }

    if (form) {
        form.addEventListener('submit', (e) => {
            e.preventDefault();
            currentPage = 1;
            fetchUsers(currentPage);
        });
    }

    if (btnClear) {
        btnClear.addEventListener('click', () => {
            if (form) form.reset();
            const container = document.getElementById('advanced-search-container');
            const icon = document.getElementById('icon-toggle-advanced');
            if (container) container.classList.add('hidden');
            if (icon) {
                icon.classList.remove('fa-chevron-up');
                icon.classList.add('fa-chevron-down');
            }
            currentPage = 1;
            fetchUsers(1);
        });
    }

    // Búsqueda al presionar Enter en el input de texto
    if (searchInput) {
        searchInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                currentPage = 1;
                fetchUsers(currentPage);
            }
        });
    }
}

/**
 * Delegación global para los botones del paginador con data-page
 */
function initUserPagination() {
    document.addEventListener('click', (e) => {
        const btn = e.target.closest('#js-pagination .page-btn[data-page]');
        if (!btn || btn.classList.contains('disabled')) return;

        e.preventDefault();
        const page = parseInt(btn.dataset.page, 10);
        if (page && page !== currentPage) {
            currentPage = page;
            fetchUsers(currentPage);
        }
    });

    document.addEventListener('keydown', (e) => {
        const input = e.target.closest('#js-pagination .page-input');
        if (!input || e.key !== 'Enter') return;

        e.preventDefault();
        goToUserPage(input);
    });

    document.addEventListener('change', (e) => {
        const input = e.target.closest('#js-pagination .page-input');
        if (input) goToUserPage(input);
    });
}

function goToUserPage(input) {
    const page = Number.parseInt(input.value, 10);
    const totalPages = Number.parseInt(input.dataset.totalPages, 10);

    if (!Number.isInteger(page) || page < 1 || page > totalPages) {
        input.value = currentPage;
        return;
    }

    if (page !== currentPage) {
        currentPage = page;
        fetchUsers(currentPage);
    }
}

/**
 * Petición AJAX unificada para recargar el partial
 */
function fetchUsers(page = 1) {
    const form = document.getElementById('userFilterForm');
    const params = new URLSearchParams();

    if (form) {
        const formData = new FormData(form);
        for (const [key, value] of formData.entries()) {
            if (value && value.trim() !== '') {
                params.append(key, value.trim());
            }
        }
    }

    params.set('page', page);

    fetch(`${window.location.pathname}?${params.toString()}`, {
        headers: {'X-Requested-With': 'XMLHttpRequest'}
    })
        .then(res => res.text())
        .then(html => {
            const wrapper = document.getElementById('table-content-wrapper');
            if (wrapper) {
                wrapper.innerHTML = html;

                // Inicializar TableManager sin que duplique el paginador
                const table = wrapper.querySelector('.managed-table');
                if (table && window.TableManager && !table._tableManager) {
                    new window.TableManager(table);
                }
            }
        })
        .catch(err => console.error('Error al cargar usuarios:', err));
}

/**
 * Envío de credenciales dentro del modal inyectado
 */
function initCredentialsModalHandler() {
    document.addEventListener('submit', (e) => {
        const form = e.target.closest('#credentialsForm');
        if (!form) return;

        window.submitAjaxForm(e, (data) => {
            window.closeModal();
            if (data && data.require_logout) {
                window.location.reload();
            } else {
                fetchUsers(currentPage);
            }
        });
    });
}