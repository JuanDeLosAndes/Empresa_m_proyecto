document.querySelectorAll('[data-foto-carrito]').forEach(imagen => {
    const respaldo = () => {
        imagen.onerror = null;
        imagen.src = '/static/images/sin-foto.svg';
    };
    imagen.onerror = respaldo;
    if (imagen.complete && imagen.naturalWidth === 0) respaldo();
});