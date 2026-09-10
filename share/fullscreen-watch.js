// Meldet an den we-wallpaper-Dienst, ob irgendein Fenster im Vollbild laeuft.
// Plasma 6 nennt die API "window*", aeltere Versionen "client*" - beides wird bedient.
var SERVICE = "org.wewallpaper.Watch";
var PATH = "/Watch";
var IFACE = "org.wewallpaper.Watch";

function windowList() {
    if (typeof workspace.windowList === "function") { return workspace.windowList(); }
    if (typeof workspace.clientList === "function") { return workspace.clientList(); }
    return [];
}

var lastState = null;

function evaluate() {
    var list = windowList();
    var any = false;
    for (var i = 0; i < list.length; i++) {
        var w = list[i];
        if (!w) { continue; }
        if (w.fullScreen === true && w.minimized !== true) { any = true; break; }
    }
    if (any !== lastState) {
        lastState = any;
        callDBus(SERVICE, PATH, IFACE, "setFullscreen", any);
    }
}

function hook(w) {
    if (!w) { return; }
    if (w.fullScreenChanged) { w.fullScreenChanged.connect(evaluate); }
    if (w.minimizedChanged) { w.minimizedChanged.connect(evaluate); }
}

var initial = windowList();
for (var i = 0; i < initial.length; i++) { hook(initial[i]); }

var added = workspace.windowAdded || workspace.clientAdded;
if (added) { added.connect(function (w) { hook(w); evaluate(); }); }
var removed = workspace.windowRemoved || workspace.clientRemoved;
if (removed) { removed.connect(function () { evaluate(); }); }

evaluate();

// ---------------------------------------------------------------- Tastenkuerzel
// KWin-Skripte duerfen globale Kuerzel anmelden; der Aufruf geht per D-Bus an
// we-wallpaper-watch, weil Skripte selbst keine Programme starten koennen.
function callWatch(method) {
    callDBus(SERVICE, PATH, IFACE, method);
}

if (typeof registerShortcut === "function") {
    registerShortcut("WeWallpaperToggle",
        "Wallpaper Engine: Wallpaper an/aus (gibt Desktop-Icons frei)",
        "Meta+Shift+W", function () { callWatch("toggleWallpaper"); });
    registerShortcut("WeWallpaperNext",
        "Wallpaper Engine: Naechstes Wallpaper",
        "Meta+Shift+N", function () { callWatch("nextWallpaper"); });
    registerShortcut("WeWallpaperPause",
        "Wallpaper Engine: Pause umschalten",
        "Meta+Shift+P", function () { callWatch("togglePause"); });
}

// ---------------------------------------------------------------- Verdeckung
// Meldet, ob auf JEDEM eingeschalteten Monitor ein maximiertes oder
// Vollbild-Fenster liegt - dann ist das Wallpaper unsichtbar und kann pausieren.
// KWin-Enum: maximizeMode 3 = MaximizeFull (die Konstante selbst ist im
// Skript-Kontext nicht sichtbar, daher der Zahlenwert).
var MAX_FULL = 3;
var OWN_CLASSES = { "linux-wallpaperengine": true };   // der Renderer selbst

function onCurrentDesktop(w) {
    if (w.onAllDesktops === true) { return true; }
    if (typeof w.desktops === "undefined" || !w.desktops) { return true; }
    var cur = workspace.currentDesktop;
    for (var i = 0; i < w.desktops.length; i++) {
        if (w.desktops[i] === cur) { return true; }
    }
    return false;
}

function covers(w, out) {
    if (!w || w.minimized === true) { return false; }
    if (w.normalWindow !== true) { return false; }
    if (OWN_CLASSES[String(w.resourceClass)]) { return false; }
    if (!w.output || !out || w.output.name !== out.name) { return false; }
    if (!onCurrentDesktop(w)) { return false; }
    if (w.fullScreen === true || w.maximizeMode === MAX_FULL) { return true; }
    var fg = w.frameGeometry, og = out.geometry;
    if (!fg || !og) { return false; }
    return fg.x <= og.x && fg.y <= og.y
        && fg.x + fg.width >= og.x + og.width
        && fg.y + fg.height >= og.y + og.height;
}

var lastCovered = null;

function evaluateCovered() {
    var outs = workspace.screens || [];
    if (!outs.length) { return; }
    var wins = windowList();
    var all = true;
    for (var o = 0; o < outs.length; o++) {
        var hit = false;
        for (var i = 0; i < wins.length; i++) {
            if (covers(wins[i], outs[o])) { hit = true; break; }
        }
        if (!hit) { all = false; break; }
    }
    if (all !== lastCovered) {
        lastCovered = all;
        callDBus(SERVICE, PATH, IFACE, "setCovered", all);
    }
}

function hookCovered(w) {
    if (!w) { return; }
    var sigs = ["maximizedChanged", "minimizedChanged", "fullScreenChanged",
                "outputChanged", "frameGeometryChanged", "desktopsChanged"];
    for (var i = 0; i < sigs.length; i++) {
        if (w[sigs[i]] && typeof w[sigs[i]].connect === "function") {
            w[sigs[i]].connect(evaluateCovered);
        }
    }
}

(function () {
    var initial = windowList();
    for (var i = 0; i < initial.length; i++) { hookCovered(initial[i]); }
    var added = workspace.windowAdded || workspace.clientAdded;
    if (added) { added.connect(function (w) { hookCovered(w); evaluateCovered(); }); }
    var removed = workspace.windowRemoved || workspace.clientRemoved;
    if (removed) { removed.connect(function () { evaluateCovered(); }); }
    if (workspace.currentDesktopChanged) { workspace.currentDesktopChanged.connect(evaluateCovered); }
    if (workspace.screensChanged) { workspace.screensChanged.connect(evaluateCovered); }
    evaluateCovered();
})();
