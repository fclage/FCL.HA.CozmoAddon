// Cozmo drive pad and speech box. Buttons do not take focus, so the page
// does not jump down to a text field after a tap.

function blurTextFields() {
  const active = document.activeElement;
  if (!active || active === document.body) return;
  const field = active.closest
    ? active.closest("input, textarea, ha-textfield")
    : null;
  if (field && field.blur) field.blur();
  else if (active.blur && active.tagName !== "HA-CARD") active.blur();
}

window.addEventListener(
  "pointerdown",
  (ev) => {
    if (!location.pathname.includes("cozmo")) return;
    const target = ev.target;
    const host = target.closest ? target.closest("cozmo-say") : null;
    if (host || target.tagName === "COZMO-SAY") return;
    if (target.closest && target.closest("input, textarea, ha-textfield")) {
      return;
    }
    blurTextFields();
  },
  true,
);

function clamp(value, lo, hi) {
  return Math.max(lo, Math.min(hi, value));
}

function readNumber(hass, entity, fallback) {
  const raw = hass?.states?.[entity]?.state;
  const value = parseFloat(raw);
  return Number.isFinite(value) ? value : fallback;
}

class CozmoPad extends HTMLElement {
  setConfig(config) {
    this._config = config || {};
    if (!this._built) this._build();
  }

  set hass(hass) {
    this._hass = hass;
    if (this._head == null) this._head = readNumber(hass, "number.cozmo_head_angle", 8);
    if (this._lift == null) this._lift = readNumber(hass, "number.cozmo_lift_height", 60);
  }

  _build() {
    this._built = true;
    const root = this.attachShadow({ mode: "open" });
    root.innerHTML = `
      <style>
        ha-card { padding: 12px; }
        .grid {
          display: grid;
          grid-template-columns: 1fr 1.15fr 1fr;
          gap: 8px;
        }
        button {
          min-height: 72px;
          border: none;
          border-radius: 18px;
          background: var(--secondary-background-color, rgba(127,127,127,0.15));
          color: var(--primary-text-color);
          font: inherit;
          font-weight: 600;
          letter-spacing: 0.01em;
          cursor: pointer;
          touch-action: manipulation;
        }
        button:active { filter: brightness(1.15); transform: translateY(1px); }
        button.stop {
          background: var(--error-color, #c62828);
          color: var(--text-primary-color, #fff);
        }
        button.go { background: var(--primary-color); color: var(--text-primary-color, #fff); }
      </style>
      <ha-card>
        <div class="grid"></div>
      </ha-card>
    `;
    const grid = root.querySelector(".grid");
    const buttons = [
      ["Lift up", "lift", 12],
      ["Forward", "drive", [90, 90, 0.45], "go"],
      ["Lift down", "lift", -12],
      ["Left", "drive", [-70, 70, 0.35]],
      ["Stop", "stop", null, "stop"],
      ["Right", "drive", [70, -70, 0.35]],
      ["Face up", "head", 8],
      ["Back", "drive", [-80, -80, 0.4]],
      ["Face down", "head", -8],
    ];
    for (const [label, kind, arg, extra] of buttons) {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = label;
      if (extra) button.className = extra;
      button.addEventListener("pointerdown", (ev) => {
        ev.preventDefault();
        blurTextFields();
      });
      button.addEventListener("click", () => this._press(kind, arg));
      grid.appendChild(button);
    }
  }

  async _press(kind, arg) {
    const hass = this._hass;
    if (!hass) return;
    blurTextFields();
    if (kind === "stop") {
      await hass.callService("ha_cozmo", "stop", {});
      return;
    }
    if (kind === "drive") {
      const [left, right, duration] = arg;
      await hass.callService("ha_cozmo", "drive", {
        left_speed: left,
        right_speed: right,
        duration,
      });
      return;
    }
    if (kind === "head") {
      this._head = clamp((this._head ?? 8) + arg, -25, 44.5);
      await hass.callService("ha_cozmo", "set_head", { angle: Math.round(this._head * 10) / 10 });
      return;
    }
    this._lift = clamp((this._lift ?? 60) + arg, 32, 92);
    await hass.callService("ha_cozmo", "set_lift", { height: Math.round(this._lift) });
  }
}

class CozmoSay extends HTMLElement {
  setConfig(config) {
    this._config = config || {};
    if (!this._built) this._build();
  }

  set hass(hass) {
    this._hass = hass;
  }

  _build() {
    this._built = true;
    const root = this.attachShadow({ mode: "open" });
    root.innerHTML = `
      <style>
        ha-card { padding: 12px; }
        form { display: flex; gap: 8px; align-items: center; }
        input {
          flex: 1;
          min-width: 0;
          min-height: 48px;
          border-radius: 14px;
          border: 1px solid var(--divider-color, rgba(127,127,127,0.4));
          background: var(--card-background-color, transparent);
          color: var(--primary-text-color);
          font: inherit;
          padding: 0 12px;
        }
        button {
          min-height: 48px;
          padding: 0 16px;
          border: none;
          border-radius: 14px;
          background: var(--primary-color);
          color: var(--text-primary-color, #fff);
          font: inherit;
          font-weight: 700;
          cursor: pointer;
          touch-action: manipulation;
        }
      </style>
      <ha-card class="cozmo-say">
        <form>
          <input type="text" maxlength="200" placeholder="Type a line" enterkeyhint="send" />
          <button type="submit">Send</button>
        </form>
      </ha-card>
    `;
    const form = root.querySelector("form");
    const input = root.querySelector("input");
    form.addEventListener("submit", (ev) => {
      ev.preventDefault();
      this._send(input);
    });
  }

  async _send(input) {
    const text = (input.value || "").trim();
    if (!text || !this._hass) return;
    await this._hass.callService("ha_cozmo", "speak", { text });
    input.value = "";
    input.blur();
  }
}

customElements.define("cozmo-pad", CozmoPad);
customElements.define("cozmo-say", CozmoSay);
window.customCards = window.customCards || [];
window.customCards.push(
  { type: "custom:cozmo-pad", name: "Cozmo pad", description: "Direction pad for Cozmo" },
  { type: "custom:cozmo-say", name: "Cozmo say", description: "Text line for Cozmo to speak" },
);
