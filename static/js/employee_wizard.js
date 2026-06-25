/**
 * SIGETH - Employee Wizard Master Controller
 * Versión: 2.0 (Full Integration)
 * Arquitectura: Vue 3 Composition API + Bridge Global
 */

if (typeof Vue === 'undefined') {
    console.error("Vue.js no está cargado.");
}

// Función auxiliar para obtener CSRF token
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

// Hacer getCookie disponible globalmente
window.getCookie = getCookie;

const {createApp, ref, computed, onMounted} = Vue;

const app = createApp({
    delimiters: ['[[', ']]'],
    setup() {
        // --- 1. CONFIGURACIÓN Y ESTADOS CORE ---
        const appElement = document.getElementById('employeeWizardApp');
        const personId = appElement ? appElement.dataset.personId : null;
        const isDashboard = appElement ? appElement.dataset.isDashboard === 'true' : false;
        const canEditPerson = appElement ? appElement.dataset.canEditPerson === 'true' : false;

        // Recuperar el tab activo de localStorage o por defecto 'personal'
        const savedPersonId = localStorage.getItem('wizardPersonId');
        let savedTab = localStorage.getItem('wizardActiveTab');

        // Verificar si la página fue recargada intencionalmente (ej. location.reload() tras guardar)
        let isReload = false;
        const navEntries = window.performance?.getEntriesByType?.("navigation");
        if (navEntries && navEntries.length > 0) {
            isReload = navEntries[0].type === "reload";
        } else if (window.performance && window.performance.navigation) {
            isReload = window.performance.navigation.type === 1; // 1 = TYPE_RELOAD
        }

        // Reiniciar al tab 'personal' si cambiamos de empleado o si es una visita nueva
        if (savedPersonId !== personId || !isReload) {
            savedTab = 'personal';
            localStorage.setItem('wizardPersonId', personId || '');
            localStorage.setItem('wizardActiveTab', 'personal');
        }

        const activeTab = ref(savedTab || 'personal');
        const detailPhotoPreviewUrl = ref(appElement && appElement.dataset.photoUrl ? appElement.dataset.photoUrl : '');
        const detailPhotoHasFile = ref(false);
        Vue.watch(activeTab, (newTab, oldTab) => {
            localStorage.setItem('wizardActiveTab', newTab);

            // Inicializar paginación de acciones si se abre el tab
            if (newTab === 'actions') {
                Vue.nextTick(() => {
                    initActionsLocalPagination();
                });
            }

            // Registro de Auditoría (Solo si cambió el tab realmente)
            if (oldTab && newTab !== oldTab) {
                const sectionMap = {
                    personal: 'Datos personales',
                    institutional: 'Datos institucionales',
                    economic: 'Datos económicos',
                    budget: 'Partida presupuestaria',
                    contracts: 'Historia laboral',
                    permissions: 'Permisos',
                    actions: 'Acciones de personal',
                    sanctions: 'Sanciones',
                    vacations: 'Vacaciones',
                    payments: 'Roles de pago',
                    curriculum: 'Curriculum',
                    telework: 'Teletrabajo',
                    schedule: 'Horario'
                };
                fetch(`/person/audit-log/${personId}/`, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': window.getCookie('csrftoken'),
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    body: new URLSearchParams({
                        action: 'VIEW',
                        section: sectionMap[newTab] || newTab
                    })
                }).catch(err => console.error('Error auditoría:', err));
            }
        });

        // --- LÓGICA DE PAGINACIÓN LOCAL PARA ACCIONES ---
        const initActionsLocalPagination = () => {
            const rowsPerPage = 10;
            let currentPage = 1;
            let searchQuery = ($('#action-search-input').val() || '').toLowerCase();
            const $allRows = $('[data-action-row]');

            const updateTable = () => {
                // Filtramos las filas si hay búsqueda
                const $filteredRows = $allRows.filter(function () {
                    if (!searchQuery) return true;
                    const text = $(this).text().toLowerCase();
                    return text.includes(searchQuery);
                });

                const totalRows = $filteredRows.length;
                const totalPages = Math.max(1, Math.ceil(totalRows / rowsPerPage));

                if (currentPage > totalPages) currentPage = totalPages;
                if (currentPage < 1) currentPage = 1;

                const start = (currentPage - 1) * rowsPerPage;
                const end = start + rowsPerPage;

                $allRows.hide();
                $filteredRows.slice(start, end).show();

                // Actualizar info y estado vacío
                const emptyRow = $('[data-action-empty-row]');
                if (totalRows === 0) {
                    if (emptyRow.length === 0) {
                        $('[data-action-tbody]').append(`
                            <tr data-action-empty-row>
                                <td colspan="6" class="text-center py-5">
                                    <i class="fas fa-inbox" style="font-size: 2.5rem; color: #cbd5e1;"></i>
                                    <p class="text-muted mt-3 mb-0">No hay acciones para la búsqueda.</p>
                                </td>
                            </tr>
                        `);
                    } else {
                        emptyRow.show();
                    }
                    $('[data-action-page-info]').text(`Mostrando 0-0 de 0`);
                    $('[data-action-total-pages]').text(`de 1`);
                    $('[data-action-page-input]').val(1);
                    $('[data-action-prev], [data-action-first], [data-action-next], [data-action-last]').prop('disabled', true);
                } else {
                    if (emptyRow.length) emptyRow.hide();
                    $('[data-action-page-info]').text(`Mostrando ${start + 1}-${Math.min(end, totalRows)} de ${totalRows}`);
                    $('[data-action-total-pages]').text(`de ${totalPages}`);
                    $('[data-action-page-input]').val(currentPage);

                    // Deshabilitar botones
                    $('[data-action-prev], [data-action-first]').prop('disabled', currentPage === 1);
                    $('[data-action-next], [data-action-last]').prop('disabled', currentPage === totalPages);
                }
            };

            // Eventos de botones
            $('[data-action-next]').off('click').on('click', () => {
                currentPage++;
                updateTable();
            });
            $('[data-action-prev]').off('click').on('click', () => {
                currentPage--;
                updateTable();
            });
            $('[data-action-first]').off('click').on('click', () => {
                currentPage = 1;
                updateTable();
            });
            $('[data-action-last]').off('click').on('click', () => {
                currentPage = 99999;
                updateTable();
            });

            $('[data-action-page-input]').off('change').on('change', function () {
                let val = parseInt($(this).val());
                if (!isNaN(val)) {
                    currentPage = val;
                    updateTable();
                }
            });

            // Eventos de búsqueda
            $('#action-search-input').off('input').on('input', function () {
                searchQuery = $(this).val().toLowerCase();
                currentPage = 1;
                updateTable();
            });

            $('#action-clear-btn').off('click').on('click', function () {
                $('#action-search-input').val('');
                searchQuery = '';
                currentPage = 1;
                updateTable();
            });

            updateTable();
        };

        const isActivityModalVisible = ref(false);
        const isReportModalVisible = ref(false);
        const reportDates = ref({start: '', end: ''});

        const teleworkData = ref({
            punches: [],
            activities: [],
            needs_update: false,
            is_own_profile: false,
            has_income: false
        });

        const teleworkForm = ref({
            title: '',
            detail: '',
            percentage: 0
        });

        const fetchTeleworkData = async () => {
            try {
                const res = await (await fetch(`/employee/api/telework/data/${personId}/`)).json();
                if (res.success) {
                    teleworkData.value = res;
                }
            } catch (e) {
                console.error("Error cargando teletrabajo", e);
            }
        };

        const markTelework = async (type) => {
            let lat = 0, lon = 0;
            if ("geolocation" in navigator) {
                try {
                    const position = await new Promise((resolve, reject) => {
                        navigator.geolocation.getCurrentPosition(resolve, reject, {
                            enableHighAccuracy: true, timeout: 5000
                        });
                    });
                    lat = position.coords.latitude;
                    lon = position.coords.longitude;
                } catch (error) {
                    console.warn("GPS falló:", error.message);
                }
            }

            const formData = new FormData();
            formData.append('punch_type', type);
            formData.append('latitude', lat);
            formData.append('longitude', lon);

            const res = await (await fetch(`/employee/api/telework/mark/${personId}/`, {
                method: 'POST',
                headers: {'X-CSRFToken': getCookie('csrftoken')},
                body: formData
            })).json();

            if (res.success) {
                window.Toast.fire({icon: 'success', title: res.message});
                fetchTeleworkData();
            }
        };

        const submitActivity = async () => {
            const formData = new FormData();
            formData.append('title', teleworkForm.value.title);
            formData.append('detail', teleworkForm.value.detail);
            formData.append('percentage', teleworkForm.value.percentage);

            const res = await (await fetch(`/employee/api/telework/add-activity/${personId}/`, {
                method: 'POST',
                headers: {'X-CSRFToken': getCookie('csrftoken')},
                body: formData
            })).json();

            if (res.success) {
                teleworkForm.value = {title: '', detail: '', percentage: 0};
                isActivityModalVisible.value = false;
                fetchTeleworkData();
                window.Toast.fire({icon: 'success', title: 'Actividad registrada'});
            }
        };

        const generateTeleworkReport = async () => {
            // Por ahora, solo una alerta. La lógica de PDF se añadirá después.
            alert(`Generando reporte desde ${reportDates.value.start} hasta ${reportDates.value.end}`);
            isReportModalVisible.value = false;
        };

        Vue.watch(activeTab, (newTab) => {
            if (newTab === 'telework') {
                fetchTeleworkData();
            }
        });

        onMounted(() => {
            if (personId) {
                refreshCvTab(personId);
            }

            if (activeTab.value === 'actions') {
                Vue.nextTick(() => {
                    initActionsLocalPagination();
                });
            }

            if (activeTab.value === 'telework') {
                fetchTeleworkData();
            }
        });


        const isSaving = ref(false);
        const isPhotoSaving = ref(false);
        const loadingList = ref(false);

        // Atributos de datos inyectados por Django
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
                        const lower = selector.toLowerCase();
                        if (lower.includes('title')) titleForm.value[name] = val;
                        if (lower.includes('experience')) expForm.value[name] = val;
                        if (lower.includes('training')) trainForm.value[name] = val;
                        if (lower.includes('person')) editForm.value[name] = val;
                        if (lower.includes('bank')) bankForm.value[name] = val;
                        if (lower.includes('payroll')) payrollForm.value[name] = val;
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
                        if (selector.toLowerCase().includes('bank')) bankForm.value[name] = val;
                        if (selector.toLowerCase().includes('payroll')) payrollForm.value[name] = val;
                    });
                }
            }, 300);
        };
        // --- 2. GESTIÓN DE MODALES ---
        const isListModalVisible = ref(false);
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
                if (type === 'academic') titleForm.value = {id: null, education_level: '', senescyt_number: ''};
                if (type === 'experience') expForm.value = {id: null, is_current: false};
                if (type === 'training') trainForm.value = {id: null};
                if (type === 'bank') { // No action 'new' usually but for consistency
                    bankForm.value = {bank: '', account_type: '', account_number: '', holder_name: ''};
                    bankErrors.value = {};
                }
                if (type === 'payroll') {
                    payrollForm.value = {
                        monthly_payment: false,
                        reserve_funds: false,
                        immediate_reserve_funds: false,
                        family_dependents: 0,
                        education_dependents: 0,
                        roles_entry_date: null,
                        roles_count: 0
                    };
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
            } else if (action === 'edit' && (type === 'academic' || type === 'experience' || type === 'training')) {
                // Show modal for edit WITHOUT resetting the form (form was populated before calling openModal)
                $(selector).removeClass('hidden');
                // Evitar scroll del body mientras el modal esté abierto
                document.body.classList.add('no-scroll');
                // Inicializar select2 y refrescar selects para que muestren los valores precargados
                initSelect2(selector);
                // Pequeña espera para asegurar que Vue haya aplicado los datos y luego refrescar selects
                setTimeout(() => refreshSelect2(selector), 200);

            } else if (action === 'edit' && type === 'payroll') {
                // Similar to bank
                $(selector).removeClass('hidden');
            } else {
                fetchListData(type);
            }
        };

        // --- 2. FORMULARIOS REACTIVOS ---
        const editForm = ref({});
        const editErrors = ref({});
        const bankForm = ref({bank: '', account_type: '', account_number: '', holder_name: ''});
        const bankErrors = ref({});
        const payrollForm = ref({
            monthly_payment: false,
            reserve_funds: false,
            immediate_reserve_funds: false,
            family_dependents: 0,
            education_dependents: 0,
            roles_entry_date: null,
            roles_count: 0
        });
        const payrollErrors = ref({});
        const titleForm = ref({education_level: '', senescyt_number: ''});
        const titleErrors = ref({});
        const expForm = ref({is_current: false});
        const expErrors = ref({});
        const trainForm = ref({training_name: ''});
        const trainErrors = ref({});
        const institutionalForm = ref({
            area: null,
            employment_status: null,
            file_number: '',
            biometric_id: '',
            institutional_email: '',
            observations: ''
        });
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

        const formatDate = (iso) => {
            if (!iso) return '';
            const d = new Date(iso);
            if (isNaN(d)) return iso;
            return d.toLocaleDateString('es-ES');
        };

        const durationBetween = (startIso, endIso, isCurrent) => {
            if (!startIso) return '';
            const start = new Date(startIso);
            const end = (isCurrent || !endIso) ? new Date() : new Date(endIso);
            if (isNaN(start) || isNaN(end)) return '';
            let totalMonths = (end.getFullYear() - start.getFullYear()) * 12 + (end.getMonth() - start.getMonth());
            if (totalMonths < 0) totalMonths = 0;
            const years = Math.floor(totalMonths / 12);
            const months = totalMonths % 12;
            const parts = [];
            if (years > 0) parts.push(years + (years === 1 ? ' año' : ' años'));
            if (months > 0) parts.push(months + (months === 1 ? ' mes' : ' meses'));
            return parts.length ? parts.join(' ') : '0 meses';
        };

        // --- 4. CONFIGURACIÓN DE PESTAÑAS ---
        const hiddenTabIds = new Set(
            (appElement?.dataset.hiddenTabs || '')
                .split(',')
                .map(t => t.trim())
                .filter(Boolean)
        );

        let visibilities = {};
        try {
            const dataScript = document.getElementById('tab-visibilities-data');
            if (dataScript) {
                visibilities = JSON.parse(dataScript.textContent);
            }
        } catch (e) {
            console.error("Error parsing tab visibilities", e);
        }

        const getSavedVisibility = (tabId) => {
            if (visibilities.hasOwnProperty(tabId)) {
                return Boolean(visibilities[tabId]);
            }
            // Fallback for default tabs if not in the dataset
            const defaultTabs = ['personal', 'curriculum', 'institutional', 'economic'];
            return defaultTabs.includes(tabId);
        };

        const tabsBase = [
            {
                id: 'personal',
                name: 'Datos Personales',
                icon: 'fa-solid fa-user',
                class: 'employee-detail-button-personal',
                isVisible: getSavedVisibility('personal')
            },
            {
                id: 'curriculum',
                name: 'Currículum Vitae',
                icon: 'fa-solid fa-file-invoice',
                class: 'employee-detail-button-curriculum',
                isVisible: getSavedVisibility('curriculum')
            },
            {
                id: 'institutional',
                name: 'Datos Inst.',
                icon: 'fa-solid fa-building',
                class: 'employee-detail-button-institutional',
                isVisible: getSavedVisibility('institutional')
            },
            {
                id: 'economic',
                name: 'Datos Económicos',
                icon: 'fa-solid fa-money-bill-1-wave',
                class: 'employee-detail-button-economic',
                isVisible: getSavedVisibility('economic')
            },
            {
                id: 'budget',
                name: 'Partida Presup.',
                icon: 'fa-solid fa-address-book',
                class: 'employee-detail-button-budget',
                isVisible: getSavedVisibility('budget')
            },
            {
                id: 'contracts',
                name: 'Historia Lab.',
                icon: 'fa-solid fa-clock-rotate-left',
                class: 'employee-detail-button-history',
                isVisible: getSavedVisibility('contracts')
            },
            {
                id: 'permissions',
                name: 'Permisos',
                icon: 'fa-solid fa-calendar-check',
                class: 'employee-detail-button-permissions',
                isVisible: getSavedVisibility('permissions')
            },
            {
                id: 'actions',
                name: 'Acciones Pers.',
                icon: 'fa-solid fa-file-invoice',
                class: 'employee-detail-button-actions',
                isVisible: getSavedVisibility('actions')
            },
            {
                id: 'sanctions',
                name: 'Sanciones',
                icon: 'fa-solid fa-gavel',
                class: 'employee-detail-button-sanctions',
                isVisible: getSavedVisibility('sanctions')
            },
            {
                id: 'vacations',
                name: 'Vacaciones',
                icon: 'fa-solid fa-plane',
                class: 'employee-detail-button-vacations',
                isVisible: getSavedVisibility('vacations')
            },
            {
                id: 'payments',
                name: 'Roles de pago',
                icon: 'fa-solid fa-money-bill',
                class: 'employee-detail-button-payments',
                isVisible: getSavedVisibility('payments')
            },
            {
                id: 'schedule',
                name: 'Horario',
                icon: 'fa-solid fa-clock',
                class: 'employee-detail-button-schedule',
                isVisible: getSavedVisibility('schedule')
            },
            {
                id: 'telework',
                name: 'Teletrabajo',
                icon: 'fa-solid fa-house-laptop',
                class: 'employee-detail-button-telework',
                isVisible: getSavedVisibility('telework')
            },
        ];

        const tabs = ref(tabsBase.filter(tab => !hiddenTabIds.has(tab.id)));

        // If it's the dashboard view, filter out the tabs that are not visible
        if (isDashboard) {
            tabs.value = tabs.value.filter(tab => tab.isVisible);
        }

        if (!tabs.value.some(tab => tab.id === activeTab.value)) {
            activeTab.value = tabs.value.length ? tabs.value[0].id : 'personal';
        }

        const toggleTabVisibility = async (tab) => {
            const action = tab.isVisible ? 'deshabilitar' : 'habilitar';

            const {value: selection} = await Swal.fire({
                title: `¿Cómo desea ${action} la pestaña "${tab.name}"?`,
                icon: 'question',
                showDenyButton: true,
                showCancelButton: true,
                confirmButtonText: 'Solo para este empleado',
                denyButtonText: 'Para TODOS los empleados',
                cancelButtonText: 'Cancelar',
                confirmButtonColor: '#3b82f6', // Azul
                denyButtonColor: '#10b981',    // Verde
            });

            // 1. CASO: SOLO PARA ESTE EMPLEADO (Botón Principal)
            if (selection === true) {
                IndividualChange(tab);
            }
            // 2. CASO: PARA TODOS (Botón "Deny" que usamos como masivo)
            else if (selection === false) {
                MassiveChange(tab);
            }
        };
        const IndividualChange = async (tab) => {
            const newVisibility = !tab.isVisible;
            try {
                const response = await fetch('/employee/api/profile-visibility/', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken')},
                    body: JSON.stringify({
                        user_id: personId,
                        tab_id: tab.id,
                        is_visible: newVisibility
                    })
                });
                const data = await response.json();
                if (data.success) {
                    tab.isVisible = newVisibility;
                    window.Toast.fire({icon: 'success', title: 'Actualizado para este usuario'});
                }
            } catch (error) {
                Swal.fire('Error', 'Problema de conexión', 'error');
            }
        };

