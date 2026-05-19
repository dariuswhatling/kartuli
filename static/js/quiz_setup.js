(() => {
    "use strict";

    const STORAGE_CHAPTERS = "kartuli.selectedChapters";
    const STORAGE_FIELDS = "kartuli.selectedFields";
    const PLAY_URL = "/quiz/play/";
    const VALID_FIELDS = ["romanised", "english", "georgian"];
    const DEFAULT_FIELDS = ["romanised", "english"];

    const els = {
        list: document.getElementById("chapter-list"),
        selectAll: document.getElementById("select-all"),
        selectNone: document.getElementById("select-none"),
        fieldGroup: document.getElementById("field-pills"),
        start: document.getElementById("start"),
        status: document.getElementById("setup-status"),
    };

    const state = {
        chapters: [],
        selected: new Set(),
        fields: new Set(DEFAULT_FIELDS),
    };

    // ---- Storage helpers ----------------------------------------------------

    function loadStoredSet(key) {
        try {
            const raw = localStorage.getItem(key);
            if (!raw) return null;
            const arr = JSON.parse(raw);
            if (Array.isArray(arr)) return new Set(arr);
        } catch {}
        return null;
    }

    function saveSet(key, set) {
        try {
            localStorage.setItem(key, JSON.stringify([...set]));
        } catch {}
    }

    // ---- Fetch --------------------------------------------------------------

    async function loadChapters() {
        const res = await fetch("/api/chapters/");
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        return data.chapters || [];
    }

    // ---- Rendering ----------------------------------------------------------

    function renderChapters() {
        els.list.innerHTML = "";
        if (state.chapters.length === 0) {
            const p = document.createElement("p");
            p.className = "dict-empty";
            p.innerHTML =
                'No chapters yet. <a href="/dictionary/">Create one in the Dictionary</a>.';
            els.list.appendChild(p);
            return;
        }
        state.chapters.forEach((chapter) => {
            const label = document.createElement("label");
            label.className = "chapter-choice";

            const cb = document.createElement("input");
            cb.type = "checkbox";
            cb.checked = state.selected.has(chapter.id);
            cb.dataset.chapterId = String(chapter.id);
            cb.addEventListener("change", () => {
                if (cb.checked) state.selected.add(chapter.id);
                else state.selected.delete(chapter.id);
                updateValidity();
            });

            const name = document.createElement("span");
            name.className = "chapter-choice-name";
            name.textContent = chapter.name;

            const count = document.createElement("span");
            count.className = "chapter-choice-count";
            const complete = chapter.cards.filter(
                (c) => c.romanised && c.english && c.georgian
            ).length;
            count.textContent =
                complete === chapter.cards.length
                    ? `${complete}`
                    : `${complete}/${chapter.cards.length}`;

            label.append(cb, name, count);
            els.list.appendChild(label);
        });
    }

    function renderFields() {
        els.fieldGroup.querySelectorAll(".field-pill").forEach((btn) => {
            const field = btn.dataset.field;
            const active = state.fields.has(field);
            btn.classList.toggle("is-active", active);
            btn.setAttribute("aria-pressed", active ? "true" : "false");
        });
    }

    // ---- Validity / status --------------------------------------------------

    function updateValidity() {
        const chapterCount = state.selected.size;
        const fieldCount = state.fields.size;

        const problems = [];
        if (state.chapters.length === 0) {
            problems.push("Add chapters in the Dictionary first.");
        } else if (chapterCount === 0) {
            problems.push("Pick at least one chapter.");
        }
        if (fieldCount < 2) {
            problems.push("Pick at least two test fields.");
        }

        els.start.disabled = problems.length > 0;
        if (problems.length === 0) {
            const total = totalEligibleCards();
            els.status.textContent =
                total >= 3
                    ? `Ready – ${pluralise(total, "card")} match your selection.`
                    : `Only ${total} matching card(s); need 3 to play. Complete more cards.`;
            if (total < 3) els.start.disabled = true;
            els.status.classList.toggle("is-error", total < 3);
        } else {
            els.status.textContent = problems.join(" ");
            els.status.classList.add("is-error");
        }
        if (problems.length === 0 && totalEligibleCards() >= 3) {
            els.status.classList.remove("is-error");
        }
    }

    function totalEligibleCards() {
        const requiredFields = [...state.fields];
        return state.chapters
            .filter((c) => state.selected.has(c.id))
            .reduce(
                (sum, chapter) =>
                    sum +
                    chapter.cards.filter((card) =>
                        requiredFields.every((f) => card[f])
                    ).length,
                0
            );
    }

    function pluralise(n, word) {
        return `${n} ${word}${n === 1 ? "" : "s"}`;
    }

    // ---- Wire up ------------------------------------------------------------

    els.selectAll.addEventListener("click", () => {
        state.selected = new Set(state.chapters.map((c) => c.id));
        renderChapters();
        updateValidity();
    });

    els.selectNone.addEventListener("click", () => {
        state.selected = new Set();
        renderChapters();
        updateValidity();
    });

    els.fieldGroup.querySelectorAll(".field-pill").forEach((btn) => {
        btn.addEventListener("click", () => {
            const field = btn.dataset.field;
            if (state.fields.has(field)) {
                if (state.fields.size <= 2) {
                    // Refuse to drop below the minimum, give a quick wiggle.
                    btn.animate(
                        [
                            { transform: "translateX(0)" },
                            { transform: "translateX(-4px)" },
                            { transform: "translateX(4px)" },
                            { transform: "translateX(0)" },
                        ],
                        { duration: 220 }
                    );
                    return;
                }
                state.fields.delete(field);
            } else {
                state.fields.add(field);
            }
            renderFields();
            updateValidity();
        });
    });

    els.start.addEventListener("click", () => {
        if (els.start.disabled) return;
        saveSet(STORAGE_CHAPTERS, state.selected);
        saveSet(STORAGE_FIELDS, state.fields);
        window.location.href = PLAY_URL;
    });

    // ---- Init ---------------------------------------------------------------

    (async () => {
        try {
            state.chapters = await loadChapters();
        } catch (err) {
            els.list.innerHTML = `<p class="dict-empty">Couldn't load chapters.</p>`;
            updateValidity();
            return;
        }

        const storedChapters = loadStoredSet(STORAGE_CHAPTERS);
        const allIds = state.chapters.map((c) => c.id);
        if (storedChapters && storedChapters.size > 0) {
            state.selected = new Set(allIds.filter((id) => storedChapters.has(id)));
            if (state.selected.size === 0) state.selected = new Set(allIds);
        } else {
            state.selected = new Set(allIds);
        }

        const storedFields = loadStoredSet(STORAGE_FIELDS);
        if (storedFields && storedFields.size >= 2) {
            state.fields = new Set(
                [...storedFields].filter((f) => VALID_FIELDS.includes(f))
            );
            if (state.fields.size < 2) state.fields = new Set(DEFAULT_FIELDS);
        } else {
            state.fields = new Set(DEFAULT_FIELDS);
        }

        renderChapters();
        renderFields();
        updateValidity();
    })();
})();
