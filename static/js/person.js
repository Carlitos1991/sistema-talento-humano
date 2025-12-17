/* static/js/apps/person.js */

document.addEventListener('DOMContentLoaded', () => {
    const {createApp, ref, onMounted} = Vue;

    // --- 1. CONFIGURACIÓN ESTATICA (Helpers) ---
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    const Toast = Swal.mixin({
        toast: true,
        position: 'top-end',
        showConfirmButton: false,
        timer: 3000,
        timerProgressBar: true
    });

    const appElement = document.getElementById('personApp');

    if (appElement) {
        // --- 2. LEER CONFIGURACIÓN DEL DOM (Data Attributes) ---
        // Parseamos el JSON que pusimos en person_list.html
        let urls = {};
        try {
            urls = JSON.parse(appElement.dataset.urls);
        } catch (e) {
            console.error("Error al parsear URLs desde data-urls:", e);
        }

        createApp({
            setup() {
                // --- Estado Reactivo ---
                const isEditing = ref(false);
                const currentId = ref(null);

                const form = ref({});
                const errors = ref({});
                const photoPreview = ref(null);

                const credsForm = ref({username: '', password: '', role: ''});
                const credsErrors = ref({});
                const currentEmployeeName = ref('');

                // Referencias DOM para Modales (CSS Custom)
                const modalPersonOverlay = document.getElementById('modalPersonOverlay');
                const modalCredsOverlay = document.getElementById('modalCredentialsOverlay');

                // --- CICLO DE VIDA (INIT) ---
                onMounted(() => {
                    initTableListeners();
                    initSearch();
                    initLocationCascading(); // <--- NUEVA FUNCIÓN MOVIDA AQUÍ
                });

                // --- 3. LÓGICA DE UBICACIONES EN CASCADA ---
                const initLocationCascading = () => {
                    const idCountry = document.getElementById('id_country');
                    const idProvince = document.getElementById('id_province');
                    const idCanton = document.getElementById('id_canton');

                    if (idCountry) idCountry.addEventListener('change', (e) => loadLocationChildren(e.target.value, 'id_province'));
                    if (idProvince) idProvince.addEventListener('change', (e) => loadLocationChildren(e.target.value, 'id_canton'));
                    if (idCanton) idCanton.addEventListener('change', (e) => loadLocationChildren(e.target.value, 'id_parish'));
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
                        // Usamos la URL que vino en el data-urls
                        // Asumiendo que la vista soporta ?parent_id=X&format=json
                        const response = await fetch(`${urls.locations}?parent_id=${parentId}&format=json`, {
                            headers: {'X-Requested-With': 'XMLHttpRequest'}
                        });

                        // Intentamos parsear JSON
                        const data = await response.json();

                        // Manejar si la respuesta viene directa lista [] o {data: []}
                        const items = Array.isArray(data) ? data : (data.data || []);

                        let options = '<option value="">-- Seleccione --</option>';
                        items.forEach(item => {
                            options += `<option value="${item.id}">${item.name}</option>`;
                        });
                        target.innerHTML = options;

                    } catch (error) {
                        console.error("Error cargando ubicaciones:", error);
                        target.innerHTML = '<option value="">Error al cargar</option>';
                    }
                };

                // --- 4. LISTENERS GLOBALES ---
                const initTableListeners = () => {
                    document.addEventListener('click', (e) => {
                        const btnEdit = e.target.closest('.btn-edit');
                        const btnKey = e.target.closest('.btn-key');

                        if (btnEdit) openEditModal(btnEdit.dataset.id);
                        if (btnKey) openCredsModal(btnKey.dataset.id);
                    });

                    // Listener Input File (Django ID)
                    const fileInput = document.getElementById('id_photo');
                    if (fileInput) {
                        fileInput.addEventListener('change', handlePhotoChange);
                    }
                };

                const initSearch = () => {
                    const searchInput = document.getElementById('searchInput');
                    if (searchInput) {
                        searchInput.addEventListener('input', debounce((e) => {
                            fetchPeople(e.target.value);
                        }, 500));
                    }
                };

                // --- Utilidades ---
                const fetchPeople = (query) => {
                    const url = `${urls.list}?q=${query}`;
                    fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
                        .then(res => res.text())
                        .then(html => {
                            document.getElementById('tableContainer').innerHTML = html;
                        });
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

                // --- Control Modales ---
                const showModal = (el) => {
                    if (el) el.classList.remove('hidden');
                };
                const hideModal = (el) => {
                    if (el) el.classList.add('hidden');
                };

                // --- Métodos Persona ---
                const openCreateModal = () => {
                    isEditing.value = false;
                    currentId.value = null;
                    form.value = {};
                    errors.value = {};
                    photoPreview.value = null;

                    document.getElementById('personFormHtml').reset();
                    showModal(modalPersonOverlay);
                };

                const openEditModal = async (id) => {
                    isEditing.value = true;
                    currentId.value = id;
                    errors.value = {};

                    try {
                        const url = urls.detail.replace('0', id);
                        const res = await fetch(url);
                        const json = await res.json();

                        if (json.success) {
                            form.value = json.data;
                            photoPreview.value = json.data.photo_url;
                            showModal(modalPersonOverlay);

                            // Disparar eventos de cambio para poblar selects cascada en edición
                            // (Opcional: Requeriría lógica extra para setear valor después de cargar ajax)
                        }
                    } catch (e) {
                        console.error(e);
                    }
                };

                const handlePhotoChange = (e) => {
                    const file = e.target.files[0];
                    if (file) photoPreview.value = URL.createObjectURL(file);
                };

                const submitPersonForm = async () => {
                    errors.value = {};
                    const htmlForm = document.getElementById('personFormHtml');
                    const formData = new FormData(htmlForm);

                    const url = isEditing.value
                        ? urls.update.replace('0', currentId.value)
                        : urls.create;

                    try {
                        const res = await fetch(url, {
                            method: 'POST',
                            body: formData,
                            headers: {'X-CSRFToken': getCookie('csrftoken')}
                        });
                        const data = await res.json();

                        if (data.success) {
                            Toast.fire({icon: 'success', title: data.message});
                            hideModal(modalPersonOverlay);
                            fetchPeople(document.getElementById('searchInput')?.value || '');
                        } else {
                            errors.value = data.errors;
                            Toast.fire({icon: 'warning', title: 'Revise el formulario'});
                        }
                    } catch (e) {
                        Toast.fire({icon: 'error', title: 'Error servidor'});
                    }
                };

                // --- Métodos Credenciales ---
                const openCredsModal = (id) => {
                    currentId.value = id;
                    credsForm.value = {username: '', password: '', role: ''};
                    credsErrors.value = {};

                    // Aquí podrías hacer un fetch para obtener el nombre si lo deseas
                    // currentEmployeeName.value = "Cargando...";

                    showModal(modalCredsOverlay);
                };

                const submitCredsForm = async () => {
                    credsErrors.value = {};
                    const formData = new FormData();
                    formData.append('username', credsForm.value.username);
                    formData.append('password', credsForm.value.password);
                    formData.append('role', credsForm.value.role);

                    const url = urls.createCredentials.replace('0', currentId.value);

                    try {
                        const res = await fetch(url, {
                            method: 'POST',
                            body: formData,
                            headers: {'X-CSRFToken': getCookie('csrftoken')}
                        });
                        const data = await res.json();

                        if (data.success) {
                            Toast.fire({icon: 'success', title: data.message});
                            hideModal(modalCredsOverlay);
                            // Recargar tabla para actualizar estado de usuario
                            setTimeout(() => fetchPeople(''), 500);
                        } else {
                            credsErrors.value = data.errors;
                        }
                    } catch (e) {
                        Toast.fire({icon: 'error', title: 'Error creando credenciales'});
                    }
                };

                const closeModal = () => {
                    hideModal(modalPersonOverlay);
                    hideModal(modalCredsOverlay);
                };

                return {
                    // Estado
                    isEditing, form, errors, photoPreview,
                    credsForm, credsErrors, currentEmployeeName,

                    // Métodos
                    openCreateModal, submitPersonForm,
                    openCredsModal, submitCredsForm, closeModal
                };
            }
        }).mount('#personApp');
    }
});