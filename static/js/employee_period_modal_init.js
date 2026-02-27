// Inicializador del modal de detalle de contrato para la vista del wizard
(function(){
    function initPeriodApp(){
        if (window.periodInstance) {
            return;
        }
        const el = document.getElementById('period-app-employee');
        if (!el) {
            return;
        }
        if (typeof Vue === 'undefined'){
            return;
        }
        try{
            const { createApp } = Vue;
            const periodAppEmp = createApp({
                delimiters: ['[[', ']]'],
                data(){ return { showDetailModal: false, selectedPeriod: {} }; },
                methods: {
                    async viewPeriodDetails(id){
                        if(!id) return;
                        try{
                            const res = await fetch(`/contract/periods/detail/${id}/`);
                            const data = await res.json();
                            if(data.success){
                                this.selectedPeriod = data.period;
                                this.showDetailModal = true;
                                document.body.classList.add('no-scroll');
                            }
                        }catch(e){ console.error('Error loading period detail', e); }
                    },
                    closeDetailModal(){
                        this.showDetailModal = false;
                        this.selectedPeriod = {};
                        document.body.classList.remove('no-scroll');
                    },
                    async deleteContractFile(id){
                        try{
                            const response = await fetch(`/contract/periods/delete-doc/${id}/`, {method: 'POST', headers: {'X-CSRFToken': (document.querySelector('[name=csrfmiddlewaretoken]')||{}).value || ''}});
                            const data = await response.json();
                            if(data.success){ this.showDetailModal = false; }
                        }catch(e){ console.error(e); }
                    }
                }
            }).mount('#period-app-employee');
            window.periodAppEmp = periodAppEmp;
            window.periodInstance = periodAppEmp;
            
        }catch(e){ console.error('Error initializing periodAppEmp', e); }
    }

    function ensureDelegation(){
        if (window.__periodDelegationBound) return;
        document.addEventListener('click', function(ev){
            const a = ev.target.closest && ev.target.closest('.open-contract');
            if (!a) return;
            ev.preventDefault();
            const id = a.dataset.id;
            try{
                if (typeof window.openContractDetail === 'function'){
                    return window.openContractDetail(id);
                }
                if (window.periodInstance && typeof window.periodInstance.viewPeriodDetails === 'function'){
                    return window.periodInstance.viewPeriodDetails(id);
                }
                // fallback: try to init and call
                initPeriodApp();
                if (window.periodInstance && typeof window.periodInstance.viewPeriodDetails === 'function'){
                    return window.periodInstance.viewPeriodDetails(id);
                }
                
            }catch(e){ console.error(e); }
        });
        window.__periodDelegationBound = true;
    }

    if (document.readyState === 'complete' || document.readyState === 'interactive'){
        initPeriodApp();
        ensureDelegation();
    } else {
        document.addEventListener('DOMContentLoaded', function(){ initPeriodApp(); ensureDelegation(); });
        // Also try on window.load as a fallback
        window.addEventListener('load', function(){ initPeriodApp(); ensureDelegation(); });
    }

    // Expose a safe global wrapper
    window.openContractDetail = function(id){
        if (window.periodInstance && typeof window.periodInstance.viewPeriodDetails === 'function'){
            return window.periodInstance.viewPeriodDetails(id);
        }
        // try init then call
        initPeriodApp();
        if (window.periodInstance && typeof window.periodInstance.viewPeriodDetails === 'function'){
            return window.periodInstance.viewPeriodDetails(id);
        }
        
    };

})();
