(() => {
    "use strict";

    const els = {
        card: document.getElementById("card"),
        direction: document.getElementById("card-direction"),
        prompt: document.getElementById("card-prompt"),
        hint: document.getElementById("card-hint"),
        options: document.getElementById("options"),
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
    };

    const KEY_LABELS = ["A", "B", "C"];
    const DIRECTION_LABELS = {
        geo_to_en: "Georgian → English",
        en_to_geo: "English → Georgian",
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
            err.data = data;
            throw err;
        }
        return data;
    }

    function renderOptions(card) {
        els.options.innerHTML = "";
        const isGeorgianOption = card.direction === "en_to_geo";
        card.options.forEach((value, index) => {
            const btn = document.createElement("button");
            btn.type = "button";
            btn.className = "option" + (isGeorgianOption ? " is-georgian" : "");
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
        const isGeorgianPrompt = card.direction === "geo_to_en";
        els.prompt.classList.toggle("is-georgian", isGeorgianPrompt);
        els.prompt.textContent = card.prompt;
        els.direction.textContent = DIRECTION_LABELS[card.direction] || "";
        els.hint.textContent = card.notes || "Pick the matching translation.";
        els.card.classList.remove("is-correct", "is-wrong");
        els.feedback.textContent = "";
        els.feedback.classList.remove("is-correct", "is-wrong");
    }

    async function loadNext() {
        state.locked = true;
        els.feedback.textContent = "";
        els.options.querySelectorAll("button").forEach((b) => {
            b.disabled = true;
            b.classList.remove("is-correct", "is-wrong", "is-dimmed");
        });

        try {
            const params = new URLSearchParams();
            if (state.lastCardId != null) params.set("last_id", state.lastCardId);
            const card = await api(`/api/quiz/next/?${params.toString()}`);
            state.current = card;
            setPrompt(card);
            renderOptions(card);
            els.options.querySelectorAll("button").forEach((b) => (b.disabled = false));
            state.locked = false;
        } catch (err) {
            els.direction.textContent = "";
            els.prompt.textContent = "—";
            els.hint.textContent =
                err.status === 404
                    ? "No cards yet. Add some in the Dictionary."
                    : "Couldn't load a card. Try refreshing.";
        }
    }

    async function onAnswer(btn, chosen) {
        if (state.locked || !state.current) return;
        state.locked = true;

        els.options.querySelectorAll("button").forEach((b) => {
            b.disabled = true;
            if (b !== btn) b.classList.add("is-dimmed");
        });

        try {
            const result = await api("/api/quiz/answer/", {
                method: "POST",
                body: JSON.stringify({
                    card_id: state.current.card_id,
                    direction: state.current.direction,
                    chosen,
                }),
            });

            state.total += 1;
            els.total.textContent = state.total;
            if (result.correct) {
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
                els.feedback.textContent = `Answer: ${result.answer}`;
                els.feedback.classList.add("is-wrong");
                els.options.querySelectorAll("button").forEach((b) => {
                    if (b.dataset.value === result.answer) {
                        b.classList.remove("is-dimmed");
                        b.classList.add("is-correct");
                    }
                });
            }
            els.correct.textContent = state.correct;
            els.streak.textContent = state.streak;
            state.lastCardId = state.current.card_id;

            const delay = result.correct ? 700 : 1500;
            setTimeout(loadNext, delay);
        } catch (err) {
            state.locked = false;
            els.feedback.textContent =
                err.status === 403
                    ? "Couldn't save (403). The page may need a refresh."
                    : `Couldn't save (${err.status || "network"}). Try again.`;
            els.feedback.classList.add("is-wrong");
            els.options.querySelectorAll("button").forEach((b) => {
                b.disabled = false;
                b.classList.remove("is-dimmed");
            });
        }
    }

    document.addEventListener("keydown", (e) => {
        if (state.locked) return;
        const idx = ["1", "2", "3", "a", "A", "b", "B", "c", "C"].indexOf(e.key);
        if (idx === -1) return;
        const optionIndex = idx < 3 ? idx : Math.floor((idx - 3) / 2);
        const buttons = els.options.querySelectorAll(".option");
        const target = buttons[optionIndex];
        if (target) target.click();
    });

    loadNext();
})();
