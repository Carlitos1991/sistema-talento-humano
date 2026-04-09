document.addEventListener('DOMContentLoaded', () => {
    const wrapper = document.querySelector('.layout-wrapper');
    const toggleBtn = document.querySelector('.sidebar-toggle');
    const sidebar = document.querySelector('.sidebar');
    const tooltip = document.createElement('div');

    if (!wrapper || !sidebar) {
        return;
    }

    tooltip.className = 'sidebar-tooltip';
    tooltip.setAttribute('role', 'tooltip');
    document.body.appendChild(tooltip);

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

    function truncateWithEllipsis(textElement) {
        const fullLabel = textElement.dataset.fullLabel || textElement.textContent.trim();
        textElement.dataset.fullLabel = fullLabel;

        // Evita truncar etiquetas cortas como "Inicio".
        if (fullLabel.length <= 8) {
            textElement.textContent = fullLabel;
            return false;
        }

        const maxWidth = textElement.clientWidth;

        if (!fullLabel || !maxWidth) {
            textElement.textContent = fullLabel;
            return false;
        }

        textElement.textContent = fullLabel;

        // Usa overflow real renderizado para decidir si truncar.
        if (textElement.scrollWidth <= (textElement.clientWidth + 1)) {
            textElement.textContent = fullLabel;
            return false;
        }

        const dot = '...';
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

        function clearCollapsedFloatingSubmenus() {
            document.querySelectorAll('.sidebar .has-submenu.collapsed-open').forEach((item) => {
                const submenu = item.querySelector('.submenu');
                if (submenu) {
                    submenu.classList.remove('collapsed-floating');
                    submenu.style.top = '';
                    submenu.style.left = '';
                    submenu.style.minWidth = '';
                    submenu.style.transform = '';
                    submenu.style.maxHeight = '';
                    submenu.style.display = '';
                    submenu.style.position = '';
                }
                item.classList.remove('collapsed-open');
            });
        }

    const applyCollapsedState = (collapsed) => {
        wrapper.classList.toggle('is-collapsed', collapsed);
        sidebar.classList.toggle('collapsed', collapsed);

            if (!collapsed) {
                clearCollapsedFloatingSubmenus();
                hideTooltip();
            }

        syncMenuLabels();
    };

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

    const isCollapsed = localStorage.getItem('sidebar_collapsed') === 'true';
    applyCollapsedState(isCollapsed);

    if (toggleBtn) {
        toggleBtn.addEventListener('click', (event) => {
            event.preventDefault();
            const collapsed = !wrapper.classList.contains('is-collapsed');
            applyCollapsedState(collapsed);
            localStorage.setItem('sidebar_collapsed', collapsed);
        });
    }

    const openActiveMenus = () => {
        document.querySelectorAll('.sidebar-menu .has-submenu.open').forEach((item) => {
            item.classList.remove('open');
        });
        document.querySelectorAll('.sidebar-menu .has-inner-submenu.is-open').forEach((item) => {
            item.classList.remove('is-open');
        });

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
    document.addEventListener('click', hideTooltip);

    const menuItems = document.querySelectorAll('.has-submenu > a');
    menuItems.forEach((item) => {
        item.addEventListener('click', (event) => {
            if (wrapper.classList.contains('is-collapsed')) {
                return;
            }

            event.preventDefault();
            const parentLi = item.parentElement;

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

            // Recalcula truncado/tooltip cuando cambia visibilidad de submenús.
            window.setTimeout(syncMenuLabels, 0);
        });
    });

    const innerToggles = document.querySelectorAll('.inner-toggle');
    innerToggles.forEach((innerToggle) => {
        innerToggle.addEventListener('click', (event) => {
            event.preventDefault();
            const parent = innerToggle.closest('.has-inner-submenu');
            if (!parent) {
                return;
            }
            parent.classList.toggle('is-open');

            // Recalcula truncado/tooltip cuando cambia visibilidad de submenús internos.
            window.setTimeout(syncMenuLabels, 0);
        });
    });

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

    sidebar.addEventListener('focusin', (event) => {
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

    sidebar.addEventListener('focusout', hideTooltip);

    sidebar.addEventListener('click', (event) => {
        const link = event.target.closest('.sidebar-menu a');
        if (!link) {
            return;
        }

        hideTooltip();
    }, true);
});
