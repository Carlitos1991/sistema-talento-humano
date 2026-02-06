document.addEventListener('DOMContentLoaded', function () {

    // --- REFERENCIAS DOM ---
    const elements = {
        permitTypeSelect: $('#id_permit_type'), // Usamos jQuery para Select2
        startDate: document.getElementById('id_start_date'),
        endDate: document.getElementById('id_end_date'),
        startTime: document.getElementById('id_start_time'),
        endTime: document.getElementById('id_end_time'),
        daysInput: document.getElementById('id_days'),
        hoursInput: document.getElementById('id_hours'),
        vacationWarning: document.getElementById('vacation-warning'),
        fileInput: document.getElementById('id_justification_file'),
        fileLabel: document.getElementById('label_file'),
        urlCheckType: document.getElementById('url_check_type')
    };

    // --- INICIALIZACIÓN ---
    initSelect2();
    setupEventListeners();

    // --- FUNCIONES ---

    function initSelect2() {
        $('.select2').select2({
            theme: 'bootstrap-5',
            width: '100%',
            placeholder: 'Seleccione una opción'
        });
    }

    function setupEventListeners() {
        // Evento cambio de Tipo de Permiso
        elements.permitTypeSelect.on('select2:select', function (e) {
            const typeId = e.params.data.id;
            fetchPermitTypeDetails(typeId);
        });

        // Eventos de cálculo de fechas
        [elements.startDate, elements.endDate].forEach(input => {
            if (input) input.addEventListener('change', calculateDuration);
        });

        // Eventos de cálculo de horas (si están llenas)
        [elements.startTime, elements.endTime].forEach(input => {
            if (input) input.addEventListener('change', calculateDuration);
        });
    }

    /**
     * Consulta al Backend las reglas del tipo de permiso seleccionado
     * sin recargar la página.
     */
    function fetchPermitTypeDetails(typeId) {
        if (!typeId) return;

        // Construir URL dinámica reemplazando el '0' por el ID real
        let baseUrl = elements.urlCheckType.dataset.url;
        const finalUrl = baseUrl.replace('/0/', `/${typeId}/`); // Ajuste según tu URL conf

        fetch(finalUrl, {
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
            .then(response => response.json())
            .then(data => {
                updateUIBasedOnType(data);
            })
            .catch(err => console.error('Error fetching permit details:', err));
    }

    /**
     * Actualiza la UI (Warnings, Requerimiento de Archivos)
     */
    function updateUIBasedOnType(data) {
        // 1. Manejo de Vacaciones
        if (data.affects_vacation) {
            elements.vacationWarning.classList.remove('d-none');
            elements.vacationWarning.classList.add('d-flex');
        } else {
            elements.vacationWarning.classList.add('d-none');
            elements.vacationWarning.classList.remove('d-flex');
        }

        // 2. Manejo de Archivo Adjunto
        const fileHelpText = document.getElementById('file_help_text');
        if (data.requires_attachment) {
            elements.fileLabel.innerHTML = 'Archivo Adjunto (PDF) <span class="text-danger">* Obligatorio</span>';
            elements.fileInput.required = true;
            fileHelpText.textContent = "Este tipo de permiso exige un documento de soporte.";
            fileHelpText.classList.add('text-danger');
        } else {
            elements.fileLabel.innerHTML = 'Archivo Adjunto (PDF)';
            elements.fileInput.required = false;
            fileHelpText.textContent = "Opcional según el tipo de permiso.";
            fileHelpText.classList.remove('text-danger');
        }
    }

    /**
     * Lógica básica de cálculo de tiempo en cliente.
     * El cálculo final y validación estricta siempre debe ser en Backend.
     */
    function calculateDuration() {
        const start = elements.startDate.value;
        const end = elements.endDate.value;

        if (start && end) {
            const date1 = new Date(start);
            const date2 = new Date(end);

            // Diferencia en tiempo
            const diffTime = Math.abs(date2 - date1);
            // Diferencia en días (aprox)
            let diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

            // Si es el mismo día, cuenta como 1 día a menos que haya horas
            if (date1.getTime() === date2.getTime()) {
                diffDays = 0; // Se calculará por horas
            } else {
                // Sumar 1 porque es inclusivo si no hay horas definidas
                diffDays += 1;
            }

            elements.daysInput.value = diffDays;
        }

        // Cálculo de horas (básico)
        const timeStart = elements.startTime.value;
        const timeEnd = elements.endTime.value;

        if (timeStart && timeEnd && elements.daysInput.value == 0) {
            // Lógica simple de horas intra-día
            const [h1, m1] = timeStart.split(':');
            const [h2, m2] = timeEnd.split(':');

            let hours = h2 - h1;
            let minutes = m2 - m1;

            if (minutes < 0) {
                hours--;
                minutes += 60;
            }

            elements.hoursInput.value = hours > 0 ? hours : 0;
            document.getElementById('id_minutes').value = minutes > 0 ? minutes : 0;
        }
    }
});