// Asegurémonos de que Vue esté disponible
if (typeof Vue === 'undefined') {
    console.error("Vue.js no está cargado. Revisa la CDN en base.html");
}

const {createApp, ref, onMounted} = Vue;

const app = createApp({
    delimiters: ['[[', ']]'],
    setup() {
        const activeTab = ref('personal');

        // Datos reactivos
        const titleForm = ref({is_current: false});
        const titleErrors = ref({});
        const bankForm = ref({});
        const bankErrors = ref({});

        // Pestañas con sus clases de estilo premium
        const tabs = [
            {
                id: 'personal',
                name: 'Datos Personales',
                icon: 'fa-solid fa-user',
                color: '#3b82f6',
                activeClass: 'active-personal'
            },
            {
                id: 'curriculum',
                name: 'Currículum Vitae',
                icon: 'fa-solid fa-file-invoice',
                color: '#10b981',
                activeClass: 'active-cv'
            },
            {
                id: 'economic',
                name: 'Datos Económicos',
                icon: 'fa-solid fa-money-bill-1-wave',
                color: '#0ea5e9',
                activeClass: 'active-econ'
            },
            {
                id: 'budget',
                name: 'Partida Presup.',
                icon: 'fa-solid fa-address-book',
                color: '#6366f1',
                activeClass: ''
            },
            {id: 'institutional', name: 'Datos Inst.', icon: 'fa-solid fa-building', color: '#f59e0b', activeClass: ''},
            {
                id: 'history',
                name: 'Historia Lab.',
                icon: 'fa-solid fa-clock-rotate-left',
                color: '#8b5cf6',
                activeClass: ''
            },
            {
                id: 'permissions',
                name: 'Permisos',
                icon: 'fa-solid fa-calendar-check',
                color: '#ec4899',
                activeClass: ''
            },
            {id: 'actions', name: 'Acciones Pers.', icon: 'fa-solid fa-gavel', color: '#ef4444', activeClass: ''},
            {id: 'vacations', name: 'Vacaciones', icon: 'fa-solid fa-plane', color: '#f97316', activeClass: ''},
        ];

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

        return {
            activeTab, tabs, titleForm, titleErrors, bankForm, bankErrors,
            openBankModal, openTitleModal
        };
    }
});

// Montaje seguro
document.addEventListener('DOMContentLoaded', () => {
    app.mount('#employeeWizardApp');
});