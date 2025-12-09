/* static/js/dashboard.js */

document.addEventListener('DOMContentLoaded', () => {
    const { createApp, ref } = Vue;

    // Solo montamos la app si existe el contenedor principal
    if (document.getElementById('mainLayout')) {
        createApp({
            setup() {
                // Estado del Sidebar (Colapsado/Expandido)
                const sidebarCollapsed = ref(false);

                // Estado del Menú de Usuario (Abierto/Cerrado)
                const userMenuOpen = ref(false);

                // Función para alternar Sidebar
                const toggleSidebar = () => {
                    sidebarCollapsed.value = !sidebarCollapsed.value;
                };

                // Función para alternar Menú Usuario
                const toggleUserMenu = () => {
                    userMenuOpen.value = !userMenuOpen.value;
                };

                // Cerrar menú usuario si se hace click fuera (Opcional, mejora UX)
                const closeUserMenu = () => {
                    userMenuOpen.value = false;
                };

                return {
                    sidebarCollapsed,
                    toggleSidebar,
                    userMenuOpen,
                    toggleUserMenu,
                    closeUserMenu
                };
            }
        }).mount('#mainLayout');
    }
});