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
        const activeTab = ref(localStorage.getItem('wizardActiveTab') || 'personal');
        
        // Watch for changes and save to localStorage
        Vue.watch(activeTab, (newTab) => {
            localStorage.setItem('wizardActiveTab', newTab);
        });

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
                person: '#modalPersonEditOverlay',
                bank: '#modalBankOverlay',
                payroll: '#modalPayrollOverlay',
                institutional: '#modalInstitutionalOverlay'
            };
            const selector = map[type];
            if (action === 'new') {
                // RESET FORMS
                if (type === 'academic') titleForm.value = {id: null, education_level: ''};
                if (type === 'experience') expForm.value = {id: null, is_current: false};
                if (type === 'training') trainForm.value = {id: null};
                if (type === 'bank') { // No action 'new' usually but for consistency
                   bankForm.value = {bank: '', account_type: '', account_number: '', holder_name: ''};
                   bankErrors.value = {};
                }
                if (type === 'payroll') {
                     payrollForm.value = {monthly_payment: false, reserve_funds: false, family_dependents: 0, education_dependents: 0, roles_entry_date: null, roles_count: 0};
                     payrollErrors.value = {};
                }

                $(selector).removeClass('hidden');
                initSelect2(selector);
            } else if (action === 'edit' && type === 'bank') {
                // Load existing bank data logic would go here if we fetched it asynchronously or injected it
                // For now, we assume user might want to edit. If data is in Django template, we might need to parse it or fetch it.
                 // Ideally we call an API to get current data or pass it in the button.
                // Simplified for now:
                $(selector).removeClass('hidden');
                initSelect2(selector);
            } else if(action === 'edit' && type === 'payroll') {
                 // Similar to bank
                 $(selector).removeClass('hidden');
            }
             else {
                fetchListData(type);
            }
        };

        // --- 2. FORMULARIOS REACTIVOS ---
        const editForm = ref({});
        const editErrors = ref({});
        const bankForm = ref({bank: '', account_type: '', account_number: '', holder_name: ''});
        const bankErrors = ref({});
        const payrollForm = ref({monthly_payment: false, reserve_funds: false, family_dependents: 0, education_dependents: 0, roles_entry_date: null, roles_count: 0});
        const payrollErrors = ref({});
        const titleForm = ref({education_level: ''});
        const titleErrors = ref({});
        const expForm = ref({is_current: false});
        const expErrors = ref({});
        const trainForm = ref({training_name: ''});
        const trainErrors = ref({});
        const institutionalForm = ref({area: null, labor_regime: null, position: null, status: null});
        const institutionalErrors = ref({});

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

                    refreshSelect2(modalSelector);
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

        const handlePhotoChange = (event) => {
            const file = event.target.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = (e) => {
                    photoPreview.value = e.target.result;
                };
                reader.readAsDataURL(file);
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

        const fetchListData = async (type) => {
            currentListType.value = type;
            loadingList.value = true;
            listItems.value = [];
            
            // Show the modal
            $('#modalCVListOverlay').removeClass('hidden');

            // Configure headers
            if (type === 'academic') listModalTitle.value = 'Mis Títulos Académicos';
            if (type === 'experience') listModalTitle.value = 'Mi Experiencia Laboral';
            if (type === 'training') listModalTitle.value = 'Mis Capacitaciones';

            try {
                let url = '';
                if (type === 'academic') url = `/employee/api/cv/list-titles/${personId}/`;
                if (type === 'experience') url = `/employee/api/cv/list-experience/${personId}/`;
                if (type === 'training') url = `/employee/api/cv/list-training/${personId}/`;

                if (url) {
                    const res = await (await fetch(url)).json();
                    if (res.success) {
                        listItems.value = res.items;
                    }
                }
            } catch (e) {
                console.error(e);
                window.Toast.fire({icon: 'error', title: 'Error cargando lista'});
            } finally {
                loadingList.value = false;
            }
        };

        const closeModal = (type) => {
             const map = {
                academic: '#modalTitleOverlay',
                experience: '#modalExperienceOverlay',
                training: '#modalTrainingOverlay',
                person: '#modalPersonEditOverlay',
                bank: '#modalBankOverlay',
                payroll: '#modalPayrollOverlay',
                institutional: '#modalInstitutionalOverlay'
            };
            const selector = map[type];
            if (selector) $(selector).addClass('hidden');
        };

        const closeListModal = () => {
            $('#modalCVListOverlay').addClass('hidden');
        };

        const editItem = (item) => {
            if (currentListType.value && item) {
                handleEditCvItem(currentListType.value, item.id);
            }
        };

        const deleteItem = (item) => {
             if (currentListType.value && item) {
                handleDeleteCvItem(currentListType.value, item.id);
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

        const openBankModal = async (personId) => {
             // Reset form first
             bankForm.value = {bank: '', account_type: '', account_number: '', holder_name: ''};
             bankErrors.value = {};
             
             // Fetch existing data
             try {
                // Assuming we somehow have personId in scope or pass it. 
                // Let's rely on the passed argument or the global personId if available.
                const pid = personId || appElement.dataset.personId;
                const response = await fetch(`/employee/person/${pid}/get-bank-account/`);
                const result = await response.json();
                if (result.success && result.data && Object.keys(result.data).length > 0) {
                     bankForm.value = result.data;
                     // Trigger change for select2
                     setTimeout(() => {
                         $('.select2-wizard-bank').trigger('change');
                     }, 100);
                }
             } catch(e) {
                 console.log("No existing bank data or error fetching it", e);
             }

             $('#modalBankOverlay').removeClass('hidden');
             initSelect2('#modalBankOverlay');
        };

        const openPayrollModal = async (personId) => {
             // Reset form
             payrollForm.value = {monthly_payment: false, reserve_funds: false, family_dependents: 0, education_dependents: 0, roles_entry_date: null, roles_count: 0};
             payrollErrors.value = {};
             
             try {
                const pid = personId || appElement.dataset.personId;
                const response = await fetch(`/employee/person/${pid}/get-payroll-info/`);
                const result = await response.json();
                if (result.success && result.data && Object.keys(result.data).length > 0) {
                    payrollForm.value = result.data;
                }
             } catch (e) {
                 console.log("No existing payroll data", e);
             }

             $('#modalPayrollOverlay').removeClass('hidden');
        };

        const saveBankAccount = async (personId) => {
             try {
                const formData = new FormData();
                Object.keys(bankForm.value).forEach(key => {
                    formData.append(key, bankForm.value[key] || '');
                });

                const response = await fetch(`/employee/person/${personId}/add-bank-account/`, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': getCookie('csrftoken')
                    },
                    body: formData
                });
                const data = await response.json();
                if (data.success) {
                    $('#modalBankOverlay').addClass('hidden');
                    // Reload tab or page
                    location.reload(); 
                } else {
                    bankErrors.value = data.errors;
                }
            } catch (error) {
                console.error(error);
                alert("Error al guardar cuenta bancaria");
            }
        };

         const savePayrollInfo = async (personId) => {
             try {
                const formData = new FormData();
                const form = payrollForm.value;

                // Booleans: CheckboxInput in Django checks for presence or 'on'
                if(form.monthly_payment) formData.append('monthly_payment', 'on');
                if(form.reserve_funds) formData.append('reserve_funds', 'on');
                
                // Numbers: Ensure they are not empty strings to avoid validation errors
                formData.append('family_dependents', (form.family_dependents === '' || form.family_dependents == null) ? 0 : form.family_dependents);
                formData.append('education_dependents', (form.education_dependents === '' || form.education_dependents == null) ? 0 : form.education_dependents);
                formData.append('roles_count', (form.roles_count === '' || form.roles_count == null) ? 0 : form.roles_count);
                
                // Dates: Send empty string if null, which Django blank=True accepts
                formData.append('roles_entry_date', form.roles_entry_date || '');

                const response = await fetch(`/employee/person/${personId}/update-payroll-info/`, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': getCookie('csrftoken')
                    },
                    body: formData
                });
                const data = await response.json();
                if (data.success) {
                    $('#modalPayrollOverlay').addClass('hidden');
                    location.reload(); 
                } else {
                    payrollErrors.value = data.errors;
                    console.error("Payroll save errors:", data.errors);
                }
            } catch (error) {
                console.error(error);
                alert("Error al guardar informacion de nomina");
            }
        };

        // --- 9. MÉTODOS: DATOS INSTITUCIONALES ---

        const openInstitutionalModal = async (personId) => {
            institutionalErrors.value = {};
            // Reset form could be here, but we usually fetch first
            try {
                 const pid = personId || appElement.dataset.personId;
                 const response = await fetch(`/employee/person/${pid}/get-institutional-data/`);
                 const res = await response.json();
                 if (res.success) {
                     institutionalForm.value = res.data;
                     
                     // Abrir modal
                     $('#modalInstitutionalOverlay').removeClass('hidden');

                     // Inicializar Select2
                     setTimeout(() => {
                        const $modal = $('#modalInstitutionalOverlay');
                        $modal.find('select.select2-wizard').each(function() {
                             $(this).select2({
                                 dropdownParent: $modal,
                                 width: '100%'
                             }).on('change', function(){
                                 institutionalForm.value[$(this).attr('name')] = $(this).val();
                             });
                             // Set value if exists to trigger visual update
                             if(institutionalForm.value[$(this).attr('name')]) {
                                 $(this).val(institutionalForm.value[$(this).attr('name')]).trigger('change.select2');
                             }
                        });
                     }, 100);
                 } else {
                     window.Toast.fire({icon: 'error', title: 'Error al cargar datos institucionales'});
                 }
            } catch (e) {
                console.error("Error fetching institutional data", e);
                window.Toast.fire({icon: 'error', title: 'Error de conexión'});
            }
        };

        const saveInstitutionalData = async (personId) => {
             if (isSaving.value) return;
             isSaving.value = true;
             
             try {
                 const pid = personId || appElement.dataset.personId;
                 const formData = new FormData();
                 Object.keys(institutionalForm.value).forEach(key => {
                     const val = institutionalForm.value[key];
                     if (val !== null && val !== undefined) {
                         formData.append(key, val);
                     }
                 });

                 const response = await fetch(`/employee/person/${pid}/save-institutional-data/`, {
                     method: 'POST',
                     headers: {
                         'X-CSRFToken': window.getCookie('csrftoken')
                     },
                     body: formData
                 });
                 const res = await response.json();
                 
                 if (res.success) {
                     window.Toast.fire({icon: 'success', title: res.message});
                     $('#modalInstitutionalOverlay').addClass('hidden');
                     setTimeout(() => location.reload(), 500);
                 } else {
                     institutionalErrors.value = res.errors;
                     window.Toast.fire({icon: 'warning', title: 'Revise los campos'});
                 }
             } catch (e) {
                 console.error("Error saving institutional data", e);
                 window.Toast.fire({icon: 'error', title: 'Error al guardar'});
             } finally {
                 isSaving.value = false;
             }
        };


        return {
            // Estados
            tabs,
            activeTab,
            isSaving,
            loadingList,
            personStats,
            refreshSelect2,
            initSelect2,
            openModal,
            openBankModal,
            openPayrollModal,
            saveBankAccount,
            savePayrollInfo,
            editForm,
            editErrors,
            titleForm,
            titleErrors,
            expForm,
            expErrors,
            trainForm,
            trainErrors,
            bankForm,
            bankErrors,
            payrollForm,
            payrollErrors,
            institutionalForm,
            institutionalErrors,
            // --- 3. UI Y PREVIEW ---
            photoPreview,
            personData,
            listModalTitle,
            listTableHead,
            listTableBody,
            // --- 3.1 BÚSQUEDA Y FILTRADO ---
            searchQuery,
            listItems,
            filteredItems,

            // Métodos Persona
            openEditPersonModal, closeEditModal, submitPersonEdit, handlePhotoChange,

            // Métodos CV
            handlePdfUpload, closeModal, closeListModal, handleEditCvItem, handleDeleteCvItem,
            submitAcademicTitle, submitExperience, submitTraining,
            editItem, deleteItem,

            // Métodos Bancos
            openBankModal, saveBankAccount, refreshCvTab,

            // Métodos Nómina
            openPayrollModal, savePayrollInfo,

            // Métodos Institucionales
            institutionalForm, institutionalErrors, openInstitutionalModal, saveInstitutionalData,
        };
    }
});

// Montaje Global
document.addEventListener('DOMContentLoaded', () => {
    app.mount('#employeeWizardApp');
});