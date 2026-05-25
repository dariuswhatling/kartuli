(() => {
    "use strict";

    const STORAGE_CHAPTERS = "kartuli.flashcardChapters";
    const SETUP_URL = "/flashcard/";

    const els = {
        fc: document.getElementById("flashcard"),
        card: document.getElementById("card"),
        direction: document.getElementById("card-direction"),
        prompt: document.getElementById("card-prompt"),
        reveal: document.getElementById("fc-reveal"),
        revealLabel: document.getElementById("fc-reveal-label"),
        revealAnswer: document.getElementById("fc-reveal-answer"),
        toolbar: document.getElementById("fc-toolbar"),
        grade: document.getElementById("fc-grade"),
        check: document.getElementById("fc-check"),
        wrong: document.getElementById("fc-wrong"),
        right: document.getElementById("fc-right"),
        streak: document.getElementById("stat-streak"),
        correct: document.getElementById("stat-correct"),
        total: document.getElementById("stat-total"),
        summary: document.getElementById("fc-summary-text"),
    };

    const state = {
        chapters: [],
        current: null,
        lastCardId: null,
        locked: false,
        revealed: false,
        streak: 0,
        correct: 0,
        total: 0,
    };

    function loadStoredChapters() {
        try {
            const raw = localStorage.getItem(STORAGE_CHAPTERS);
            if (!raw) return null;
            const arr = JSON.parse(raw);
            if (Array.isArray(arr)) return arr.filter((id) => Number.isInteger(id));
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

    function applyLengthClass(el, text) {
        const len = (text || "").length;
        el.classList.remove("len-medium", "len-long", "len-xlong");
        if (len > 30) el.classList.add("len-xlong");
        else if (len > 18) el.classList.add("len-long");
        else if (len > 10) el.classList.add("len-medium");
    }

    function showSummary() {
        const cText = `${state.chapters.length} chapter${state.chapters.length === 1 ? "" : "s"}`;
        els.summary.textContent = `${cText} · Romanised ↔ English`;
    }

    /** Hide front and back so the previous card cannot flash during load. */
    function collapseForTransition() {
        state.revealed = false;
        els.reveal.hidden = true;
        els.revealAnswer.textContent = "";
        els.revealLabel.textContent = "";
        els.prompt.textContent = "";
        els.direction.textContent = "";
        els.toolbar.hidden = true;
        els.grade.hidden = true;
        els.check.disabled = true;
        els.wrong.disabled = true;
        els.right.disabled = true;
        els.card.classList.add("fc-front-hidden");
        els.card.classList.remove("is-correct", "is-wrong");
        els.fc?.classList.add("fc-is-transitioning");
    }

    function showReveal(card) {
        state.revealed = true;
        els.fc?.classList.remove("fc-is-transitioning");
        els.revealLabel.textContent = card.answer_label;
        els.revealAnswer.textContent = card.answer;
        applyLengthClass(els.revealAnswer, card.answer);
        els.reveal.hidden = false;
        els.toolbar.hidden = true;
        els.grade.hidden = false;
        els.check.disabled = true;
        els.wrong.disabled = false;
        els.right.disabled = false;
        els.card.classList.add("fc-front-hidden");
    }

    function showFront(card) {
        state.revealed = false;
        els.prompt.classList.remove("is-georgian");
        els.prompt.textContent = card.prompt;
        applyLengthClass(els.prompt, card.prompt);
        els.direction.textContent = `Think of the ${card.answer_label.toLowerCase()}`;
        els.reveal.hidden = true;
        els.revealAnswer.textContent = "";
        els.revealLabel.textContent = "";
        els.card.classList.remove("fc-front-hidden", "is-correct", "is-wrong", "has-audio");
        els.fc?.classList.remove("fc-is-transitioning", "fc-flash-ok", "fc-flash-bad");
        els.toolbar.hidden = false;
        els.grade.hidden = true;
        els.check.disabled = false;
        els.wrong.disabled = true;
        els.right.disabled = true;
    }

    function showEmptyState(message) {
        collapseForTransition();
        els.direction.textContent = message;
        els.fc?.classList.remove("fc-is-transitioning");
        els.check.disabled = true;
    }

    async function loadNext() {
        state.locked = true;

        try {
            const params = new URLSearchParams();
            params.set("chapters", state.chapters.join(","));
            if (state.lastCardId != null) params.set("last_id", state.lastCardId);
            const card = await api(`/api/flashcard/next/?${params.toString()}`);
            state.current = card;
            showFront(card);
            state.locked = false;
        } catch (err) {
            showEmptyState(
                (err.data && err.data.message) ||
                    "Couldn't load a card. Try refreshing."
            );
        }
    }

    function finishRound(wasCorrect) {
        state.total += 1;
        els.total.textContent = state.total;

        if (wasCorrect) {
            state.correct += 1;
            state.streak += 1;
        } else {
            state.streak = 0;
        }
        els.correct.textContent = state.correct;
        els.streak.textContent = state.streak;
        state.lastCardId = state.current.card_id;

        state.locked = true;
        collapseForTransition();
        els.fc?.classList.remove("fc-flash-ok", "fc-flash-bad");
        els.fc?.classList.add(wasCorrect ? "fc-flash-ok" : "fc-flash-bad");

        const delay = wasCorrect ? 450 : 750;
        setTimeout(() => {
            els.fc?.classList.remove("fc-flash-ok", "fc-flash-bad");
            loadNext();
        }, delay);
    }

    function onCheck() {
        if (state.locked || !state.current || state.revealed) return;
        showReveal(state.current);
    }

    function onGrade(wasCorrect) {
        if (!state.revealed || state.locked || !state.current) return;
        finishRound(wasCorrect);
    }

    els.check.addEventListener("click", onCheck);
    els.wrong.addEventListener("click", () => onGrade(false));
    els.right.addEventListener("click", () => onGrade(true));

    const chapters = loadStoredChapters();
    if (!chapters || chapters.length === 0) {
        window.location.replace(SETUP_URL);
    } else {
        state.chapters = chapters;
        showSummary();
        loadNext();
    }
})();
