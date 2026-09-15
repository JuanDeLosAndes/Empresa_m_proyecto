/**
 * MSPS - interacción del navbar: mini pestañas de "Iniciar sesion" y
 * "Registrarse", incluyendo el paso previo de elegir tipo de cuenta
 * (persona natural / empresa) dentro del panel de registro.
 */
(function () {
    "use strict";

    const authRoot = document.querySelector("[data-auth-root]");
    if (!authRoot) return;

    const triggers = authRoot.querySelectorAll("[data-auth-trigger]");
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
        }
    }

    function showRegisterView(view) {
        registerViews.forEach((section) => {
            section.hidden = section.dataset.registerView !== view;
        });
    }

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
        if (!authRoot.contains(event.target)) {
            closeAllPanels();
        }
    });

    // Tecla Escape: cerrar
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            closeAllPanels();
        }
    });
})();