(() => {
    "use strict";

    const els = {
        card: document.getElementById("card"),
        direction: document.getElementById("card-direction"),
        prompt: document.getElementById("card-prompt"),
        options: document.getElementById("options"),
        feedback: document.getElementById("feedback"),
        streak: document.getElementById("stat-streak"),
        correct: document.getElementById("stat-correct"),
        total: document.getElementById("stat-total"),
        picker: document.getElementById("chapter-picker"),
        pickerSummary: document.getElementById("chapter-picker-summary"),
        chapterList: document.getElementById("chapter-list"),
        selectAll: document.getElementById("select-all"),
        selectNone: document.getElementById("select-none"),
    };

    const KEY_LABELS = ["A", "B", "C"];
    const STORAGE_KEY = "kartuli.selectedChapters";

    const state = {
        chapters: [],
        selected: new Set(),
        current: null,
        lastCardId: null,
        locked: false,
        streak: 0,
        correct: 0,
        total: 0,
    };

    async function api(url) {
        const res = await fetch(url);
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
            const err = new Error(data.message || data.error || `HTTP ${res.status}`);
            err.status = res.status;
            err.data = data;
            throw err;
        }
        return data;
    }

    function loadSelection() {
        try {
            const raw = localStorage.getItem(STORAGE_KEY);
            if (!raw) return null;
            return new Set(JSON.parse(raw));
        } catch {
            return null;
        }
    }

    function saveSelection() {
        try {
            localStorage.setItem(
                STORAGE_KEY,
                JSON.stringify([...state.selected])
            );
        } catch {}
    }

    function isGeorgianField(field) {
        return field === "georgian";
    }

    function renderChapterPicker() {
        els.chapterList.innerHTML = "";
        if (state.chapters.length === 0) {
            const empty = document.createElement("p");
            empty.className = "dict-empty";
            empty.textContent = "No chapters yet. Add some in the Dictionary.";
            els.chapterList.appendChild(empty);
            updatePickerSummary();
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
                saveSelection();
                updatePickerSummary();
                loadNext();
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
            els.chapterList.appendChild(label);
        });
        updatePickerSummary();
    }

    function updatePickerSummary() {
        const total = state.chapters.length;
        const selected = state.selected.size;
        if (total === 0) {
            els.pickerSummary.textContent = "none";
            return;
        }
        if (selected === 0) {
            els.pickerSummary.textContent = "none selected";
        } else if (selected === total) {
            els.pickerSummary.textContent = "all";
        } else {
            els.pickerSummary.textContent = `${selected} of ${total}`;
        }
    }

    function renderOptions(card) {
        els.options.innerHTML = "";
        const answerIsGeorgian = isGeorgianField(card.answer_field);
        card.options.forEach((value, index) => {
            const btn = document.createElement("button");
            btn.type = "button";
            btn.className = "option" + (answerIsGeorgian ? " is-georgian" : "");
            btn.dataset.value = value;
            const key = document.createElement("span");
            key.className = "option-key";
            key.textContent = KEY_LABELS[index] || "";
            const text = document.createElement("span");
            text.className = "option-text";
            text.textContent = value;
            btn.append(key, text);
            btn.addEventListener("click", () => onAnswer(btn, value));
            els.options.appendChild(btn);
        });
    }

    function setPrompt(card) {
        els.prompt.classList.toggle(
            "is-georgian",
            isGeorgianField(card.prompt_field)
        );
        els.prompt.textContent = card.prompt;
        els.direction.textContent = `${card.prompt_label} → ${card.answer_label}`;
        els.card.classList.remove("is-correct", "is-wrong");
        els.feedback.textContent = "";
        els.feedback.classList.remove("is-correct", "is-wrong");
    }

    function showEmptyState(message) {
        els.direction.textContent = "";
        els.prompt.textContent = "—";
        els.options.innerHTML = "";
        els.feedback.textContent = message;
        els.feedback.classList.remove("is-correct");
        els.feedback.classList.add("is-wrong");
    }

    async function loadNext() {
        state.locked = true;
        els.feedback.textContent = "";
        els.options.querySelectorAll("button").forEach((b) => {
            b.disabled = true;
            b.classList.remove("is-correct", "is-wrong", "is-dimmed");
        });

        if (state.chapters.length === 0) {
            showEmptyState("Create a chapter and add cards in the Dictionary.");
            return;
        }
        if (state.selected.size === 0) {
            showEmptyState("Pick at least one chapter above to start practising.");
            return;
        }

        try {
            const params = new URLSearchParams();
            params.set("chapters", [...state.selected].join(","));
            if (state.lastCardId != null) {
                params.set("last_id", state.lastCardId);
            }
            const card = await api(`/api/quiz/next/?${params.toString()}`);
            state.current = card;
            setPrompt(card);
            renderOptions(card);
            els.options.querySelectorAll("button").forEach((b) => (b.disabled = false));
            state.locked = false;
        } catch (err) {
            showEmptyState(
                err.data && err.data.message
                    ? err.data.message
                    : "Couldn't load a card. Try refreshing."
            );
        }
    }

    function onAnswer(btn, chosen) {
        if (state.locked || !state.current) return;
        state.locked = true;

        els.options.querySelectorAll("button").forEach((b) => {
            b.disabled = true;
            if (b !== btn) b.classList.add("is-dimmed");
        });

        const answer = state.current.answer;
        const correct = chosen === answer;
        state.total += 1;
        els.total.textContent = state.total;

        if (correct) {
            state.correct += 1;
            state.streak += 1;
            btn.classList.add("is-correct");
            els.card.classList.add("is-correct");
            els.feedback.textContent = "Correct";
            els.feedback.classList.add("is-correct");
        } else {
            state.streak = 0;
            btn.classList.add("is-wrong");
            els.card.classList.add("is-wrong");
            els.feedback.textContent = `Answer: ${answer}`;
            els.feedback.classList.add("is-wrong");
            els.options.querySelectorAll("button").forEach((b) => {
                if (b.dataset.value === answer) {
                    b.classList.remove("is-dimmed");
                    b.classList.add("is-correct");
                }
            });
        }
        els.correct.textContent = state.correct;
        els.streak.textContent = state.streak;
        state.lastCardId = state.current.card_id;

        const delay = correct ? 700 : 1500;
        setTimeout(loadNext, delay);
    }

    els.selectAll.addEventListener("click", () => {
        state.selected = new Set(state.chapters.map((c) => c.id));
        saveSelection();
        renderChapterPicker();
        loadNext();
    });

    els.selectNone.addEventListener("click", () => {
        state.selected = new Set();
        saveSelection();
        renderChapterPicker();
        loadNext();
    });

    document.addEventListener("keydown", (e) => {
        if (state.locked) return;
        const idx = ["1", "2", "3", "a", "A", "b", "B", "c", "C"].indexOf(e.key);
        if (idx === -1) return;
        const optionIndex = idx < 3 ? idx : Math.floor((idx - 3) / 2);
        const buttons = els.options.querySelectorAll(".option");
        const target = buttons[optionIndex];
        if (target) target.click();
    });

    (async () => {
        try {
            const data = await api("/api/chapters/");
            state.chapters = data.chapters || [];

            const stored = loadSelection();
            const allIds = state.chapters.map((c) => c.id);
            if (stored && stored.size > 0) {
                // Drop ids that no longer exist
                state.selected = new Set(
                    allIds.filter((id) => stored.has(id))
                );
                if (state.selected.size === 0) {
                    state.selected = new Set(allIds);
                }
            } else {
                state.selected = new Set(allIds);
            }
            saveSelection();
            renderChapterPicker();
            await loadNext();
        } catch (err) {
            showEmptyState("Couldn't load chapters.");
        }
    })();
})();
