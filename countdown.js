// countdown.html: a split-flap countdown to the weekly session, Friday 10:00 US Eastern. It holds at zero
// for the hour the session runs, then counts down to the next Friday. Everything runs in the browser.
(() => {
  const TZ = "America/New_York";
  const HOLD_MS = 60 * 60 * 1000;   // stays at zero 10:00 to 11:00 Eastern

  const partsFmt = new Intl.DateTimeFormat("en-US", { timeZone: TZ, hourCycle: "h23", weekday: "short",
    year: "numeric", month: "numeric", day: "numeric", hour: "numeric", minute: "numeric", second: "numeric" });
  const DOW = { Sun: 0, Mon: 1, Tue: 2, Wed: 3, Thu: 4, Fri: 5, Sat: 6 };
  function etParts(ms) {
    const p = {};
    for (const { type, value } of partsFmt.formatToParts(new Date(ms))) p[type] = value;
    return { y: +p.year, mo: +p.month, d: +p.day, h: +p.hour % 24, mi: +p.minute, s: +p.second, dow: DOW[p.weekday] };
  }
  // The instant of an Eastern wall-clock time, with EST or EDT, whichever applies that day.
  function etToUtc(y, mo, d, h) {
    const guess = Date.UTC(y, mo - 1, d, h);
    let t = guess;
    for (let i = 0; i < 2; i++) {
      const p = etParts(t);
      t = guess - (Date.UTC(p.y, p.mo - 1, p.d, p.h, p.mi, p.s) - t);
    }
    return t;
  }
  // This week's Friday 10:00 Eastern until 11:00 that day, then next week's.
  function targetFor(now) {
    const p = etParts(now);
    const ahead = (5 - p.dow + 7) % 7;
    let t = etToUtc(p.y, p.mo, p.d + ahead, 10);
    if (now >= t + HOLD_MS) t = etToUtc(p.y, p.mo, p.d + ahead + 7, 10);
    return t;
  }
  const pad = n => String(n).padStart(2, "0");
  function state(now) {
    const target = targetFor(now);
    const sec = Math.max(0, Math.ceil((target - now) / 1000));
    const d = Math.floor(sec / 86400), h = Math.floor(sec / 3600) % 24, m = Math.floor(sec / 60) % 60, s = sec % 60;
    // Days, hours and minutes; under a day, hours, minutes and seconds.
    const [vals, units] = d >= 1 ? [[d, h, m], ["days", "hours", "minutes"]]
                                 : [[h, m, s], ["hours", "minutes", "seconds"]];
    return { digits: vals.map(pad).join("").split(""), units, target, sec };
  }

  // ISO style: [YYYY-MM-DD HH:MM, UTC±HH:MM] in a time zone, 24-hour.
  const isoFmts = {};
  function iso(ms, tz) {
    const f = isoFmts[tz] || (isoFmts[tz] = new Intl.DateTimeFormat("en-US", { timeZone: tz, hourCycle: "h23",
      year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", timeZoneName: "longOffset" }));
    const p = {};
    for (const { type, value } of f.formatToParts(new Date(ms))) p[type] = value;
    const off = p.timeZoneName === "GMT" ? "+00:00" : p.timeZoneName.replace("GMT", "");
    return [`${p.year}-${p.month}-${p.day} ${p.hour}:${p.minute}`, `UTC${off.replace("-", "−")}`];
  }

  const $ = id => document.getElementById(id);
  const flip = $("flip"), stage = $("stage"), leadNow = $("leadNow");
  const unitEls = ["unitA", "unitB", "unitC"].map($);
  const tUtc = $("tUtc"), tEt = $("tEt"), oEt = $("oEt"), lLocal = $("lLocal"), tLocal = $("tLocal"), oLocal = $("oLocal");
  const localRow = document.querySelectorAll(".times .local");
  const localTz = Intl.DateTimeFormat().resolvedOptions().timeZone;
  lLocal.textContent = localTz;
  const reduce = matchMedia("(prefers-reduced-motion: reduce)");
  const setText = (el, v) => { if (el.textContent !== v) el.textContent = v; };

  // Each tile: two static halves and two flaps. On a change the old top half folds down over the new digit,
  // then the new bottom half falls into place; .flipping comes off on animationend, or after a second.
  const tiles = [...document.querySelectorAll(".tile")];
  for (const t of tiles) {
    for (const cls of ["half top", "half bot", "half top flap", "half bot flap"]) {
      const half = document.createElement("span"), d = document.createElement("span");
      half.className = cls; d.className = "d";
      half.append(d); t.append(half);
    }
    for (const side of ["l", "r"]) {
      const hinge = document.createElement("span");
      hinge.className = "hinge " + side;
      t.append(hinge);
    }
  }
  function setTile(tile, v, animate) {
    const [top, bot, flapTop, flapBot] = tile.querySelectorAll(".half > .d");
    const old = top.textContent;
    if (tile.flipDone) tile.flipDone();
    if (!animate) { for (const d of [top, bot, flapTop, flapBot]) setText(d, v); return; }
    setText(top, v); setText(bot, old); setText(flapTop, old); setText(flapBot, v);
    tile.classList.remove("flipping");
    void tile.offsetWidth;
    tile.classList.add("flipping");
    const flap = flapBot.parentElement;
    const done = () => {
      clearTimeout(timer); flap.removeEventListener("animationend", done);
      tile.flipDone = null; setText(bot, v); tile.classList.remove("flipping");
    };
    const timer = setTimeout(done, 1000);
    flap.addEventListener("animationend", done);
    tile.flipDone = done;
  }

  let shown = null;
  function render() {
    const now = Date.now();
    const st = state(now);
    const animate = shown !== null && !reduce.matches && !document.hidden;
    st.digits.forEach((v, i) => { if (!shown || shown[i] !== v) setTile(tiles[i], v, animate); });
    shown = st.digits;
    st.units.forEach((u, i) => setText(unitEls[i], u));
    flip.setAttribute("aria-label", st.units.map((u, i) => `${st.digits[2 * i]}${st.digits[2 * i + 1]} ${u}`).join(", "));
    // Counting down: when it starts. During the session: when it ends.
    const live = st.sec === 0;
    stage.classList.toggle("live", live);
    leadNow.hidden = !live;
    const at = live ? st.target + HOLD_MS : st.target;
    const [u] = iso(at, "UTC"), [e, eo] = iso(at, TZ), [l, lo] = iso(at, localTz);
    setText(tUtc, u); setText(tEt, e); setText(oEt, eo); setText(tLocal, l); setText(oLocal, lo);
    // A viewer in Eastern time sees no third row. It is blanked, not removed, so the layout never moves.
    const sameAsEt = l === e && lo === eo;
    for (const el of localRow) el.classList.toggle("blank", sameAsEt);
    setTimeout(render, 1000 - (Date.now() % 1000) + 5);
  }
  render();
})();
