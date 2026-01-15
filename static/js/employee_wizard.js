/**
 * SIGETH - Employee Wizard Master Controller
 * Versión: 2.0 (Full Integration)
 * Arquitectura: Vue 3 Composition API + Bridge Global
 */

if (typeof Vue === 'undefined') {
    console.error("Vue.js no está cargado.");
}

const {createApp, ref, computed, onMounted} = Vue;

const app = createApp({
    delimiters: ['[[', ']]'],
    setup() {
        // --- 1. CONFIGURACIÓN Y ESTADOS CORE ---
        const activeTab = ref('personal');
        const isSaving = ref(false);
        const loadingList = ref(false);
        const appElement = document.getElementById('employeeWizardApp');

        // Atributos de datos inyectados por Django
        const personId = appElement ? appElement.dataset.personId : null;
        const personStats = ref({
            titles: appElement ? parseInt(appElement.dataset.titles) : 0,
            experiences: appElement ? parseInt(appElement.dataset.experiences) : 0,
            courses: appElement ? parseInt(appElement.dataset.courses) : 0,
            experienceYears: 0,
            experienceMonths: 0
        });
        // --- 1. LÓGICA SELECT2 DEFINITIVA ---
        const refreshSelect2 = (selector) => {
            setTimeout(() => {
                const $modal = $(selector);
                const $selects = $modal.find('.select2-wizard');

                $selects.each(function () {
                    if ($(this).data('select2')) {
                        $(this).select2('destroy');
                    }
                    $(this).select2({
                        dropdownParent: $modal,
                        width: '100%'
                    }).on('change', function () {
                        const name = $(this).attr('name');
                        const val = $(this).val();
                        // Sincronización manual según el formulario activo
                        if (selector.includes('Title')) titleForm.value[name] = val;
                        if (selector.includes('Experience')) expForm.value[name] = val;
                        if (selector.includes('Training')) trainForm.value[name] = val;
                        if (selector.includes('Person')) editForm.value[name] = val;
                    });
                });
            }, 300);
        };
        const initSelect2 = (selector) => {
            setTimeout(() => {
                const $modal = $(selector);
                const $selects = $modal.find('.select2-wizard');
                if ($selects.length > 0) {
                    $selects.select2({
                        dropdownParent: $modal,
                        width: '100%'
                    }).on('change', function () {
                        const name = $(this).attr('name');
                        const val = $(this).val();
                        if (selector.includes('Title')) titleForm.value[name] = val;
                        if (selector.includes('Experience')) expForm.value[name] = val;
                        if (selector.includes('Training')) trainForm.value[name] = val;
                        if (selector.includes('Person')) editForm.value[name] = val;
                    });
                }
            }, 300);
        };
        // --- 2. GESTIÓN DE MODALES ---
        const openModal = (type, action) => {
            const map = {
                academic: '#modalTitleOverlay',
                experience: '#modalExperienceOverlay',
                training: '#modalTrainingOverlay',
                person: '#modalPersonEditOverlay'
            };
            const selector = map[type];
            if (action === 'new') {
                // RESET FORMS (Para que al dar 'Nuevo' no salgan datos de una edición previa)
                if (type === 'academic') titleForm.value = {id: null, education_level: ''};
                if (type === 'experience') expForm.value = {id: null, is_current: false};
                if (type === 'training') trainForm.value = {id: null};

                $(selector).removeClass('hidden');
                initSelect2(selector);
            } else {
                fetchListData(type);
            }
        };

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

        // --- 3. UI Y PREVIEW ---
        const photoPreview = ref(null);
        const personData = ref({full_name: ''});
        const listModalTitle = ref('');
        const listTableHead = ref('');
        const listTableBody = ref('');
        
        // --- 3.1 BÚSQUEDA Y FILTRADO ---
        const searchQuery = ref('');
        const listItems = ref([]);
        const currentListType = ref(''); // Tipo actual de lista (academic, experience, training)
        const filteredItems = computed(() => {
            if (!searchQuery.value) {
                return listItems.value;
            }
            const query = searchQuery.value.toLowerCase();
            return listItems.value.filter(item => 
                (item.name && item.name.toLowerCase().includes(query)) ||
                (item.code && item.code.toLowerCase().includes(query))
            );
        });

        // --- 4. CONFIGURACIÓN DE PESTAÑAS ---
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
            {
                id: 'sanctions',
                name: 'Sanciones',
                icon: 'fa-solid fa-gavel',
                class: 'employee-detail-button-sanctions'
            },
            {
                id: 'payments',
                name: 'Roles de pago',
                icon: 'fa-solid fa-money-bill',
                class: 'employee-detail-button-payments'
            },
            {id: 'vacations', name: 'Vacaciones', icon: 'fa-solid fa-plane', class: 'employee-detail-button-vacations'},
        ];

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
                if ($(target).data('select2')) $(target).trigger('change.select2');
            } catch (e) {
                console.error("Error en loadLocations", e);
            }
        };

        const handleLocationCascada = async (parentId, targetId) => {
            await loadLocations(parentId, targetId);
        };
        const handleEditCvItem = async (type, id) => {
            try {
                const res = await (await fetch(`/employee/api/cv/detail/${type}/${id}/`)).json();
                if (res.success) {
                    $('#modalCVListOverlay').addClass('hidden');
                    if (type === 'academic') {
                        titleForm.value = res.data;
                        openModal('academic', 'new');
                    }
                    if (type === 'experience') {
                        expForm.value = res.data;
                        openModal('experience', 'new');
                    }
                    if (type === 'training') {
                        trainForm.value = res.data;
                        openModal('training', 'new');
                    }
                }
            } catch (e) {
                console.error(e);
            }
        };

        // --- 6. MÉTODOS: GESTIÓN DE PERSONA ---

        const openEditPersonModal = async (pId) => {
            editErrors.value = {};
            try {
                const response = await fetch(`/person/detail/${pId}/`);
                const res = await response.json();
                if (res.success) {
                    editForm.value = res.data;
                    personData.value = {full_name: res.data.first_name + ' ' + res.data.last_name};
                    photoPreview.value = res.data.photo_url;

                    const modalSelector = '#modalPersonEditOverlay';
                    $(modalSelector).removeClass('hidden');
                    document.body.classList.add('no-scroll');

                    // Cargar datos de ubicación en los selects
                    if (res.data.country) await loadLocations(res.data.country, 'id_province_modal', res.data.province);
                    if (res.data.province) await loadLocations(res.data.province, 'id_canton_modal', res.data.canton);
                    if (res.data.canton) await loadLocations(res.data.canton, 'id_parish_modal', res.data.parish);

                    initSelect2InModal(modalSelector);
                }
            } catch (e) {
                window.Toast.fire({icon: 'error', title: 'Error al obtener datos'});
            }
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
                    setTimeout(() => location.reload(), 1000);
                } else {
                    editErrors.value = res.errors;
                    window.Toast.fire({icon: 'warning', title: 'Revise los campos'});
                }
            } catch (e) {
                window.Toast.fire({icon: 'error', title: 'Error de servidor'});
            } finally {
                isSaving.value = false;
            }
        };

        const closeEditModal = () => {
            $('#modalPersonEditOverlay').addClass('hidden');
            document.body.classList.remove('no-scroll');
        };

        // --- 7. MÉTODOS: CURRICULUM VITAE (PDF Y CRUD) ---

        const refreshCvTab = async (pId) => {
            // En lugar de reemplazar todo el HTML, actualizar solo los contadores
            console.log('refreshCvTab: Actualizando estadísticas reactivamente');
            try {
                // Obtener la persona actualizada para los contadores
                const [titlesRes, expRes, trainRes] = await Promise.all([
                    fetch(`/employee/api/cv/list-titles/${pId}/`),
                    fetch(`/employee/api/cv/list-experience/${pId}/`),
                    fetch(`/employee/api/cv/list-training/${pId}/`)
                ]);
                
                const titlesData = await titlesRes.json();
                const expData = await expRes.json();
                const trainData = await trainRes.json();
                
                if (titlesData.success) {
                    personStats.value.titles = titlesData.items.length;
                }
                
                if (expData.success) {
                    personStats.value.experiences = expData.items.length;
                    personStats.value.experienceYears = expData.total_years || 0;
                    personStats.value.experienceMonths = expData.total_months || 0;
                }
                
                if (trainData.success) {
                    personStats.value.courses = trainData.items.length;
                }
                
                console.log('refreshCvTab: Estadísticas actualizadas', personStats.value);
            } catch (e) {
                console.error('Error actualizando estadísticas:', e);
            }
        };

        const handlePdfUpload = async (event, pId) => {
            const file = event.target.files[0];
            if (!file) return;
            const formData = new FormData();
            formData.append('pdf_file', file);
            window.Toast.fire({icon: 'info', title: 'Subiendo archivo...'});
            try {
                const res = await (await fetch(`/employee/api/upload-cv/${pId}/`, {
                    method: 'POST', body: formData, headers: {'X-CSRFToken': window.getCookie('csrftoken')}
                })).json();
                if (res.success) {
                    window.Toast.fire({icon: 'success', title: res.message});
                    refreshCvTab(pId);
                }
            } catch (e) {
                console.error(e);
            }
        };

        const submitAcademicTitle = async () => {
            if (isSaving.value) return;
            isSaving.value = true;
            const formData = new FormData();
            Object.keys(titleForm.value).forEach(k => formData.append(k, titleForm.value[k]));
            try {
                const url = titleForm.value.id ? `/employee/api/cv/edit-title/${titleForm.value.id}/` : `/employee/api/cv/add-title/${personId}/`;
                const res = await (await fetch(url, {
                    method: 'POST',
                    body: formData,
                    headers: {'X-CSRFToken': window.getCookie('csrftoken')}
                })).json();
                if (res.success) {
                    window.Toast.fire({icon: 'success', title: res.message});
                    closeModal('academic');
                    refreshCvTab(personId);
                } else {
                    titleErrors.value = res.errors;
                }
            } finally {
                isSaving.value = false;
            }
        };

        const submitExperience = async () => {
            if (isSaving.value) return;
            isSaving.value = true;
            const formData = new FormData();
            Object.keys(expForm.value).forEach(k => formData.append(k, expForm.value[k]));
            try {
                const url = expForm.value.id ? `/employee/api/cv/edit-experience/${expForm.value.id}/` : `/employee/api/cv/add-experience/${personId}/`;
                const res = await (await fetch(url, {
                    method: 'POST', body: formData, headers: {'X-CSRFToken': window.getCookie('csrftoken')}
                })).json();
                if (res.success) {
                    window.Toast.fire({icon: 'success', title: res.message});
                    closeModal('experience');
                    refreshCvTab(personId);
                } else {
                    expErrors.value = res.errors;
                }
            } finally {
                isSaving.value = false;
            }
        };

        const submitTraining = async () => {
            if (isSaving.value) return;
            isSaving.value = true;
            const formData = new FormData();
            Object.keys(trainForm.value).forEach(k => formData.append(k, trainForm.value[k]));
            try {
                const url = trainForm.value.id ? `/employee/api/cv/edit-training/${trainForm.value.id}/` : `/employee/api/cv/add-training/${personId}/`;
                const res = await (await fetch(url, {
                    method: 'POST', body: formData, headers: {'X-CSRFToken': window.getCookie('csrftoken')}
                })).json();
                if (res.success) {
                    window.Toast.fire({icon: 'success', title: res.message});
                    closeModal('training');
                    refreshCvTab(personId);
                } else {
                    trainErrors.value = res.errors;
                }
            } finally {
                isSaving.value = false;
            }
        };

        const handleDeleteCvItem = async (type, id) => {
            const result = await Swal.fire({
                title: '¿Eliminar registro?',
                icon: 'warning',
                showCancelButton: true,
                confirmButtonText: 'Sí, borrar',
                customClass: {
                    confirmButton: 'swal2-confirm btn-swal-danger',
                    cancelButton: 'swal2-cancel btn-swal-cancel'
                },
                buttonsStyling: false
            });
            if (result.isConfirmed) {
                const res = await (await fetch(`/employee/api/cv/delete/${type}/${id}/`, {
                    method: 'POST', headers: {'X-CSRFToken': window.getCookie('csrftoken')}
                })).json();
                if (res.success) {
                    window.Toast.fire({icon: 'success', title: res.message});
                    fetchListData(type); // Recargar modal lista
                    refreshCvTab(personId); // Recargar parcial verde
                }
            }
        };

        window.handleCvAction = (type, action) => openModal(type, action);
        window.handleEditCvItem = (type, id) => handleEditCvItem(type, id);
        window.handleDeleteCvItem = (type, id) => handleDeleteCvItem(type, id);

        // --- 8. MÉTODOS: DATOS ECONÓMICOS ---

        const openBankModal = () => {
            bankForm.value = {holder_name: personData.value.full_name};
            $('#modalBankOverlay').removeClass('hidden');
            initSelect2InModal('#modalBankOverlay');
        };

        const saveBankAccount = async () => {
            const formData = new FormData();
            Object.keys(bankForm.value).forEach(k => formData.append(k, bankForm.value[k]));
            try {
                const res = await (await fetch(`/employee/api/add-bank-account/${personId}/`, {
                    method: 'POST', body: formData, headers: {'X-CSRFToken': window.getCookie('csrftoken')}
                })).json();
                if (res.success) {
                    window.Toast.fire({icon: 'success', title: res.message});
                    location.reload();
                } else {
                    bankErrors.value = res.errors;
                }
            } catch (e) {
                console.error(e);
            }
        };

        // --- 9. AUXILIARES DE MODALES ---


        const closeModal = (type) => {
            const map = {
                academic: '#modalTitleOverlay', experience: '#modalExperienceOverlay',
                training: '#modalTrainingOverlay', bank: '#modalBankOverlay',
                list: '#modalCVListOverlay', person: '#modalPersonEditOverlay'
            };
            $(map[type]).addClass('hidden');
            document.body.classList.remove('no-scroll');
        };

        const closeListModal = () => {
            $('#modalCVListOverlay').addClass('hidden');
            document.body.classList.remove('no-scroll');
        };

        const fetchListData = async (type) => {
            loadingList.value = true;
            searchQuery.value = '';
            listItems.value = [];
            currentListType.value = type; // Guardar tipo actual
            $('#modalCVListOverlay').removeClass('hidden');

            const titles = {
                academic: 'Títulos Académicos',
                experience: 'Experiencia Laboral',
                training: 'Capacitaciones'
            };
            const urls = {academic: 'list-titles', experience: 'list-experience', training: 'list-training'};
            listModalTitle.value = `Items de: ${titles[type]}`;

            try {
                const res = await (await fetch(`/employee/api/cv/${urls[type]}/${personId}/`)).json();
                
                // Llenar listItems con los datos estructurados
                if (res.items && Array.isArray(res.items)) {
                    listItems.value = res.items.map(item => ({
                        id: item.id,
                        name: item.name || item.title || item.institution || 'Sin nombre',
                        code: item.code || item.level || type.charAt(0).toUpperCase(),
                        status: 'active'
                    }));
                }
                
                // Actualizar años y meses de experiencia si es el tipo 'experience'
                if (type === 'experience' && res.total_years !== undefined) {
                    personStats.value.experienceYears = res.total_years;
                    personStats.value.experienceMonths = res.total_months;
                }
            } catch (e) {
                console.error('Error al cargar lista:', e);
                Swal.fire({
                    icon: 'error',
                    title: 'Error',
                    text: 'No se pudo cargar el listado',
                    toast: true,
                    position: 'top-end',
                    showConfirmButton: false,
                    timer: 3000
                });
            } finally {
                loadingList.value = false;
            }
        };

        // --- 10. PUENTE GLOBAL (BRIDGE) PARA HTML DINÁMICO ---
        window.handleCvAction = (type, action) => openModal(type, action);
        window.handleDeleteCvItem = (type, id) => handleDeleteCvItem(type, id);
        
        // Función helper para recalcular experiencia después de eliminar
        const recalculateExperience = async () => {
            try {
                const res = await fetch(`/employee/api/cv/list-experience/${personId}/`);
                const data = await res.json();
                if (data.success && data.total_years !== undefined) {
                    personStats.value.experienceYears = data.total_years;
                    personStats.value.experienceMonths = data.total_months;
                }
            } catch (e) {
                console.error('Error recalculando experiencia:', e);
            }
        };

        const handlePhotoChange = (e) => {
            const file = e.target.files[0];
            if (file) photoPreview.value = URL.createObjectURL(file);
        };
        
        // --- 10.1 FUNCIONES PARA ACCIONES DE LISTA ---
        const editItem = async (item) => {
            try {
                // Cerrar modal de lista
                $('#modalCVListOverlay').addClass('hidden');
                
                // Cargar datos del item
                const res = await fetch(`/employee/api/cv/detail/${currentListType.value}/${item.id}/`);
                const data = await res.json();
                
                if (data.success) {
                    // Poblar formulario según el tipo
                    if (currentListType.value === 'academic') {
                        titleForm.value = {
                            id: data.data.id,
                            education_level: data.data.education_level,
                            title_obtained: data.data.title_obtained,
                            educational_institution: data.data.educational_institution,
                            graduation_year: data.data.graduation_year
                        };
                        $('#modalTitleOverlay').removeClass('hidden');
                        refreshSelect2('#modalTitleOverlay');
                    } else if (currentListType.value === 'experience') {
                        expForm.value = {
                            id: data.data.id,
                            company_name: data.data.company_name,
                            position: data.data.position,
                            start_date: data.data.start_date,
                            end_date: data.data.end_date,
                            is_current: data.data.is_current
                        };
                        $('#modalExperienceOverlay').removeClass('hidden');
                        refreshSelect2('#modalExperienceOverlay');
                    } else if (currentListType.value === 'training') {
                        trainForm.value = {
                            id: data.data.id,
                            training_name: data.data.training_name,
                            institution: data.data.institution,
                            hours: data.data.hours,
                            completion_date: data.data.completion_date
                        };
                        $('#modalTrainingOverlay').removeClass('hidden');
                        refreshSelect2('#modalTrainingOverlay');
                    }
                }
            } catch (e) {
                console.error('Error al cargar item:', e);
                Swal.fire({
                    icon: 'error',
                    title: 'Error',
                    text: 'No se pudo cargar el registro',
                    toast: true,
                    position: 'top-end',
                    showConfirmButton: false,
                    timer: 3000
                });
            }
        };
        
        const deleteItem = async (item) => {
            const result = await Swal.fire({
                title: '¿Eliminar registro?',
                text: `Se eliminará: ${item.name}`,
                icon: 'warning',
                showCancelButton: true,
                confirmButtonColor: '#dc2626',
                cancelButtonColor: '#64748b',
                confirmButtonText: 'Sí, eliminar',
                cancelButtonText: 'Cancelar'
            });
            
            if (result.isConfirmed) {
                try {
                    const res = await fetch(`/employee/api/cv/delete/${currentListType.value}/${item.id}/`, {
                        method: 'POST',
                        headers: {
                            'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
                            'Content-Type': 'application/json'
                        }
                    });
                    
                    const data = await res.json();
                    
                    if (data.success) {
                        // Actualizar la lista removiendo el item eliminado
                        listItems.value = listItems.value.filter(i => i.id !== item.id);
                        
                        // Actualizar contador de stats
                        if (currentListType.value === 'academic') personStats.value.titles--;
                        if (currentListType.value === 'experience') {
                            personStats.value.experiences--;
                            // Recalcular años y meses de experiencia
                            await recalculateExperience();
                        }
                        if (currentListType.value === 'training') personStats.value.courses--;
                        
                        Swal.fire({
                            icon: 'success',
                            title: 'Eliminado',
                            text: data.message || 'Registro eliminado correctamente',
                            toast: true,
                            position: 'top-end',
                            showConfirmButton: false,
                            timer: 2000
                        });
                    } else {
                        throw new Error(data.message || 'Error al eliminar');
                    }
                } catch (e) {
                    console.error('Error al eliminar:', e);
                    Swal.fire({
                        icon: 'error',
                        title: 'Error',
                        text: 'No se pudo eliminar el registro',
                        toast: true,
                        position: 'top-end',
                        showConfirmButton: false,
                        timer: 3000
                    });
                }
            }
        };

        // --- 11. INICIALIZACIÓN ---
        onMounted(async () => {
            // Cargar años y meses de experiencia al iniciar
            await recalculateExperience();
        });

        // --- 12. EL RETURN DEFINITIVO (Sincronización con Template) ---
        return {
            // Estados
            activeTab, isSaving, loadingList, tabs, personStats, personData,
            editForm, editErrors, photoPreview,
            titleForm, titleErrors, expForm, expErrors, trainForm, trainErrors,
            bankForm, bankErrors,
            listModalTitle, listTableHead, listTableBody,
            searchQuery, listItems, filteredItems,

            // Métodos Persona
            openEditPersonModal, closeEditModal, submitPersonEdit, handlePhotoChange,

            // Métodos CV
            handlePdfUpload, openModal, closeModal, closeListModal, handleEditCvItem, handleDeleteCvItem,
            submitAcademicTitle, submitExperience, submitTraining,
            editItem, deleteItem,

            // Métodos Bancos
            openBankModal, saveBankAccount, refreshCvTab
        };
    }
});

// Montaje Global
document.addEventListener('DOMContentLoaded', () => {
    app.mount('#employeeWizardApp');
});