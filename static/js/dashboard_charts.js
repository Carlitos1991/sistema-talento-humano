document.addEventListener('DOMContentLoaded', function () {
    if (typeof Chart === 'undefined') {
        console.error('Chart.js no está disponible para mostrar los gráficos del dashboard.');
        return;
    }

    const readChartData = function (id) {
        const element = document.getElementById(id);
        if (!element) return null;

        try {
            return JSON.parse(element.textContent);
        } catch (error) {
            console.error(`No se pudieron leer los datos del gráfico ${id}.`, error);
            return null;
        }
    };

    const createChart = function (canvasId, dataId, type, colors) {
        const canvas = document.getElementById(canvasId);
        const data = readChartData(dataId);
        if (!canvas || !data || !Array.isArray(data.labels) || !Array.isArray(data.values)) return;

        new Chart(canvas, {
            type: type,
            data: {
                labels: data.labels,
                datasets: [{
                    data: data.values,
                    backgroundColor: colors,
                    borderColor: '#ffffff',
                    borderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false }
                },
                scales: type === 'bar' ? {
                    y: {
                        beginAtZero: true,
                        ticks: { precision: 0 }
                    }
                } : {}
            }
        });
    };

    createChart(
        'budgetBarChart',
        'budgetChartData',
        'bar',
        ['#10b981', '#f59e0b', '#ef4444', '#3b82f6']
    );
    createChart(
        'employeeDonutChart',
        'employeeChartData',
        'doughnut',
        ['#f59e0b', '#10b981', '#3b82f6', '#ef4444']
    );
    createChart(
        'genderChart',
        'genderChartData',
        'doughnut',
        ['#3b82f6', '#ec4899']
    );
});