// Función nueva para el cambio masivo
        const MassiveChange = async (tab) => {
            const newVisibility = !tab.isVisible;
            const actionText = newVisibility ? 'habilitado' : 'deshabilitado';

            try {
                const formData = new FormData();
                formData.append('tab_id', tab.id);
                formData.append('is_visible', newVisibility);

                const response = await fetch('/employee/api/bulk-visibility/', {
                    method: 'POST',
                    headers: {'X-CSRFToken': getCookie('csrftoken')},
                    body: formData
                });
                const data = await response.json();

                if (data.success) {
                    tab.isVisible = newVisibility; // Actualizamos la vista actual
                    Swal.fire('¡Éxito Masivo!', `Se ha ${actionText} la pestaña para todos los empleados.`, 'success');
                }
            } catch (error) {
                Swal.fire('Error', 'No se pudo realizar la acción masiva', 'error');
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
                    isListModalVisible.value = false;

                    if (type === 'academic') {
                        titleForm.value = res.data;
                        openModal('academic', 'edit');
                    }
                    if (type === 'experience') {
                        expForm.value = res.data;
                        openModal('experience', 'edit');
                    }
                    if (type === 'training') {
                        trainForm.value = res.data;
                        openModal('training', 'edit');
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

                if (!response.ok) {
                    const errorData = await response.json();
                    console.error('Error del servidor:', errorData);
                    window.Toast.fire({
                        icon: 'error',
                        title: errorData.message || 'Error al actualizar datos',
                        text: JSON.stringify(errorData.errors || {})
                    });
                    editErrors.value = errorData.errors || {};
                    isSaving.value = false;
                    return;
                }

                const res = await response.json();
                if (res.success) {
                    window.Toast.fire({icon: 'success', title: res.message});
                    setTimeout(() => location.reload(), 1000);
                } else {
                    editErrors.value = res.errors;
                    window.Toast.fire({icon: 'warning', title: 'Revise los campos'});
                }
            } catch (e) {
                console.error('Error capturado:', e);
                window.Toast.fire({icon: 'error', title: 'Error de servidor: ' + e.message});
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

        const handleDetailPhotoChange = (event) => {
            const file = event.target.files && event.target.files[0];
            if (!file) return;

            detailPhotoHasFile.value = true;
            const reader = new FileReader();
            reader.onload = (e) => {
                detailPhotoPreviewUrl.value = e.target.result;
            };
            reader.readAsDataURL(file);
        };

        const submitDetailPhotoUpdate = async () => {
            if (isPhotoSaving.value) return;

            const form = document.getElementById('detailPhotoForm');
            const input = document.getElementById('detailPhotoInput');

            if (!form || !input || !input.files || !input.files[0]) {
                window.Toast.fire({icon: 'warning', title: 'Seleccione una foto primero.'});
                return;
            }

            isPhotoSaving.value = true;
            const formData = new FormData(form);

            try {
                const response = await fetch(form.action, {
                    method: 'POST',
                    body: formData,
                    headers: {'X-CSRFToken': window.getCookie('csrftoken')}
                });
                const result = await response.json();

                if (response.ok && result.success) {
                    window.Toast.fire({icon: 'success', title: result.message || 'Foto actualizada correctamente.'});
                    setTimeout(() => location.reload(), 700);
                    return;
                }

                window.Toast.fire({icon: 'error', title: result.message || 'No se pudo actualizar la foto.'});
            } catch (e) {
                console.error('Error actualizando foto:', e);
                window.Toast.fire({icon: 'error', title: 'Error de comunicación con el servidor.'});
            } finally {
                isPhotoSaving.value = false;
            }
        };

        const getAuditQueryValue = () => {
            return (document.getElementById('personAuditSearchInput')?.value || '').trim();
        };

        const loadAuditHistory = async (page = 1) => {
            const results = document.getElementById('personAuditResults');
            if (!results) return;

            const query = getAuditQueryValue();
            results.innerHTML = '<div class="py-4 text-center text-muted"><i class="fa-solid fa-spinner fa-spin me-2"></i>Cargando movimientos...</div>';

            try {
                const params = new URLSearchParams();
                params.set('page', String(page));
                if (query) params.set('q', query);

                const response = await fetch(`/person/audit-history/${personId}/?${params.toString()}`, {
                    headers: {'X-Requested-With': 'XMLHttpRequest'}
                });
                results.innerHTML = await response.text();
            } catch (error) {
                console.error('Error cargando auditoría:', error);
                results.innerHTML = '<div class="py-4 text-center text-danger">No se pudo cargar la auditoría.</div>';
            }
        };

        const openAuditModal = async (pId) => {
            const modal = document.getElementById('personAuditOverlay');
            const results = document.getElementById('personAuditResults');
            if (!modal || !results) return;

            modal.classList.remove('hidden');
            document.body.classList.add('no-scroll');

            if (!modal.dataset.auditBound) {
                document.getElementById('personAuditSearchBtn')?.addEventListener('click', () => loadAuditHistory(1));
                document.getElementById('personAuditResetBtn')?.addEventListener('click', () => {
                    const input = document.getElementById('personAuditSearchInput');
                    if (input) input.value = '';
                    loadAuditHistory(1);
                });
                document.getElementById('personAuditSearchInput')?.addEventListener('keydown', (event) => {
                    if (event.key === 'Enter') {
                        event.preventDefault();
                        loadAuditHistory(1);
                    }
                });
                document.getElementById('personAuditExportBtn')?.addEventListener('click', async () => {
                    const query = getAuditQueryValue();
                    const params = new URLSearchParams();
                    if (query) params.set('q', query);
                    params.set('export', '1');

                    try {
                        const response = await fetch(`/person/audit-history/${personId}/?${params.toString()}`, {
                            headers: {'X-Requested-With': 'XMLHttpRequest'}
                        });
                        const blob = await response.blob();
                        const url = window.URL.createObjectURL(blob);
                        const a = document.createElement('a');
                        a.href = url;
                        a.download = `auditoria_persona_${personId}.xlsx`;
                        document.body.appendChild(a);
                        a.click();
                        a.remove();
                        window.URL.revokeObjectURL(url);
                    } catch (error) {
                        console.error('Error exportando auditoría:', error);
                    }
                });

                results.addEventListener('click', (event) => {
                    const button = event.target.closest('.js-audit-page');
                    if (!button || button.disabled) return;
                    loadAuditHistory(Number(button.dataset.page || 1));
                });
                modal.dataset.auditBound = '1';
            }

            await loadAuditHistory(1);
        };

        const closeAuditModal = () => {
            const modal = document.getElementById('personAuditOverlay');
            if (modal) modal.classList.add('hidden');
            document.body.classList.remove('no-scroll');
        };

        const closeEditModal = () => {
            $('#modalPersonEditOverlay').addClass('hidden');
            document.body.classList.remove('no-scroll');
        };

        // --- 7. MÉTODOS: CURRICULUM VITAE (PDF Y CRUD) ---

        const refreshCvTab = async (pId) => {
            // En lugar de reemplazar todo el HTML, actualizar solo los contadores

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


            } catch (e) {
                console.error('Error actualizando estadísticas:', e);
            }
        };

        const refreshInstitutionalTab = async (pId) => {
            try {
                const pid = pId || appElement.dataset.personId;
                const res = await (await fetch(`/employee/person/${pid}/get-institutional-data/`)).json();
                if (res.success && res.data) {
                    // Update reactive form
                    institutionalForm.value = res.data;

                    // Update DOM elements in the institutional tab (so we don't reload whole page)
                    const setText = (id, value) => {
                        const el = document.getElementById(id);
                        if (el) el.textContent = (value !== null && value !== undefined && value !== '') ? value : '—';
                    };

                    setText('inst_file_number', res.data.file_number || '—');
                    setText('inst_biometric_id', res.data.biometric_id || 'No registrado');
                    setText('inst_entry_date', res.data.entry_date ? new Date(res.data.entry_date).toLocaleDateString('es-ES') : '—');
                    setText('inst_institutional_email', res.data.institutional_email || 'Sin especificar');
                    setText('inst_area', res.data.area_name || (appElement.dataset.areaName || 'Sin asignar'));
                    setText('inst_employment_status', res.data.employment_status_name || '—');
                    // Es jefe
                    const isBossEl = document.getElementById('inst_is_boss');
                    if (isBossEl) {
                        const isBoss = !!res.data.is_boss;
                        isBossEl.textContent = isBoss ? 'SÍ' : 'NO';
                        isBossEl.classList.remove('active', 'neutral');
                        isBossEl.classList.add(isBoss ? 'active' : 'neutral');
                    }
                    // Contrato colectivo
                    const collEl = document.getElementById('inst_collective_contract');
                    if (collEl) {
                        collEl.innerHTML = res.data.collective_contract ? '<span class="status-badge neutral">SÍ</span>' : '<span class="status-badge neutral">NO</span>';
                    }
                    setText('inst_observations', res.data.observations || 'Ninguna observación registrada.');

                    // Set active tab to institutional so UI remains there
                    activeTab.value = 'institutional';
                }
            } catch (e) {
                console.error('Error refreshing institutional tab', e);
            } finally {
                // Ensure body scroll is enabled
                document.body.classList.remove('no-scroll');
            }
        };

        const refreshEconomicTab = async (pId) => {
            try {
                const pid = pId || appElement.dataset.personId;

                // Fetch both bank and payroll summaries
                const [bankRes, payrollRes] = await Promise.all([
                    fetch(`/employee/person/${pid}/get-bank-account/`),
                    fetch(`/employee/person/${pid}/get-payroll-info/`)
                ]);

                const bankData = await bankRes.json();
                const payrollData = await payrollRes.json();


                // Update DOM elements if present
                if (bankData && bankData.success) {
                    const b = bankData.data || {};
                    // Support multiple response shapes
                    const bankName = b.bank_name || (b.bank && (b.bank.name || b.bank_name)) || '';
                    const accountTypeName = b.account_type_name || (b.account_type && (b.account_type.name || b.account_type)) || '';
                    const accountNumber = b.account_number || b.account || '';
                    const holderName = b.holder_name || b.holder || '';
                    const isActive = (typeof b.is_active !== 'undefined') ? b.is_active : (b.active || false);
                    const setText = (id, val) => {
                        const el = document.getElementById(id);
                        if (el) el.textContent = (val !== null && val !== undefined && val !== '') ? val : '—';
                    };
                    setText('econ_bank_institution', bankName || '—');
                    setText('econ_bank_type', accountTypeName || '—');
                    setText('econ_bank_number', accountNumber || '—');
                    setText('econ_bank_holder', holderName || '—');
                    const statusEl = document.getElementById('econ_bank_status');
                    if (statusEl) {
                        statusEl.textContent = isActive ? 'Activa' : 'Inactiva';
                        statusEl.classList.remove('active', 'neutral');
                        statusEl.classList.add(isActive ? 'active' : 'neutral');
                    }
                } else {

                }

                if (payrollData && payrollData.success) {
                    const p = payrollData.data || {};
                    // Update small summary fields in the tab if exist
                    const setText = (id, val) => {
                        const el = document.getElementById(id);
                        if (el) el.textContent = (val !== null && val !== undefined && val !== '') ? val : '—';
                    };
                    setText('econ_payroll_monthly', p.monthly_payment ? 'SÍ' : 'NO');
                    setText('econ_payroll_reserve', p.reserve_funds ? 'ACUMULA' : 'NO ACUMULA');
                    setText('econ_payroll_family', p.family_dependents ?? '0');
                    setText('econ_payroll_education', p.education_dependents ?? '0');
                    setText('econ_payroll_roles_entry', p.roles_entry_date ? new Date(p.roles_entry_date).toLocaleDateString('es-ES') : '—');
                    // Mantener la pestaña activa en económico
                    activeTab.value = 'economic';
                } else {

                }
            } catch (e) {
                console.error('Error refreshing economic tab', e);
            } finally {
                document.body.classList.remove('no-scroll');
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
                    // Attempt to update the CV action banner buttons without reloading the page
                    try {
                        const wrapper = document.querySelector('.cv-action-banner .header-actions-wrapper');
                        if (wrapper) {
                            // Keep the existing file input (Vue attached handler) if present
                            const fileInput = wrapper.querySelector('#pdfInput');
                            // Remove existing action buttons
                            Array.from(wrapper.querySelectorAll('.btn-header-premium')).forEach(n => n.remove());

                            // Determine file URL from response (try multiple possible keys)
                            const url = (res.data && (res.data.pdf_file && res.data.pdf_file.url)) || res.data?.file_url || res.data?.url || res.file_url || res.url || null;

                            // Build buttons HTML
                            let buttonsHtml = '';
                            if (url) {
                                buttonsHtml += `<a href="${url}" target="_blank" class="btn-header-premium" style="background: #3b82f6; color: white;"><i class="fa-solid fa-eye"></i> VER DOCUMENTO</a>`;
                            }
                            buttonsHtml += `<button class="btn-header-premium" style="background: #10b981; color: white;" onclick="document.getElementById('pdfInput').click()"><i class="fa-solid fa-arrows-rotate"></i> ACTUALIZAR</button>`;

                            // Insert after the file input if it exists, otherwise append to wrapper
                            if (fileInput) fileInput.insertAdjacentHTML('afterend', buttonsHtml);
                            else wrapper.insertAdjacentHTML('beforeend', buttonsHtml);
                        }
                    } catch (e) {
                        console.warn('Error updating CV banner buttons', e);
                    }
                    // Refresh counters and small UI on the CV tab
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
            isListModalVisible.value = true;

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
                        // Si pedimos experiencia, actualizar los contadores de tiempo total
                        if (type === 'experience') {
                            personStats.value.experienceYears = res.total_years || 0;
                            personStats.value.experienceMonths = res.total_months || 0;
                            // También mantener contaje de ítems
                            personStats.value.experiences = res.items ? res.items.length : 0;
                        }
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
            isListModalVisible.value = false;
            currentListType.value = '';
            document.body.classList.remove('no-scroll');
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

        const handleCvAction = (type, action) => {
            if (action === 'new' && !canEditPerson) return;
            openModal(type, action);
        };

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
                    // Set underlying select values so select2 shows the correct items
                    setTimeout(() => {
                        try {
                            if (bankForm.value.bank) $('.select2-wizard-bank[name="bank"]').val(bankForm.value.bank).trigger('change');
                            if (bankForm.value.account_type) $('.select2-wizard-bank[name="account_type"]').val(bankForm.value.account_type).trigger('change');
                        } catch (e) {
                            console.warn('select2 set value failed', e);
                        }
                    }, 120);
                }
            } catch (e) {

            }

            $('#modalBankOverlay').removeClass('hidden');
            initSelect2('#modalBankOverlay');
        };

        const openPayrollModal = async (personId) => {
            // Reset form
            payrollForm.value = {
                monthly_payment: false,
                reserve_funds: false,
                immediate_reserve_funds: false,
                family_dependents: 0,
                education_dependents: 0,
                roles_entry_date: null,
                roles_count: 0
            };
            payrollErrors.value = {};

            try {
                const pid = personId || appElement.dataset.personId;
                const response = await fetch(`/employee/person/${pid}/get-payroll-info/`);
                const result = await response.json();
                if (result.success && result.data && Object.keys(result.data).length > 0) {
                    payrollForm.value = result.data;
                }
            } catch (e) {

            }

            $('#modalPayrollOverlay').removeClass('hidden');
        };

        const saveBankAccount = async (personId) => {
            try {
                const pid = personId || appElement.dataset.personId;
                // Build form payload, prefer reactive state but fallback to DOM values
                const formData = new FormData();
                const payloadDebug = {};
                const keys = ['bank', 'account_type', 'account_number', 'holder_name'];
                keys.forEach(key => {
                    let val = bankForm.value ? bankForm.value[key] : '';
                    // If reactive state is empty, try jQuery (.val()) first because select2 plays with DOM
                    if ((val === undefined || val === null || val === '')) {
                        try {
                            if (window.jQuery && window.jQuery(`[name="${key}"]`).length) {
                                val = window.jQuery(`[name="${key}"]`).val();
                            } else if (document.querySelector(`[name="${key}"]`)) {
                                val = document.querySelector(`[name="${key}"]`).value;
                            }
                        } catch (e) {
                            val = '';
                        }
                    }
                    if (val === undefined || val === null) val = '';
                    formData.append(key, val);
                    payloadDebug[key] = val;
                });
                // More debug: if selects are blank, show underlying select element and jQuery state
                try {
                    const bankEl = document.querySelector('[name="bank"]');
                    console.debug('bank select element', bankEl, window.jQuery ? window.jQuery('[name="bank"]').val() : null);
                    const typeEl = document.querySelector('[name="account_type"]');
                    console.debug('account_type select element', typeEl, window.jQuery ? window.jQuery('[name="account_type"]').val() : null);
                } catch (e) {
                }
                // Debug log: muestra en consola los valores que se enviarán
                console.debug('saveBankAccount payload', payloadDebug);

                const response = await fetch(`/employee/person/${pid}/add-bank-account/`, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': getCookie('csrftoken')
                    },
                    body: formData
                });
                const data = await response.json();
                if (data.success) {
                    $('#modalBankOverlay').addClass('hidden');
                    // Mensaje de éxito (SweetAlert2 si está disponible)
                    if (window.Swal) {
                        Swal.fire({
                            position: 'top-end',
                            icon: 'success',
                            title: data.message || 'Guardado',
                            showConfirmButton: false,
                            timer: 1400
                        });
                    } else if (window.Toast) {
                        window.Toast.fire({icon: 'success', title: data.message || 'Guardado'});
                    }
                    // Refrescar sólo el tab económico
                    await refreshEconomicTab(pid);
                } else {
                    bankErrors.value = data.errors;
                }
            } catch (error) {
                console.error(error);
                console.debug('bankForm current state', bankForm.value);
                if (window.Swal) Swal.fire({position: 'top-end', icon: 'error', title: 'Error al guardar'});
                else alert("Error al guardar cuenta bancaria");
            }
        };

        const savePayrollInfo = async (personId) => {
            try {
                const pid = personId || appElement.dataset.personId;
                const formData = new FormData();
                const form = payrollForm.value;

                // Booleans: CheckboxInput in Django checks for presence or 'on'
                if (form.monthly_payment) formData.append('monthly_payment', 'on');
                if (form.reserve_funds) formData.append('reserve_funds', 'on');
                if (form.immediate_reserve_funds) formData.append('immediate_reserve_funds', 'on');

                // Numbers: Ensure they are not empty strings to avoid validation errors
                formData.append('family_dependents', (form.family_dependents === '' || form.family_dependents == null) ? 0 : form.family_dependents);
                formData.append('education_dependents', (form.education_dependents === '' || form.education_dependents == null) ? 0 : form.education_dependents);
                formData.append('roles_count', (form.roles_count === '' || form.roles_count == null) ? 0 : form.roles_count);

                // Dates: Send empty string if null, which Django blank=True accepts
                formData.append('roles_entry_date', form.roles_entry_date || '');

                const response = await fetch(`/employee/person/${pid}/update-payroll-info/`, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': getCookie('csrftoken')
                    },
                    body: formData
                });
                const data = await response.json();
                if (data.success) {
                    $('#modalPayrollOverlay').addClass('hidden');
                    if (window.Swal) {
                        Swal.fire({
                            position: 'top-end',
                            icon: 'success',
                            title: data.message || 'Guardado',
                            showConfirmButton: false,
                            timer: 1400
                        });
                    } else if (window.Toast) {
                        window.Toast.fire({icon: 'success', title: data.message || 'Guardado'});
                    }
                    // Refrescar sólo el tab económico
                    await refreshEconomicTab(pid);
                } else {
                    payrollErrors.value = data.errors;
                    console.error("Payroll save errors:", data.errors);
                }
            } catch (error) {
                console.error(error);
                if (window.Swal) Swal.fire({position: 'top-end', icon: 'error', title: 'Error al guardar'});
                else alert("Error al guardar informacion de nomina");
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

                    // Abrir modal (solo mostrar campos editables en este modal)
                    $('#modalInstitutionalOverlay').removeClass('hidden');
                    document.body.classList.add('no-scroll');
                } else {
                    window.Toast.fire({icon: 'error', title: 'Error al cargar datos institucionales'});
                }
            } catch (e) {
                console.error("Error fetching institutional data", e);
                window.Toast.fire({icon: 'error', title: 'Error de conexión'});
            }
        };

        const openScheduleChangeModal = (empId) => {
            // La URL debe coincidir con la de tu urls.py: name='employee_schedule_change_modal'
            const url = `/schedule/assignment/change-modal/${empId}/`;
            const modalPlaceholder = document.getElementById('action-modal-employee');

            if (!modalPlaceholder) return;

            fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
                .then(response => {
                    if (!response.ok) throw new Error('Error al cargar el modal');
                    return response.text();
                })
                .then(html => {
                    modalPlaceholder.innerHTML = `
                <div class="modal-overlay" style="display:flex; align-items:center; justify-content:center;">
                    <div class="animate__animated animate__fadeInDown" 
                         style="max-width:650px; width:100%; background:transparent;"> 
                        ${html}
                    </div>
                </div>
            `;
                    document.body.classList.add('no-scroll');

                    // Si el modal tiene un botón de cerrar manual con clase 'js-close-modal'
                    const closeBtn = modalPlaceholder.querySelector('.btn-cancel, .btn-close-modal');
                    if (closeBtn) {
                        closeBtn.onclick = () => {
                            modalPlaceholder.innerHTML = '';
                            document.body.classList.remove('no-scroll');
                        };
                    }
                })
                .catch(err => {
                    console.error(err);
                    Swal.fire("Error", "No se pudo cargar el formulario de horarios.", "error");
                });
        };
        $(document).on('submit', '#action-modal-employee form', function (e) {
            e.preventDefault();
            const $form = $(this);
            $.ajax({
                url: $form.attr('action'),
                method: 'POST',
                data: $form.serialize(),
                success: function (res) {
                    if (res.success) {
                        Swal.fire("¡Éxito!", res.message, "success");
                        $('#action-modal-employee').empty(); // Cerramos el modal
                        document.body.classList.remove('no-scroll');
                        location.reload();
                    }
                }
            });
        });

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
                        'X-CSRFToken': getCookie('csrftoken')
                    },
                    body: formData
                });
                const res = await response.json();

                if (res.success) {
                    window.Toast.fire({icon: 'success', title: res.message});
                    $('#modalInstitutionalOverlay').addClass('hidden');
                    // Refrescar sólo el tab institucional y mantenerlo activo
                    await refreshInstitutionalTab(pid);
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
            detailPhotoPreviewUrl,
            detailPhotoHasFile,
            personStats,
            canEditPerson,
            isListModalVisible,
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
            currentListType,
            openScheduleChangeModal,
            // Métodos Persona
            openEditPersonModal,
            closeEditModal,
            submitPersonEdit,
            handlePhotoChange,
            openAuditModal,
            closeAuditModal,
            handleDetailPhotoChange,
            submitDetailPhotoUpdate,

            // Métodos CV
            handlePdfUpload,
            closeModal,
            closeListModal,
            handleEditCvItem,
            handleDeleteCvItem,
            submitAcademicTitle,
            submitExperience,
            submitTraining,
            editItem,
            deleteItem,
            formatDate,
            durationBetween,
            handleCvAction,

            // Métodos Bancos
            openBankModal,
            saveBankAccount,
            refreshEconomicTab,
            refreshCvTab,

            // Métodos Nómina
            openPayrollModal,
            savePayrollInfo,

            // Métodos Institucionales
            institutionalForm,
            institutionalErrors,
            openInstitutionalModal,
            saveInstitutionalData,
            refreshInstitutionalTab,

            toggleTabVisibility,
            teleworkData,
            teleworkForm,
            markTelework,
            submitActivity,
            fetchTeleworkData,
            isActivityModalVisible,
            isReportModalVisible,
            reportDates,
            generateTeleworkReport,
        };
    }
});
$(document).on('click', '.js-close-detail-modal', function () {
    $('#action-modal-employee').empty();
    $('body').removeClass('modal-open');
});

