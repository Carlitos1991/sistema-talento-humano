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
    
    // Close on overlay click (but not when clicking inside dialog)
    modal.addEventListener('click', function(e) {
        if (e.target === modal) {
            hideModal();
        }
    });
});
