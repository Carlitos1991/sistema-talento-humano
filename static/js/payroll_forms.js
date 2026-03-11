/* =====================================================================
   LÓGICA JAVASCRIPT PARA FORMULARIOS DE NÓMINA (Ingresos, Egresos, Aportes)
   ===================================================================== */

document.addEventListener("DOMContentLoaded", function () {
    initBudgetMappingToggle();
});

/**
 * Controla la visibilidad de los campos de mapeo presupuestario
 * en los formularios de creación/edición de rubros.
 */
function initBudgetMappingToggle() {
    const mappingCheckbox = document.querySelector('input[name="has_mapping"]');
    const budgetFieldsBox = document.getElementById('budgetMappingFields');

    if (mappingCheckbox && budgetFieldsBox) {
        const toggleFields = () => {
            if (mappingCheckbox.checked) {
                budgetFieldsBox.classList.remove('hidden-mapping');
            } else {
                budgetFieldsBox.classList.add('hidden-mapping');
            }
        };

        // Ejecutar estado inicial
        toggleFields();

        // Escuchar cambios en el checkbox
        mappingCheckbox.addEventListener('change', toggleFields);
    }
}