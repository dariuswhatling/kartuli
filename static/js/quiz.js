(() => {
    "use strict";

    const STORAGE_CHAPTERS = "kartuli.selectedChapters";
    const STORAGE_FIELDS = "kartuli.selectedFields";
    const SETUP_URL = "/quiz/";
    const VALID_FIELDS = ["romanised", "english", "georgian"];
    const FIELD_LABELS = {
        romanised: "Romanised",
        english: "English",
        georgian: "Georgian",
    };
    const KEY_LABELS = ["A", "B", "C", "D"];

    const els = {
        card: document.getElementById("card"),
        direction: document.getElementById("card-direction"),
        prompt: document.getElementById("card-prompt"),
        options: document.getElementById("options"),
        feedback: document.getElementById("feedback"),
        streak: document.getElementById("stat-streak"),
        correct: document.getElementById("stat-correct"),
        total: document.getElementById("stat-total"),
        summary: document.getElementById("quiz-summary-text"),
    };

    const state = {
        chapters: [],
        fields: [],
        current: null,
        lastCardId: null,
        locked: false,
        streak: 0,
        correct: 0,
        total: 0,
    };

    function loadStoredSet(key) {
        try {
            const raw = localStorage.getItem(key);
            if (!raw) return null;
            const arr = JSON.parse(raw);
            if (Array.isArray(arr)) return arr;
        } catch {}
        return null;
    }

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

    function isGeorgianField(field) {
        return field === "georgian";
    }

    // ---- Audio playback -----------------------------------------------------

    let currentAudio = null;
    function playAudio(url) {
        if (!url) return;
        if (currentAudio) {
            try { currentAudio.pause(); } catch {}
        }
        const audio = new Audio(url);
        audio.preload = "auto";
        currentAudio = audio;
        audio.play().catch(() => {
            // Autoplay may be blocked until first user interaction; ignore.
        });
    }

    // ---- Font sizing based on prompt length --------------------------------

    function applyLengthClass(el, text) {
        const len = (text || "").length;
        el.classList.remove("len-medium", "len-long", "len-xlong");
        if (len > 30) el.classList.add("len-xlong");
        else if (len > 18) el.classList.add("len-long");
        else if (len > 10) el.classList.add("len-medium");
    }

    function showSummary() {
        const cText = `${state.chapters.length} chapter${state.chapters.length === 1 ? "" : "s"}`;
        const fText = state.fields
            .map((f) => FIELD_LABELS[f].slice(0, 3))
            .join(" · ");
        els.summary.textContent = `${cText} · ${fText}`;
    }

    function showEmptyState(message) {
        els.direction.textContent = "";
        els.prompt.textContent = "—";
        els.options.innerHTML = "";
        els.feedback.textContent = message;
        els.feedback.classList.remove("is-correct");
        els.feedback.classList.add("is-wrong");
    }

    function setPrompt(card) {
        els.prompt.classList.toggle(
            "is-georgian",
            isGeorgianField(card.prompt_field)
        );
        els.prompt.textContent = card.prompt;
        applyLengthClass(els.prompt, card.prompt);
        els.direction.textContent = `${card.prompt_label} → ${card.answer_label}`;
        els.card.classList.remove("is-correct", "is-wrong");
        els.card.classList.toggle("has-audio", !!card.prompt_audio_url);
        els.feedback.textContent = "";
        els.feedback.classList.remove("is-correct", "is-wrong");
    }

    function renderOptions(card) {
        els.options.innerHTML = "";
        const answerIsGeorgian = isGeorgianField(card.answer_field);
        card.options.forEach((opt, index) => {
            const value = typeof opt === "string" ? opt : opt.value;
            const audioUrl = typeof opt === "string" ? null : opt.audio_url;

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
            applyLengthClass(text, value);

            btn.append(key, text);

            if (audioUrl) {
                const hear = document.createElement("button");
                hear.type = "button";
                hear.className = "option-audio";
                hear.setAttribute("aria-label", "Hear pronunciation");
                hear.title = "Hear pronunciation";
                hear.innerHTML =
                    '<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path fill="currentColor" d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z"/></svg>';
                hear.addEventListener("click", (e) => {
                    e.stopPropagation();
                    playAudio(audioUrl);
                });
                btn.append(hear);
            }

            btn.addEventListener("click", () => onAnswer(btn, value));
            els.options.appendChild(btn);
        });
    }

    async function loadNext() {
        state.locked = true;
        els.feedback.textContent = "";
        els.options.querySelectorAll("button.option").forEach((b) => {
            b.disabled = true;
            b.classList.remove("is-correct", "is-wrong", "is-dimmed");
        });

        try {
            const params = new URLSearchParams();
            params.set("chapters", state.chapters.join(","));
            params.set("fields", state.fields.join(","));
            if (state.lastCardId != null) params.set("last_id", state.lastCardId);
            const card = await api(`/api/quiz/next/?${params.toString()}`);
            state.current = card;
            setPrompt(card);
            renderOptions(card);
            els.options.querySelectorAll("button.option").forEach((b) => (b.disabled = false));
            state.locked = false;
        } catch (err) {
            showEmptyState(
                (err.data && err.data.message) ||
                    "Couldn't load a card. Try refreshing."
            );
        }
    }

    els.card.addEventListener("click", () => {
        if (!state.current) return;
        playAudio(state.current.prompt_audio_url);
    });

    function onAnswer(btn, chosen) {
        if (state.locked || !state.current) return;
        state.locked = true;

        els.options.querySelectorAll("button.option").forEach((b) => {
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
            els.options.querySelectorAll("button.option").forEach((b) => {
                if (b.dataset.value === answer) {
                    b.classList.remove("is-dimmed");
                    b.classList.add("is-correct");
                }
            });
        }
        els.correct.textContent = state.correct;
        els.streak.textContent = state.streak;
        state.lastCardId = state.current.card_id;

        setTimeout(loadNext, correct ? 700 : 1500);
    }

    document.addEventListener("keydown", (e) => {
        if (state.locked) return;
        const keyMap = {
            "1": 0, "2": 1, "3": 2, "4": 3,
            a: 0, A: 0, b: 1, B: 1, c: 2, C: 2, d: 3, D: 3,
        };
        const idx = keyMap[e.key];
        if (idx == null) return;
        const target = els.options.querySelectorAll(".option")[idx];
        if (target) target.click();
    });

    // ---- Boot ---------------------------------------------------------------

    const storedChapters = loadStoredSet(STORAGE_CHAPTERS);
    const storedFields = loadStoredSet(STORAGE_FIELDS);

    const fields = (storedFields || []).filter((f) => VALID_FIELDS.includes(f));
    const chapters = (storedChapters || []).filter((id) => Number.isInteger(id));

    if (chapters.length === 0 || fields.length < 2) {
        window.location.replace(SETUP_URL);
    } else {
        state.chapters = chapters;
        state.fields = fields;
        showSummary();
        loadNext();
    }
})();
