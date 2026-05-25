(() => {
    "use strict";

    const els = {
        chapters: document.getElementById("cw-chapters"),
        search: document.getElementById("cw-search"),
        count: document.getElementById("cw-count"),
        banner: document.getElementById("cw-banner"),
    };

    const SPEAKER_SVG =
        '<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path fill="currentColor" d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z"/></svg>';

    const state = {
        chapters: [],
        query: "",
    };

    function playAudio(url) {
        window.KartuliAudio?.play(url);
    }

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

    function showBanner(message) {
        els.banner.innerHTML = "";
        const banner = document.createElement("div");
        banner.className = "banner is-info";
        banner.setAttribute("role", "status");
        const body = document.createElement("div");
        body.className = "banner-body";
        const p = document.createElement("p");
        p.textContent = message;
        body.appendChild(p);
        banner.appendChild(body);
        els.banner.appendChild(banner);
    }

    function matchesQuery(card, query) {
        if (!query) return true;
        const hay = `${card.georgian} ${card.romanised} ${card.english}`.toLowerCase();
        return hay.includes(query);
    }

    function renderCardRow(card) {
        const row = document.createElement("div");
        row.className = "cw-row";
        row.dataset.cardId = String(card.id);

        const play = document.createElement("button");
        play.type = "button";
        play.className = "row-audio";
        play.setAttribute("aria-label", "Hear pronunciation");
        play.innerHTML = SPEAKER_SVG;

        const geo = document.createElement("span");
        geo.className = "cw-cell cw-georgian";
        geo.textContent = card.georgian;

        const rom = document.createElement("span");
        rom.className = "cw-cell cw-romanised";
        rom.textContent = card.romanised || "—";

        const eng = document.createElement("span");
        eng.className = "cw-cell cw-english";
        eng.textContent = card.english;

        function syncPlay() {
            if (card.audio_georgian_url) {
                play.disabled = false;
                play.classList.add("is-ready");
                play.classList.remove("is-pending");
                play.dataset.audioUrl = card.audio_georgian_url;
                play.title = "Hear pronunciation";
            } else {
                play.disabled = true;
                play.classList.add("is-pending");
                play.classList.remove("is-ready");
                delete play.dataset.audioUrl;
                play.title = "Audio generating…";
            }
        }

        play.addEventListener("click", (e) => {
            e.stopPropagation();
            const url = play.dataset.audioUrl;
            if (url) playAudio(url);
        });

        syncPlay();
        row.append(play, geo, rom, eng);
        return row;
    }

    function render() {
        const query = state.query;
        els.chapters.innerHTML = "";

        let visibleTotal = 0;
        let anyChapter = false;

        state.chapters.forEach((chapter) => {
            const visible = chapter.cards.filter((c) => matchesQuery(c, query));
            if (!visible.length) return;
            anyChapter = true;
            visibleTotal += visible.length;

            const section = document.createElement("section");
            section.className = "chapter";
            section.dataset.chapterId = String(chapter.id);

            const header = document.createElement("button");
            header.type = "button";
            header.className = "cw-chapter-toggle";
            header.setAttribute("aria-expanded", "true");

            const title = document.createElement("span");
            title.className = "cw-chapter-name";
            title.textContent = chapter.name;

            const meta = document.createElement("span");
            meta.className = "chapter-meta";
            meta.textContent = `${visible.length}`;

            header.append(title, meta);
            header.addEventListener("click", () => {
                const open = section.classList.toggle("is-collapsed");
                header.setAttribute("aria-expanded", open ? "false" : "true");
            });

            const list = document.createElement("div");
            list.className = "card-list";
            visible.forEach((card) => list.appendChild(renderCardRow(card)));

            section.append(header, list);
            els.chapters.appendChild(section);
        });

        if (!anyChapter) {
            const empty = document.createElement("p");
            empty.className = "dict-empty";
            empty.textContent = query
                ? "No words match your search."
                : "No words loaded.";
            els.chapters.appendChild(empty);
        }

        const total = state.chapters.reduce((n, ch) => n + ch.cards.length, 0);
        if (query) {
            els.count.textContent = `${visibleTotal} of ${total} words`;
        } else {
            els.count.textContent = `${total} words · ${state.chapters.length} chapters`;
        }
    }

    async function refreshAudio() {
        const needsAudio = state.chapters.some((ch) =>
            ch.cards.some((c) => c.georgian && !c.audio_georgian_url)
        );
        if (!needsAudio) return;

        try {
            const data = await api("/api/common-words/");
            state.chapters = data.chapters;
            render();
        } catch {
            /* ignore poll errors */
        }
    }

    async function load() {
        try {
            const data = await api("/api/common-words/");
            state.chapters = data.chapters;
            render();

            const pending = state.chapters.some((ch) =>
                ch.cards.some((c) => c.georgian && !c.audio_georgian_url)
            );
            if (pending) {
                let attempts = 0;
                const timer = setInterval(async () => {
                    attempts += 1;
                    if (attempts > 40) {
                        clearInterval(timer);
                        return;
                    }
                    await refreshAudio();
                    const still = state.chapters.some((ch) =>
                        ch.cards.some((c) => c.georgian && !c.audio_georgian_url)
                    );
                    if (!still) clearInterval(timer);
                }, 2000);
            }
        } catch (err) {
            els.chapters.innerHTML = "";
            const empty = document.createElement("p");
            empty.className = "dict-empty";
            empty.textContent = err.message || "Could not load vocabulary.";
            els.chapters.appendChild(empty);
            els.count.textContent = "";
            if (err.status === 404) {
                showBanner(
                    "Run python manage.py import_1000_words on the server to load this list."
                );
            }
        }
    }

    els.search.addEventListener("input", () => {
        state.query = els.search.value.trim().toLowerCase();
        render();
    });

    load();
})();
