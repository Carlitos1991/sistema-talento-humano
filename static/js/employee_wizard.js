// Asegurémonos de que Vue esté disponible
if (typeof Vue === 'undefined') {
    console.error("Vue.js no está cargado. Revisa la CDN en base.html");
}

const {createApp, ref, onMounted} = Vue;

const app = createApp({
    delimiters: ['[[', ']]'],
    setup() {
        const activeTab = ref('personal');
        const isSaving = ref(false);
        // Datos reactivos
        const titleForm = ref({is_current: false});
        const titleErrors = ref({});
        const bankForm = ref({});
        const bankErrors = ref({});
        const editForm = ref({});
        const editErrors = ref({});
        const photoPreview = ref(null);
        const personData = ref({full_name: ''});

        // Pestañas con sus clases de estilo premium
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
                id: 'institutional',
                name: 'Datos Inst.',
                icon: 'fa-solid fa-building',
                class: 'employee-detail-button-institutional'
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
            {id: 'actions', name: 'Acciones Pers.', icon: 'fa-solid fa-gavel', class: 'employee-detail-button-actions'},
            {id: 'vacations', name: 'Vacaciones', icon: 'fa-solid fa-plane', class: 'employee-detail-button-vacations'},
        ];
        const initModalSelects = () => {
            // Usamos un pequeño delay para asegurar que Vue ya renderizó los elementos
            setTimeout(() => {
                $('.select2-wizard').select2({
                    dropdownParent: $('#modalPersonEditOverlay'), // Vital para que el dropdown no quede detrás del modal
                    width: '100%',
                    language: {noResults: () => "No se encontraron resultados"}
                }).on('change', function (e) {
                    // Sincronizar el cambio de Select2 con el objeto reactivo de Vue
                    const fieldName = $(this).attr('name');
                    const value = $(this).val();
                    editForm.value[fieldName] = value;

                    // Si el cambio es en país/provincia/cantón, disparar la carga de cascada
                    if (fieldName === 'country') handleLocationChange(value, 'id_province_modal');
                    if (fieldName === 'province') handleLocationChange(value, 'id_canton_modal');
                    if (fieldName === 'canton') handleLocationChange(value, 'id_parish_modal');
                });
            }, 100);
        };
        // Función auxiliar para cascada desde Select2
        const handleLocationChange = async (parentId, targetId) => {
            await loadLocations(parentId, targetId);
            // Refrescar el Select2 del hijo para que muestre los nuevos datos
            $(`#${targetId}`).trigger('change.select2');
        };

        // Métodos de UI
        const openBankModal = () => {
            bankErrors.value = {};
            const modal = document.getElementById('modalBankOverlay');
            if (modal) modal.classList.remove('hidden');
        };

        const openTitleModal = () => {
            titleErrors.value = {};
            const modal = document.getElementById('modalTitleOverlay');
            if (modal) modal.classList.remove('hidden');
        };
        const openEditPersonModal = async (personId) => {
            editErrors.value = {};
            const modal = document.getElementById('modalPersonEditOverlay');
            if (!modal) {
                console.error("ERROR CRÍTICO: No se encontró el elemento con ID 'modalPersonEditOverlay' en el DOM.");
                window.Toast.fire({icon: 'error', title: 'Error interno: No se encuentra el contenedor del modal.'});
                return; // Detenemos la ejecución aquí
            }
            editErrors.value = {};
            try {
                const response = await fetch(`/person/detail/${personId}/`);
                if (!response.ok) throw new Error("Error en la respuesta del servidor");

                const res = await response.json();

                if (res.success) {
                    editForm.value = res.data;
                    personData.value = {full_name: res.data.first_name + ' ' + res.data.last_name};
                    photoPreview.value = res.data.photo_url;

                    // Cargamos las ubicaciones de forma secuencial y segura
                    try {
                        if (res.data.country) {
                            await loadLocations(res.data.country, 'id_province_modal', res.data.province);
                        }
                        if (res.data.province) {
                            await loadLocations(res.data.province, 'id_canton_modal', res.data.canton);
                        }
                        if (res.data.canton) {
                            await loadLocations(res.data.canton, 'id_parish_modal', res.data.parish);
                        }
                    } catch (locError) {
                        console.warn("Error cargando cascada de ubicaciones:", locError);
                    }

                    document.getElementById('modalPersonEditOverlay').classList.remove('hidden');
                    document.body.classList.add('no-scroll');
                } else {
                    throw new Error(res.message || "Error desconocido");
                }
            } catch (e) {
                console.error("Error detallado:", e); // Esto te dirá el error real en F12
                window.Toast.fire({icon: 'error', title: 'Error al obtener los datos: ' + e.message});
            }
        };
        const loadLocations = async (parentId, targetId, selectedValue = null) => {
            const target = document.getElementById(targetId);
            if (!target) return;

            try {
                // CORRECCIÓN: Usar la ruta definida en core/urls.py
                const response = await fetch(`/api/locations/?parent_id=${parentId}`);

                if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

                const res = await response.json();

                let options = '<option value="">-- Seleccione --</option>';

                // Ahora res.data existirá gracias al cambio en Python
                if (res.success && res.data) {
                    res.data.forEach(loc => {
                        options += `<option value="${loc.id}">${loc.name}</option>`;
                    });
                }

                target.innerHTML = options;
                if (selectedValue) target.value = selectedValue;
                if ($(target).data('select2')) {
                    $(target).trigger('change.select2');
                }
            } catch (e) {
                console.error(`Error cargando locaciones para el target ${targetId}:`, e);
            }
        };

        const submitPersonEdit = async () => {
            if (isSaving.value) return;
            isSaving.value = true;
            const formData = new FormData(document.getElementById('personEditForm'));
            const personId = editForm.value.id;

            try {
                const response = await fetch(`/person/update/${personId}/`, {
                    method: 'POST',
                    body: formData,
                    headers: {'X-CSRFToken': window.getCookie('csrftoken')}
                });

                const res = await response.json();

                if (res.success) {
                    window.Toast.fire({
                        icon: 'success',
                        title: res.message
                    });
                    setTimeout(() => {
                        location.reload();
                    }, 1000);
                } else {
                    console.error("Errores de validación:", res.errors);
                    editErrors.value = res.errors;
                    window.Toast.fire({icon: 'warning', title: 'Revise los campos marcados'});
                }
            } catch (e) {
                console.error("Error técnico:", e);
                window.Toast.fire({icon: 'error', title: 'Error al guardar datos'});
            } finally {
                isSaving.value = false; // Liberar el botón
            }
        };

        const handlePhotoChange = (e) => {
            const file = e.target.files[0];
            if (file) photoPreview.value = URL.createObjectURL(file);
        };

        const closeEditModal = () => {
            document.getElementById('modalPersonEditOverlay').classList.add('hidden');
            document.body.classList.remove('no-scroll');
        };
        document.addEventListener('change', async (e) => {
            if (e.target.id === 'id_country_modal') await loadLocations(e.target.value, 'id_province_modal');
            if (e.target.id === 'id_province_modal') await loadLocations(e.target.value, 'id_canton_modal');
            if (e.target.id === 'id_canton_modal') await loadLocations(e.target.value, 'id_parish_modal');
        });

        return {
            activeTab, tabs, titleForm, titleErrors, bankForm, bankErrors,
            editForm, editErrors, photoPreview, personData, isSaving,
            openEditPersonModal, submitPersonEdit, handlePhotoChange, closeEditModal,
            openBankModal, openTitleModal
        };
    }
});

// Montaje seguro
document.addEventListener('DOMContentLoaded', () => {
    console.log('=== DOM LOADED ===');
    console.log('Vue disponible:', typeof Vue !== 'undefined');
    const appElement = document.getElementById('employeeWizardApp');
    console.log('Elemento #employeeWizardApp encontrado:', appElement !== null);

    if (appElement) {
        try {
            app.mount('#employeeWizardApp');
            console.log('✅ Vue app montada correctamente');
        } catch (error) {
            console.error('❌ Error al montar Vue app:', error);
        }
    } else {
        console.error('❌ No se encontró el elemento #employeeWizardApp');
    }
});