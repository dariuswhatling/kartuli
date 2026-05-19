/**
 * Shared audio playback with gain boost for quiet TTS recordings.
 * Used by quiz, keyboard, and dictionary pages.
 */
(() => {
    "use strict";

    /** Playback gain (1 = normal; ~2.5 makes quiet Cartesia MP3s easier to hear). */
    const GAIN = 2.5;

    let audioContext = null;
    let currentSource = null;
    let currentElement = null;

    function getAudioContext() {
        if (!audioContext) {
            const Ctx = window.AudioContext || window.webkitAudioContext;
            if (!Ctx) return null;
            audioContext = new Ctx();
        }
        return audioContext;
    }

    function stop() {
        if (currentSource) {
            try {
                currentSource.stop();
            } catch {}
            currentSource = null;
        }
        if (currentElement) {
            try {
                currentElement.pause();
            } catch {}
            currentElement = null;
        }
    }

    async function play(url) {
        if (!url) return;
        stop();

        const ctx = getAudioContext();
        if (!ctx) {
            playFallback(url);
            return;
        }

        try {
            if (ctx.state === "suspended") {
                await ctx.resume();
            }
            const response = await fetch(url);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const buffer = await ctx.decodeAudioData(await response.arrayBuffer());

            const source = ctx.createBufferSource();
            const gain = ctx.createGain();
            gain.gain.value = GAIN;
            source.buffer = buffer;
            source.connect(gain);
            gain.connect(ctx.destination);
            source.onended = () => {
                if (currentSource === source) currentSource = null;
            };
            source.start(0);
            currentSource = source;
        } catch {
            playFallback(url);
        }
    }

    function playFallback(url) {
        const el = new Audio(url);
        el.volume = 1;
        currentElement = el;
        el.play().catch(() => {});
    }

    window.KartuliAudio = { play, stop, gain: GAIN };
})();
