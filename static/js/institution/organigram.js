/* static/js/institution/organigram.js */

document.addEventListener('DOMContentLoaded', () => {
    const imgElement = document.getElementById('main-image');
    const uploadPlaceholder = document.getElementById('upload-placeholder');
    const toolbar = document.getElementById('toolbar');
    const btnSave = document.getElementById('btn-save-float');
    const uploadForm = document.getElementById('uploadForm');
    const viewerBox = document.getElementById('viewer-box');
    const btnMunicipio = document.getElementById('btn-municipio-link');
    if (btnMunicipio) {
        btnMunicipio.addEventListener('click', function () {
            const targetUrl = this.dataset.url;
            if (targetUrl) {
                // Navegación estándar a la nueva vista
                window.location.href = targetUrl;
            }
        });
    }
    // Buscamos el input file de forma segura dentro del form
    const fileInput = uploadForm ? uploadForm.querySelector('input[type="file"]') : null;

    // --- VARIABLES DE ZOOM & PAN ---
    let currentScale = 1;
    let isDragging = false;
    let startX, startY, translateX = 0, translateY = 0;

    // --- FUNCIONES DE UTILIDAD ---
    function updateTransform() {
        if (imgElement) {
            imgElement.style.transform = `translate(${translateX}px, ${translateY}px) scale(${currentScale})`;
        }
    }

    function zoomImage(amount) {
        if (!imgElement || imgElement.classList.contains('hidden')) return;
        currentScale += amount;
        if (currentScale < 0.1) currentScale = 0.1;
        if (currentScale > 5) currentScale = 5;
        updateTransform();
    }

    function resetZoom() {
        currentScale = 1;
        translateX = 0;
        translateY = 0;
        updateTransform();
    }

    // --- EVENT LISTENERS PARA BOTONES DEL TOOLBAR ---
    const btnZoomIn = document.getElementById('btn-zoom-in');
    const btnZoomOut = document.getElementById('btn-zoom-out');
    const btnReset = document.getElementById('btn-reset');
    const btnDownload = document.getElementById('btn-download');
    const btnTriggerUpload = document.getElementById('btn-trigger-upload');

    if (btnZoomIn) btnZoomIn.addEventListener('click', () => zoomImage(0.1));
    if (btnZoomOut) btnZoomOut.addEventListener('click', () => zoomImage(-0.1));
    if (btnReset) btnReset.addEventListener('click', resetZoom);

    if (btnDownload) {
        btnDownload.addEventListener('click', () => {
            if (!imgElement || !imgElement.src) return;
            const link = document.createElement('a');
            link.href = imgElement.src;
            link.download = 'organigrama_institucional.jpg';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        });
    }

    // --- LOGICA DE CARGA DE IMAGEN ---
    function triggerUploadAction() {
        if (fileInput) {
            fileInput.click();
        } else {
            console.error("No se encontró el input file.");
        }
    }

    // Listener para el botón del toolbar (lápiz)
    if (btnTriggerUpload) {
        btnTriggerUpload.addEventListener('click', triggerUploadAction);
    }

    // Listener para la zona grande de carga (placeholder)
    if (uploadPlaceholder) {
        uploadPlaceholder.addEventListener('click', (e) => {
            // Si el clic fue en el input file, no hacemos nada (el input se maneja solo)
            if (e.target === fileInput) return;
            triggerUploadAction();
        });
    }

    // --- LOGICA DEL INPUT FILE ---
    if (fileInput) {
        // Evitar propagación al hacer click en el input mismo
        fileInput.addEventListener('click', (e) => e.stopPropagation());

        fileInput.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = function (evt) {
                    imgElement.src = evt.target.result;
                    imgElement.classList.remove('hidden');

                    if (uploadPlaceholder) uploadPlaceholder.classList.add('hidden');
                    if (toolbar) toolbar.classList.remove('hidden');
                    if (btnSave) btnSave.style.display = 'block';

                    resetZoom();
                };
                reader.readAsDataURL(file);
            }
        });
    }

    // --- LOGICA DE GUARDAR ---
    if (btnSave && uploadForm) {
        btnSave.addEventListener('click', () => {
            uploadForm.submit();
        });
    }

    // --- LOGICA DE MOUSE (DRAG & WHEEL) ---
    if (viewerBox) {
        viewerBox.addEventListener('mousedown', (e) => {
            // Evitar arrastre si clicamos en botones
            if (e.target.closest('.tool-btn') || e.target.closest('.btn-save-float')) return;

            isDragging = true;
            startX = e.clientX - translateX;
            startY = e.clientY - translateY;
            if (imgElement) imgElement.style.cursor = 'grabbing';
        });

        window.addEventListener('mouseup', () => {
            isDragging = false;
            if (imgElement) imgElement.style.cursor = 'grab';
        });

        window.addEventListener('mousemove', (e) => {
            if (!isDragging) return;
            e.preventDefault();
            translateX = e.clientX - startX;
            translateY = e.clientY - startY;
            updateTransform();
        });

        viewerBox.addEventListener('wheel', (e) => {
            if (!imgElement || imgElement.classList.contains('hidden')) return;
            e.preventDefault();
            const delta = e.deltaY > 0 ? -0.1 : 0.1;
            zoomImage(delta);
        });
    }
});