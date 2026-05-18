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
        lastCardId: null,
        locked: false,
        streak: 0,
        correct: 0,
        total: 0,
        keys: {}, // georgian char -> button element
    };

    function getCsrfToken() {
        const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : "";
    }

    async function api(url, options = {}) {
        const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
        if (options.method && options.method !== "GET") {
            headers["X-CSRFToken"] = getCsrfToken();
        }
        const res = await fetch(url, { ...options, headers });
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
            if (state.lastCardId != null) params.set("last_id", state.lastCardId);
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

    async function onTap(letter) {
        if (state.locked || !state.current) return;
        state.locked = true;
        setKeysEnabled(false);

        const tappedBtn = state.keys[letter];

        try {
            const result = await api("/api/quiz/answer/", {
                method: "POST",
                body: JSON.stringify({
                    card_id: state.current.card_id,
                    direction: state.current.direction,
                    chosen: letter,
                }),
            });

            state.total += 1;
            els.total.textContent = state.total;

            if (result.correct) {
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
                const correctBtn = state.keys[result.answer];
                if (correctBtn) correctBtn.classList.add("is-correct");
                els.feedback.textContent = `Answer: ${result.answer}`;
                els.feedback.classList.add("is-wrong");
            }
            els.correct.textContent = state.correct;
            els.streak.textContent = state.streak;
            state.lastCardId = state.current.card_id;

            const delay = result.correct ? 650 : 1500;
            setTimeout(loadNext, delay);
        } catch (err) {
            state.locked = false;
            setKeysEnabled(true);
            els.feedback.textContent =
                err.status === 403
                    ? "Couldn't save (403). The page may need a refresh."
                    : `Couldn't save (${err.status || "network"}). Try again.`;
            els.feedback.classList.add("is-wrong");
        }
    }

    (async () => {
        await buildKeyboard();
        await loadNext();
    })();
})();
