const $ = (id) => document.getElementById(id);

function headers(extra = {}) {
  const token = $("token").value.trim();
  const h = { ...extra };
  if (token) h.Authorization = `Bearer ${token}`;
  return h;
}

async function api(path, opts = {}) {
  const res = await fetch(path, { ...opts, headers: headers(opts.headers) });
  const text = await res.text();
  let body = null;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    body = text;
  }
  if (!res.ok) throw new Error((body && body.error) || res.statusText);
  return body;
}

async function cmd(name, fields = {}) {
  return api("/v1/command", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ cmd: name, ...fields }),
  });
}

function showErr(msg) {
  const el = $("err");
  if (!msg) {
    el.hidden = true;
    el.textContent = "";
    return;
  }
  el.hidden = false;
  el.textContent = msg;
}

async function refreshStatus() {
  try {
    const st = await api("/v1/status");
    $("dot").classList.toggle("on", Boolean(st.robot_connected));
    $("conn").textContent = st.robot_connected ? "connected" : "disconnected";
    $("batt").textContent = st.battery_voltage != null ? `${st.battery_voltage} V` : "—";
    showErr(st.last_error || "");
  } catch (err) {
    $("conn").textContent = "companion unreachable";
    showErr(String(err.message || err));
  }
}

async function scanWifi() {
  const data = await api("/v1/wifi/scan");
  const sel = $("ssidSelect");
  sel.innerHTML = "";
  const nets = data.networks || [];
  if (!nets.length) {
    sel.append(new Option("No Cozmo_* seen — type SSID", ""));
    $("wifiHint").textContent = `iface ${data.iface || "(unset)"}`;
    return;
  }
  sel.append(new Option("Pick a Cozmo AP", ""));
  for (const n of nets) {
    sel.append(new Option(`${n.ssid}  ${n.signal}%`, n.ssid));
  }
  $("wifiHint").textContent = `${nets.length} network(s) on ${data.iface || "?"}`;
}

function tickCamera() {
  $("cam").src = `/v1/camera.jpg?t=${Date.now()}`;
}

$("token").value = localStorage.getItem("hacozmo.token") || "";
$("token").addEventListener("change", () => {
  localStorage.setItem("hacozmo.token", $("token").value.trim());
});

$("btnScan").addEventListener("click", () => scanWifi().catch((e) => showErr(e.message)));
$("ssidSelect").addEventListener("change", () => {
  if ($("ssidSelect").value) $("ssid").value = $("ssidSelect").value;
});
$("btnJoin").addEventListener("click", async () => {
  try {
    await api("/v1/wifi", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ssid: $("ssid").value, password: $("psk").value }),
    });
    $("wifiHint").textContent = "join requested";
  } catch (err) {
    showErr(err.message);
  }
});
$("btnStop").addEventListener("click", () => cmd("stop"));
$("btnSay").addEventListener("click", () => cmd("speak", { text: $("say").value }));
$("btnIdleOn").addEventListener("click", () => cmd("personality", { enabled: true }));
$("btnIdleOff").addEventListener("click", () => cmd("personality", { enabled: false }));
document.querySelectorAll("[data-drive]").forEach((btn) => {
  btn.addEventListener("click", () => {
    const [left, right] = btn.dataset.drive.split(",").map(Number);
    cmd("drive", { left, right, duration: 0.4 }).catch((err) =>
      showErr(err.message || String(err)),
    );
  });
});

const faces = ["happiness", "sadness", "anger", "surprise", "neutral", "asleep"];
for (const name of faces) {
  const b = document.createElement("button");
  b.type = "button";
  b.textContent = name;
  b.addEventListener("click", () => cmd("face", { expression: name }));
  $("faces").append(b);
}

api("/v1/catalog")
  .then((cat) => {
    for (const a of cat.animations || []) {
      const b = document.createElement("button");
      b.type = "button";
      b.textContent = a.label;
      b.addEventListener("click", () => cmd("play_command", { name: a.id }));
      $("anims").append(b);
    }
  })
  .catch(() => {});

scanWifi().catch(() => {});
refreshStatus().catch((err) => showErr(String(err.message || err)));
setInterval(refreshStatus, 3000);
setInterval(tickCamera, 800);
