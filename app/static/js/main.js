/**
 * MSPS - interacción del navbar: mini pestañas de "Iniciar sesion" y
 * "Registrarse", incluyendo el paso previo de elegir tipo de cuenta
 * (persona natural / empresa) dentro del panel de registro.
 */
(function () {
    "use strict";

    const authRoot = document.querySelector("[data-auth-root]");
    if (!authRoot) return;

    const triggers = document.querySelectorAll("[data-auth-trigger]");
    const panels = authRoot.querySelectorAll("[data-auth-panel]");
    const registerViews = authRoot.querySelectorAll("[data-register-view]");

    function closeAllPanels() {
        panels.forEach((panel) => {
            panel.hidden = true;
        });
    }

    function openPanel(name) {
        closeAllPanels();
        const panel = authRoot.querySelector(`[data-auth-panel="${name}"]`);
        if (panel) {
            panel.hidden = false;
            panel.querySelector("button, input")?.focus();
        }
    }

    function showRegisterView(view) {
        registerViews.forEach((section) => {
            section.hidden = section.dataset.registerView !== view;
        });
    }

    document.addEventListener('msps:login', () => {
        openPanel('login');
        authRoot.querySelector('[name="identificador"]')?.focus();
    });

    document.addEventListener('click', event => {
        const link = event.target.closest('a[href]');
        if (!link || !authRoot.querySelector('[data-auth-panel="login"]')) return;
        const destino = link.getAttribute('href');
        if (['/carrito', '/?acceso=login', '/?acceso=registro'].includes(destino)) {
            event.preventDefault();
            const panel = destino.endsWith('registro') ? 'register' : 'login';
            openPanel(panel);
            authRoot.querySelector('[data-auth-panel="' + panel + '"] input')?.focus();
        }
    });

    authRoot.querySelectorAll('.auth-panel form').forEach(form => {
        form.addEventListener('submit', async event => {
            event.preventDefault();
            const boton = form.querySelector('button');
            const estado = form.closest('.auth-panel').querySelector('[data-estado]');
            if (!form.reportValidity()) return;
            boton.disabled = true;
            estado.textContent = '';
            try {
                const respuesta = await fetch(form.action, {
                    method: 'POST', body: new FormData(form), headers: {Accept: 'application/json'}
                });
                const datos = await respuesta.json();
                if (!respuesta.ok) {
                    const campo = datos.campo && form.elements.namedItem(datos.campo);
                    if (campo) {
                        campo.setCustomValidity(datos.mensaje);
                        campo.reportValidity();
                    } else {
                        estado.textContent = datos.mensaje || 'Revisa los campos e intenta de nuevo.';
                        if (respuesta.status === 401) {
                            form.querySelectorAll('input').forEach(input => input.setAttribute('aria-invalid', 'true'));
                        }
                    }
                } else if (form.getAttribute('action') === '/login') {
                    location.reload();
                } else {
                    form.reset();
                    closeAllPanels();
                    const aviso = document.querySelector('#aviso-correo');
                    aviso.querySelector('[role="status"]').textContent = datos.mensaje;
                    aviso.showModal();
                }
            } catch {
                estado.textContent = 'No se pudo completar la solicitud. Intenta de nuevo.';
            } finally {
                boton.disabled = false;
            }
        });
    });

    // Alternar mini pestañas de login / registro
    triggers.forEach((trigger) => {
        trigger.addEventListener("click", (event) => {
            event.stopPropagation();
            const name = trigger.dataset.authTrigger;
            const panel = authRoot.querySelector(`[data-auth-panel="${name}"]`);
            const isOpen = panel && !panel.hidden;

            if (isOpen) {
                closeAllPanels();
                return;
            }

            openPanel(name);
            if (name === "register") {
                showRegisterView("choice");
            }
        });
    });

    // Cerrar con el botón "x"
    authRoot.querySelectorAll("[data-auth-close]").forEach((btn) => {
        btn.addEventListener("click", closeAllPanels);
    });

    // Saltar entre login <-> registro desde los enlaces internos
    authRoot.querySelectorAll("[data-auth-switch]").forEach((link) => {
        link.addEventListener("click", (event) => {
            event.preventDefault();
            const target = link.dataset.authSwitch;
            openPanel(target);
            if (target === "register") {
                showRegisterView("choice");
            }
        });
    });

    // Paso 1 -> paso 2 del registro: elegir "persona natural" o "empresa"
    authRoot.querySelectorAll("[data-register-select]").forEach((btn) => {
        btn.addEventListener("click", (event) => {
            event.preventDefault();
            showRegisterView(btn.dataset.registerSelect);
        });
    });

    // Clic fuera del panel: cerrar
    document.addEventListener("click", (event) => {
        if (!event.defaultPrevented && !authRoot.contains(event.target)) {
            closeAllPanels();
        }
    });

    // Tecla Escape: cerrar
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            closeAllPanels();
        }
    });

    const params = new URLSearchParams(window.location.search);
    if (params.get("registro") === "ok") {
        params.delete("registro");
        const query = params.toString();
        window.history.replaceState({}, "", window.location.pathname + (query ? "?" + query : ""));
    }
})();