(() => {
    "use strict";

    const els = {
        card: document.getElementById("card"),
        direction: document.getElementById("card-direction"),
        prompt: document.getElementById("card-prompt"),
        grid: document.getElementById("kb-grid"),
        feedback: document.getElementById("feedback"),
        streak: document.getElementById("stat-streak"),
        correct: document.getElementById("stat-correct"),
        total: document.getElementById("stat-total"),
        toggleButtons: document.querySelectorAll(".mode-toggle-option"),
    };

    const DIRECTIONS = {
        en_to_geo: {
            promptKey: "sound",
            answerKey: "georgian",
            keysKey: "georgian",
            keyboardLabel: "Georgian alphabet keyboard",
            instruction: "Tap the matching letter",
        },
        geo_to_en: {
            promptKey: "georgian",
            answerKey: "sound",
            keysKey: "sound",
            keyboardLabel: "Romanised sound keyboard",
            instruction: "Tap the matching sound",
        },
    };

    const state = {
        pairs: [],
        direction: "en_to_geo",
        current: null,
        lastPrompt: null,
        locked: false,
        streak: 0,
        correct: 0,
        total: 0,
        keys: {}, // value -> button element
    };

    async function fetchAlphabet() {
        const res = await fetch("/api/alphabet/");
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        return data.pairs || [];
    }

    function isGeorgianFont(direction, role) {
        // role = "prompt" | "key"
        const cfg = DIRECTIONS[direction];
        const field = role === "prompt" ? cfg.promptKey : cfg.keysKey;
        return field === "georgian";
    }

    function clearKeyHighlights() {
        Object.values(state.keys).forEach((btn) => {
            btn.classList.remove("is-correct", "is-wrong");
        });
        els.card.classList.remove("is-correct", "is-wrong");
        els.feedback.textContent = "";
        els.feedback.classList.remove("is-correct", "is-wrong");
    }

    function setKeysEnabled(enabled) {
        Object.values(state.keys).forEach((btn) => (btn.disabled = !enabled));
    }

    function buildKeyboard() {
        const cfg = DIRECTIONS[state.direction];
        els.grid.innerHTML = "";
        els.grid.setAttribute("aria-label", cfg.keyboardLabel);
        state.keys = {};

        const georgianFont = isGeorgianFont(state.direction, "key");
        const seen = new Set();
        const values = [];
        for (const pair of state.pairs) {
            const v = pair[cfg.keysKey];
            if (seen.has(v)) continue;
            seen.add(v);
            values.push(v);
        }

        values.forEach((value) => {
            const btn = document.createElement("button");
            btn.type = "button";
            btn.className = "kb-key" + (georgianFont ? "" : " is-sound");
            btn.textContent = value;
            btn.dataset.value = value;
            btn.disabled = true;
            btn.addEventListener("click", () => onTap(value));
            els.grid.appendChild(btn);
            state.keys[value] = btn;
        });
    }

    function pickNext() {
        const cfg = DIRECTIONS[state.direction];
        const eligible = state.pairs.filter(
            (p) => p[cfg.promptKey] !== state.lastPrompt
        );
        const pool = eligible.length ? eligible : state.pairs;
        const pair = pool[Math.floor(Math.random() * pool.length)];
        return {
            prompt: pair[cfg.promptKey],
            answer: pair[cfg.answerKey],
        };
    }

    function loadNext() {
        if (!state.pairs.length) return;
        const cfg = DIRECTIONS[state.direction];
        state.locked = true;
        setKeysEnabled(false);
        clearKeyHighlights();

        state.current = pickNext();
        els.direction.textContent = cfg.instruction;
        els.prompt.textContent = state.current.prompt;
        els.prompt.classList.toggle(
            "is-georgian",
            isGeorgianFont(state.direction, "prompt")
        );

        setKeysEnabled(true);
        state.locked = false;
    }

    function onTap(value) {
        if (state.locked || !state.current) return;
        state.locked = true;
        setKeysEnabled(false);

        const tapped = state.keys[value];
        const answer = state.current.answer;
        const correct = value === answer;

        state.total += 1;
        els.total.textContent = state.total;

        if (correct) {
            state.correct += 1;
            state.streak += 1;
            tapped.classList.add("is-correct");
            els.card.classList.add("is-correct");
            els.feedback.textContent = "Correct";
            els.feedback.classList.add("is-correct");
        } else {
            state.streak = 0;
            tapped.classList.add("is-wrong");
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

    function setDirection(direction) {
        if (!(direction in DIRECTIONS) || direction === state.direction) return;
        state.direction = direction;
        state.lastPrompt = null;
        els.toggleButtons.forEach((btn) => {
            const active = btn.dataset.direction === direction;
            btn.classList.toggle("is-active", active);
            btn.setAttribute("aria-selected", active ? "true" : "false");
        });
        buildKeyboard();
        loadNext();
    }

    els.toggleButtons.forEach((btn) => {
        btn.addEventListener("click", () => setDirection(btn.dataset.direction));
    });

    (async () => {
        try {
            state.pairs = await fetchAlphabet();
            if (!state.pairs.length) {
                els.grid.innerHTML =
                    '<p class="kb-empty">Alphabet is empty.</p>';
                return;
            }
            buildKeyboard();
            loadNext();
        } catch (err) {
            els.grid.innerHTML =
                '<p class="kb-empty">Couldn\'t load the alphabet.</p>';
        }
    })();
})();
