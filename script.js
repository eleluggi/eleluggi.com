document.addEventListener("DOMContentLoaded", () => {
    // Initialisiere Brot-Animation
    setupBreadAnimation();
    
    // Spracheinstellung beim Laden setzen
    const savedLang = localStorage.getItem("language") || "de";
    switchLanguage(savedLang);
});

// Animiertes Brot
function setupBreadAnimation() {
    const bread = document.getElementById("animated-bread");

    if (!bread) return; // Wenn das Brot nicht auf der Seite ist, beende die Funktion

    bread.addEventListener("click", () => {
        bread.style.animation = "none";
        bread.style.left = "50%";
        bread.style.top = "50%";
        bread.style.transform = "translate(-50%, -50%)";
        alert("Du hast das Brot gefangen! Jetzt kannst du es toasten.");
    });

    bread.addEventListener("mouseover", () => {
        const randomX = Math.floor(Math.random() * (window.innerWidth - 50));
        const randomY = Math.floor(Math.random() * (window.innerHeight - 50));
        bread.style.left = `${randomX}px`;
        bread.style.top = `${randomY}px`;
    });
}

document.addEventListener("DOMContentLoaded", () => {
    let savedLang = localStorage.getItem("language");

    // Falls keine Sprache gespeichert ist, auf Englisch setzen
    if (!savedLang) {
        savedLang = "en"; // Standard: Englisch
        localStorage.setItem("language", savedLang);
    }

    applyLanguage(savedLang);
});

// Sprachumschalter-Funktion
function switchLanguage(lang) {
    console.log("Switching to:", lang); // Debugging

    localStorage.setItem("language", lang); // Speichern der Sprache
    applyLanguage(lang);
}

function applyLanguage(lang) {
    console.log("Applying language:", lang); // Debugging

    // Hintergrundbild für US-Flagge setzen
    if (lang === "us") {
        document.body.style.backgroundImage = `url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 7410 3900"><path d="M0,0h7410v3900H0" fill="%23b31942"/><path d="M0,450H7410m0,600H0m0,600H7410m0,600H0m0,600H7410m0,600H0" stroke="%23FFF" stroke-width="300"/><path d="M0,0h2964v2100H0" fill="%230a3161"/><g fill="%23FFF"><g id="s18"><g id="s9"><g id="s5"><g id="s4"><path id="s" d="M247,90 317.534230,307.082039 132.873218,172.917961H361.126782L176.465770,307.082039z"/><use xlink:href="%23s" y="420"/><use xlink:href="%23s" y="840"/><use xlink:href="%23s" y="1260"/></g><use xlink:href="%23s" y="1680"/></g><use xlink:href="%23s4" x="247" y="210"/></g><use xlink:href="%23s9" x="494"/></g><use xlink:href="%23s18" x="988"/><use xlink:href="%23s9" x="1976"/><use xlink:href="%23s5" x="2470"/></g></svg>')`;
        document.body.style.backgroundSize = "cover"; // Passt sich automatisch an den Viewport an
        document.body.style.backgroundPosition = "center"; // Zentriert
        document.body.style.backgroundRepeat = "no-repeat"; // Verhindert Wiederholung
    } else {
        document.body.style.backgroundImage = ""; // Setzt normalen Hintergrund zurück
    }

    // Sprachelemente umschalten
    document.querySelectorAll("[data-lang]").forEach(element => {
        element.style.display = (element.getAttribute("data-lang") === lang) ? "block" : "none";
    });

    // Sprachbutton-Highlight aktualisieren
    document.querySelectorAll(".lang-link").forEach(link => {
        link.classList.remove("active");
    });

    const activeLang = document.getElementById("lang-" + lang);
    if (activeLang) {
        activeLang.classList.add("active");
    }
}

// Beim Laden der Seite direkt die Sprache setzen
window.addEventListener("load", () => {
    let savedLang = localStorage.getItem("language");
    if (!savedLang) {
        savedLang = "en"; // Standard-Sprache setzen
        localStorage.setItem("language", savedLang);
    }
    applyLanguage(savedLang);
});




