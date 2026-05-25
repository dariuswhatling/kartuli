(() => {
    "use strict";

    const toggle = document.getElementById("nav-toggle");
    const closeBtn = document.getElementById("nav-close");
    const backdrop = document.getElementById("nav-backdrop");
    const nav = document.getElementById("site-nav");

    if (!toggle || !nav) return;

    const mobileMq = window.matchMedia("(max-width: 860px)");

    function isMobileNav() {
        return mobileMq.matches;
    }

    if (isMobileNav()) {
        nav.setAttribute("aria-hidden", "true");
    }

    function setOpen(open) {
        const useDrawer = isMobileNav();
        document.body.classList.toggle("nav-open", open && useDrawer);
        toggle.setAttribute("aria-expanded", open && useDrawer ? "true" : "false");
        toggle.setAttribute("aria-label", open && useDrawer ? "Close menu" : "Open menu");
        if (backdrop) {
            backdrop.hidden = !(open && useDrawer);
        }
        if (useDrawer) {
            nav.setAttribute("aria-hidden", open ? "false" : "true");
        } else {
            nav.removeAttribute("aria-hidden");
        }
    }

    function openMenu() {
        setOpen(true);
    }

    function closeMenu() {
        setOpen(false);
    }

    toggle.addEventListener("click", () => {
        if (!isMobileNav()) return;
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

    mobileMq.addEventListener("change", () => {
        closeMenu();
    });
})();
