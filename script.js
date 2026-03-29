const audio = document.getElementById("audio");

const currentTrackEl = document.getElementById("currentTrack");
const statusEl = document.getElementById("status");
const queueInfoEl = document.getElementById("queueInfo");
const remainingTimeEl = document.getElementById("remainingTime");
const nextTrackEl = document.getElementById("nextTrack");

const startBtn = document.getElementById("startBtn");
const toggleBtn = document.getElementById("toggleBtn");

const LIBRARY = window.RADIO_LIBRARY || {
  songs: [],
  jingles: [],
  stationSeed: "station"
};

const SONGS = Array.isArray(LIBRARY.songs) ? LIBRARY.songs : [];
const JINGLES = Array.isArray(LIBRARY.jingles) ? LIBRARY.jingles : [];
const STATION_SEED = LIBRARY.stationSeed || "station";

const DAY_SECONDS = 86400;
const RESYNC_INTERVAL_MS = 15000;
const DRIFT_TOLERANCE_SECONDS = 1.5;
const UI_TICK_MS = 1000;

// 2x mit Jingle, 1x ohne
const JINGLE_PATTERN = [true, true, false];

let radioStarted = false;
let resyncInterval = null;
let uiInterval = null;

let currentDayKey = null;
let currentSchedule = [];
let currentScheduleTotal = 0;
let currentLiveIndex = -1;

function setStatus(text) {
  if (statusEl) statusEl.textContent = text;
}

function setQueueInfo(text) {
  if (queueInfoEl) queueInfoEl.textContent = text;
}

function setCurrentTrack(text) {
  if (currentTrackEl) currentTrackEl.textContent = text;
}

function setRemainingTime(text) {
  if (remainingTimeEl) remainingTimeEl.textContent = text;
}

function setNextTrack(text) {
  if (nextTrackEl) nextTrackEl.textContent = text;
}

function updateToggleButton() {
  if (!toggleBtn || !audio) return;
  toggleBtn.textContent = audio.paused ? "WEITER" : "PAUSE";
}

function sanitizeTitle(title) {
  if (!title) return "unknown_signal";
  return title.replace(/_/g, " ").replace(/\.mp3$/i, "").trim();
}

