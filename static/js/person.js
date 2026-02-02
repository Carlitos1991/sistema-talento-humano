/* static/js/apps/person.js */

let vueApp = null;

// --- FUNCIONES GLOBALES (Accesibles desde HTML) ---
window.toggleSearchModal = (show) => {
    const el = document.getElementById('modalAdvancedSearch');
    if (el) {
        show ? el.classList.remove('hidden') : el.classList.add('hidden');
        document.body.classList.toggle('no-scroll', show);
    } else {
        console.warn('El modal modalAdvancedSearch no existe en el DOM.');
    }
};

window.applyAdvancedSearch = () => {
    if (vueApp) vueApp.handleAdvancedSearch();
    window.toggleSearchModal(false);
};

window.resetAdvancedSearch = () => {
    document.getElementById('advancedSearchForm')?.reset();
    $('.select2-field').val(null).trigger('change');
    if (vueApp) vueApp.resetFilters();
};

window.changePage = (page) => {
    if (vueApp) vueApp.fetchPeople(page);
};

window.quickFilterStatus = (statusId) => {
    const statusSelect = document.querySelector('select[name="status"]');
    if (statusSelect) {
        statusSelect.value = statusId;
        $(statusSelect).trigger('change');
    }
    if (vueApp) vueApp.applyQuickFilter(statusId);
};


