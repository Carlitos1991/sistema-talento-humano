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

// Configuración Global de SweetAlert2 en Español
if (typeof Swal !== 'undefined') {
    // Establecer textos por defecto en español globalmente
    const swalDefaults = Swal.mixin({
        confirmButtonText: 'Aceptar',
        cancelButtonText: 'Cancelar',
        denyButtonText: 'Denegar'
    });
    
    // Sobrescribir el Swal global con los defaults en español
    window.Swal = swalDefaults;
    
    // Toast notification personalizado
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
    const sidebar = document.querySelector('.sidebar');
    const isSidebarCollapsed = () => {
        return !!(wrapper && wrapper.classList.contains('is-collapsed')) || !!(sidebar && sidebar.classList.contains('collapsed'));
    };

    const closeCollapsedSubmenus = (exceptItem = null) => {
        document.querySelectorAll('.sidebar .has-submenu.collapsed-open').forEach((item) => {
            if (item !== exceptItem) {
                const submenu = item.querySelector('.submenu');
                if (submenu) {
                    submenu.classList.remove('collapsed-floating');
                    submenu.style.top = '';
                    submenu.style.left = '';
                    submenu.style.minWidth = '';
                    submenu.style.transform = '';
                    submenu.style.maxHeight = '';
                    submenu.style.display = '';
                }
                item.classList.remove('collapsed-open');
            }
        });
    };

    const positionFloatingSubmenu = (submenu, trigger) => {
        const sidebarRect = sidebar.getBoundingClientRect();
        const triggerRect = trigger.getBoundingClientRect();

        submenu.style.display = 'block';
        submenu.style.position = 'fixed';
        submenu.style.minWidth = '220px';

        requestAnimationFrame(() => {
            const menuHeight = submenu.offsetHeight || 220;
            const viewportPadding = 12;
            const idealTop = triggerRect.top;
            const maxTop = window.innerHeight - menuHeight - viewportPadding;
            const top = Math.max(viewportPadding, Math.min(idealTop, maxTop));

            submenu.classList.add('collapsed-floating');
            submenu.style.top = `${top}px`;
            submenu.style.left = `${sidebarRect.right + 6}px`;
            submenu.style.transform = 'none';
            submenu.style.maxHeight = '70vh';
        });
    };

    const openActiveSidebarBranches = () => {
        document.querySelectorAll('.sidebar-menu a.active, .sidebar-menu a.active-child').forEach((link) => {
            const parentSubmenu = link.closest('.has-submenu');
            if (parentSubmenu) {
                parentSubmenu.classList.add('open');
            }

            const innerSubmenu = link.closest('.has-inner-submenu');
            if (innerSubmenu) {
                innerSubmenu.classList.add('is-open');
            }
        });
    };

    openActiveSidebarBranches();

    document.querySelectorAll('.sidebar .has-submenu > a').forEach((trigger) => {
        trigger.addEventListener('click', (event) => {
            if (!isSidebarCollapsed()) {
                return;
            }

            event.preventDefault();
            event.stopPropagation();
            const parentItem = trigger.parentElement;
            const submenu = parentItem.querySelector('.submenu');
            const wasOpen = parentItem.classList.contains('collapsed-open');

            closeCollapsedSubmenus(parentItem);
            parentItem.classList.toggle('collapsed-open', !wasOpen);

            if (!wasOpen) {
                if (submenu) {
                    positionFloatingSubmenu(submenu, trigger);
                }
            }
        });
    });

    document.addEventListener('click', (event) => {
        if (!isSidebarCollapsed()) {
            return;
        }

        const clickedInsideSidebar = event.target.closest('.sidebar');
        if (!clickedInsideSidebar) {
            closeCollapsedSubmenus();
        }
    });

    window.addEventListener('resize', () => {
        if (!isSidebarCollapsed()) {
            return;
        }

        const openItem = document.querySelector('.sidebar .has-submenu.collapsed-open');
        if (!openItem) {
            return;
        }

        const trigger = openItem.querySelector(':scope > a');
        const submenu = openItem.querySelector('.submenu');
        if (!trigger || !submenu) {
            return;
        }

        positionFloatingSubmenu(submenu, trigger);
    });

    // User Dropdown (Si existe)
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
});