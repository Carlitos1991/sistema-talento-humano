document.addEventListener('DOMContentLoaded', () => {
    const modal = document.getElementById('roleModalOverlay');
    const form = document.getElementById('roleForm');
    const title = document.getElementById('roleModalTitle');
    const tableContainer = document.getElementById('table-content-wrapper');
    const searchInput = document.getElementById('table-search');

    if (!modal || !form) return;

    const permissionCheckboxes = () => form.querySelectorAll('.perm-check');

    // Cerrar modal
    window.closeRoleModal = () => {
        modal.classList.add('hidden');
        form.reset();
        permissionCheckboxes().forEach(cb => {
            cb.checked = false;
        });
        resetDashboardType();
        resetToggleButtonsText();
    };

    const openRoleModal = () => {
        modal.classList.remove('hidden');
    };

    const resetDashboardType = () => {
        form.querySelectorAll('input[name="dashboard_type"]').forEach(input => {
            input.checked = false;
        });
    };

    const resetToggleButtonsText = () => {
        document.querySelectorAll('[data-toggle-module]').forEach(btn => {
            btn.innerHTML = '<i class="fa-solid fa-check"></i> Marcar Todo';
        });
    };

    // Abrir Crear Rol
    const openCreate = () => {
        form.reset();
        permissionCheckboxes().forEach(cb => {
            cb.checked = false;
        });
        resetDashboardType();
        resetToggleButtonsText();
        form.action = form.dataset.createUrl;
        if (title) title.textContent = 'Crear Nuevo Perfil';
        openRoleModal();
    };

    // Abrir Editar Rol vía AJAX
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
            resetToggleButtonsText();

            // Marcar checkboxes asignados
            const assignedIds = (data.data.permissions || []).map(Number);
            permissionCheckboxes().forEach(checkbox => {
                checkbox.checked = assignedIds.includes(Number(checkbox.value));
            });

            // Asignar nombre del rol
            const nameInput = form.querySelector('[name="name"]');
            if (nameInput) nameInput.value = data.data.name || '';

            // Asignar tipo de dashboard
            resetDashboardType();
            if (data.data.dashboard_type) {
                const dashboardInput = form.querySelector(
                    `[name="dashboard_type"][value="${data.data.dashboard_type}"]`
                );
                if (dashboardInput) dashboardInput.checked = true;
            }

            form.action = url;
            if (title) title.textContent = 'Configurar Rol';
            openRoleModal();
        } catch (error) {
            console.error('Error al cargar el perfil:', error);
            if (typeof showToast === 'function') {
                showToast(error.message || 'No se pudo cargar el perfil.', 'error');
            }
        }
    };

    // Botón Nuevo Rol
    document.getElementById('btn-add-role')?.addEventListener('click', openCreate);

    // Click en botón Editar Rol en la tabla (delegación para soportar AJAX)
    document.getElementById('table-app')?.addEventListener('click', event => {
        const button = event.target.closest('.btn-edit-role[data-url]');
        if (button) {
            event.preventDefault();
            openEdit(button.dataset.url);
        }
    });

    // Envío del Formulario vía submitAjaxForm global
    form.addEventListener('submit', event => {
        if (typeof window.submitAjaxForm === 'function') {
            window.submitAjaxForm(event, () => {
                closeRoleModal();
                fetchRoles(searchInput?.value || '');
            });
        }
    });

    // Plantillas Rápidas (Chips)
    document.querySelectorAll('[data-permission-template]').forEach(input => {
        input.addEventListener('change', () => {
            const template = input.dataset.permissionTemplate;
            permissionCheckboxes().forEach(cb => {
                cb.checked = false;
            });

            const selectors = {
                manager: '.perm-check',
                creator: '.perm-view, .perm-add, .perm-change',
                editor: '.perm-view, .perm-change',
                read: '.perm-view'
            };

            const targetSelector = selectors[template];
            if (targetSelector) {
                form.querySelectorAll(targetSelector).forEach(cb => {
                    cb.checked = true;
                });
            }
        });
    });

    // MARCAR / DESMARCAR TODO POR MÓDULO (Lógica Corregida)
    document.addEventListener('click', event => {
        const button = event.target.closest('[data-toggle-module]');
        if (!button) return;

        event.preventDefault();

        const moduleIndex = button.dataset.toggleModule;
        const table = document.querySelector(`.module-table-${moduleIndex}`);
        if (!table) return;

        const checkboxes = table.querySelectorAll('.perm-check');
        if (!checkboxes.length) return;

        // Si AL MENOS UNO está desmarcado, se marca TODO.
        // Si TODOS ya estaban marcados, se desmarca TODO.
        const shouldCheckAll = Array.from(checkboxes).some(cb => !cb.checked);

        checkboxes.forEach(cb => {
            cb.checked = shouldCheckAll;
        });

        button.innerHTML = shouldCheckAll
            ? '<i class="fa-solid fa-xmark"></i> Desmarcar'
            : '<i class="fa-solid fa-check"></i> Marcar Todo';
    });

    // Toggle horizontal por fila (columna Admin)
    document.addEventListener('change', event => {
        const checkbox = event.target.closest('[data-toggle-model]');
        if (!checkbox) return;

        const row = checkbox.closest('tr');
        if (!row) return;

        row.querySelectorAll('.perm-check:not(.perm-admin-all)').forEach(item => {
            item.checked = checkbox.checked;
        });
    });

    // Búsqueda AJAX de roles en vivo
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