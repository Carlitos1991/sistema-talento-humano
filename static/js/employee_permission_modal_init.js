// Inicializador para abrir modal de detalle de permiso desde el wizard
(function(){
    function fetchAndShow(url, containerSel){
        if(!url) return;
        const container = document.getElementById(containerSel.replace('#',''));
        if(!container) return;
        fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
            .then(r => r.text())
            .then(html => {
                // Wrap returned HTML in a centered overlay so it behaves as a modal
                const wrapper = document.createElement('div');
                wrapper.className = 'modal-overlay';
                const box = document.createElement('div');
                box.className = 'modal-box';
                // insert the server HTML inside the modal box
                box.innerHTML = html;
                wrapper.appendChild(box);
                container.innerHTML = '';
                container.appendChild(wrapper);
                document.body.classList.add('no-scroll');
            }).catch(e => console.error('Error cargando detalle permiso', e));
    }

    function ensureDelegation(){
        if(window.__permissionDelegationBound) return;
        document.addEventListener('click', function(ev){
            const a = ev.target.closest && ev.target.closest('.open-permission');
            if(!a) return;
            ev.preventDefault();
            const url = a.dataset.url || (a.dataset.id ? `/permissions/admin/${a.dataset.id}/detail/` : null);
            fetchAndShow(url, '#permission-modal-employee');
        });

        // cierre delegación
        document.addEventListener('click', function(ev){
            const btn = ev.target.closest && ev.target.closest('.js-close-modal');
            if(!btn) return;
            // limpiar contenedor padre más cercano
            const permContainer = document.getElementById('permission-modal-employee');
            if(permContainer && permContainer.contains(btn)){
                permContainer.innerHTML = '';
                document.body.classList.remove('no-scroll');
            }
            const periodContainer = document.getElementById('period-app-employee');
            if(periodContainer && periodContainer.contains(btn)){
                // delegate to period app if necessary; period app handles its own close
                // but we guard by removing no-scroll just in case
                document.body.classList.remove('no-scroll');
            }
        });

        window.__permissionDelegationBound = true;
    }

    // Filtrado cliente para los botones rápidos
    function initPermissionFilters(){
        // Keep for backward compatibility: add 'active' to ALL when possible
        let container = document.querySelector('.info-box-styled.info-box-accent-pink');
        if(!container) container = document.querySelector('.grid-info-personal');
        if(!container) return;
        const first = container.querySelector('.permission-filter-btn[data-filter="ALL"]');
        if(first){ first.classList.add('active'); first.classList.add('permission-filter-active-requested'); }
        console.log('[permFilters] init: ensured default active button');
    }

    // Delegated click handler so filters work even if buttons are rendered later by Vue
    document.addEventListener('click', function(ev){
        const btn = ev.target.closest && ev.target.closest('.permission-filter-btn');
        if(!btn) return;
        ev.preventDefault();
        // find the nearest permissions panel container
        let panel = btn.closest('.info-box-styled.info-box-accent-pink');
        if(!panel) panel = btn.closest('.grid-info-personal');
        console.log('[permFilters][delegate] clicked:', btn.dataset.filter, 'panel=', panel);
        if(!panel) return;
        const btns = panel.querySelectorAll('.permission-filter-btn');
        btns.forEach(x => x.classList.remove('active', 'permission-filter-active-approved', 'permission-filter-active-rejected', 'permission-filter-active-requested'));
        btn.classList.add('active');
        const filter = (btn.dataset.filter || '').toUpperCase();
        if(filter === 'APPROVED') btn.classList.add('permission-filter-active-approved');
        else if(filter === 'REJECTED') btn.classList.add('permission-filter-active-rejected');
        else if(filter === 'REQUESTED') btn.classList.add('permission-filter-active-requested');
        else btn.classList.add('permission-filter-active-requested');

        const items = panel.querySelectorAll('.budget-history-item');
        console.log('[permFilters][delegate] total items found:', items.length);
        let visibleCount = 0;
        items.forEach(it => {
            const status = (it.dataset.status || '').trim();
            console.log('[permFilters][delegate] item status=', status, 'filter=', filter);
            let show = true;
            if(filter === 'ALL'){
                show = true;
            } else if(filter === 'REQUESTED'){
                show = (status === 'REQUESTED');
            } else {
                show = (status === filter);
            }
            it.style.display = show ? '' : 'none';
            if(show) visibleCount++;
        });
        console.log('[permFilters][delegate] visible after filter:', visibleCount);
    });

    function readyInit(){
        ensureDelegation();
        initPermissionFilters();
        // Cleanup any orphaned modal overlays or stale no-scroll class that
        // could have been left by other flows (prevents blank areas)
        setTimeout(() => {
            try {
                // if body has no-scroll but there is no visible modal-overlay, remove it
                const bodyHasNoScroll = document.body.classList.contains('no-scroll');
                const visibleOverlay = Array.from(document.querySelectorAll('.modal-overlay')).some(o => {
                    return !o.classList.contains('hidden') && (getComputedStyle(o).display !== 'none');
                });
                if(bodyHasNoScroll && !visibleOverlay){
                    document.body.classList.remove('no-scroll');
                }

                // remove empty overlays inside the permission modal container
                const permContainer = document.getElementById('permission-modal-employee');
                if(permContainer && permContainer.children.length > 0){
                    const child = permContainer.children[0];
                    // if child is modal-overlay but contains no significant content, clear it
                    if(child && child.classList && child.classList.contains('modal-overlay')){
                        // check innerText length
                        if(!child.textContent || child.textContent.trim().length === 0){
                            permContainer.innerHTML = '';
                            document.body.classList.remove('no-scroll');
                        }
                    }
                }
            } catch(e){ console.warn('cleanup overlays error', e); }
        }, 120);
    }

    if (document.readyState === 'complete' || document.readyState === 'interactive'){
        readyInit();
    } else {
        document.addEventListener('DOMContentLoaded', readyInit);
        window.addEventListener('load', readyInit);
    }

    window.openPermissionDetail = function(id){
        const url = id ? `/permissions/admin/${id}/detail/` : null;
        if(url) fetchAndShow(url, '#permission-modal-employee');
    };

})();
