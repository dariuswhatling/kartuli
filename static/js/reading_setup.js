(() => {
    "use strict";

    const STORAGE_CHAPTERS = "kartuli.readingChapters";
    const PLAY_URL = "/reading/play/";

    const els = {
        list: document.getElementById("chapter-list"),
        selectAll: document.getElementById("select-all"),
        selectNone: document.getElementById("select-none"),
        start: document.getElementById("start"),
        status: document.getElementById("setup-status"),
    };

    const state = {
        chapters: [],
        selected: new Set(),
    };

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

    function isEligible(card) {
        return !!(card.georgian && card.romanised);
    }

    async function loadChapters() {
        const res = await fetch("/api/common-words/");
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
            throw new Error(data.message || data.error || `HTTP ${res.status}`);
        }
        return data.chapters || [];
    }

    function renderChapters() {
        els.list.innerHTML = "";
        if (state.chapters.length === 0) {
            const p = document.createElement("p");
            p.className = "dict-empty";
            p.textContent =
                "1000-word list not loaded yet. Redeploy or run import_1000_words on the server.";
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
            const eligible = chapter.cards.filter(isEligible).length;
            count.textContent =
                eligible === chapter.cards.length
                    ? `${eligible}`
                    : `${eligible}/${chapter.cards.length}`;

            label.append(cb, name, count);
            els.list.appendChild(label);
        });
    }

    function totalEligibleCards() {
        return state.chapters
            .filter((c) => state.selected.has(c.id))
            .reduce(
                (sum, chapter) =>
                    sum + chapter.cards.filter(isEligible).length,
                0
            );
    }

    function pluralise(n, word) {
        return `${n} ${word}${n === 1 ? "" : "s"}`;
    }

    function updateValidity() {
        const problems = [];
        if (state.chapters.length === 0) {
            problems.push("Import the 1000-word list first.");
        } else if (state.selected.size === 0) {
            problems.push("Pick at least one category.");
        }

        const total = totalEligibleCards();
        els.start.disabled = problems.length > 0 || total < 4;

        if (problems.length === 0) {
            if (total < 4) {
                els.status.textContent =
                    "Need at least 4 words with Georgian and romanised text.";
                els.status.classList.add("is-error");
            } else {
                els.status.textContent = `Ready – ${pluralise(total, "word")} available.`;
                els.status.classList.remove("is-error");
            }
        } else {
            els.status.textContent = problems.join(" ");
            els.status.classList.add("is-error");
        }
    }

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

    els.start.addEventListener("click", () => {
        if (els.start.disabled) return;
        saveSet(STORAGE_CHAPTERS, state.selected);
        window.location.href = PLAY_URL;
    });

    (async () => {
        try {
            state.chapters = await loadChapters();
        } catch (err) {
            els.list.innerHTML = `<p class="dict-empty">${err.message || "Couldn't load categories."}</p>`;
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

        renderChapters();
        updateValidity();
    })();
})();
