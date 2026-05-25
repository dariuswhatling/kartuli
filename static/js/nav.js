(() => {
    "use strict";

    const toggle = document.getElementById("nav-toggle");
    const closeBtn = document.getElementById("nav-close");
    const backdrop = document.getElementById("nav-backdrop");
    const nav = document.getElementById("site-nav");

    if (!toggle || !nav) return;

    function setOpen(open) {
        document.body.classList.toggle("nav-open", open);
        toggle.setAttribute("aria-expanded", open ? "true" : "false");
        toggle.setAttribute("aria-label", open ? "Close menu" : "Open menu");
        if (backdrop) backdrop.hidden = !open;
    }

    function openMenu() {
        setOpen(true);
    }

    function closeMenu() {
        setOpen(false);
    }

    toggle.addEventListener("click", () => {
        if (document.body.classList.contains("nav-open")) {
            closeMenu();
        } else {
            openMenu();
        }
    });

    closeBtn?.addEventListener("click", closeMenu);
    backdrop?.addEventListener("click", closeMenu);

    nav.querySelectorAll(".nav-link").forEach((link) => {
        link.addEventListener("click", closeMenu);
    });

    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") closeMenu();
    });

    window.matchMedia("(min-width: 861px)").addEventListener("change", (e) => {
        if (e.matches) closeMenu();
    });
})();
