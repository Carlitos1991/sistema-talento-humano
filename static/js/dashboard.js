/* static/js/dashboard.js */

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
                // Antes verificaba la URL, ahora forzamos a que empiece cerrado.
                const activeSubmenu = ref(null);

                // --- Función Toggle Sidebar ---
                const toggleSidebar = () => {
                    sidebarCollapsed.value = !sidebarCollapsed.value;
                    localStorage.setItem('sidebar_collapsed', sidebarCollapsed.value);

                    // Al colapsar o expandir, cerramos cualquier menú abierto
                    // para mantener la interfaz limpia hasta que el usuario haga clic.
                    activeSubmenu.value = null;
                };

                const toggleUserMenu = () => {
                    userMenuOpen.value = !userMenuOpen.value;
                };

                const closeUserMenu = () => {
                    userMenuOpen.value = false;
                };

                // Función Toggle Submenú (Click en la flecha/texto "Ajustes")
                const toggleSubmenu = (menuName) => {
                    // Si está colapsado, no permitimos abrir el acordeón manualmente
                    // (El CSS se encarga del menú flotante)
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