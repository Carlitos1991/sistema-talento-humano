/* static/js/dashboard.js */

// ==========================================
// 1. UTILIDADES GLOBALES (No tocar)
// ==========================================
window.getCookie = function (name) {
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
};

// Configuración Global de Toast
if (typeof Swal !== 'undefined') {
    window.Toast = Swal.mixin({
        toast: true,
        position: 'top-end',
        showConfirmButton: false,
        timer: 3000,
        timerProgressBar: true,
        didOpen: (toast) => {
            toast.addEventListener('mouseenter', Swal.stopTimer);
            toast.addEventListener('mouseleave', Swal.resumeTimer);
        }
    });
}

// ==========================================
// 2. LÓGICA DEL LAYOUT (Vanilla JS)
// ==========================================
document.addEventListener('DOMContentLoaded', () => {

    const wrapper = document.querySelector('.layout-wrapper');
    const toggleBtn = document.querySelector('.sidebar-toggle'); // Asegúrate que tu botón en navbar tenga esta clase
    const sidebar = document.querySelector('.sidebar');

    // 1. Recuperar estado del Sidebar
    const isCollapsed = localStorage.getItem('sidebar_collapsed') === 'true';
    if (isCollapsed && wrapper) {
        wrapper.classList.add('is-collapsed');
        if (sidebar) sidebar.classList.add('collapsed');
    }

    // 2. Evento Toggle Sidebar
    if (toggleBtn && wrapper) {
        toggleBtn.addEventListener('click', (e) => {
            e.preventDefault();
            wrapper.classList.toggle('is-collapsed');

            // Guardar estado
            const collapsed = wrapper.classList.contains('is-collapsed');
            if (sidebar) sidebar.classList.toggle('collapsed');
            localStorage.setItem('sidebar_collapsed', collapsed);
        });
    }

    // 3. Manejo de Submenús (Acordeón)
    const menuItems = document.querySelectorAll('.has-submenu > a');
    menuItems.forEach(item => {
        item.addEventListener('click', (e) => {
            // Si el sidebar está colapsado, no hacemos acordeón (se usa hover CSS)
            if (wrapper.classList.contains('is-collapsed')) return;

            e.preventDefault();
            const parentLi = item.parentElement;

            // Cerrar otros abiertos
            document.querySelectorAll('.sidebar-menu li.open').forEach(li => {
                if (li !== parentLi) li.classList.remove('open');
            });

            // Toggle actual
            parentLi.classList.toggle('open');
            
            // Si cerramos el menú principal, cerramos también los submenús internos
            if (!parentLi.classList.contains('open')) {
                const innerOpen = parentLi.querySelector('.has-inner-submenu.is-open');
                if (innerOpen) {
                    innerOpen.classList.remove('is-open');
                    localStorage.setItem('admin_menu_open', 'false');
                }
            }
        });
    });

    // 4. User Dropdown (Si existe)
    const userTrigger = document.querySelector('.user-trigger');
    const dropdownMenu = document.querySelector('.dropdown-menu'); // Asegúrate de tener clases unicas si hay varios

    if (userTrigger && dropdownMenu) {
        // Toggle click
        userTrigger.addEventListener('click', (e) => {
            e.stopPropagation();
            dropdownMenu.classList.toggle('hidden'); // O la clase que uses para mostrar/ocultar
            // Si usas style.display en tu css:
            // dropdownMenu.style.display = dropdownMenu.style.display === 'block' ? 'none' : 'block';
        });

        // Click fuera para cerrar
        document.addEventListener('click', (e) => {
            if (!userTrigger.contains(e.target) && !dropdownMenu.contains(e.target)) {
                dropdownMenu.classList.add('hidden');
                // dropdownMenu.style.display = 'none';
            }
        });
    }
    const innerToggle = document.querySelector('.inner-toggle');
    if (innerToggle) {
        innerToggle.addEventListener('click', (e) => {
            e.preventDefault();
            const parent = innerToggle.closest('.has-inner-submenu');
            parent.classList.toggle('is-open');

            // Guardar estado en localStorage
            localStorage.setItem('admin_menu_open', parent.classList.contains('is-open'));
        });

        // Restaurar estado
        if (localStorage.getItem('admin_menu_open') === 'true') {
            document.querySelector('.has-inner-submenu').classList.add('is-open');
        }
    }
});