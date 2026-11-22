(() => {
    let oscuro = window.matchMedia('(prefers-color-scheme: dark)').matches;
    try {
        const guardado = localStorage.getItem('msps-tema');
        if (guardado) oscuro = guardado === 'noche';
    } catch {}
    const aplicar = () => {
        document.documentElement.dataset.tema = oscuro ? 'noche' : 'dia';
        document.querySelector('button[data-tema]')?.setAttribute('aria-pressed', String(oscuro));
    };
    aplicar();
    document.addEventListener('DOMContentLoaded', () => {
        aplicar();
        document.querySelector('button[data-tema]').addEventListener('click', () => {
            oscuro = !oscuro;
            aplicar();
            try { localStorage.setItem('msps-tema', document.documentElement.dataset.tema); } catch {}
        });
    });
})();