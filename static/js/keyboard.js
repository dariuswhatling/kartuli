(() => {
    "use strict";

    const els = {
        kb: document.getElementById("kb"),
        card: document.getElementById("card"),
        direction: document.getElementById("card-direction"),
        prompt: document.getElementById("card-prompt"),
        grid: document.getElementById("kb-grid"),
        drawPanel: document.getElementById("kb-draw"),
        drawCanvas: document.getElementById("draw-canvas"),
        drawToolbar: document.getElementById("draw-toolbar"),
        drawClear: document.getElementById("draw-clear"),
        drawCheck: document.getElementById("draw-check"),
        drawReveal: document.getElementById("draw-reveal"),
        drawRevealLetter: document.getElementById("draw-reveal-letter"),
        drawGrade: document.getElementById("draw-grade"),
        drawWrong: document.getElementById("draw-wrong"),
        drawRight: document.getElementById("draw-right"),
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
            instruction: "Draw the letter for this sound",
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
        drawRevealed: false,
    };

    const canvasState = {
        ctx: null,
        cssSize: 220,
        hasInk: false,
        drawing: false,
    };

    function playAudio(url) {
        window.KartuliAudio?.play(url);
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
        if (cfg.interaction === "draw") return role === "reveal";
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

    function hideDrawReveal() {
        state.drawRevealed = false;
        els.drawReveal.hidden = true;
        els.drawRevealLetter.textContent = "";
        els.drawRevealLetter.setAttribute("aria-hidden", "true");
        els.drawGrade.hidden = true;
        els.drawToolbar.hidden = false;
        els.drawCheck.disabled = false;
        els.drawClear.disabled = false;
        els.drawWrong.disabled = true;
        els.drawRight.disabled = true;
    }

    function showDrawReveal(letter) {
        state.drawRevealed = true;
        els.drawRevealLetter.textContent = letter;
        els.drawRevealLetter.removeAttribute("aria-hidden");
        els.drawReveal.hidden = false;
        els.drawGrade.hidden = false;
        els.drawToolbar.hidden = true;
        els.drawCheck.disabled = true;
        els.drawClear.disabled = true;
        els.drawWrong.disabled = false;
        els.drawRight.disabled = false;
    }

    function updateModeUI() {
        const draw = isDrawMode();
        els.kb?.classList.toggle("kb-is-draw", draw);
        els.feedback?.classList.toggle("kb-panel-hidden", draw);

        if (draw) {
            els.grid.classList.add("kb-panel-hidden");
            els.grid.hidden = true;
            els.grid.setAttribute("aria-hidden", "true");
            els.grid.innerHTML = "";
            state.keys = {};
            els.drawPanel.classList.remove("kb-panel-hidden");
            els.drawPanel.hidden = false;
            els.drawPanel.removeAttribute("aria-hidden");
            setupCanvas();
            hideDrawReveal();
            clearCanvas();
        } else {
            els.drawPanel.classList.add("kb-panel-hidden");
            els.drawPanel.hidden = true;
            els.drawPanel.setAttribute("aria-hidden", "true");
            hideDrawReveal();
            els.grid.classList.remove("kb-panel-hidden");
            els.grid.hidden = false;
            els.grid.removeAttribute("aria-hidden");
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
        const maxSide = Math.min(
            wrap?.clientWidth || 280,
            window.innerWidth - 40,
            240
        );
        const size = Math.max(160, maxSide);
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
        ctx.lineWidth = Math.max(8, Math.round(size / 20));
        ctx.strokeStyle = "#000000";
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
        const scaleX = canvasState.cssSize / (rect.width || canvasState.cssSize);
        const scaleY = canvasState.cssSize / (rect.height || canvasState.cssSize);
        return {
            x: (clientX - rect.left) * scaleX,
            y: (clientY - rect.top) * scaleY,
        };
    }

    function startStroke(event) {
        if (state.locked || !isDrawMode() || state.drawRevealed) return;
        event.preventDefault();
        els.drawCanvas.setPointerCapture?.(event.pointerId);
        canvasState.drawing = true;
        const { x, y } = canvasCoords(event);
        const { ctx } = canvasState;
        ctx.beginPath();
        ctx.moveTo(x, y);
    }

    function moveStroke(event) {
        if (!canvasState.drawing || state.locked || state.drawRevealed) return;
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
        clearKeyHighlights();
        hideDrawReveal();

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

    function finishRound(correct) {
        state.total += 1;
        els.total.textContent = state.total;

        if (correct) {
            state.correct += 1;
            state.streak += 1;
            els.card.classList.add("is-correct");
        } else {
            state.streak = 0;
            els.card.classList.add("is-wrong");
        }
        els.correct.textContent = state.correct;
        els.streak.textContent = state.streak;
        state.lastPrompt = state.current.prompt;

        state.locked = true;
        els.drawWrong.disabled = true;
        els.drawRight.disabled = true;

        const delay = correct ? 500 : 900;
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
        const correct = value === state.current.answer;

        if (correct) tapped.classList.add("is-correct");
        else tapped.classList.add("is-wrong");

        finishRound(correct);
    }

    function onDrawCheck() {
        if (state.locked || !state.current || !isDrawMode() || state.drawRevealed) {
            return;
        }
        if (!canvasState.hasInk) {
            els.card.classList.add("is-wrong");
            setTimeout(() => els.card.classList.remove("is-wrong"), 400);
            return;
        }

        showDrawReveal(state.current.answer);
    }

    function onDrawGrade(correct) {
        if (!state.drawRevealed || state.locked || !state.current) return;
        els.card.classList.remove("is-correct", "is-wrong");
        if (correct) els.card.classList.add("is-correct");
        else els.card.classList.add("is-wrong");
        finishRound(correct);
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

    els.drawClear.addEventListener("click", () => {
        if (!state.drawRevealed) clearCanvas();
    });
    els.drawCheck.addEventListener("click", onDrawCheck);
    els.drawWrong.addEventListener("click", () => onDrawGrade(false));
    els.drawRight.addEventListener("click", () => onDrawGrade(true));

    const canvas = els.drawCanvas;
    canvas.style.touchAction = "none";
    canvas.addEventListener("pointerdown", startStroke);
    canvas.addEventListener("pointermove", moveStroke);
    canvas.addEventListener("pointerup", endStroke);
    canvas.addEventListener("pointerleave", endStroke);
    canvas.addEventListener("pointercancel", endStroke);

    window.addEventListener("resize", () => {
        if (isDrawMode() && !state.drawRevealed) setupCanvas();
    });

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
