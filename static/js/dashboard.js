document.addEventListener('DOMContentLoaded', () => {
    const {createApp, ref} = Vue;

    if (document.getElementById('mainLayout')) {
        createApp({
            setup() {
                // 1. Cargar estado desde LocalStorage
                const storedState = localStorage.getItem('sidebar_collapsed') === 'true';
                const sidebarCollapsed = ref(storedState);
                const userMenuOpen = ref(false);

                // 2. CAMBIO: Inicializar SIEMPRE en null (Cerrado)
                const activeSubmenu = ref(null);

                // --- Función Toggle Sidebar ---
                const toggleSidebar = () => {
                    sidebarCollapsed.value = !sidebarCollapsed.value;
                    localStorage.setItem('sidebar_collapsed', sidebarCollapsed.value);

                    // Al colapsar o expandir, cerramos cualquier menú abierto
                    activeSubmenu.value = null;
                };

                const toggleUserMenu = () => {
                    userMenuOpen.value = !userMenuOpen.value;
                };

                const closeUserMenu = () => {
                    userMenuOpen.value = false;
                };

                // Función Toggle Submenú
                const toggleSubmenu = (menuName) => {
                    if (sidebarCollapsed.value) {
                        return;
                    }

                    // Comportamiento normal: Abrir/Cerrar al hacer clic
                    activeSubmenu.value = activeSubmenu.value === menuName ? null : menuName;
                };

                return {
                    sidebarCollapsed,
                    toggleSidebar,
                    userMenuOpen,
                    toggleUserMenu,
                    closeUserMenu,
                    activeSubmenu,
                    toggleSubmenu
                };
            }
        }).mount('#mainLayout');
    }
});