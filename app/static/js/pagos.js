document.querySelectorAll('[data-iniciar-pago]').forEach(form => {
    form.addEventListener('submit', () => {
        const boton = form.querySelector('button[type="submit"]');
        boton.disabled = true;
        boton.textContent = 'Abriendo Wompi…';
    });
});
const panelPago = document.querySelector('[data-pago-referencia]');
if (panelPago && panelPago.dataset.pagoEstado === 'PENDING') {
    let intentos = 0;
    const consultar = async () => {
        intentos += 1;
        try {
            const respuesta = await fetch('/api/pagos/' + encodeURIComponent(panelPago.dataset.pagoReferencia), {cache: 'no-store'});
            if (!respuesta.ok) throw new Error();
            const pago = await respuesta.json();
            if (pago.estado !== 'PENDING') {
                location.reload();
                return;
            }
        } catch (_) {
            // Conservar el estado pendiente hasta recibir confirmación del servidor.
        }
        if (intentos < 12) setTimeout(consultar, 5000);
        else document.getElementById('pago-espera').textContent = 'El pago sigue pendiente. Puedes volver a Mis pagos o actualizar el estado más tarde. Evita repetir el pago mientras se confirma.';
    };
    setTimeout(consultar, 5000);
}