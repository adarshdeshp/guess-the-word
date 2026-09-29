(() => {
  const root = document.querySelector("[data-game]");
  if (!root) return;

  const LENGTH = 5;
  const MAX = Number(root.dataset.maxGuesses);
  const endpoint = root.dataset.endpoint;
  const home = root.dataset.home;
  const csrf = root.dataset.csrf;
  const rows = [...root.querySelectorAll(".board .row")];
  const toast = root.querySelector("[data-toast]");
  const counter = root.querySelector("[data-counter]");
  const dialog = root.querySelector("[data-result]");
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const FLIP_MS = reduceMotion ? 0 : 420;
  const STAGGER_MS = reduceMotion ? 0 : 260;

  let current = Number(root.dataset.attempts); // index of the row being typed into
  let buffer = "";
  let busy = false;
  let finished = root.dataset.status !== "in_progress";

  // ----- on-screen keyboard state -----
  const keys = new Map();
  root.querySelectorAll(".key[data-key]").forEach((k) => keys.set(k.dataset.key, k));
  const rank = { absent: 1, present: 2, correct: 3 };

  function markKey(letter, state) {
    const key = keys.get(letter);
    if (!key) return;
    const prev = key.dataset.state;
    if (!prev || rank[state] > rank[prev]) key.dataset.state = state;
  }

  rows.slice(0, current).forEach((row) =>
    row.querySelectorAll(".tile").forEach((t) => markKey(t.textContent.trim(), t.dataset.state))
  );

  // ----- messages -----
  let toastTimer;
  function say(message) {
    toast.textContent = message;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => (toast.textContent = ""), 2600);
  }

  function shake(row) {
    if (reduceMotion || !row) return;
    row.classList.remove("shake");
    void row.offsetWidth; // restart the animation
    row.classList.add("shake");
  }

  // ----- typing -----
  function render(poppedIndex) {
    const row = rows[current];
    if (!row) return;
    row.querySelectorAll(".tile").forEach((tile, i) => {
      tile.textContent = buffer[i] || "";
      tile.dataset.filled = buffer[i] ? "true" : "false";
      if (i === poppedIndex && !reduceMotion) {
        tile.classList.remove("pop");
        void tile.offsetWidth;
        tile.classList.add("pop");
      }
    });
  }

  function type(letter) {
    if (finished || busy || buffer.length >= LENGTH) return;
    buffer += letter;
    render(buffer.length - 1);
  }

  function erase() {
    if (finished || busy || !buffer) return;
    buffer = buffer.slice(0, -1);
    render();
  }

  // ----- reveal -----
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));
  const labels = { correct: "right spot", present: "wrong spot", absent: "not in word" };

  async function reveal(row, guess, result) {
    const tiles = [...row.querySelectorAll(".tile")];
    await Promise.all(
      tiles.map(async (tile, i) => {
        await wait(i * STAGGER_MS);
        tile.classList.add("flip");
        await wait(FLIP_MS / 2);
        tile.dataset.state = result[i];
        tile.removeAttribute("data-filled");
        tile.setAttribute("aria-label", `${guess[i]}, ${labels[result[i]]}`);
        await wait(FLIP_MS / 2);
        tile.classList.remove("flip");
      })
    );
  }

  // ----- submit -----
  async function submit() {
    if (finished || busy) return;
    const row = rows[current];
    if (buffer.length < LENGTH) {
      say("Enter all 5 letters first.");
      shake(row);
      return;
    }

    busy = true;
    try {
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
        body: JSON.stringify({ guess: buffer }),
      });
      const data = await res.json().catch(() => ({}));

      if (!res.ok) {
        say(data.error || "That guess wasn't saved. Try again.");
        shake(row);
        if (res.status === 409) setTimeout(() => (window.location.href = home), 1400);
        return;
      }

      await reveal(row, data.guess, data.result);
      [...data.guess].forEach((ch, i) => markKey(ch, data.result[i]));
      current += 1;
      buffer = "";

      if (data.status === "in_progress") {
        counter.textContent = `${data.remaining} ${data.remaining === 1 ? "guess" : "guesses"} left`;
      } else {
        finished = true;
        counter.textContent =
          data.status === "won" ? `Solved in ${data.attempt}` : `Not solved. The word was ${data.answer}.`;
        root.querySelector(".keyboard")?.setAttribute("inert", "");
        await wait(reduceMotion ? 0 : 350);
        showResult(data);
      }
    } catch {
      say("Connection lost. Check your network and press Enter again.");
    } finally {
      busy = false;
    }
  }

  // ----- result dialog -----
  function showResult(data) {
    const won = data.status === "won";
    const wordBox = dialog.querySelector("[data-result-word]");
    wordBox.replaceChildren(
      ...[...data.answer].map((ch) => {
        const t = document.createElement("span");
        t.className = "tile tile-sm";
        t.dataset.state = won ? "correct" : "absent";
        t.textContent = ch;
        return t;
      })
    );
    dialog.querySelector("[data-result-title]").textContent = won ? "Congratulations!" : "Better luck next time";
    dialog.querySelector("[data-result-text]").textContent = won
      ? `You found ${data.answer} in ${data.attempt} ${data.attempt === 1 ? "guess" : "guesses"}.`
      : `The word was ${data.answer}.`;

    const ok = dialog.querySelector("[data-result-ok]");
    const leave = () => (window.location.href = home);
    ok.addEventListener("click", leave, { once: true });
    dialog.addEventListener("cancel", (e) => { e.preventDefault(); leave(); }, { once: true });

    if (typeof dialog.showModal === "function") dialog.showModal();
    else dialog.setAttribute("open", "");
    ok.focus();
  }

  // ----- input wiring -----
  root.querySelectorAll(".key").forEach((key) => {
    key.addEventListener("click", () => {
      if (key.dataset.action === "enter") submit();
      else if (key.dataset.action === "back") erase();
      else type(key.dataset.key);
      key.blur(); // keep Enter on the physical keyboard from re-clicking this key
    });
  });

  document.addEventListener("keydown", (e) => {
    if (e.ctrlKey || e.metaKey || e.altKey || dialog.open) return;
    if (e.key === "Enter") { e.preventDefault(); submit(); return; }
    if (e.key === "Backspace") { e.preventDefault(); erase(); return; }
    if (/^[a-z]$/i.test(e.key)) {
      const letter = e.key.toUpperCase();
      type(letter);
      const k = keys.get(letter);
      if (k) { k.classList.add("pressed"); setTimeout(() => k.classList.remove("pressed"), 90); }
    }
  });

  if (MAX && current >= MAX) finished = true;
})();
