// Dentro del método loadForm del Vue Component para Grupos
if (data.permissions) {
    // Vanilla JS para marcar los checkboxes basados en el array de IDs
    // Esto se ejecuta después de que el HTML del modal (con los checkboxes) se haya insertado en el DOM
    setTimeout(() => {
        // Resetear todos
        document.querySelectorAll('input[name="permissions"]').forEach(el => el.checked = false);

        // Marcar los que vienen del backend
        data.permissions.forEach(id => {
            const el = document.getElementById(`perm_${id}`);
            if (el) el.checked = true;
        });
    }, 50); // Pequeño delay para asegurar renderizado
}