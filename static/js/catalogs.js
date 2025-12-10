// File: static/js/catalogs.js
(function () {
  if (typeof Vue === 'undefined') {
    console.error('Vue no está cargado. Incluye Vue 3 antes de este script.');
    return;
  }
  const { createApp } = Vue;
  const app = createApp({
    // Evita el warning "Component is missing template or render function"
    render() { return null; },

    data() { return { visible: false }; },
    methods: {
      overlay() { return document.querySelector('.modal-overlay'); },
      open() {
        const o = this.overlay(); if (!o) return;
        o.classList.remove('hidden'); this.visible = true;
        const first = o.querySelector('input, textarea, select, button'); if (first) first.focus();
      },
      close() {
        const o = this.overlay(); if (!o) return;
        o.classList.add('hidden'); this.visible = false;
      },
      bind() {
        document.querySelectorAll('[data-modal-open="catalog-modal"]').forEach(btn => {
          btn.addEventListener('click', e => { e.preventDefault(); this.open(); });
        });
        document.querySelectorAll('[data-modal-close="catalog-modal"]').forEach(btn => {
          btn.addEventListener('click', e => { e.preventDefault(); this.close(); });
        });
        const o = this.overlay();
        if (o) o.addEventListener('click', e => { if (e.target === o) this.close(); });
      }
    },
    mounted() { this.bind(); }
  });

  const mountPoint = document.createElement('div');
  mountPoint.id = 'catalog-modal-vue-app';
  document.body.appendChild(mountPoint);
  app.mount(mountPoint);
})();
