(() => {
    "use strict";

    const els = {
        addForm: document.getElementById("dict-add"),
        addGeorgian: document.getElementById("add-georgian"),
        addEnglish: document.getElementById("add-english"),
        addNotes: document.getElementById("add-notes"),
        list: document.getElementById("dict-list"),
        search: document.getElementById("dict-search"),
        count: document.getElementById("dict-count"),
    };

    const state = {
        cards: [],
        filter: "",
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

    function fmtAccuracy(stats) {
        if (!stats || stats.accuracy == null) return "untouched";
        const pct = Math.round(stats.accuracy * 100);
        return `${stats.correct}/${stats.total} · ${pct}%`;
    }

    function renderRow(card) {
        const row = document.createElement("div");
        row.className = "dict-row";
        row.dataset.id = card.id;

        const geoField = document.createElement("div");
        geoField.className = "field-georgian";
        const geoInput = document.createElement("input");
        geoInput.type = "text";
        geoInput.value = card.georgian;
        geoInput.spellcheck = false;
        geoInput.dataset.field = "georgian";
        geoField.appendChild(geoInput);

        const engField = document.createElement("div");
        engField.className = "field-english";
        const engInput = document.createElement("input");
        engInput.type = "text";
        engInput.value = card.english;
        engInput.spellcheck = false;
        engInput.dataset.field = "english";
        engField.appendChild(engInput);

        const actions = document.createElement("div");
        actions.className = "dict-actions";
        const saveBtn = document.createElement("button");
        saveBtn.type = "button";
        saveBtn.className = "btn btn-primary btn-icon";
        saveBtn.textContent = "Save";
        saveBtn.dataset.action = "save";
        saveBtn.disabled = true;
        const delBtn = document.createElement("button");
        delBtn.type = "button";
        delBtn.className = "btn btn-danger btn-icon";
        delBtn.textContent = "Delete";
        delBtn.dataset.action = "delete";
        actions.append(saveBtn, delBtn);

        const meta = document.createElement("div");
        meta.className = "meta";
        const notesInput = document.createElement("input");
        notesInput.type = "text";
        notesInput.placeholder = "notes";
        notesInput.value = card.notes || "";
        notesInput.dataset.field = "notes";
        const stats = document.createElement("span");
        stats.className = "dict-stats";
        stats.textContent = fmtAccuracy(card.stats);
        if (card.stats && card.stats.recent_wrong > 0) {
            stats.style.color = "var(--warn)";
            stats.title = `${card.stats.recent_wrong} of the last ${5} attempts were wrong`;
        }
        meta.append(notesInput, stats);

        row.append(geoField, engField, actions, meta);

        const markDirty = () => {
            row.classList.add("is-dirty");
            row.classList.remove("is-saved");
            saveBtn.disabled = false;
        };
        [geoInput, engInput, notesInput].forEach((input) => {
            input.addEventListener("input", markDirty);
            input.addEventListener("keydown", (e) => {
                if (e.key === "Enter" && !saveBtn.disabled) {
                    e.preventDefault();
                    saveBtn.click();
                }
            });
        });

        saveBtn.addEventListener("click", () => saveRow(row, card));
        delBtn.addEventListener("click", () => deleteRow(row, card));

        return row;
    }

    async function saveRow(row, card) {
        const georgian = row.querySelector('[data-field="georgian"]').value.trim();
        const english = row.querySelector('[data-field="english"]').value.trim();
        const notes = row.querySelector('[data-field="notes"]').value.trim();
        if (!georgian || !english) {
            row.classList.remove("is-saved");
            return;
        }
        try {
            const updated = await api(`/api/cards/${card.id}/`, {
                method: "PUT",
                body: JSON.stringify({ georgian, english, notes }),
            });
            Object.assign(card, updated);
            row.classList.remove("is-dirty");
            row.classList.add("is-saved");
            row.querySelector('[data-action="save"]').disabled = true;
            setTimeout(() => row.classList.remove("is-saved"), 1200);
        } catch (err) {
            alert(err.message || "Could not save card.");
        }
    }

    async function deleteRow(row, card) {
        if (!confirm(`Delete "${card.georgian} – ${card.english}"?`)) return;
        try {
            await api(`/api/cards/${card.id}/`, { method: "DELETE" });
            state.cards = state.cards.filter((c) => c.id !== card.id);
            render();
        } catch (err) {
            alert(err.message || "Could not delete card.");
        }
    }

    function render() {
        const q = state.filter.trim().toLowerCase();
        const filtered = state.cards.filter((c) => {
            if (!q) return true;
            return (
                c.georgian.toLowerCase().includes(q) ||
                c.english.toLowerCase().includes(q) ||
                (c.notes || "").toLowerCase().includes(q)
            );
        });
        els.count.textContent = `${filtered.length} of ${state.cards.length} cards`;
        els.list.innerHTML = "";
        if (filtered.length === 0) {
            const empty = document.createElement("p");
            empty.className = "dict-empty";
            empty.textContent = state.cards.length
                ? "No matches."
                : "No cards yet — add one above.";
            els.list.appendChild(empty);
            return;
        }
        filtered.forEach((card) => els.list.appendChild(renderRow(card)));
    }

    async function load() {
        try {
            const data = await api("/api/cards/");
            state.cards = data.cards || [];
            render();
        } catch (err) {
            els.list.innerHTML = `<p class="dict-empty">Couldn't load cards.</p>`;
        }
    }

    els.addForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const georgian = els.addGeorgian.value.trim();
        const english = els.addEnglish.value.trim();
        const notes = els.addNotes.value.trim();
        if (!georgian || !english) return;
        try {
            const card = await api("/api/cards/", {
                method: "POST",
                body: JSON.stringify({ georgian, english, notes }),
            });
            state.cards.push(card);
            els.addForm.reset();
            els.addGeorgian.focus();
            render();
        } catch (err) {
            alert(err.message || "Could not add card.");
        }
    });

    els.search.addEventListener("input", (e) => {
        state.filter = e.target.value;
        render();
    });

    load();
})();
