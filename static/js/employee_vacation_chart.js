document.addEventListener('DOMContentLoaded', function(){
    try {
        // Try to initialize charts when Chart is available. If Chart.js isn't loaded yet,
        // poll until it is. Once available, initialize existing canvases and set up
        // observers to initialize canvases inserted later (ajax/vue tab rendering).
        const startWhenChartReady = function(cb){
            if (typeof Chart !== 'undefined') return cb();
            const waitForChart = setInterval(function(){
                if (typeof Chart !== 'undefined'){
                    clearInterval(waitForChart);
                    return cb();
                }
            }, 100);
            // safety timeout
            setTimeout(function(){ clearInterval(waitForChart); if (typeof Chart !== 'undefined') cb(); }, 8000);
        };

        startWhenChartReady(function(){
            initVacationCharts();

            // Observe DOM mutations to initialize charts that appear later
            const observer = new MutationObserver(function(mutations){
                let found = false;
                mutations.forEach(function(m){
                    m.addedNodes.forEach(function(node){
                        if (!node) return;
                        if (node.nodeType === 1){
                            if (node.querySelector && node.querySelector('[id^="vacationPieChart-"]')) found = true;
                            if (node.id && node.id.indexOf('vacationPieChart-') === 0) found = true;
                        }
                    });
                });
                if (found) initVacationCharts();
            });
            observer.observe(document.body, { childList: true, subtree: true });

            // Also run a few periodic retries to catch late renders (up to ~3s)
            let retries = 0;
            const retryInterval = setInterval(function(){
                retries += 1;
                initVacationCharts();
                if (retries > 15) clearInterval(retryInterval);
            }, 200);
        });
    } catch (e) {
        console.error('Error initializing vacation charts', e);
    }

    function initVacationCharts(){
        const canvases = document.querySelectorAll('[id^="vacationPieChart-"]');
        canvases.forEach(function(canvas){
            try {
                // Normaliza separador decimal (Django puede usar coma con USE_L10N=True)
                const parseLocaleFloat = (v) => parseFloat(String(v || 0).replace(',', '.')) || 0;
                const saldo = parseLocaleFloat(canvas.dataset.saldo);
                const permits = parseLocaleFloat(canvas.dataset.permits);
                const vacations = parseLocaleFloat(canvas.dataset.vacations);
                const total = parseLocaleFloat(canvas.dataset.total) || (saldo + permits + vacations);

                const data = [saldo, permits, vacations];
                const labels = ['Saldo','Permisos','Vacaciones'];
                const colors = ['#06b6d4','#f59e0b','#0ea5a4'];

                // If already rendered and values unchanged, skip re-render to avoid flicker
                const prev = canvas._vacationData || { data: [] };
                const same = prev.data.length === data.length && prev.data.every((v,i)=> Number(v) === Number(data[i]));
                if (canvas._chartInstance && same) return;

                // If chart exists but data changed, update it instead of destroy/create
                if (canvas._chartInstance) {
                    try {
                        canvas._chartInstance.data.datasets[0].data = data;
                        canvas._chartInstance.update();
                        canvas._vacationData = { data: data.slice() };
                        return;
                    } catch(e) {
                        try { canvas._chartInstance.destroy(); } catch(err){}
                    }
                }

                const ctx = canvas.getContext('2d');

                // Fijar tamaño explícito para que Chart.js no expanda el canvas
                canvas.width  = 150;
                canvas.height = 150;

                canvas._chartInstance = new Chart(ctx, {
                    type: 'doughnut',
                    data: { labels: labels, datasets: [{ data: data, backgroundColor: colors, borderWidth: 0 }] },
                    options: {
                        responsive: false,
                        maintainAspectRatio: false,
                        animation: { duration: 0 },
                        hover: { mode: 'nearest' },
                        plugins: {
                            legend: { display: false },
                            tooltip: {
                                enabled: true,
                                callbacks: {
                                    label: function(context){
                                        const value = Number(context.raw || 0);
                                        return context.label + ': ' + value.toFixed(2);
                                    }
                                }
                            }
                        }
                    }
                });

                // store data snapshot to avoid unnecessary redraws
                canvas._vacationData = { data: data.slice() };
            } catch (err) {
                console.error('Error rendering vacation chart for', canvas.id, err);
            }
        });
    }
});
