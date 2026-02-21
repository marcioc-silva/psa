self.addEventListener('fetch', function(event) {
    // Este código básico permite que o navegador reconheça o app como instalável
    event.respondWith(fetch(event.request));
});