document.addEventListener('DOMContentLoaded', () => {
    const appElement = document.getElementById('personApp');
    if (!appElement) return;

    const {createApp, ref, onMounted} = Vue;
    let urls = {};
    try {
        urls = JSON.parse(appElement.dataset.urls);
    } catch (e) {
        console.error(e);
    }

    const app = createApp({
        setup() {
            // --- 1. DEFINICIÓN DE VARIABLES REACTIVAS ---

            // Filtros y Búsqueda
            const activeFilters = ref({});

            // Vista Rápida
            const loadingQuickView = ref(false);
            const quickViewHtml = ref('');
            const currentDetailUrl = ref('#'); // <--- FALTABA ESTA VARIABLE

            // Formularios (Crear/Editar)
            const isEditing = ref(false);
            const form = ref({});
            const errors = ref({});
            const photoPreview = ref(null);
            const currentId = ref(null);

            // Credenciales
            const credsForm = ref({username: '', password: '', role: ''});
            const credsErrors = ref({});

            // ----------------------------------------------------
            // 2. BÚSQUEDA INMEDIATA (FRONTEND)
            // ----------------------------------------------------
            const initLocalSearch = () => {
                const input = document.getElementById('searchInput');
                if (!input) return;

                // Clonamos el nodo para eliminar listeners viejos y asegurar limpieza
                const newInput = input.cloneNode(true);
                input.parentNode.replaceChild(newInput, input);

                newInput.addEventListener('input', (e) => {
                    const term = e.target.value.toLowerCase().trim();
                    const rows = document.querySelectorAll('#table-body tr');

                    rows.forEach(row => {
                        const text = row.innerText.toLowerCase();
                        if (text.includes(term) || term === '') {
                            row.style.display = '';
                        } else {
                            row.style.display = 'none';
                        }
                    });
                });
            };

            // ----------------------------------------------------
            // 3. BÚSQUEDA AVANZADA & PAGINACIÓN (BACKEND)
            // ----------------------------------------------------
            const fetchPeople = async (page = 1) => {
                const params = new URLSearchParams();
                params.append('page', page);

                // Añadir filtros avanzados activos
                for (const [key, value] of Object.entries(activeFilters.value)) {
                    if (value) params.append(key, value);
                }

                try {
                    const response = await fetch(`${urls.list}?${params.toString()}`, {
                        headers: {'X-Requested-With': 'XMLHttpRequest'}
                    });
                    const data = await response.json();

                    if (data.success) {
                        const container = document.getElementById('tableContainer');
                        if (container) {
                            container.innerHTML = data.html;

                            // Limpiar filtro local visual al cargar nuevos datos
                            const searchInput = document.getElementById('searchInput');
                            if (searchInput) searchInput.value = '';
                        }
                    }
                } catch (error) {
                    console.error("Error fetching data:", error);
                }
            };

            const handleAdvancedSearch = () => {
                const formData = new FormData(document.getElementById('advancedSearchForm'));
                activeFilters.value = Object.fromEntries(formData.entries());
                fetchPeople(1);
            };

            const resetFilters = () => {
                activeFilters.value = {};
                fetchPeople(1);
            };

            const applyQuickFilter = (statusId) => {
                activeFilters.value = {'status': statusId};
                fetchPeople(1);
            };

            // ----------------------------------------------------
            // 4. VISTA RÁPIDA (DELEGACIÓN DE EVENTOS)
            // ----------------------------------------------------
            const initTableListeners = () => {
                const container = document.getElementById('tableContainer');
                if (!container) return;

                container.addEventListener('click', (e) => {
                    const btn = e.target.closest('.btn-quick-view');
                    if (btn) {
                        e.preventDefault();
                        const personId = btn.dataset.id;
                        if (personId) {
                            openQuickView(personId);
                        }
                    }
                });
            };

            const openQuickView = async (id) => {
                loadingQuickView.value = true;
                quickViewHtml.value = '<div class="p-4 text-center text-gray-500">Cargando información...</div>';
                currentDetailUrl.value = `/employee/detail/${id}/`; // Actualiza el link "Ver más"

                const modal = document.getElementById('modalQuickViewOverlay');
                showModal(modal);

                try {
                    const res = await fetch(`/person/quick-view-partial/${id}/`);
                    if (res.ok) {
                        quickViewHtml.value = await res.text();
                    } else {
                        quickViewHtml.value = '<p class="text-error p-4">No se pudo cargar la información.</p>';
                    }
                } catch (e) {
                    quickViewHtml.value = '<p class="text-error p-4">Error de conexión.</p>';
                } finally {
                    loadingQuickView.value = false;
                }
            };

            const closeQuickView = () => {
                hideModal(document.getElementById('modalQuickViewOverlay'));
            };

            // ----------------------------------------------------
            // 5. MODALES Y FORMULARIOS
            // ----------------------------------------------------
            const showModal = (el) => {
                if (el) {
                    el.classList.remove('hidden');
                    document.body.classList.add('no-scroll');
                }
            };
            const hideModal = (el) => {
                if (el) {
                    el.classList.add('hidden');
                    if (document.querySelectorAll('.modal-overlay:not(.hidden)').length === 0) {
                        document.body.classList.remove('no-scroll');
                    }
                }
            };

            const openCreateModal = () => {
                isEditing.value = false;
                currentId.value = null;
                form.value = {};
                errors.value = {};
                photoPreview.value = null;
                document.getElementById('personFormHtml')?.reset();
                showModal(document.getElementById('modalPersonOverlay'));
            };

            const openEditModal = async (id) => {
                isEditing.value = true;
                currentId.value = id;
                errors.value = {};
                try {
                    const res = await fetch(urls.detail.replace('0', id));
                    const json = await res.json();
                    if (json.success) {
                        form.value = json.data;
                        photoPreview.value = json.data.photo_url;
                        showModal(document.getElementById('modalPersonOverlay'));
                    }
                } catch (e) {
                    console.error(e);
                }
            };

            const submitPersonForm = async () => {
                errors.value = {};
                const formData = new FormData(document.getElementById('personFormHtml'));
                const url = isEditing.value ? urls.update.replace('0', currentId.value) : urls.create;

                try {
                    const res = await fetch(url, {
                        method: 'POST',
                        body: formData,
                        headers: {'X-CSRFToken': window.getCookie('csrftoken')}
                    });
                    const data = await res.json();

                    if (data.success) {
                        if (window.Toast) window.Toast.fire({icon: 'success', title: data.message});
                        hideModal(document.getElementById('modalPersonOverlay'));
                        fetchPeople(1); // Recarga la tabla en página 1
                    } else {
                        errors.value = data.errors;
                        if (window.Toast) window.Toast.fire({icon: 'warning', title: 'Revise el formulario'});
                    }
                } catch (e) {
                    console.error(e);
                    if (window.Toast) window.Toast.fire({icon: 'error', title: 'Error servidor'});
                }
            };

            // Credenciales
            const openCredsModal = (id) => {
                currentId.value = id;
                credsForm.value = {username: '', password: '', role: ''};
                credsErrors.value = {};
                showModal(document.getElementById('modalCredentialsOverlay'));
            };

            const submitCredsForm = async () => {
                credsErrors.value = {};
                const formData = new FormData();
                formData.append('username', credsForm.value.username);
                formData.append('password', credsForm.value.password);
                formData.append('role', credsForm.value.role);

                try {
                    const res = await fetch(urls.createCredentials.replace('0', currentId.value), {
                        method: 'POST',
                        body: formData,
                        headers: {'X-CSRFToken': window.getCookie('csrftoken')}
                    });
                    const data = await res.json();

                    if (data.success) {
                        if (window.Toast) window.Toast.fire({icon: 'success', title: data.message});
                        hideModal(document.getElementById('modalCredentialsOverlay'));
                        fetchPeople(1);
                    } else {
                        credsErrors.value = data.errors;
                    }
                } catch (e) {
                    if (window.Toast) window.Toast.fire({icon: 'error', title: 'Error creando credenciales'});
                }
            };

            const closeModal = () => {
                hideModal(document.getElementById('modalPersonOverlay'));
                hideModal(document.getElementById('modalCredentialsOverlay'));
            };

            // ----------------------------------------------------
            // CICLO DE VIDA
            // ----------------------------------------------------
            onMounted(() => {
                initLocalSearch();
                initTableListeners();

                $('.select2-field').select2({
                    dropdownParent: $('#modalAdvancedSearch')
                });
            });

            return {
                // Métodos
                fetchPeople, handleAdvancedSearch, resetFilters, applyQuickFilter,
                openCreateModal, openEditModal, submitPersonForm,
                openCredsModal, submitCredsForm, closeModal,
                openQuickView, closeQuickView,

                // Estado Reactivo (Devolvemos las constantes, NO re-creamos refs)
                activeFilters,
                loadingQuickView, quickViewHtml, currentDetailUrl,
                isEditing, form, errors, photoPreview,
                credsForm, credsErrors
            };
        }
    });

    vueApp = app.mount('#personApp');
});