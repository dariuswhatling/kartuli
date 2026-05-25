(() => {
    "use strict";

    const els = {
        card: document.getElementById("card"),
        direction: document.getElementById("card-direction"),
        prompt: document.getElementById("card-prompt"),
        grid: document.getElementById("kb-grid"),
        drawPanel: document.getElementById("kb-draw"),
        drawCanvas: document.getElementById("draw-canvas"),
        drawClear: document.getElementById("draw-clear"),
        drawCheck: document.getElementById("draw-check"),
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
            interaction: "keyboard",
        },
        geo_to_en: {
            promptKey: "georgian",
            answerKey: "sound",
            keysKey: "sound",
            keyboardLabel: "Romanised sound keyboard",
            instruction: "Tap the matching sound",
            interaction: "keyboard",
        },
        draw_to_geo: {
            promptKey: "sound",
            answerKey: "georgian",
            instruction: "Draw the matching Georgian letter",
            interaction: "draw",
        },
    };

    const state = {
        pairs: [],
        direction: "geo_to_en",
        current: null,
        lastPrompt: null,
        locked: false,
        streak: 0,
        correct: 0,
        total: 0,
        keys: {},
    };

    const canvasState = {
        ctx: null,
        cssSize: 280,
        hasInk: false,
        drawing: false,
    };

    function playAudio(url) {
        window.KartuliAudio?.play(url);
    }

    function getCsrfToken() {
        const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : "";
    }

    async function fetchAlphabet() {
        const res = await fetch("/api/alphabet/");
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        return data.pairs || [];
    }

    function isDrawMode() {
        return DIRECTIONS[state.direction].interaction === "draw";
    }

    function isGeorgianFont(direction, role) {
        const cfg = DIRECTIONS[direction];
        if (cfg.interaction === "draw" && role === "prompt") return false;
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

    function updateModeUI() {
        const draw = isDrawMode();
        els.grid.hidden = draw;
        els.drawPanel.hidden = !draw;
        if (draw) {
            setupCanvas();
            clearCanvas();
        } else {
            buildKeyboard();
        }
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

    function setupCanvas() {
        const canvas = els.drawCanvas;
        const wrap = canvas.parentElement;
        const size = Math.min(wrap.clientWidth || 320, 320);
        canvasState.cssSize = size;
        const dpr = window.devicePixelRatio || 1;
        canvas.width = Math.floor(size * dpr);
        canvas.height = Math.floor(size * dpr);
        canvas.style.width = `${size}px`;
        canvas.style.height = `${size}px`;

        const ctx = canvas.getContext("2d");
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        ctx.lineCap = "round";
        ctx.lineJoin = "round";
        ctx.lineWidth = 5;
        ctx.strokeStyle = "#0b1220";
        canvasState.ctx = ctx;
        clearCanvas();
    }

    function clearCanvas() {
        if (!canvasState.ctx) return;
        const { ctx } = canvasState;
        const s = canvasState.cssSize;
        ctx.fillStyle = "#ffffff";
        ctx.fillRect(0, 0, s, s);
        canvasState.hasInk = false;
    }

    function canvasCoords(event) {
        const rect = els.drawCanvas.getBoundingClientRect();
        const clientX = event.clientX ?? event.touches?.[0]?.clientX ?? 0;
        const clientY = event.clientY ?? event.touches?.[0]?.clientY ?? 0;
        return {
            x: clientX - rect.left,
            y: clientY - rect.top,
        };
    }

    function startStroke(event) {
        if (state.locked || !isDrawMode()) return;
        event.preventDefault();
        canvasState.drawing = true;
        const { x, y } = canvasCoords(event);
        const { ctx } = canvasState;
        ctx.beginPath();
        ctx.moveTo(x, y);
    }

    function moveStroke(event) {
        if (!canvasState.drawing || state.locked) return;
        event.preventDefault();
        const { x, y } = canvasCoords(event);
        const { ctx } = canvasState;
        ctx.lineTo(x, y);
        ctx.stroke();
        canvasState.hasInk = true;
    }

    function endStroke() {
        canvasState.drawing = false;
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
            audio_url: pair.audio_url || null,
        };
    }

    function loadNext() {
        if (!state.pairs.length) return;
        const cfg = DIRECTIONS[state.direction];
        state.locked = true;
        setKeysEnabled(false);
        if (isDrawMode()) els.drawCheck.disabled = true;
        clearKeyHighlights();

        state.current = pickNext();
        els.direction.textContent = cfg.instruction;
        els.prompt.textContent = state.current.prompt;
        els.prompt.classList.toggle(
            "is-georgian",
            isGeorgianFont(state.direction, "prompt")
        );
        els.card.classList.toggle(
            "has-audio",
            !isDrawMode() && !!state.current.audio_url
        );

        if (isDrawMode()) {
            clearCanvas();
            els.drawCheck.disabled = false;
        } else {
            setKeysEnabled(true);
        }
        state.locked = false;
    }

    function finishRound(correct, recognized) {
        const answer = state.current.answer;
        state.total += 1;
        els.total.textContent = state.total;

        if (correct) {
            state.correct += 1;
            state.streak += 1;
            els.card.classList.add("is-correct");
            els.feedback.textContent = "Correct";
            els.feedback.classList.add("is-correct");
        } else {
            state.streak = 0;
            els.card.classList.add("is-wrong");
            const drawn = recognized ? `You drew: ${recognized}. ` : "";
            els.feedback.textContent = `${drawn}Answer: ${answer}`;
            els.feedback.classList.add("is-wrong");
        }
        els.correct.textContent = state.correct;
        els.streak.textContent = state.streak;
        state.lastPrompt = state.current.prompt;

        const delay = correct ? 650 : 1800;
        setTimeout(loadNext, delay);
    }

    els.card.addEventListener("click", () => {
        if (!state.current || isDrawMode()) return;
        playAudio(state.current.audio_url);
    });

    function onTap(value) {
        if (state.locked || !state.current) return;
        state.locked = true;
        setKeysEnabled(false);

        const tapped = state.keys[value];
        const answer = state.current.answer;
        const correct = value === answer;

        if (correct) tapped.classList.add("is-correct");
        else tapped.classList.add("is-wrong");

        finishRound(correct, value);
    }

    async function onDrawCheck() {
        if (state.locked || !state.current || !isDrawMode()) return;
        if (!canvasState.hasInk) {
            els.feedback.textContent = "Draw a letter in the box first";
            els.feedback.classList.remove("is-correct", "is-wrong");
            return;
        }

        state.locked = true;
        els.drawCheck.disabled = true;
        els.feedback.textContent = "Checking…";
        els.feedback.classList.remove("is-correct", "is-wrong");

        try {
            const res = await fetch("/api/keyboard/recognize/", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": getCsrfToken(),
                },
                body: JSON.stringify({
                    image: els.drawCanvas.toDataURL("image/png"),
                    expected: state.current.answer,
                }),
            });
            const data = await res.json().catch(() => ({}));
            if (!res.ok) {
                throw new Error(data.message || data.error || `HTTP ${res.status}`);
            }

            if (data.recognized == null) {
                els.feedback.textContent =
                    data.message || "Couldn't read that — try again";
                els.feedback.classList.add("is-wrong");
                state.locked = false;
                els.drawCheck.disabled = false;
                return;
            }

            finishRound(!!data.correct, data.recognized);
        } catch (err) {
            els.feedback.textContent = err.message || "Recognition failed";
            els.feedback.classList.add("is-wrong");
            state.locked = false;
            els.drawCheck.disabled = false;
        }
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
        updateModeUI();
        loadNext();
    }

    els.toggleButtons.forEach((btn) => {
        btn.addEventListener("click", () => setDirection(btn.dataset.direction));
    });

    els.drawClear.addEventListener("click", clearCanvas);
    els.drawCheck.addEventListener("click", onDrawCheck);

    const canvas = els.drawCanvas;
    canvas.addEventListener("pointerdown", startStroke);
    canvas.addEventListener("pointermove", moveStroke);
    canvas.addEventListener("pointerup", endStroke);
    canvas.addEventListener("pointerleave", endStroke);
    canvas.addEventListener("pointercancel", endStroke);

    (async () => {
        try {
            state.pairs = await fetchAlphabet();
            if (!state.pairs.length) {
                els.grid.innerHTML =
                    '<p class="kb-empty">Alphabet is empty.</p>';
                return;
            }
            updateModeUI();
            loadNext();
        } catch (err) {
            els.grid.innerHTML =
                '<p class="kb-empty">Couldn\'t load the alphabet.</p>';
        }
    })();
})();
