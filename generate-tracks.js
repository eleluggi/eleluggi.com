const fs = require("fs");
const path = require("path");
const mm = require("music-metadata");

const songsDir = path.join(__dirname, "audio", "songs");
const jinglesDir = path.join(__dirname, "audio", "jingles");
const outputFile = path.join(__dirname, "tracks.js");

// Kannst du ändern, wenn du willst.
// Wenn du den Seed änderst, ändert sich die ganze "Radiopersönlichkeit".
const STATION_SEED = "transmission_8842";

async function getMp3Files(dir, webPrefix) {
  if (!fs.existsSync(dir)) return [];

  const files = fs
    .readdirSync(dir)
    .filter(file => file.toLowerCase().endsWith(".mp3"))
    .sort((a, b) => a.localeCompare(b, "de"));

  const result = [];

  for (const file of files) {
    const absolutePath = path.join(dir, file);

    try {
      const metadata = await mm.parseFile(absolutePath);
      const duration = Number(metadata.format.duration || 0);

      if (!duration || duration <= 0) {
        console.warn(`Keine brauchbare Dauer für ${file}, übersprungen.`);
        continue;
      }

      result.push({
        title: file.replace(/\.mp3$/i, ""),
        file: `${webPrefix}/${encodeURIComponent(file)}`,
        duration: Number(duration.toFixed(3))
      });
    } catch (err) {
      console.warn(`Fehler bei ${file}: ${err.message}`);
    }
  }

  return result;
}

async function main() {
  const songs = await getMp3Files(songsDir, "./audio/songs");
  const jingles = await getMp3Files(jinglesDir, "./audio/jingles");

  const output = `window.RADIO_LIBRARY = ${JSON.stringify({
    stationSeed: STATION_SEED,
    generatedAt: new Date().toISOString(),
    songs,
    jingles
  }, null, 2)};`;

  fs.writeFileSync(outputFile, output, "utf8");

  console.log("tracks.js wurde erzeugt.");
  console.log(`Songs: ${songs.length}`);
  console.log(`Jingles: ${jingles.length}`);
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
