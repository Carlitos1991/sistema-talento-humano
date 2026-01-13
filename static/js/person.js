/* static/js/apps/person.js */

document.addEventListener('DOMContentLoaded', () => {
    // Verificamos primero si existe el elemento para no ejecutar lógica innecesaria
    const appElement = document.getElementById('personApp');
    if (!appElement) return;

    const {createApp, ref, onMounted} = Vue;

    // 1. LEER CONFIGURACIÓN (Data Attributes)
    let urls = {};
    try {
        if (appElement.dataset.urls) {
            urls = JSON.parse(appElement.dataset.urls);
        } else {
            console.error("Falta atributo data-urls en #personApp");
        }
    } catch (e) {
        console.error("Error al parsear URLs:", e);
    }

    // 2. INICIAR VUE
    createApp({
        setup() {
            // Estado Reactivo
            const isEditing = ref(false);
            const currentId = ref(null);
            const loadingQuickView = ref(false);
            const quickViewHtml = ref('');
            const currentDetailUrl = ref('#');

            // Formularios
            const form = ref({});
            const errors = ref({});
            const photoPreview = ref(null);

            const credsForm = ref({username: '', password: '', role: ''});
            const credsErrors = ref({});

            // --- CICLO DE VIDA ---
            onMounted(() => {
                initTableListeners();
                initSearch();
                initLocationCascading();
            });

            // --- LÓGICA UBICACIONES (CASCADA) ---
            const initLocationCascading = () => {
                const map = {
                    'id_country': 'id_province',
                    'id_province': 'id_canton',
                    'id_canton': 'id_parish'
                };

                Object.keys(map).forEach(sourceId => {
                    const el = document.getElementById(sourceId);
                    if (el) {
                        el.addEventListener('change', (e) => loadLocationChildren(e.target.value, map[sourceId]));
                    }
                });
            };

            const loadLocationChildren = async (parentId, targetSelectId) => {
                const target = document.getElementById(targetSelectId);
                if (!target) return;

                target.innerHTML = '<option value="">Cargando...</option>';

                if (!parentId) {
                    target.innerHTML = '<option value="">-- Seleccione --</option>';
                    return;
                }

                try {
                    if (!urls.locations) throw new Error("URL locations no definida");

                    const response = await fetch(`${urls.locations}?parent_id=${parentId}&format=json`, {
                        headers: {'X-Requested-With': 'XMLHttpRequest'}
                    });
                    const data = await response.json();

                    let options = '<option value="">-- Seleccione --</option>';
                    (Array.isArray(data) ? data : data.data || []).forEach(item => {
                        options += `<option value="${item.id}">${item.name}</option>`;
                    });
                    target.innerHTML = options;

                } catch (error) {
                    console.error("Error cargando ubicaciones:", error);
                    target.innerHTML = '<option value="">Error</option>';
                }
            };

            // --- LISTENERS TABLA (Delegación de eventos) ---
            const initTableListeners = () => {
                const tableContainer = document.getElementById('tableContainer');
                if (!tableContainer) return;

                tableContainer.addEventListener('click', (e) => {
                    // ... otros botones (edit, delete)

                    // Vista Rápida
                    const btnQuick = e.target.closest('.btn-quick-view');
                    if (btnQuick && btnQuick.dataset.id) {
                        openQuickView(btnQuick.dataset.id);
                    }
                });
            };
            const openQuickView = async (id) => {
                loadingQuickView.value = true;
                quickViewHtml.value = '';
                // Preparar URL para el detalle completo (para el paso siguiente)
                currentDetailUrl.value = `/employee/detail/${id}/`;

                const modal = document.getElementById('modalQuickViewOverlay');
                showModal(modal);

                try {
                    const response = await fetch(`/person/quick-view/${id}/`, {
                        headers: {'X-Requested-With': 'XMLHttpRequest'}
                    });
                    if (response.ok) {
                        quickViewHtml.value = await response.text();
                    } else {
                        quickViewHtml.value = '<p class="text-error">Error al cargar la información.</p>';
                    }
                } catch (error) {
                    quickViewHtml.value = '<p class="text-error">Error de conexión.</p>';
                } finally {
                    loadingQuickView.value = false;
                }
            };
            const closeQuickView = () => {
                const modal = document.getElementById('modalQuickViewOverlay');
                hideModal(modal);
            };


            const initSearch = () => {
                const searchInput = document.getElementById('searchInput');
                if (searchInput) {
                    searchInput.addEventListener('input', debounce((e) => {
                        fetchPeople(e.target.value);
                    }, 500));
                }
            };

            // --- API ACTIONS ---
            const fetchPeople = (query) => {
                fetch(`${urls.list}?q=${query}`, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
                    .then(res => res.text())
                    .then(html => {
                        document.getElementById('tableContainer').innerHTML = html;
                    });
            };


            // --- MODALES ACTIONS ---
            // CORRECCIÓN PRINCIPAL: Buscar el elemento DOM DENTRO de la función
            const openCreateModal = () => {
                isEditing.value = false;
                currentId.value = null;
                form.value = {};
                errors.value = {};
                photoPreview.value = null;

                // Reiniciar form visualmente
                document.getElementById('personFormHtml')?.reset();

                // Buscar el modal AHORA (en vivo)
                const modal = document.getElementById('modalPersonOverlay');
                showModal(modal);
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

                        // Carga en cascada
                        const d = json.data;
                        if (d.country) {
                            await loadLocationChildren(d.country, 'id_province');
                            document.getElementById('id_province').value = d.province;
                        }
                        if (d.province) {
                            await loadLocationChildren(d.province, 'id_canton');
                            document.getElementById('id_canton').value = d.canton;
                        }
                        if (d.canton) {
                            await loadLocationChildren(d.canton, 'id_parish');
                            document.getElementById('id_parish').value = d.parish || '';
                        }

                        // Buscar el modal AHORA
                        const modal = document.getElementById('modalPersonOverlay');
                        showModal(modal);
                    }
                } catch (e) {
                    console.error(e);
                    if (window.Toast) window.Toast.fire({icon: 'error', title: 'Error cargando datos'});
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

                        const modal = document.getElementById('modalPersonOverlay');
                        hideModal(modal);

                        fetchPeople(document.getElementById('searchInput')?.value || '');
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

                const modal = document.getElementById('modalCredentialsOverlay');
                showModal(modal);
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

                        const modal = document.getElementById('modalCredentialsOverlay');
                        hideModal(modal);

                        setTimeout(() => fetchPeople(''), 500);
                    } else {
                        credsErrors.value = data.errors;
                    }
                } catch (e) {
                    if (window.Toast) window.Toast.fire({icon: 'error', title: 'Error creando credenciales'});
                }
            };

            // Helpers UI
            const showModal = (el) => {
                if (el) {
                    el.classList.remove('hidden');
                    document.body.classList.add('no-scroll'); // <--- NUEVO: Bloquea fondo
                }
            };
            const hideModal = (el) => {
                if (el) {
                    el.classList.add('hidden');
                    // Solo quitamos no-scroll si NO hay otros modales abiertos
                    // (Por si abres credenciales encima de editar)
                    const openModals = document.querySelectorAll('.modal-overlay:not(.hidden)');
                    if (openModals.length === 0) {
                        document.body.classList.remove('no-scroll'); // <--- NUEVO: Desbloquea
                    }
                }
            };

            const handlePhotoChange = (e) => {
                if (e.target.files[0]) photoPreview.value = URL.createObjectURL(e.target.files[0]);
            };

            const closeModal = () => {
                const m1 = document.getElementById('modalPersonOverlay');
                const m2 = document.getElementById('modalCredentialsOverlay');
                hideModal(m1);
                hideModal(m2);
            };

            function debounce(func, timeout = 300) {
                let timer;
                return (...args) => {
                    clearTimeout(timer);
                    timer = setTimeout(() => {
                        func.apply(this, args);
                    }, timeout);
                };
            }

            return {
                isEditing, form, errors, photoPreview,
                credsForm, credsErrors,
                openCreateModal, submitPersonForm,
                openCredsModal, submitCredsForm, closeModal,
                loadingQuickView, quickViewHtml, currentDetailUrl,
                openQuickView, closeQuickView
            };
        }
    }).mount('#personApp');
});