/* static/js/dashboard.js */

document.addEventListener('DOMContentLoaded', () => {
    const {createApp, ref} = Vue;

    if (document.getElementById('mainLayout')) {
        createApp({
            setup() {
                // 1. LEER ESTADO GUARDADO (LocalStorage)
                // Si no existe, por defecto es false (expandido)
                const storedState = localStorage.getItem('sidebar_collapsed') === 'true';

                // Inicializamos la variable reactiva con el valor guardado
                const sidebarCollapsed = ref(storedState);
                const userMenuOpen = ref(false);

                // Lógica para determinar qué menú está activo según la URL actual
                const currentPath = window.location.pathname;
                const activeSubmenu = ref(
                    currentPath.includes('/settings/') ? 'settings' : null
                );

                // --- FUNCIÓN TOGGLE SIDEBAR (MODIFICADA) ---
                const toggleSidebar = () => {
                    sidebarCollapsed.value = !sidebarCollapsed.value;

                    // 2. GUARDAR EL NUEVO ESTADO EN EL NAVEGADOR
                    localStorage.setItem('sidebar_collapsed', sidebarCollapsed.value);

                    // Al colapsar, forzamos cierre de menús para limpieza visual
                    if (sidebarCollapsed.value) {
                        activeSubmenu.value = null;
                    } else {
                        // Opcional: Al expandir, si estamos en una sección, reabrirla
                        if (currentPath.includes('/settings/')) {
                            activeSubmenu.value = 'settings';
                        }
                    }
                };

                const toggleUserMenu = () => {
                    userMenuOpen.value = !userMenuOpen.value;
                };

                const closeUserMenu = () => {
                    userMenuOpen.value = false;
                };

                const toggleSubmenu = (menuName) => {
                    // Si está colapsado, no hacemos nada (el CSS hover se encarga)
                    if (sidebarCollapsed.value) {
                        return;
                    }
                    // Comportamiento acordeón normal
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