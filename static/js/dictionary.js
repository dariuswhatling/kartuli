(() => {
    "use strict";

    const els = {
        container: document.getElementById("chapters"),
        addChapter: document.getElementById("add-chapter"),
        count: document.getElementById("dict-count"),
    };

    const SAVE_DEBOUNCE_MS = 450;
    const FIELDS = ["romanised", "english", "georgian"];

    const state = {
        chapters: [],
    };

    // ---- CSRF + fetch helper ------------------------------------------------

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

    // ---- Debounce helper ----------------------------------------------------

    function debounce(fn, ms) {
        let timer = null;
        const wrapped = (...args) => {
            if (timer) clearTimeout(timer);
            timer = setTimeout(() => {
                timer = null;
                fn(...args);
            }, ms);
        };
        wrapped.flush = () => {
            if (timer) {
                clearTimeout(timer);
                timer = null;
                fn();
            }
        };
        return wrapped;
    }

    // ---- Rendering: a single card row --------------------------------------

    function setStatus(rowEl, status) {
        rowEl.dataset.status = status || "";
    }

    function renderCardRow(chapterId, card) {
        const row = document.createElement("div");
        row.className = "card-row";
        row.dataset.chapterId = String(chapterId);
        if (card.id != null) row.dataset.cardId = String(card.id);

        const inputs = {};
        FIELDS.forEach((field) => {
            const input = document.createElement("input");
            input.type = "text";
            input.spellcheck = false;
            input.autocomplete = "off";
            input.dataset.field = field;
            input.placeholder =
                field === "romanised"
                    ? "romanised"
                    : field === "english"
                    ? "english"
                    : "ქართული";
            input.value = card[field] || "";
            if (field === "georgian") input.classList.add("is-georgian");
            inputs[field] = input;
            row.appendChild(input);
        });

        const del = document.createElement("button");
        del.type = "button";
        del.className = "row-delete";
        del.setAttribute("aria-label", "Delete card");
        del.title = "Delete card";
        del.innerHTML = "&times;";
        row.appendChild(del);

        // --- Auto-save logic for this row ---
        const localState = {
            id: card.id ?? null,
            romanised: card.romanised || "",
            english: card.english || "",
            georgian: card.georgian || "",
            saving: false,
        };

        async function flushSave() {
            const next = {
                romanised: inputs.romanised.value.trim(),
                english: inputs.english.value.trim(),
                georgian: inputs.georgian.value.trim(),
            };
            const allEmpty = !next.romanised && !next.english && !next.georgian;

            if (localState.id == null) {
                if (allEmpty) return;
                if (localState.saving) return;
                localState.saving = true;
                setStatus(row, "saving");
                try {
                    const created = await api("/api/cards/", {
                        method: "POST",
                        body: JSON.stringify({
                            chapter_id: chapterId,
                            ...next,
                        }),
                    });
                    localState.id = created.id;
                    row.dataset.cardId = String(created.id);
                    Object.assign(localState, next);
                    // Update in-memory chapter cards list
                    const chapter = state.chapters.find((c) => c.id === chapterId);
                    if (chapter) chapter.cards.push(created);
                    ensureBlankRow(chapterId);
                    setStatus(row, "saved");
                    setTimeout(() => {
                        if (row.dataset.status === "saved") setStatus(row, "");
                    }, 900);
                } catch (err) {
                    setStatus(row, "error");
                    row.title = err.message || "Save failed";
                } finally {
                    localState.saving = false;
                }
                return;
            }

            // Existing card → PUT update
            const dirty = FIELDS.some((f) => localState[f] !== next[f]);
            if (!dirty) return;
            setStatus(row, "saving");
            try {
                const updated = await api(`/api/cards/${localState.id}/`, {
                    method: "PUT",
                    body: JSON.stringify(next),
                });
                Object.assign(localState, next);
                const chapter = state.chapters.find((c) => c.id === chapterId);
                if (chapter) {
                    const idx = chapter.cards.findIndex((c) => c.id === localState.id);
                    if (idx >= 0) chapter.cards[idx] = updated;
                }
                setStatus(row, "saved");
                setTimeout(() => {
                    if (row.dataset.status === "saved") setStatus(row, "");
                }, 900);
            } catch (err) {
                setStatus(row, "error");
                row.title = err.message || "Save failed";
            }
        }

        const debouncedSave = debounce(flushSave, SAVE_DEBOUNCE_MS);

        FIELDS.forEach((field) => {
            inputs[field].addEventListener("input", () => {
                setStatus(row, "dirty");
                debouncedSave();
            });
            inputs[field].addEventListener("blur", () => debouncedSave.flush());
            inputs[field].addEventListener("keydown", (e) => {
                if (e.key === "Enter") {
                    e.preventDefault();
                    debouncedSave.flush();
                    // Move focus to next field or next row
                    const order = FIELDS.indexOf(field);
                    if (order < FIELDS.length - 1) {
                        inputs[FIELDS[order + 1]].focus();
                    } else {
                        const nextRow = row.nextElementSibling;
                        if (nextRow && nextRow.classList.contains("card-row")) {
                            const firstInput = nextRow.querySelector("input");
                            if (firstInput) firstInput.focus();
                        }
                    }
                }
            });
        });

        del.addEventListener("click", async () => {
            const allEmpty = FIELDS.every((f) => !inputs[f].value.trim());
            if (localState.id == null) {
                if (allEmpty) {
                    row.remove();
                    return;
                }
                if (!confirm("Discard this unsaved row?")) return;
                row.remove();
                return;
            }
            if (!confirm("Delete this card?")) return;
            try {
                await api(`/api/cards/${localState.id}/`, { method: "DELETE" });
                const chapter = state.chapters.find((c) => c.id === chapterId);
                if (chapter) {
                    chapter.cards = chapter.cards.filter((c) => c.id !== localState.id);
                }
                row.remove();
            } catch (err) {
                alert(err.message || "Couldn't delete card.");
            }
        });

        return row;
    }

    // ---- Rendering: a chapter section --------------------------------------

    function renderChapter(chapter) {
        const section = document.createElement("section");
        section.className = "chapter";
        section.dataset.chapterId = String(chapter.id);

        // Header
        const header = document.createElement("header");
        header.className = "chapter-header";

        const nameInput = document.createElement("input");
        nameInput.type = "text";
        nameInput.value = chapter.name;
        nameInput.className = "chapter-name";
        nameInput.placeholder = "Chapter name";
        nameInput.autocomplete = "off";
        nameInput.spellcheck = false;

        const meta = document.createElement("span");
        meta.className = "chapter-meta";
        meta.textContent = pluralise(chapter.cards.length, "card");

        const del = document.createElement("button");
        del.type = "button";
        del.className = "btn btn-danger btn-icon chapter-delete";
        del.textContent = "Delete";

        header.append(nameInput, meta, del);

        // Body
        const list = document.createElement("div");
        list.className = "card-list";
        chapter.cards.forEach((card) => {
            list.appendChild(renderCardRow(chapter.id, card));
        });
        // Always end with a blank row for quick entry.
        list.appendChild(renderCardRow(chapter.id, {}));

        section.append(header, list);

        // Wire chapter name autosave
        const saveName = debounce(async () => {
            const newName = nameInput.value.trim();
            if (newName === chapter.name) return;
            try {
                const updated = await api(`/api/chapters/${chapter.id}/`, {
                    method: "PUT",
                    body: JSON.stringify({ name: newName }),
                });
                chapter.name = updated.name;
                nameInput.value = updated.name;
            } catch (err) {
                nameInput.value = chapter.name;
                alert(err.message || "Couldn't rename chapter.");
            }
        }, SAVE_DEBOUNCE_MS);
        nameInput.addEventListener("input", saveName);
        nameInput.addEventListener("blur", saveName.flush);

        del.addEventListener("click", async () => {
            if (
                !confirm(
                    `Delete chapter "${chapter.name}" and all ${chapter.cards.length} card(s)?`
                )
            ) {
                return;
            }
            try {
                await api(`/api/chapters/${chapter.id}/`, { method: "DELETE" });
                state.chapters = state.chapters.filter((c) => c.id !== chapter.id);
                section.remove();
                updateCount();
            } catch (err) {
                alert(err.message || "Couldn't delete chapter.");
            }
        });

        return section;
    }

    function ensureBlankRow(chapterId) {
        const section = els.container.querySelector(
            `.chapter[data-chapter-id="${chapterId}"]`
        );
        if (!section) return;
        const list = section.querySelector(".card-list");
        const last = list.lastElementChild;
        const lastIsBlank =
            last &&
            last.classList.contains("card-row") &&
            !last.dataset.cardId;
        if (!lastIsBlank) {
            list.appendChild(renderCardRow(chapterId, {}));
        }
        // Update card count in header (existing saved cards only)
        const meta = section.querySelector(".chapter-meta");
        const chapter = state.chapters.find((c) => c.id === chapterId);
        if (meta && chapter) meta.textContent = pluralise(chapter.cards.length, "card");
    }

    function pluralise(n, word) {
        return `${n} ${word}${n === 1 ? "" : "s"}`;
    }

    function updateCount() {
        els.count.textContent = pluralise(state.chapters.length, "chapter");
    }

    // ---- Page render --------------------------------------------------------

    function renderAll() {
        els.container.innerHTML = "";
        if (state.chapters.length === 0) {
            const empty = document.createElement("p");
            empty.className = "dict-empty";
            empty.textContent =
                "No chapters yet. Add one above to start building your dictionary.";
            els.container.appendChild(empty);
        } else {
            state.chapters.forEach((chapter) => {
                els.container.appendChild(renderChapter(chapter));
            });
        }
        updateCount();
    }

    // ---- Top-level actions --------------------------------------------------

    els.addChapter.addEventListener("click", async () => {
        try {
            const created = await api("/api/chapters/", {
                method: "POST",
                body: JSON.stringify({ name: "Untitled chapter" }),
            });
            created.cards = [];
            state.chapters.push(created);
            // If list was empty, wipe placeholder
            if (els.container.querySelector(".dict-empty")) {
                els.container.innerHTML = "";
            }
            els.container.appendChild(renderChapter(created));
            updateCount();
            // Focus the new chapter's name input so the user can rename immediately
            const section = els.container.querySelector(
                `.chapter[data-chapter-id="${created.id}"]`
            );
            const nameInput = section && section.querySelector(".chapter-name");
            if (nameInput) {
                nameInput.focus();
                nameInput.select();
            }
        } catch (err) {
            alert(err.message || "Couldn't create chapter.");
        }
    });

    async function load() {
        try {
            const data = await api("/api/chapters/");
            state.chapters = data.chapters || [];
            renderAll();
        } catch (err) {
            els.container.innerHTML = `<p class="dict-empty">Couldn't load chapters.</p>`;
        }
    }

    load();
})();
