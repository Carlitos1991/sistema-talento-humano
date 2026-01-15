/**
 * SIGETH - Employee Wizard Controller
 * Arquitectura: Vue 3 Composition API
 */

if (typeof Vue === 'undefined') {
    console.error("Vue.js no está cargado.");
}

const {createApp, ref, onMounted} = Vue;

const app = createApp({
    delimiters: ['[[', ']]'],
    setup() {
        // --- 1. ESTADOS DE NAVEGACIÓN Y CARGA ---
        const activeTab = ref('personal');
        const isSaving = ref(false);
        const loadingList = ref(false);
        const appElement = document.getElementById('employeeWizardApp');
        const personId = appElement ? appElement.dataset.personId : null;
        if (!personId) {
            console.error("ERROR CRÍTICO: No se pudo obtener el personId del dataset.");
        }
        // --- 2. FORMULARIOS REACTIVOS ---
        const editForm = ref({});
        const editErrors = ref({});
        const titleForm = ref({education_level: ''});
        const titleErrors = ref({});
        const expForm = ref({is_current: false});
        const expErrors = ref({});
        const trainForm = ref({training_name: ''});
        const trainErrors = ref({});
        const bankForm = ref({});
        const bankErrors = ref({});

        // --- 3. DATOS DE IDENTIDAD Y ESTADÍSTICAS ---
        const photoPreview = ref(null);
        const personData = ref({full_name: ''});
        const personStats = ref({
            titles: appElement ? parseInt(appElement.dataset.titles) : 0,
            experiences: appElement ? parseInt(appElement.dataset.experiences) : 0,
            courses: appElement ? parseInt(appElement.dataset.courses) : 0
        });

        // --- 4. LISTADOS GENÉRICOS (MODAL LIST) ---
        const listModalTitle = ref('');
        const listTableHead = ref('');
        const listTableBody = ref('');

        // --- 5. CONFIGURACIÓN DE PESTAÑAS ---
        const tabs = [
            {
                id: 'personal',
                name: 'Datos Personales',
                icon: 'fa-solid fa-user',
                class: 'employee-detail-button-personal'
            },
            {
                id: 'curriculum',
                name: 'Currículum Vitae',
                icon: 'fa-solid fa-file-invoice',
                class: 'employee-detail-button-curriculum'
            },
            {
                id: 'institutional',
                name: 'Datos Inst.',
                icon: 'fa-solid fa-building',
                class: 'employee-detail-button-institutional'
            },
            {
                id: 'economic',
                name: 'Datos Económicos',
                icon: 'fa-solid fa-money-bill-1-wave',
                class: 'employee-detail-button-economic'
            },
            {
                id: 'budget',
                name: 'Partida Presup.',
                icon: 'fa-solid fa-address-book',
                class: 'employee-detail-button-budget'
            },
            {
                id: 'history',
                name: 'Historia Lab.',
                icon: 'fa-solid fa-clock-rotate-left',
                class: 'employee-detail-button-history'
            },
            {
                id: 'permissions',
                name: 'Permisos',
                icon: 'fa-solid fa-calendar-check',
                class: 'employee-detail-button-permissions'
            },
            {
                id: 'actions',
                name: 'Acciones Pers.',
                icon: 'fa-solid fa-file-invoice',
                class: 'employee-detail-button-actions'
            },
            {id: 'vacations', name: 'Vacaciones', icon: 'fa-solid fa-plane', class: 'employee-detail-button-vacations'},
        ];

        // --- 6. MÉTODOS: GESTIÓN DE PERSONA (EDICIÓN) ---

        const openEditPersonModal = async (pId) => {
            editErrors.value = {};
            try {
                const response = await fetch(`/person/detail/${pId}/`);
                const res = await response.json();
                if (res.success) {
                    editForm.value = res.data;
                    personData.value = {full_name: res.data.first_name + ' ' + res.data.last_name};
                    photoPreview.value = res.data.photo_url;

                    // Cargar cascada de ubicaciones
                    if (res.data.country) await loadLocations(res.data.country, 'id_province_modal', res.data.province);
                    if (res.data.province) await loadLocations(res.data.province, 'id_canton_modal', res.data.canton);
                    if (res.data.canton) await loadLocations(res.data.canton, 'id_parish_modal', res.data.parish);

                    document.getElementById('modalPersonEditOverlay').classList.remove('hidden');
                    document.body.classList.add('no-scroll');
                }
            } catch (e) {
                window.Toast.fire({icon: 'error', title: 'Error al obtener datos'});
            }
        };

        const closeEditModal = () => {
            document.getElementById('modalPersonEditOverlay').classList.add('hidden');
            document.body.classList.remove('no-scroll');
        };

        const submitPersonEdit = async () => {
            if (isSaving.value) return;
            isSaving.value = true;
            const formData = new FormData(document.getElementById('personEditForm'));
            try {
                const response = await fetch(`/person/update/${editForm.value.id}/`, {
                    method: 'POST', body: formData, headers: {'X-CSRFToken': window.getCookie('csrftoken')}
                });
                const res = await response.json();
                if (res.success) {
                    window.Toast.fire({icon: 'success', title: res.message});
                    setTimeout(() => {
                        location.reload();
                    }, 1000);
                } else {
                    editErrors.value = res.errors;
                    window.Toast.fire({icon: 'warning', title: 'Revise los campos marcados'});
                }
            } catch (e) {
                window.Toast.fire({icon: 'error', title: 'Error al guardar'});
            } finally {
                isSaving.value = false;
            }
        };

        // --- 7. MÉTODOS: CURRICULUM VITAE (PDF, Títulos, Experiencia, Cursos) ---

        const refreshCvTab = async (pId) => {
            try {
                const response = await fetch(`/employee/partial/cv/${pId}/`, {
                    headers: {'X-Requested-With': 'XMLHttpRequest'}
                });
                const htmlText = await response.text();
                const container = document.getElementById('curriculum-tab-container');
                if (container) container.innerHTML = htmlText;
            } catch (e) {
                console.error("Error al refrescar fragmento CV", e);
            }
        };

        const handlePdfUpload = async (event, pId) => {
            const file = event.target.files[0];
            if (!file) return;
            if (file.type !== 'application/pdf') {
                window.Toast.fire({icon: 'error', title: 'Debe ser un archivo PDF'});
                return;
            }
            window.Toast.fire({icon: 'info', title: 'Subiendo archivo...'});
            const formData = new FormData();
            formData.append('pdf_file', file);
            try {
                const response = await fetch(`/employee/api/upload-cv/${pId}/`, {
                    method: 'POST', body: formData, headers: {'X-CSRFToken': window.getCookie('csrftoken')}
                });
                const res = await response.json();
                if (res.success) {
                    window.Toast.fire({icon: 'success', title: res.message});
                    await refreshCvTab(pId);
                }
            } catch (error) {
                window.Toast.fire({icon: 'error', title: 'Error de conexión'});
            }
        };

        const submitAcademicTitle = async () => {
            if (isSaving.value) return;
            isSaving.value = true;
            const formData = new FormData();
            Object.keys(titleForm.value).forEach(key => formData.append(key, titleForm.value[key]));
            try {
                const res = await fetch(`/employee/api/cv/add-title/${personId}/`, {
                    method: 'POST', body: formData, headers: {'X-CSRFToken': window.getCookie('csrftoken')}
                });
                const data = await res.json();
                if (data.success) {
                    window.Toast.fire({icon: 'success', title: data.message});
                    closeModal('academic');
                    await refreshCvTab(personId);
                } else {
                    titleErrors.value = data.errors;
                }
            } catch (e) {
                window.Toast.fire({icon: 'error', title: 'Error al guardar título'});
            } finally {
                isSaving.value = false;
            }
        };

        const submitExperience = async () => {
            if (isSaving.value) return;
            isSaving.value = true;
            const formData = new FormData();
            Object.keys(expForm.value).forEach(key => formData.append(key, expForm.value[key]));
            try {
                const res = await fetch(`/employee/api/cv/add-experience/${personId}/`, {
                    method: 'POST', body: formData, headers: {'X-CSRFToken': window.getCookie('csrftoken')}
                });
                const data = await res.json();
                if (data.success) {
                    window.Toast.fire({icon: 'success', title: data.message});
                    closeModal('experience');
                    await refreshCvTab(personId);
                } else {
                    expErrors.value = data.errors;
                }
            } catch (e) {
                window.Toast.fire({icon: 'error', title: 'Error al guardar experiencia'});
            } finally {
                isSaving.value = false;
            }
        };

        const submitTraining = async () => {
            if (isSaving.value) return;
            isSaving.value = true;
            const formData = new FormData();
            Object.keys(trainForm.value).forEach(key => formData.append(key, trainForm.value[key]));
            try {
                const res = await fetch(`/employee/api/cv/add-training/${personId}/`, {
                    method: 'POST', body: formData, headers: {'X-CSRFToken': window.getCookie('csrftoken')}
                });
                const data = await res.json();
                if (data.success) {
                    window.Toast.fire({icon: 'success', title: data.message});
                    closeModal('training');
                    await refreshCvTab(personId);
                } else {
                    trainErrors.value = data.errors;
                }
            } catch (e) {
                window.Toast.fire({icon: 'error', title: 'Error al guardar capacitación'});
            } finally {
                isSaving.value = false;
            }
        };

        // --- 8. MÉTODOS: DATOS ECONÓMICOS ---

        const openBankModal = () => {
            bankForm.value = {holder_name: personData.value.full_name};
            document.getElementById('modalBankOverlay').classList.remove('hidden');
        };

        const saveBankAccount = async (pId) => {
            const formData = new FormData();
            Object.keys(bankForm.value).forEach(key => formData.append(key, bankForm.value[key]));
            try {
                const response = await fetch(`/employee/api/add-bank-account/${pId}/`, {
                    method: 'POST', body: formData, headers: {'X-CSRFToken': window.getCookie('csrftoken')}
                });
                const data = await response.json();
                if (data.success) {
                    window.Toast.fire({icon: 'success', title: data.message});
                    location.reload();
                } else {
                    bankErrors.value = data.errors;
                }
            } catch (e) {
                window.Toast.fire({icon: 'error', title: 'Error al procesar banco'});
            }
        };

        // --- 9. AUXILIARES: MODALES, UBICACIONES, FOTOS ---

        const openModal = (type, action) => {
            if (action === 'new') {
                const map = {
                    academic: 'modalTitleOverlay',
                    experience: 'modalExperienceOverlay',
                    training: 'modalTrainingOverlay'
                };
                const modal = document.getElementById(map[type]);
                if (modal) {
                    modal.classList.remove('hidden');
                    document.body.classList.add('no-scroll');
                }
            } else {
                // Si la acción es 'list', llamamos al cargador de datos
                fetchListData(type);
            }
        };

        const closeModal = (type) => {
            const map = {
                academic: 'modalTitleOverlay',
                experience: 'modalExperienceOverlay',
                training: 'modalTrainingOverlay',
                bank: 'modalBankOverlay',
                list: 'modalCVListOverlay'
            };
            const modalId = map[type];
            const modal = document.getElementById(modalId);
            if (modal) modal.classList.add('hidden');
            document.body.classList.remove('no-scroll');
        };

        const fetchListData = async (type) => {
            loadingList.value = true;

            // 1. Mostrar modal de lista con spinner de carga
            const modal = document.getElementById('modalCVListOverlay');
            if (modal) {
                modal.classList.remove('hidden');
                document.body.classList.add('no-scroll');
            }

            // 2. Configuración de títulos y rutas
            const config = {
                academic: {title: 'Títulos Académicos', url: 'list-titles'},
                experience: {title: 'Experiencia Laboral', url: 'list-experience'},
                training: {title: 'Capacitaciones Registradas', url: 'list-training'}
            };

            listModalTitle.value = config[type].title;
            listTableBody.value = `<tr><td colspan="4" class="text-center py-5"><i class="fa-solid fa-spinner fa-spin fa-2x text-primary"></i><br>Cargando...</td></tr>`;

            try {
                // 3. Petición al servidor (Django)
                const response = await fetch(`/employee/api/cv/${config[type].url}/${personId}/`);
                const data = await response.json();

                // 4. Inyectar el HTML que devuelve Django
                listTableHead.value = data.header; // Cabecera de la tabla
                listTableBody.value = data.html;     // Filas de la tabla
            } catch (e) {
                console.error("Error en fetchListData:", e);
                listTableBody.value = `<tr><td colspan="4" class="text-error text-center p-4">Error al conectar con el servidor</td></tr>`;
            } finally {
                loadingList.value = false;
            }
        };

        const loadLocations = async (parentId, targetId, selectedValue = null) => {
            const target = document.getElementById(targetId);
            if (!target) return;
            try {
                const response = await fetch(`/api/locations/?parent_id=${parentId}`);
                const res = await response.json();
                let options = '<option value="">-- Seleccione --</option>';
                if (res.success && res.data) {
                    res.data.forEach(loc => {
                        options += `<option value="${loc.id}">${loc.name}</option>`;
                    });
                }
                target.innerHTML = options;
                if (selectedValue) target.value = selectedValue;
            } catch (e) {
                console.error("Error cargando locaciones", e);
            }
        };

        const handlePhotoChange = (e) => {
            const file = e.target.files[0];
            if (file) photoPreview.value = URL.createObjectURL(file);
        };
        const closeListModal = () => {
            const modal = document.getElementById('modalCVListOverlay');
            if (modal) modal.classList.add('hidden');
            document.body.classList.remove('no-scroll');
        };
        window.handleCvAction = (type, action) => {
            openModal(type, action);
        };

        // --- 10. EL RETURN: TODO LO QUE EL HTML PUEDE VER ---
        return {
            activeTab, isSaving, loadingList, tabs, personStats, personData,
            editForm, editErrors, photoPreview,
            titleForm, titleErrors, expForm, expErrors, trainForm, trainErrors,
            bankForm, bankErrors,
            listModalTitle, listTableHead, listTableBody,
            openEditPersonModal, closeEditModal, submitPersonEdit,
            handlePdfUpload, openModal, closeModal,
            closeListModal, fetchListData,
            submitAcademicTitle, submitExperience, submitTraining,
            openBankModal, saveBankAccount, handlePhotoChange
        };
    }
});

// Montaje Global
document.addEventListener('DOMContentLoaded', () => {
    app.mount('#employeeWizardApp');
});