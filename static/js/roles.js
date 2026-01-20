/* static/js/roles.js */

document.addEventListener('DOMContentLoaded', () => {
    const {createApp, ref} = Vue;
    const mountEl = document.getElementById('role-modal-app');

    // =========================================================
    // 1. APP VUE (Modal de Crear/Editar)
    // =========================================================
    if (mountEl) {
        createApp({
            delimiters: ['[[', ']]'],
            setup() {
                const isVisible = ref(false);
                const isEditing = ref(false);
                const currentId = ref(null);
                const errors = ref({});
                const formElementId = 'roleForm';

                // --- AYUDANTES INTERNOS ---
                const uncheckAll = () => {
                    document.querySelectorAll('.perm-check').forEach(el => el.checked = false);
                };

                // --- GESTIÓN DE CHECKBOX ADMIN POR MODELO ---
                const toggleAllPermsForModel = (event, modelId) => {
                    const isChecked = event.target.checked;
                    const row = event.target.closest('tr');
                    if (row) {
                        row.querySelectorAll('.custom-checkbox:not(.perm-admin-all)').forEach(cb => {
                            cb.checked = isChecked;
                        });
                    }
                };

                // --- FUNCIONES UI ---
                const applyTemplate = (type) => {
                    uncheckAll();
                    if (type === 'manager') {
                        document.querySelectorAll('.perm-check').forEach(el => el.checked = true);
                    } else if (type === 'creator') {
                        document.querySelectorAll('.perm-view, .perm-add, .perm-change').forEach(el => el.checked = true);
                    } else if (type === 'editor') {
                        document.querySelectorAll('.perm-view, .perm-change').forEach(el => el.checked = true);
                    } else if (type === 'read') {
                        document.querySelectorAll('.perm-view').forEach(el => el.checked = true);
                    }
                };

                const toggleModule = (tableIndex) => {
                    const table = document.querySelector(`.module-table-${tableIndex}`);
                    if (table) {
                        const checkboxes = table.querySelectorAll('.perm-check');
                        const allChecked = Array.from(checkboxes).every(c => c.checked);
                        checkboxes.forEach(c => c.checked = !allChecked);
                    }
                };

                // --- APERTURA ---
                const openCreate = () => {
                    isEditing.value = false;
                    currentId.value = null;
                    errors.value = {};
                    const form = document.getElementById(formElementId);
                    if (form) form.reset();
                    uncheckAll();
                    isVisible.value = true;
                    document.body.classList.add('no-scroll');
                };

                const openEdit = async (id) => {
                    isEditing.value = true;
                    currentId.value = id;
                    errors.value = {};
                    const form = document.getElementById(formElementId);
                    if (form) form.reset();
                    uncheckAll();

                    try {
                        const response = await fetch(`/security/roles/update/${id}/`, {
                            headers: {'X-Requested-With': 'XMLHttpRequest'}
                        });
                        const res = await response.json();

                        if (res.success) {
                            const nameInput = document.querySelector('[name="name"]');
                            if (nameInput) nameInput.value = res.data.name;

                            if (res.data.permissions) {
                                res.data.permissions.forEach(permId => {
                                    const chk = document.querySelector(`input[name="permissions[]"][value="${permId}"]`);
                                    if (chk) chk.checked = true;
                                });
                            }
                            isVisible.value = true;
                            document.body.classList.add('no-scroll');
                        }
                    } catch (e) {
                        console.error(e);
                        if (window.Toast) window.Toast.fire({icon: 'error', title: 'Error al cargar rol'});
                    }
                };

                const closeModal = () => {
                    isVisible.value = false;
                    document.body.classList.remove('no-scroll');
                };

                // --- GUARDAR ---
                const submitRole = async () => {
                    const formEl = document.getElementById(formElementId);
                    const formData = new FormData(formEl);
                    let url = '/security/roles/create/';
                    if (isEditing.value) url = `/security/roles/update/${currentId.value}/`;

                    try {
                        const response = await fetch(url, {
                            method: 'POST',
                            body: formData,
                            headers: {'X-CSRFToken': window.getCookie('csrftoken')}
                        });
                        const data = await response.json();

                        if (data.success) {
                            if (window.Toast) window.Toast.fire({icon: 'success', title: data.message});
                            closeModal();
                            // Recargar tabla automáticamente buscando de nuevo
                            fetchRoles(document.getElementById('table-search')?.value || '');
                        } else {
                            errors.value = data.errors;
                            if (window.Toast) window.Toast.fire({icon: 'warning', title: 'Revise el formulario'});
                        }
                    } catch (e) {
                        console.error(e);
                        if (window.Toast) window.Toast.fire({icon: 'error', title: 'Error al guardar'});
                    }
                };

                // Exponer al scope global
                window.roleActions = {openCreate, openEdit};

                return {
                    isVisible, isEditing, errors,
                    closeModal, submitRole,
                    applyTemplate, toggleModule, toggleAllPermsForModel
                };
            }
        }).mount('#role-modal-app');
    }

    // =========================================================
    // 2. LISTENERS DOM (Botones y Tabla)
    // =========================================================

    // Botón Nuevo Rol
    const btnAdd = document.getElementById('btn-add-role');
    if (btnAdd) {
        btnAdd.addEventListener('click', (e) => {
            e.preventDefault();
            if (window.roleActions) window.roleActions.openCreate();
        });
    }

    // Delegación eventos Tabla (Editar)
    const tableApp = document.getElementById('table-app');
    if (tableApp) {
        tableApp.addEventListener('click', (e) => {
            const btnEdit = e.target.closest('.btn-edit-role');
            if (btnEdit && btnEdit.dataset.url) {
                const url = btnEdit.dataset.url;
                const parts = url.split('/').filter(Boolean);
                const id = parts[parts.length - 1];
                if (window.roleActions) window.roleActions.openEdit(id);
            }
        });
    }

    // =========================================================
    // 3. LÓGICA DE BÚSQUEDA (LO QUE FALTABA)
    // =========================================================
    const searchInput = document.getElementById('table-search');
    const tableContainer = document.getElementById('table-content-wrapper');

    // Función Debounce para no saturar al escribir
    function debounce(func, timeout = 300) {
        let timer;
        return (...args) => {
            clearTimeout(timer);
            timer = setTimeout(() => {
                func.apply(this, args);
            }, timeout);
        };
    }

    // Función que hace la petición AJAX
    function fetchRoles(query) {
        // Usamos la URL actual (que es RoleListView) y le pasamos ?q=
        const url = `${window.location.pathname}?q=${encodeURIComponent(query)}`;

        fetch(url, {
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        })
            .then(response => response.text())
            .then(html => {
                if (tableContainer) {
                    tableContainer.innerHTML = html;
                }
            })
            .catch(err => console.error("Error en búsqueda:", err));
    }

    // Listener del Input
    if (searchInput) {
        searchInput.addEventListener('input', debounce((e) => {
            fetchRoles(e.target.value);
        }, 500));
    }
});