// Delegación global para abrir el detalle de la acción (Evita eventos duplicados y 404s)
$(document).off('click', '.js-view-action-detail').on('click', '.js-view-action-detail', function (e) {
    e.preventDefault();
    const url = $(this).data('url');
    const modalPlaceholder = $('#action-modal-employee');

    fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
        .then(response => response.json())
        .then(data => {
            if (data && data.html) {
                modalPlaceholder.html(`
                    <div class="modal-overlay" style="display:flex;">
                        <div class="modal-container-medium animate-scale-in shadow-card animate__animated animate__fadeInDown" 
                             style="max-width:850px;background:#fff;border-radius:12px;display:flex;flex-direction:column;max-height:85vh;overflow:hidden;box-shadow:0 25px 50px -12px rgba(0,0,0,.25);">
                            <div style="display:flex;flex-direction:column;height:100%;width:100%;">
                                ${data.html}
                            </div>
                        </div>
                    </div>
                `);
                $('body').addClass('modal-open');
            } else {
                Swal.fire("Error", "Respuesta inválida del servidor al cargar el detalle.", "error");
            }
        })
        .catch(err => Swal.fire("Error", "No se pudo cargar el detalle de la acción.", "error"));
});

// Montaje Global
document.addEventListener('DOMContentLoaded', () => {
    app.mount('#employeeWizardApp');
});