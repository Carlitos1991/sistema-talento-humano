const {createApp} = Vue;

const reportApp = createApp({
        delimiters: ['[[', ']]'],
        data() {
            return {
                searchQuery: '',
                showMonthlyModal: false,
                showSpecificModal: false,
                selectedEmp: {id: '', name: '', dni: ''},
                monthlyForm: {month: new Date().getMonth() + 1, year: new Date().getFullYear()},
                specificForm: {start: '', end: ''}
            }
        },
        methods: {
            async search() {
                const response = await fetch(`?q=${this.searchQuery}`, {headers: {'X-Requested-With': 'XMLHttpRequest'}});
                const data = await response.json();
                document.getElementById('table-content-wrapper').innerHTML = data.html;
            },
            openMonthly(id, name, dni) {
                this.selectedEmp = {id, name, dni};
                this.showMonthlyModal = true;
            },
            openSpecific(id, name, dni) {
                this.selectedEmp = {id, name, dni};
                this.showSpecificModal = true;
            },
            downloadMonthly() {
                const url = `/biometric/reports/monthly-pdf/?emp_id=${this.selectedEmp.id}&month=${this.monthlyForm.month}&year=${this.monthlyForm.year}`;
                window.open(url, '_blank');
            },
            downloadSpecific() {
                const url = `/biometric/reports/specific-pdf/?emp_id=${this.selectedEmp.id}&start=${this.specificForm.start}&end=${this.specificForm.end}`;
                window.open(url, '_blank');
            }
        }
    })
;

window.reportVM = reportApp.mount('#report-app');