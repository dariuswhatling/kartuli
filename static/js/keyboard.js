(() => {
    "use strict";

    const els = {
        card: document.getElementById("card"),
        prompt: document.getElementById("card-prompt"),
        grid: document.getElementById("kb-grid"),
        feedback: document.getElementById("feedback"),
        streak: document.getElementById("stat-streak"),
        correct: document.getElementById("stat-correct"),
        total: document.getElementById("stat-total"),
    };

    const state = {
        current: null,
        lastPrompt: null,
        locked: false,
        streak: 0,
        correct: 0,
        total: 0,
        keys: {}, // georgian char -> button element
    };

    async function api(url) {
        const res = await fetch(url);
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
            const err = new Error(data.message || data.error || `HTTP ${res.status}`);
            err.status = res.status;
            throw err;
        }
        return data;
    }

    function clearKeyHighlights() {
        Object.values(state.keys).forEach((btn) => {
            btn.classList.remove("is-correct", "is-wrong", "is-dimmed");
        });
        els.card.classList.remove("is-correct", "is-wrong");
        els.feedback.textContent = "";
        els.feedback.classList.remove("is-correct", "is-wrong");
    }

    function setKeysEnabled(enabled) {
        Object.values(state.keys).forEach((btn) => (btn.disabled = !enabled));
    }

    async function buildKeyboard() {
        const data = await api("/api/quiz/keyboard-layout/");
        els.grid.innerHTML = "";
        state.keys = {};
        (data.letters || []).forEach((letter) => {
            const btn = document.createElement("button");
            btn.type = "button";
            btn.className = "kb-key";
            btn.textContent = letter;
            btn.dataset.value = letter;
            btn.disabled = true;
            btn.addEventListener("click", () => onTap(letter));
            els.grid.appendChild(btn);
            state.keys[letter] = btn;
        });
        if ((data.letters || []).length === 0) {
            const empty = document.createElement("p");
            empty.className = "kb-empty";
            empty.textContent =
                "No single-letter cards yet. Add some letters in the Dictionary.";
            els.grid.appendChild(empty);
        }
    }

    async function loadNext() {
        state.locked = true;
        setKeysEnabled(false);
        clearKeyHighlights();
        els.prompt.textContent = "…";

        try {
            const params = new URLSearchParams();
            if (state.lastPrompt) params.set("last", state.lastPrompt);
            const card = await api(
                `/api/quiz/keyboard-next/?${params.toString()}`
            );
            state.current = card;
            els.prompt.textContent = card.prompt;
            setKeysEnabled(true);
            state.locked = false;
        } catch (err) {
            els.prompt.textContent = "—";
            els.feedback.textContent =
                err.status === 404
                    ? "No alphabet cards available."
                    : `Couldn't load (${err.status || "network"}).`;
            els.feedback.classList.add("is-wrong");
        }
    }

    function onTap(letter) {
        if (state.locked || !state.current) return;
        state.locked = true;
        setKeysEnabled(false);

        const tappedBtn = state.keys[letter];
        const answer = state.current.answer;
        const correct = letter === answer;

        state.total += 1;
        els.total.textContent = state.total;

        if (correct) {
            state.correct += 1;
            state.streak += 1;
            tappedBtn.classList.add("is-correct");
            els.card.classList.add("is-correct");
            els.feedback.textContent = "Correct";
            els.feedback.classList.add("is-correct");
        } else {
            state.streak = 0;
            tappedBtn.classList.add("is-wrong");
            els.card.classList.add("is-wrong");
            const correctBtn = state.keys[answer];
            if (correctBtn) correctBtn.classList.add("is-correct");
            els.feedback.textContent = `Answer: ${answer}`;
            els.feedback.classList.add("is-wrong");
        }
        els.correct.textContent = state.correct;
        els.streak.textContent = state.streak;
        state.lastPrompt = state.current.prompt;

        const delay = correct ? 650 : 1500;
        setTimeout(loadNext, delay);
    }

    (async () => {
        await buildKeyboard();
        await loadNext();
    })();
})();