function hashString(str) {
  let h = 2166136261 >>> 0;
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

function mulberry32(seed) {
  let t = seed >>> 0;
  return function () {
    t += 0x6D2B79F5;
    let r = Math.imul(t ^ (t >>> 15), 1 | t);
    r ^= r + Math.imul(r ^ (r >>> 7), 61 | r);
    return ((r ^ (r >>> 14)) >>> 0) / 4294967296;
  };
}

function shuffleDeterministic(array, seedString) {
  const arr = [...array];
  const rng = mulberry32(hashString(seedString));

  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(rng() * (i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }

  return arr;
}

function getUtcDayKey(date = new Date()) {
  const y = date.getUTCFullYear();
  const m = String(date.getUTCMonth() + 1).padStart(2, "0");
  const d = String(date.getUTCDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function getUtcSecondsOfDay(date = new Date()) {
  return (
    date.getUTCHours() * 3600 +
    date.getUTCMinutes() * 60 +
    date.getUTCSeconds() +
    date.getUTCMilliseconds() / 1000
  );
}

function formatTime(seconds) {
  const safe = Math.max(0, Math.ceil(seconds));
  const mins = Math.floor(safe / 60);
  const secs = safe % 60;
  return `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
}

function pickJingle(seedBase) {
  if (!JINGLES.length) return null;
  const rng = mulberry32(hashString(seedBase));
  const index = Math.floor(rng() * JINGLES.length);
  return JINGLES[index];
}

function shouldInsertJingleAfterSong(globalSongCount) {
  if (!JINGLES.length) return false;
  const slot = globalSongCount % JINGLE_PATTERN.length;
  return JINGLE_PATTERN[slot];
}

function buildDaySchedule(dayKey) {
  if (!SONGS.length) {
    return { schedule: [], totalDuration: 0 };
  }

  const schedule = [];
  let elapsed = 0;
  let deckIndex = 0;
  let previousSongFile = null;
  let globalSongCount = 0;

  while (elapsed < DAY_SECONDS) {
    let deck = shuffleDeterministic(
      SONGS,
      `${STATION_SEED}|${dayKey}|deck|${deckIndex}`
    );

    if (deck.length > 1 && previousSongFile && deck[0].file === previousSongFile) {
      deck.push(deck.shift());
    }

    for (let i = 0; i < deck.length; i++) {
      const song = deck[i];
      const songDuration = Number(song.duration || 0);

      if (songDuration <= 0) continue;

      schedule.push({
        type: "song",
        title: song.title,
        file: song.file,
        duration: songDuration,
        start: elapsed,
        end: elapsed + songDuration
      });

      elapsed += songDuration;
      previousSongFile = song.file;

      if (elapsed >= DAY_SECONDS) break;

      const insertJingle = shouldInsertJingleAfterSong(globalSongCount);

      if (insertJingle) {
        const jingle = pickJingle(
          `${STATION_SEED}|${dayKey}|jingle|${deckIndex}|${globalSongCount}`
        );

        if (jingle) {
          const jingleDuration = Number(jingle.duration || 0);

          if (jingleDuration > 0) {
            schedule.push({
              type: "jingle",
              title: jingle.title,
              file: jingle.file,
              duration: jingleDuration,
              start: elapsed,
              end: elapsed + jingleDuration
            });

            elapsed += jingleDuration;

            if (elapsed >= DAY_SECONDS) break;
          }
        }
      }

      globalSongCount += 1;
    }

    deckIndex += 1;
  }

  return {
    schedule,
    totalDuration: elapsed
  };
}

function ensureScheduleForToday() {
  const dayKey = getUtcDayKey();

  if (dayKey !== currentDayKey) {
    const built = buildDaySchedule(dayKey);
    currentDayKey = dayKey;
    currentSchedule = built.schedule;
    currentScheduleTotal = built.totalDuration;
  }
}

function findScheduleItemAt(secondOfDay) {
  ensureScheduleForToday();

  if (!currentSchedule.length) return null;

  for (let i = 0; i < currentSchedule.length; i++) {
    const item = currentSchedule[i];

    if (secondOfDay >= item.start && secondOfDay < item.end) {
      return {
        item,
        offset: secondOfDay - item.start,
        index: i
      };
    }
  }

  const lastIndex = currentSchedule.length - 1;
  const last = currentSchedule[lastIndex];

  return {
    item: last,
    offset: Math.max(0, Math.min(last.duration - 0.05, secondOfDay - last.start)),
    index: lastIndex
  };
}

function getLiveState(date = new Date()) {
  const secondOfDay = getUtcSecondsOfDay(date);
  return findScheduleItemAt(secondOfDay);
}

function getNextScheduleItem(index) {
  ensureScheduleForToday();

  if (!currentSchedule.length) return null;
  if (index < 0) return null;

  const nextIndex = index + 1;

  if (nextIndex < currentSchedule.length) {
    return currentSchedule[nextIndex];
  }

  const now = new Date();
  const tomorrow = new Date(now.getTime() + 24 * 60 * 60 * 1000);
  const tomorrowKey = getUtcDayKey(tomorrow);
  const tomorrowSchedule = buildDaySchedule(tomorrowKey).schedule;

  return tomorrowSchedule.length ? tomorrowSchedule[0] : null;
}

function getNextSongAfter(index) {
  ensureScheduleForToday();

  if (!currentSchedule.length || index < 0) return null;

  for (let i = index + 1; i < currentSchedule.length; i++) {
    if (currentSchedule[i].type === "song") {
      return currentSchedule[i];
    }
  }

  const now = new Date();
  const tomorrow = new Date(now.getTime() + 24 * 60 * 60 * 1000);
  const tomorrowKey = getUtcDayKey(tomorrow);
  const tomorrowSchedule = buildDaySchedule(tomorrowKey).schedule;

  for (const item of tomorrowSchedule) {
    if (item.type === "song") {
      return item;
    }
  }

  return null;
}

function describeType(type) {
  return type === "jingle" ? "station_noise..." : "signal locked.";
}

function describeQueue(item) {
  if (!item) return "local small server / endless archive / unstable taste";

  if (item.type === "jingle") {
    return "local small server / station id / archive in motion";
  }

  return "local small server / endless archive / unstable taste";
}

function describeNextSong(item) {
  if (!item) return "next: unknown";
  return `next: ${sanitizeTitle(item.title)}`;
}

function waitForMetadata(media) {
  return new Promise((resolve, reject) => {
    if (!media) {
      reject(new Error("Kein Audio-Element gefunden."));
      return;
    }

    if (media.readyState >= 1) {
      resolve();
      return;
    }

    const onLoaded = () => {
      cleanup();
      resolve();
    };

    const onError = () => {
      cleanup();
      reject(new Error("Audio-Metadaten konnten nicht geladen werden."));
    };

    const cleanup = () => {
      media.removeEventListener("loadedmetadata", onLoaded);
      media.removeEventListener("error", onError);
    };

    media.addEventListener("loadedmetadata", onLoaded);
    media.addEventListener("error", onError);
  });
}

async function loadAndSeek(item, offsetSeconds, autoplay = true) {
  if (!audio || !item) return;

  const sameSource = audio.getAttribute("data-current-file") === item.file;
  const safeOffset = Math.max(0, Math.min(item.duration - 0.05, offsetSeconds));

  if (!sameSource) {
    audio.src = item.file;
    audio.setAttribute("data-current-file", item.file);
    audio.load();
    await waitForMetadata(audio);
  }

  const currentDrift = Math.abs((audio.currentTime || 0) - safeOffset);

  if (!sameSource || currentDrift > DRIFT_TOLERANCE_SECONDS) {
    try {
      audio.currentTime = safeOffset;
    } catch (err) {
      console.warn("Seek fehlgeschlagen:", err);
    }
  }

  setCurrentTrack(sanitizeTitle(item.title));
  setStatus(describeType(item.type));
  setQueueInfo(describeQueue(item));

  const nextSong = getNextSongAfter(currentLiveIndex);
  setNextTrack(describeNextSong(nextSong));

  updateToggleButton();

  if (autoplay) {
    await audio.play();
    updateToggleButton();
  }
}

function updateInfoPanelFromLiveState(live) {
  if (!live || !live.item) {
    setRemainingTime("remaining: --:--");
    setNextTrack("next: unknown");
    return;
  }

  currentLiveIndex = live.index;

  const remaining = Math.max(0, live.item.duration - live.offset);
  setRemainingTime(`remaining: ${formatTime(remaining)}`);

  const nextSong = getNextSongAfter(live.index);
  setNextTrack(describeNextSong(nextSong));
}

async function syncToLive({ autoplay = true } = {}) {
  if (!audio) return;

  const live = getLiveState();

  if (!live || !live.item) {
    setCurrentTrack("no_tracks_found");
    setStatus("keine tracks geladen.");
    setQueueInfo("prüf generate-tracks.js und tracks.js");
    setRemainingTime("remaining: --:--");
    setNextTrack("next: unknown");
    return;
  }

  currentLiveIndex = live.index;

  try {
    await loadAndSeek(live.item, live.offset, autoplay);
    updateInfoPanelFromLiveState(live);
  } catch (err) {
    console.error(err);
    setStatus("audio konnte nicht geladen werden.");
    setQueueInfo("wahrscheinlich dateiname oder pfad verkackt.");
  }
}

async function startRadio() {
  if (!SONGS.length) {
    setCurrentTrack("no_tracks_found");
    setStatus("keine songs gefunden.");
    setQueueInfo("du hast vermutlich noch kein brauchbares tracks.js");
    setRemainingTime("remaining: --:--");
    setNextTrack("next: unknown");
    return;
  }

  radioStarted = true;
  await syncToLive({ autoplay: true });
  startResyncLoop();
  startUiLoop();
}

function startResyncLoop() {
  stopResyncLoop();

  resyncInterval = setInterval(async () => {
    if (!radioStarted || !audio || audio.paused) return;

    const live = getLiveState();
    if (!live || !live.item) return;

    const currentFile = audio.getAttribute("data-current-file");
    const drift = Math.abs((audio.currentTime || 0) - live.offset);

    if (currentFile !== live.item.file || drift > DRIFT_TOLERANCE_SECONDS) {
      await syncToLive({ autoplay: true });
    } else {
      updateInfoPanelFromLiveState(live);
    }
  }, RESYNC_INTERVAL_MS);
}

function stopResyncLoop() {
  if (resyncInterval) {
    clearInterval(resyncInterval);
    resyncInterval = null;
  }
}

function startUiLoop() {
  stopUiLoop();

  uiInterval = setInterval(() => {
    if (!radioStarted) return;

    const live = getLiveState();
    if (!live || !live.item) return;

    updateInfoPanelFromLiveState(live);
  }, UI_TICK_MS);
}

function stopUiLoop() {
  if (uiInterval) {
    clearInterval(uiInterval);
    uiInterval = null;
  }
}

function togglePlayback() {
  if (!audio) return;

  if (!radioStarted) {
    startRadio();
    return;
  }

  if (audio.paused) {
    syncToLive({ autoplay: true });
  } else {
    audio.pause();
    setStatus("paused.");
    updateToggleButton();
  }
}

if (startBtn) {
  startBtn.addEventListener("click", () => {
    startRadio();
  });
}

if (toggleBtn) {
  toggleBtn.addEventListener("click", () => {
    togglePlayback();
  });
}

if (audio) {
  audio.addEventListener("play", () => {
    updateToggleButton();
  });

  audio.addEventListener("pause", () => {
    updateToggleButton();
  });

  audio.addEventListener("ended", async () => {
    if (!radioStarted) return;
    await syncToLive({ autoplay: true });
  });

  audio.addEventListener("error", () => {
    console.error("Audiofehler:", audio.currentSrc);
    setStatus("datei konnte nicht geladen werden.");
    setQueueInfo("irgendwo stimmt ein pfad nicht.");
  });
}

document.addEventListener("visibilitychange", async () => {
  if (document.visibilityState === "visible" && radioStarted && audio && !audio.paused) {
    await syncToLive({ autoplay: true });
  }
});

window.addEventListener("focus", async () => {
  if (radioStarted && audio && !audio.paused) {
    await syncToLive({ autoplay: true });
  }
});

window.addEventListener("DOMContentLoaded", () => {
  ensureScheduleForToday();

  if (!SONGS.length) {
    setCurrentTrack("waiting_for_signal...");
    setStatus("keine tracks geladen.");
    setQueueInfo("erst generate-tracks.js laufen lassen.");
    setRemainingTime("remaining: --:--");
    setNextTrack("next: unknown");
  } else {
    const live = getLiveState();

    if (live?.item) {
      currentLiveIndex = live.index;
      setCurrentTrack(sanitizeTitle(live.item.title));
      setStatus("ready.");
      setQueueInfo(describeQueue(live.item));
      updateInfoPanelFromLiveState(live);
    } else {
      setCurrentTrack("waiting_for_signal...");
      setStatus("ready.");
      setQueueInfo("local small server / endless archive / unstable taste");
      setRemainingTime("remaining: --:--");
      setNextTrack("next: unknown");
    }
  }

  updateToggleButton();
});
