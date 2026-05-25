(() => {
    "use strict";

    const STORAGE_CHAPTERS = "kartuli.flashcardChapters";
    const PLAY_URL = "/flashcard/play/";

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

    async function loadChapters() {
        const res = await fetch("/api/chapters/");
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        return data.chapters || [];
    }

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
            const eligible = chapter.cards.filter(
                (c) => c.romanised && c.english
            ).length;
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
                    sum +
                    chapter.cards.filter((card) => card.romanised && card.english)
                        .length,
                0
            );
    }

    function pluralise(n, word) {
        return `${n} ${word}${n === 1 ? "" : "s"}`;
    }

    function updateValidity() {
        const problems = [];
        if (state.chapters.length === 0) {
            problems.push("Add chapters in the Dictionary first.");
        } else if (state.selected.size === 0) {
            problems.push("Pick at least one chapter.");
        }

        els.start.disabled = problems.length > 0;
        if (problems.length === 0) {
            const total = totalEligibleCards();
            els.status.textContent =
                total >= 1
                    ? `Ready – ${pluralise(total, "card")} with Romanised and English.`
                    : "No eligible cards — each card needs Romanised and English filled in.";
            if (total < 1) els.start.disabled = true;
            els.status.classList.toggle("is-error", total < 1);
        } else {
            els.status.textContent = problems.join(" ");
            els.status.classList.add("is-error");
        }
        if (problems.length === 0 && totalEligibleCards() >= 1) {
            els.status.classList.remove("is-error");
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

        renderChapters();
        updateValidity();
    })();
})();
