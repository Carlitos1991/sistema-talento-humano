document.addEventListener('DOMContentLoaded', () => {
    const wrapper = document.querySelector('.layout-wrapper');
    const toggleBtn = document.querySelector('.sidebar-toggle');
    const sidebar = document.querySelector('.sidebar');
    const sidebarBody = sidebar ? sidebar.querySelector('.sidebar-body') : null;
    const tooltip = document.createElement('div');

    if (!wrapper || !sidebar) {
        return;
    }

    tooltip.className = 'sidebar-tooltip';
    tooltip.setAttribute('role', 'tooltip');
    document.body.appendChild(tooltip);

    // =====================================================================
    // 1. TOOLTIPS (MODO COLAPSADO)
    // =====================================================================
    function hideTooltip() {
        tooltip.classList.remove('is-visible');
        tooltip.textContent = '';
    }

    function showTooltip(link, label) {
        const rect = link.getBoundingClientRect();
        tooltip.textContent = label;
        tooltip.classList.add('is-visible');

        const tooltipRect = tooltip.getBoundingClientRect();
        const top = Math.max(12, rect.top + (rect.height / 2) - (tooltipRect.height / 2));
        const left = rect.right + 14;

        tooltip.style.top = `${top}px`;
        tooltip.style.left = `${left}px`;
    }

    // =====================================================================
    // 2. TRUNCADO DE TEXTO
    // =====================================================================
    function truncateWithEllipsis(textElement) {
        let fullLabel = textElement.dataset.fullLabel || textElement.textContent.trim();
        textElement.dataset.fullLabel = fullLabel;

        if (fullLabel.length <= 8) {
            textElement.textContent = fullLabel;
            return false;
        }

        const maxWidth = textElement.clientWidth;
        if (!fullLabel || !maxWidth) {
            textElement.textContent = fullLabel;
            return false;
        }

        fullLabel = fullLabel.replace(/[\.\s]+$/g, '').trim();
        textElement.textContent = fullLabel;

        if (textElement.scrollWidth <= (textElement.clientWidth + 1)) {
            textElement.textContent = fullLabel;
            return false;
        }

        const dot = '.';
        let right = fullLabel.length - 1;
        let best = dot;

        while (right >= 1) {
            const candidate = `${fullLabel.slice(0, right).trimEnd()}${dot}`;
            textElement.textContent = candidate;

            if (textElement.scrollWidth <= maxWidth) {
                best = candidate;
                break;
            }

            right -= 1;
        }

        textElement.textContent = best;
        return true;
    }

    function syncMenuLabels() {
        const collapsed = wrapper.classList.contains('is-collapsed');
        const menuLinks = document.querySelectorAll('.sidebar-menu a');

        menuLinks.forEach((link) => {
            const textElement = link.querySelector('.menu-text');
            if (!textElement) {
                return;
            }

            const fullLabel = textElement.dataset.fullLabel || textElement.textContent.trim();
            textElement.dataset.fullLabel = fullLabel;

            const isOpenCollapsedTrigger = !!link.closest('.has-submenu.collapsed-open');

            if (isOpenCollapsedTrigger) {
                link.classList.remove('has-tooltip');
                link.dataset.tooltip = '';
                textElement.textContent = fullLabel;
                return;
            }

            if (collapsed) {
                textElement.textContent = fullLabel;
                link.classList.toggle('has-tooltip', true);
                link.dataset.tooltip = fullLabel;
                return;
            }

            const wasTruncated = truncateWithEllipsis(textElement);
            link.classList.toggle('has-tooltip', wasTruncated);
            link.dataset.tooltip = wasTruncated ? fullLabel : '';
        });

        if (!collapsed) {
            hideTooltip();
        }
    }

    // =====================================================================
    // 3. LIMPIEZA DE SUBMENÚS FLOTANTES
    // =====================================================================
    function clearCollapsedFloatingSubmenus() {
        document.querySelectorAll('.sidebar .has-submenu').forEach((item) => {
            item.classList.remove('collapsed-open');
            const submenu = item.querySelector('.submenu');
            if (submenu) {
                submenu.removeAttribute('style'); // Borra coordenadas y estilos en línea
            }
        });
    }

    const applyCollapsedState = (collapsed) => {
        wrapper.classList.toggle('is-collapsed', collapsed);
        sidebar.classList.toggle('collapsed', collapsed);

        clearCollapsedFloatingSubmenus();
        hideTooltip();

        if (collapsed) {
            document.querySelectorAll('.sidebar-menu li.open').forEach(el => el.classList.remove('open'));
        }

        syncMenuLabels();
    };

    const isCollapsed = localStorage.getItem('sidebar_collapsed') === 'true';
    applyCollapsedState(isCollapsed);

    if (toggleBtn) {
        toggleBtn.addEventListener('click', (event) => {
            event.preventDefault();
            const nextState = !wrapper.classList.contains('is-collapsed');
            applyCollapsedState(nextState);
            localStorage.setItem('sidebar_collapsed', nextState);
        });
    }

    // =====================================================================
    // 4. RESTAURAR MENÚS ACTIVOS AL CARGAR
    // =====================================================================
    const openActiveMenus = () => {
        if (wrapper.classList.contains('is-collapsed')) {
            return;
        }

        const activeLinks = document.querySelectorAll('.sidebar-menu a.active, .sidebar-menu a.active-child');

        activeLinks.forEach((link) => {
            const innerSubmenu = link.closest('.has-inner-submenu');
            if (innerSubmenu) {
                innerSubmenu.classList.add('is-open');
            }

            const submenuItem = link.closest('.has-submenu');
            if (submenuItem) {
                submenuItem.classList.add('open');
            }
        });
    };

    openActiveMenus();
    window.setTimeout(syncMenuLabels, 0);
    window.addEventListener('load', syncMenuLabels);
    window.addEventListener('resize', syncMenuLabels);
    window.addEventListener('scroll', hideTooltip, true);

    // =====================================================================
    // 5. CLIC EN SUBMENÚS (EXPANDIDO Y COLAPSADO)
    // =====================================================================
    const menuItems = document.querySelectorAll('.has-submenu > a');

    menuItems.forEach((item) => {
        item.addEventListener('click', (event) => {
            event.preventDefault();
            const parentLi = item.parentElement;
            const submenu = parentLi.querySelector('.submenu');
            const isCurrentlyCollapsed = wrapper.classList.contains('is-collapsed');

            if (isCurrentlyCollapsed) {
                const wasOpen = parentLi.classList.contains('collapsed-open');

                // 1. Cierra absolutamente todos los submenús previos
                clearCollapsedFloatingSubmenus();

                // 2. Si este no estaba abierto, abrirlo en su posición exacta
                if (!wasOpen && submenu) {
                    const rect = item.getBoundingClientRect();
                    parentLi.classList.add('collapsed-open');

                    submenu.style.position = 'fixed';
                    submenu.style.top = `${Math.round(rect.top)}px`;
                    submenu.style.left = `${Math.round(rect.right)}px`;
                    submenu.style.zIndex = '999999';
                    submenu.style.display = 'block';
                }
                return;
            }

            // Modo expandido: acordeón estándar
            document.querySelectorAll('.sidebar-menu li.open').forEach((li) => {
                if (li !== parentLi) {
                    li.classList.remove('open');
                }
            });

            parentLi.classList.toggle('open');

            if (!parentLi.classList.contains('open')) {
                const innerOpen = parentLi.querySelector('.has-inner-submenu.is-open');
                if (innerOpen) {
                    innerOpen.classList.remove('is-open');
                }
            }

            window.setTimeout(syncMenuLabels, 0);
        });
    });

    // =====================================================================
    // 6. TERCER NIVEL (ADMINISTRACIÓN)
    // =====================================================================
    const innerToggles = document.querySelectorAll('.inner-toggle');
    innerToggles.forEach((innerToggle) => {
        innerToggle.addEventListener('click', (event) => {
            event.preventDefault();
            const parent = innerToggle.closest('.has-inner-submenu');
            if (!parent) {
                return;
            }
            parent.classList.toggle('is-open');
            window.setTimeout(syncMenuLabels, 0);
        });
    });

    // =====================================================================
    // 7. CIERRE DE FLOTANTES AL CLIC AFUERA O SCROLL
    // =====================================================================
    document.addEventListener('click', (event) => {
        if (wrapper.classList.contains('is-collapsed')) {
            if (!event.target.closest('.has-submenu')) {
                clearCollapsedFloatingSubmenus();
            }
        }
        hideTooltip();
    });

    if (sidebarBody) {
        sidebarBody.addEventListener('scroll', () => {
            if (wrapper.classList.contains('is-collapsed')) {
                clearCollapsedFloatingSubmenus();
            }
        });
    }

    // Tooltips al pasar el mouse
    sidebar.addEventListener('mouseover', (event) => {
        const link = event.target.closest('.sidebar-menu a.has-tooltip');
        if (!link || !sidebar.contains(link)) {
            return;
        }

        if (link.closest('.has-submenu.collapsed-open')) {
            hideTooltip();
            return;
        }

        const label = link.dataset.tooltip;
        if (label) {
            showTooltip(link, label);
        }
    });

    sidebar.addEventListener('mouseout', (event) => {
        const link = event.target.closest('.sidebar-menu a.has-tooltip');
        if (!link || !sidebar.contains(link)) {
            return;
        }

        const related = event.relatedTarget;
        if (related && link.contains(related)) {
            return;
        }

        hideTooltip();
    });
});

// Función global toggle
function toggleSidebar() {
    const wrapper = document.getElementById('mainWrapper');
    const sidebar = document.getElementById('mainSidebar');
    if (!wrapper || !sidebar) return;

    const isCollapsed = wrapper.classList.toggle('is-collapsed');
    sidebar.classList.toggle('collapsed', isCollapsed);
    localStorage.setItem('sidebar_collapsed', isCollapsed);

    document.querySelectorAll('.sidebar-menu li.open').forEach(el => el.classList.remove('open'));
    document.querySelectorAll('.sidebar .has-submenu').forEach(el => {
        el.classList.remove('collapsed-open');
        const sub = el.querySelector('.submenu');
        if (sub) {
            sub.removeAttribute('style');
        }
    });
}