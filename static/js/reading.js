(() => {
    "use strict";

    const STORAGE_CHAPTERS = "kartuli.readingChapters";
    const SETUP_URL = "/reading/";
    const KEY_LABELS = ["A", "B", "C", "D"];

    const els = {
        card: document.getElementById("card"),
        direction: document.getElementById("card-direction"),
        prompt: document.getElementById("card-prompt"),
        options: document.getElementById("options"),
        feedback: document.getElementById("feedback"),
        learn: document.getElementById("reading-learn"),
        learnGeorgian: document.getElementById("learn-georgian"),
        learnRomanised: document.getElementById("learn-romanised"),
        learnEnglish: document.getElementById("learn-english"),
        next: document.getElementById("reading-next"),
        streak: document.getElementById("stat-streak"),
        correct: document.getElementById("stat-correct"),
        total: document.getElementById("stat-total"),
        summary: document.getElementById("reading-summary-text"),
    };

    const state = {
        chapters: [],
        current: null,
        lastCardId: null,
        locked: false,
        answered: false,
        streak: 0,
        correct: 0,
        total: 0,
    };

    function loadStoredChapters() {
        try {
            const raw = localStorage.getItem(STORAGE_CHAPTERS);
            if (!raw) return null;
            const arr = JSON.parse(raw);
            if (Array.isArray(arr)) {
                return arr.filter((id) => Number.isInteger(id));
            }
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

    function playAudio(url) {
        window.KartuliAudio?.play(url);
    }

    function applyLengthClass(el, text) {
        const len = (text || "").length;
        el.classList.remove("len-medium", "len-long", "len-xlong");
        if (len > 30) el.classList.add("len-xlong");
        else if (len > 18) el.classList.add("len-long");
        else if (len > 10) el.classList.add("len-medium");
    }

    function showSummary() {
        const cText = `${state.chapters.length} categor${state.chapters.length === 1 ? "y" : "ies"}`;
        els.summary.textContent = `1000 words · ${cText}`;
    }

    function showEmptyState(message) {
        els.direction.textContent = "";
        els.prompt.textContent = "—";
        els.options.innerHTML = "";
        els.feedback.textContent = message;
        els.feedback.classList.remove("is-correct");
        els.feedback.classList.add("is-wrong");
        els.learn.hidden = true;
        els.next.hidden = true;
    }

    function hideLearnPanel() {
        state.answered = false;
        els.learn.hidden = true;
        els.next.hidden = true;
    }

    function showLearnPanel(card) {
        els.learnGeorgian.textContent = card.georgian || "—";
        els.learnRomanised.textContent = card.romanised || "—";
        els.learnEnglish.textContent = card.english || "—";
        applyLengthClass(els.learnGeorgian, card.georgian);
        els.learn.hidden = false;
        els.next.hidden = false;
    }

    function setPrompt(card) {
        els.prompt.classList.add("is-georgian");
        els.prompt.textContent = card.georgian;
        applyLengthClass(els.prompt, card.georgian);
        els.direction.textContent = "Georgian → Romanised";
        els.card.classList.remove("is-correct", "is-wrong");
        els.card.classList.toggle("has-audio", !!card.prompt_audio_url);
        els.feedback.textContent = "";
        els.feedback.classList.remove("is-correct", "is-wrong");
        hideLearnPanel();
    }

    function renderOptions(card) {
        els.options.innerHTML = "";
        card.options.forEach((opt, index) => {
            const value = typeof opt === "string" ? opt : opt.value;
            const audioUrl = typeof opt === "string" ? null : opt.audio_url;

            const btn = document.createElement("button");
            btn.type = "button";
            btn.className = "option";
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
        hideLearnPanel();
        els.feedback.textContent = "";

        try {
            const params = new URLSearchParams();
            params.set("chapters", state.chapters.join(","));
            if (state.lastCardId != null) params.set("last_id", state.lastCardId);
            const card = await api(`/api/reading/next/?${params.toString()}`);
            state.current = card;
            setPrompt(card);
            renderOptions(card);
            els.options.querySelectorAll("button.option").forEach((b) => {
                b.disabled = false;
                b.classList.remove("is-correct", "is-wrong", "is-dimmed");
            });
            state.locked = false;
        } catch (err) {
            showEmptyState(
                (err.data && err.data.message) ||
                    "Couldn't load a word. Try refreshing."
            );
        }
    }

    els.card.addEventListener("click", () => {
        if (!state.current || state.answered) return;
        playAudio(state.current.prompt_audio_url);
    });

    function onAnswer(btn, chosen) {
        if (state.locked || !state.current || state.answered) return;
        state.locked = true;
        state.answered = true;

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

        showLearnPanel(state.current);
        state.locked = false;
    }

    els.next.addEventListener("click", () => {
        if (state.locked) return;
        loadNext();
    });

    document.addEventListener("keydown", (e) => {
        if (state.locked) return;
        if (state.answered) {
            if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                loadNext();
            }
            return;
        }
        const keyMap = {
            "1": 0, "2": 1, "3": 2, "4": 3,
            a: 0, A: 0, b: 1, B: 1, c: 2, C: 2, d: 3, D: 3,
        };
        const idx = keyMap[e.key];
        if (idx == null) return;
        const target = els.options.querySelectorAll(".option")[idx];
        if (target) target.click();
    });

    const chapters = loadStoredChapters();
    if (!chapters || chapters.length === 0) {
        window.location.replace(SETUP_URL);
    } else {
        state.chapters = chapters;
        showSummary();
        loadNext();
    }
})();
