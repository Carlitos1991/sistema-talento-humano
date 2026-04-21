/* Modal event handlers - Move outside template to avoid Vue compilation warnings */
document.addEventListener('DOMContentLoaded', function() {
    const modal = document.getElementById('documentModal-overlay');
    if (!modal) return;
    
    const form = document.getElementById('documentForm');
    
    function hideModal() {
        modal.classList.add('hidden');
        document.body.classList.remove('no-scroll');
    }
    
    // Form submit handler
    if (form) {
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            if (window.documentsInstance && typeof window.documentsInstance.saveDocument === 'function') {
                window.documentsInstance.saveDocument();
            }
        });
    }
    
    // Close button
    const closeBtn = document.getElementById('modal-close-btn');
    if (closeBtn) {
        closeBtn.addEventListener('click', hideModal);
    }
    
    // Cancel button
    const cancelBtn = document.getElementById('modal-cancel-btn');
    if (cancelBtn) {
        cancelBtn.addEventListener('click', hideModal);
    }
    
    // Prevent closing modal by clicking outside (overlay)
    // Users must use the 'Cerrar' button or the close icon to dismiss explicitly.
    // This avoids accidental loss of input when clicking fuera del modal.
    // Do nothing on overlay click; optionally focus first input to guide the user.
    modal.addEventListener('click', function(e) {
        if (e.target === modal) {
            const firstInput = modal.querySelector('input, textarea, select');
            if (firstInput) firstInput.focus();
            // Optionally provide a gentle hint (no modal hide)
            if (typeof Swal !== 'undefined') {
                try { Swal.dismiss(); } catch (e) {}
            }
        }
    });
});
