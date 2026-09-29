document.addEventListener('DOMContentLoaded', () => {
    const modal = document.getElementById('roleModalOverlay');
    const form = document.getElementById('roleForm');
    const title = document.getElementById('roleModalTitle');
    const tableContainer = document.getElementById('table-content-wrapper');
    const searchInput = document.getElementById('table-search');

    if (!modal || !form) return;

    const permissionCheckboxes = () => document.querySelectorAll('.perm-check');

    window.closeRoleModal = () => {
        window.closeModal('roleModalOverlay');
        form.reset();
        permissionCheckboxes().forEach(checkbox => {
            checkbox.checked = false;
        });
    };

    const openRoleModal = () => {
        window.openModal('roleModalOverlay');
    };

    const resetDashboardType = () => {
        document.querySelectorAll('input[name="dashboard_type"]').forEach(input => {
            input.checked = false;
        });
    };

    const openCreate = () => {
        form.reset();
        permissionCheckboxes().forEach(checkbox => {
            checkbox.checked = false;
        });
        resetDashboardType();
        form.action = form.dataset.createUrl;
        title.textContent = 'Crear Nuevo Perfil';
        openRoleModal();
    };

    const openEdit = async (url) => {
        try {
            const response = await fetch(url, {
                headers: {'X-Requested-With': 'XMLHttpRequest'}
            });
            const data = await response.json();

            if (!response.ok || !data.success) {
                throw new Error(data.message || 'No se pudo cargar el perfil.');
            }

            form.reset();
            permissionCheckboxes().forEach(checkbox => {
                checkbox.checked = data.data.permissions.includes(Number(checkbox.value));
            });

            const nameInput = form.querySelector('[name="name"]');
            if (nameInput) nameInput.value = data.data.name || '';

            resetDashboardType();
            if (data.data.dashboard_type) {
                const dashboardInput = form.querySelector(
                    `[name="dashboard_type"][value="${data.data.dashboard_type}"]`
                );
                if (dashboardInput) dashboardInput.checked = true;
            }

            form.action = url;
            title.textContent = 'Configurar Perfil de Acceso';
            openRoleModal();
        } catch (error) {
            console.error('Error al cargar el perfil:', error);
            showToast(error.message || 'No se pudo cargar el perfil.', 'error');
        }
    };

    document.getElementById('btn-add-role')?.addEventListener('click', openCreate);

    document.getElementById('table-app')?.addEventListener('click', event => {
        const button = event.target.closest('.btn-edit-role[data-url]');
        if (button) openEdit(button.dataset.url);
    });

    form.addEventListener('submit', event => {
        window.submitAjaxForm(event, () => {
            closeRoleModal();
            fetchRoles(searchInput?.value || '');
        });
    });

    document.querySelectorAll('[data-permission-template]').forEach(input => {
        input.addEventListener('change', () => {
            permissionCheckboxes().forEach(checkbox => {
                checkbox.checked = false;
            });

            const selectors = {
                manager: '.perm-check',
                creator: '.perm-view, .perm-add, .perm-change',
                editor: '.perm-view, .perm-change',
                read: '.perm-view'
            };
            document.querySelectorAll(selectors[input.dataset.permissionTemplate] || '')
                .forEach(checkbox => checkbox.checked = true);
        });
    });

    document.addEventListener('click', event => {
        const button = event.target.closest('[data-toggle-module]');
        if (!button) return;

        const table = document.querySelector(`.module-table-${button.dataset.toggleModule}`);
        if (!table) return;

        const checkboxes = table.querySelectorAll('.perm-check');
        const allChecked = [...checkboxes].every(checkbox => checkbox.checked);
        checkboxes.forEach(checkbox => checkbox.checked = !allChecked);
    });

    document.addEventListener('change', event => {
        const checkbox = event.target.closest('[data-toggle-model]');
        if (!checkbox) return;

        const row = checkbox.closest('tr');
        row?.querySelectorAll('.custom-checkbox:not(.perm-admin-all)')
            .forEach(item => item.checked = checkbox.checked);
    });

    function fetchRoles(query) {
        const url = `${window.location.pathname}?q=${encodeURIComponent(query)}`;
        fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
            .then(response => response.text())
            .then(html => {
                if (tableContainer) tableContainer.innerHTML = html;
            })
            .catch(error => console.error('Error en búsqueda:', error));
    }

    let searchTimeout;
    searchInput?.addEventListener('input', event => {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => fetchRoles(event.target.value), 300);
    });
});
