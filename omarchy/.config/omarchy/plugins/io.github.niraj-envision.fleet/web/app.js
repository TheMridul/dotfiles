/* Fleet — VPS manager for Omarchy.
   One module, no build step: the app is served straight off disk so it stays
   hackable the way the rest of an Omarchy box is. */

const TOKEN = new URLSearchParams(location.search).get("t") || "";
const $  = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];

window.__errs = [];

function recordError(kind, err) {
  const msg = (err && (err.stack || err.message)) || String(err);
  window.__errs.push({ kind, msg, at: Date.now() });
  if (window.__errs.length > 50) window.__errs.shift();
  console.error("[fleet]", kind, err);
  // Report once per distinct message so a render loop cannot spam the server.
  if (!recordError.seen) recordError.seen = new Set();
  const key = kind + ":" + msg.slice(0, 200);
  if (!recordError.seen.has(key)) {
    if (recordError.seen.size > 200) recordError.seen.clear();
    recordError.seen.add(key);
    try {
      fetch(`/api/clientlog?t=${TOKEN}`, { method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ kind, message: msg.slice(0, 2000) }) });
    } catch { /* logging must never itself throw */ }
  }
}

window.addEventListener("error", (e) => recordError("error", e.error || e.message));
window.addEventListener("unhandledrejection", (e) => recordError("promise", e.reason));

const S = {
  hosts: [], byId: {}, activeId: null, tab: "overview",
  theme: {}, settings: {}, sessions: [], terms: {}, activeTerm: {},
  inventory: {}, series: {}, ws: null, blueprints: [], snippets: [],
  vpns: [], vpnTooling: {}, vpnOpen: false, vpnErr: {},
};

/* ───────────────────────────────── helpers ─────────────────────────────── */

async function api(path, opts = {}) {
  const url = "/api/" + path + (path.includes("?") ? "&" : "?") + "t=" + TOKEN;
  // Scans and transfers legitimately take minutes; everything else should not
  // be able to hang a button forever.
  const ms = opts.timeout ?? 45000;
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), ms);
  let res;
  try {
    res = await fetch(url, {
      method: opts.method || "GET",
      headers: opts.body ? { "Content-Type": "application/json" } : {},
      body: opts.body ? JSON.stringify(opts.body) : undefined,
      signal: ctl.signal,
    });
  } catch (e) {
    throw new Error(e.name === "AbortError"
      ? `timed out after ${Math.round(ms / 1000)}s` : e.message);
  } finally {
    clearTimeout(timer);
  }
  const text = await res.text();
  let data; try { data = JSON.parse(text); } catch { data = { error: text }; }
  if (!res.ok) throw new Error(data.error || res.statusText);
  return data;
}

const esc = (s) => String(s ?? "").replace(/[&<>"']/g,
  (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

function bytes(n) {
  if (!n && n !== 0) return "—";
  const u = ["B", "K", "M", "G", "T", "P"];
  let i = 0; n = Number(n);
  while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
  return (n < 10 && i > 0 ? n.toFixed(1) : Math.round(n)) + u[i];
}

function dur(sec) {
  if (!sec && sec !== 0) return "—";
  const d = Math.floor(sec / 86400), h = Math.floor(sec % 86400 / 3600),
        m = Math.floor(sec % 3600 / 60);
  if (d) return `${d}d ${h}h`;
  if (h) return `${h}h ${m}m`;
  return `${m}m`;
}

function age(sec) {
  if (!sec && sec !== 0) return "—";
  const d = Math.floor(sec / 86400);
  if (d >= 730) return (d / 365).toFixed(1) + "y";
  if (d >= 60) return Math.floor(d / 30) + "mo";
  if (d >= 1) return d + "d";
  return Math.floor(sec / 3600) + "h";
}

const ago = (ts) => {
  if (!ts) return "—";
  const s = Math.floor(Date.now() / 1000) - ts;
  if (s < 60) return s + "s ago";
  if (s < 3600) return Math.floor(s / 60) + "m ago";
  if (s < 86400) return Math.floor(s / 3600) + "h ago";
  return Math.floor(s / 86400) + "d ago";
};

/* Severity colour for a 0-100 utilisation figure. Keeping this in one place
   means a disk at 91% and a CPU at 91% read the same way everywhere. */
function sev(pct) {
  if (pct == null) return "var(--muted)";
  if (pct >= 90) return "var(--red)";
  if (pct >= 75) return "var(--yellow)";
  return "var(--green)";
}

function toast(msg, kind = "") {
  const el = document.createElement("div");
  el.className = "toast " + kind;
  el.textContent = msg;
  $("#toasts").appendChild(el);
  setTimeout(() => { el.style.opacity = "0"; el.style.transition = "opacity .3s"; }, 3600);
  setTimeout(() => el.remove(), 4000);
}

/* ─────────────────────────── compositor bar inset ──────────────────────── */

/* A fullscreen window covers the whole monitor, bar strip included, so the
   app's own header ends up underneath it. In tiled mode the compositor already
   reserves that space and no inset is wanted. Detecting the difference is the
   whole trick: a window sitting at the very top of the screen and as tall as
   the screen is fullscreen; anything else is not. */
// Enough to lift the header off the screen edge without eating a visible band;
// the header already carries 11px of its own padding.
const FULLSCREEN_BREATHING_PX = 10;
let lastInset = null;

function applyBarInset() {
  const d = S.desktop || {};
  const bar = d.bar;
  let top = 0, bottom = 0;
  // Only a genuinely fullscreen window covers the bar's strip; a tiled or
  // maximised one already has the space reserved for it by the compositor.
  // Hyprland lets a fullscreen window cover the bar, so nothing is hidden --
  // the app just ends up flush against the screen edge with none of the
  // breathing room a tiled window gets from the gap. A small inset restores
  // that. `bar` is for compositors that keep their bar painted on top, where
  // the header really would be hidden without reserving its full height.
  const mode = (S.settings && S.settings.fullscreen_inset) || "auto";
  if (d.fullscreen && mode !== "none") {
    const px = mode === "bar" ? ((bar && bar.height) || 0) : FULLSCREEN_BREATHING_PX;
    if (bar && bar.position === "bottom") bottom = px; else top = px;
  }
  const key = top + ":" + bottom;
  if (key === lastInset) return;
  lastInset = key;
  const root = document.documentElement;
  root.style.setProperty("--bar-inset-top", top + "px");
  root.style.setProperty("--bar-inset-bottom", bottom + "px");
  setTimeout(fitActiveTerm, 60);   // the terminal sizes from its container
}

/* ───────────────────────────────── theme ───────────────────────────────── */

function applyTheme(t) {
  S.theme = t || {};
  const root = document.documentElement;
  for (const [k, v] of Object.entries(S.theme)) {
    if (k === "name" || k === "mode") continue;
    root.style.setProperty("--" + k.replace(/_/g, "-"), v);
  }
  const mode = S.theme.mode === "light" ? "light" : "dark";
  const accent = S.theme.accent || S.theme.blue || S.theme.foreground;
  root.dataset.themeMode = mode;
  root.style.colorScheme = mode;
  root.style.setProperty("--accent", accent);
  root.style.setProperty("--accent-foreground", contrastText(accent));
  root.style.setProperty("--selection-background",
    S.theme.selection_background || S.theme.selection);
  root.style.setProperty("--selection-foreground",
    S.theme.selection_foreground || S.theme.bright_foreground || S.theme.foreground);
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta && S.theme.background) meta.content = S.theme.background;
  $("#theme-name").textContent = S.theme.name || "";
  for (const t2 of Object.values(S.terms)) applyTermTheme(t2.term);
}

function contrastText(color) {
  let rgb = null;
  const hex = String(color || "").trim().match(/^#([0-9a-f]{3}|[0-9a-f]{6})$/i);
  if (hex) {
    let h = hex[1];
    if (h.length === 3) h = h.split("").map((x) => x + x).join("");
    rgb = [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16));
  } else {
    const m = String(color || "").match(/^rgba?\(\s*([0-9.]+)[, ]+([0-9.]+)[, ]+([0-9.]+)/i);
    if (m) rgb = m.slice(1, 4).map(Number);
  }
  if (!rgb) return S.theme.mode === "light" ? "#ffffff" : "#000000";
  const linear = rgb.map((v) => {
    const c = Math.max(0, Math.min(255, v)) / 255;
    return c <= .04045 ? c / 12.92 : ((c + .055) / 1.055) ** 2.4;
  });
  const luminance = .2126 * linear[0] + .7152 * linear[1] + .0722 * linear[2];
  return luminance > .42 ? "#000000" : "#ffffff";
}

function termTheme() {
  const c = S.theme;
  return {
    background: c.background, foreground: c.foreground,
    cursor: c.bright_foreground || c.foreground,
    cursorAccent: c.background, selectionBackground: c.selection,
    black: c.color0, red: c.color1, green: c.color2, yellow: c.color3,
    blue: c.color4, magenta: c.color5, cyan: c.color6, white: c.color7,
    brightBlack: c.color8, brightRed: c.color9, brightGreen: c.color10,
    brightYellow: c.color11, brightBlue: c.color12, brightMagenta: c.color13,
    brightCyan: c.color14, brightWhite: c.color15,
  };
}
function applyTermTheme(term) { try { term.options.theme = termTheme(); } catch {} }

/* ──────────────────────────────── sidebar ──────────────────────────────── */

function sparkBars(hid) {
  const s = (S.series[hid] || []).slice(-8);
  if (!s.length) return "";
  return s.map((p) => {
    const v = Math.max(3, Math.min(16, (p.cpu || 0) / 100 * 16));
    return `<div class="gauge-mini" style="height:${v}px;background:${sev(p.cpu)}"></div>`;
  }).join("");
}

function renderSidebar() {
  const list = $("#host-list");
  if (!S.hosts.length) { list.innerHTML = ""; return; }

  const groups = {};
  for (const h of S.hosts) (groups[h.group || ""] ||= []).push(h);

  let html = "";
  for (const [g, items] of Object.entries(groups)) {
    if (g) html += `<div class="group-label">${esc(g)}</div>`;
    for (const h of items) {
      const st = h.state?.status || "idle";
      const m = h.metrics || {};
      const sub = st === "online"
        ? `${m.cpu_pct != null ? Math.round(m.cpu_pct) + "%" : "—"} · ${
            m.mem?.pct != null ? Math.round(m.mem.pct) + "%" : "—"} · ${
            m.primary_ip || h.hostname}`
        : (h.state?.error ? h.state.error.slice(0, 34) : `${h.user}@${h.hostname}`);
      html += `
      <div class="host ${h.id === S.activeId ? "active" : ""}" data-id="${h.id}"
           title="${esc(h.user + "@" + h.hostname + ":" + h.port)}">
        <div class="host-icon" style="color:var(--${esc(h.color || "blue")})">${esc(h.icon)}</div>
        <div class="host-main">
          <div class="host-name">${esc(h.name)}</div>
          <div class="host-sub">${esc(sub)}</div>
        </div>
        <div class="host-gauges">
          ${st === "online" ? sparkBars(h.id) : ""}
          <span class="dot dot-${esc(st)}"></span>
        </div>
      </div>`;
    }
  }
  list.innerHTML = html;
  $$(".host", list).forEach((el) =>
    el.onclick = () => selectHost(el.dataset.id));
}

/* ─────────────────────────────── host header ───────────────────────────── */

function statBlock(label, value, pct, colorOverride) {
  const c = colorOverride || sev(pct);
  return `<div class="stat">
    <div class="stat-label">${esc(label)}</div>
    <div class="stat-value" style="color:${c}">${value}</div>
    ${pct != null ? `<div class="stat-bar"><div class="stat-fill"
        style="width:${Math.min(100, pct)}%;background:${c}"></div></div>` : ""}
  </div>`;
}

function renderHead() {
  const h = S.byId[S.activeId];
  if (!h) return;
  const m = h.metrics || {};
  const st = h.state?.status || "idle";

  $("#hh-icon").textContent = h.icon;
  $("#hh-icon").style.color = `var(--${h.color || "blue"})`;
  $("#hh-name").textContent = h.name;
  const badge = $("#hh-status");
  badge.textContent = st;
  badge.className = "pill " + st;
  $("#hh-target").textContent = `${h.user}@${h.hostname}:${h.port}`;
  $("#hh-os").textContent = m.os ? `${m.os}${m.kernel ? " · " + m.kernel : ""}` : "";
  $("#hh-os").title = $("#hh-os").textContent;

  const disk = (m.disks || []).find((d) => d.mount === "/") || (m.disks || [])[0];
  $("#hh-stats").innerHTML = st === "online" ? [
    statBlock("CPU", m.cpu_pct != null ? Math.round(m.cpu_pct) + "%" : "—", m.cpu_pct),
    statBlock("RAM", m.mem?.total ? `${bytes(m.mem.used)}/${bytes(m.mem.total)}` : "—", m.mem?.pct),
    statBlock("Disk", disk ? `${bytes(disk.used)}/${bytes(disk.total)}` : "—", disk?.pct),
    statBlock("Load", (m.load || [])[0]?.toFixed(2) ?? "—",
              m.cpucount ? Math.min(100, (m.load?.[0] || 0) / m.cpucount * 100) : null),
    statBlock("Up", dur(m.uptime), null, "var(--foreground)"),
    statBlock("Age", age(m.age), null, "var(--magenta)"),
    statBlock("IP", esc(m.primary_ip || "—"), null, "var(--accent)"),
  ].join("") : `<div class="dim">${esc(h.state?.error || "not connected")}</div>`;

  const tun = h.vpn ? vpnById(h.vpn) : null;
  const hv = $("#hh-vpn");
  if (hv) {
    hv.hidden = !tun;
    if (tun) {
      const ts = vpnStatus(tun);
      // "up" and "carrying this host" are different questions; the routing
      // table answers the second one and the header reports what it said.
      const routed = h.vpn_routed !== false;
      hv.textContent = "⇅ " + tun.name + (ts !== "up"
        ? " · " + (VPN_LABEL[ts] || ts)
        : routed ? "" : " · not routing this host");
      hv.className = "hh-vpn " + (ts !== "up" ? "bad" : routed ? "ok" : "warn");
      hv.title = ts === "up"
        ? `${h.hostname} goes through ${tun.status?.iface || tun.name}`
        : `This host connects through ${tun.name}, which is ${VPN_LABEL[ts] || ts}`;
    }
  }

  const counts = h.counts || {};
  $("#n-apps").textContent = counts.package ? counts.package : "";
}

/* ─────────────────────────────── navigation ────────────────────────────── */

async function selectHost(id) {
  const changed = S.activeId !== id;
  S.activeId = id;
  if (changed) {
    FB.host = id; FB.path = "~"; FB.entries = []; FB.sel.clear();
    FB.df = null; FB.error = "";
  }
  $("#empty-state").hidden = true;
  $("#host-view").hidden = false;
  renderSidebar(); renderHead();
  wsSend({ type: "focus", host_id: id });
  api("focus", { method: "POST", body: { host_id: id } }).catch(() => {});
  if (!S.series[id]) loadSeries(id);
  renderPanel();
}

function setTab(tab) {
  if (document.activeElement && document.activeElement !== document.body)
    document.activeElement.blur();
  S.tab = tab;
  $$(".tab").forEach((t) => t.classList.toggle("active", t.dataset.tab === tab));
  $$(".panel").forEach((p) => { p.hidden = p.dataset.panel !== tab; });
  renderPanel();
  if (tab === "terminal") setTimeout(fitActiveTerm, 30);
}

function renderFilesTab(h) {
  if (!FB.entries.length && !FB.loading && !FB.error) return fbLoad(FB.host || h.id, FB.path);
  renderFiles();
}

function renderPanel() {
  const h = S.byId[S.activeId];
  if (!h) return;
  const fn = { overview: renderOverview, terminal: renderTerminal, apps: renderApps,
               files: renderFilesTab, commands: renderCommands,
               blueprint: renderBlueprints, events: renderEvents }[S.tab];
  if (!fn) return;
  try {
    const out = fn(h);
    if (out && typeof out.catch === "function") {
      out.catch((e) => { recordError("panel:" + S.tab, e); panelError(S.tab, e); });
    }
  } catch (e) {
    recordError("panel:" + S.tab, e);
    panelError(S.tab, e);
  }
}

function panelError(tab, e) {
  const p = $(`.panel[data-panel="${tab}"]`);
  if (!p) return;
  p.innerHTML = `<div class="empty"><div class="empty-inner">
    <div class="empty-glyph" style="color:var(--red)">!</div>
    <h1>This view failed to render</h1>
    <p>${esc((e && e.message) || String(e))}</p>
    <div class="empty-actions">
      <button class="primary-btn" id="panel-retry">Try again</button>
    </div></div></div>`;
  const b = $("#panel-retry");
  if (b) b.onclick = () => renderPanel();
}

async function loadSeries(id) {
  try {
    const r = await api(`hosts/${id}/series?n=120`);
    S.series[id] = r.series || [];
  } catch { S.series[id] = []; }
}

/* ──────────────────────────────── websocket ────────────────────────────── */

function wsSend(obj) {
  if (S.ws && S.ws.readyState === 1) S.ws.send(JSON.stringify(obj));
}

let wsRetry = 0;

function connectWS() {
  const ws = new WebSocket(`ws://${location.host}/ws/events?t=${TOKEN}`);
  S.ws = ws;
  ws.onopen = () => {
    wsRetry = 0;
    const d = $("#conn-dot");
    d.className = "dot dot-online";
    d.title = "Connected to the Fleet server";
    if (S.activeId) wsSend({ type: "focus", host_id: S.activeId });
  };
  ws.onclose = async (e) => {
    const d = $("#conn-dot");
    d.className = "dot dot-offline";
    d.title = `Server link closed (code ${e.code})`;

    // A window left open from an earlier run holds a token the current server
    // has never seen. Retrying that forever hammers the server with 401s, so
    // check once and stop for good if the token is dead.
    try {
      const res = await fetch(`/api/state?t=${TOKEN}`);
      if (res.status === 401) {
        d.title = "This window is from an earlier Fleet session";
        toast("This window belongs to an older Fleet session — reopen Fleet.", "err");
        return;
      }
    } catch { /* server down: fall through and keep retrying */ }

    wsRetry = Math.min(wsRetry + 1, 6);
    setTimeout(connectWS, Math.min(15000, 800 * 2 ** (wsRetry - 1)));
  };
  ws.onerror = () => { $("#conn-dot").title = "Server link error"; };
  ws.onmessage = (ev) => {
    const { type, data } = JSON.parse(ev.data);
    if (type === "metrics") {
      const h = S.byId[data.host_id];
      if (h) h.metrics = data.metrics;
      (S.series[data.host_id] ||= []).push({
        ts: Math.floor(Date.now() / 1000),
        cpu: data.metrics.cpu_pct, mem: data.metrics.mem?.pct,
        disk: data.metrics.disk_worst,
        rx: (data.metrics.nets || []).reduce((a, n) => a + (n.rx_bps || 0), 0),
        tx: (data.metrics.nets || []).reduce((a, n) => a + (n.tx_bps || 0), 0),
        load1: (data.metrics.load || [])[0],
      });
      if (S.series[data.host_id].length > 140) S.series[data.host_id].shift();
      renderSidebar();
      if (data.host_id === S.activeId) {
        renderHead();
        if (S.tab === "overview") renderOverview(S.byId[S.activeId]);
      }
    } else if (type === "hoststate") {
      const h = S.byId[data.host_id];
      if (h) h.state = data.state;
      renderSidebar();
      if (data.host_id === S.activeId) renderHead();
    } else if (type === "theme") {
      applyTheme(data);
    } else if (type === "hello") {
      applyTheme(data.theme);
      setHosts(data.hosts);
    } else if (type === "speedtest") {
      const h = S.byId[data.host_id];
      if (h) {
        h.speed_running = data.status === "running";
        if (data.result) h.speed = data.result;
      }
      if (data.status === "done" && data.result) {
        const r = data.result;
        toast(r.error ? `Speed test failed: ${r.error}`
          : `${h?.name}: ${mbps(r.down_bps)} down / ${mbps(r.up_bps)} up`,
          r.error ? "err" : "ok");
      }
      if (data.host_id === S.activeId && S.tab === "overview")
        renderOverview(S.byId[S.activeId]);
    } else if (type === "desktop") {
      S.desktop = data;
      applyBarInset();
    } else if (type === "filejob") {
      const i = FB.jobs.findIndex((j) => j.id === data.id);
      if (i >= 0) FB.jobs[i] = data; else FB.jobs = [data, ...FB.jobs].slice(0, 6);
      if (data.status === "done") {
        toast(`${data.label} — ${bytes(data.done)} in ${data.elapsed}s`, "ok");
        if (S.tab === "files") fbLoad(FB.host, FB.path);
      } else if (data.status === "error") {
        toast(`${data.label} failed: ${data.error}`, "err");
      }
      if (S.tab === "files") renderFiles();
    } else if (type === "vpnstate") {
      const v = vpnById(data.id);
      if (v) v.status = { ...(v.status || {}), ...data };
      renderVpnStrip();
      repaintVpnManager();
      // Bringing a tunnel up is asynchronous and often unattended, so a failure
      // has to announce itself — once per distinct message, not per poll.
      if (data.status === "error" && data.error) {
        if (S.vpnErr[data.id] !== data.error) {
          S.vpnErr[data.id] = data.error;
          toast(`${data.name || "VPN"}: ${data.error}`, "err");
        }
      } else {
        S.vpnErr[data.id] = "";
      }
      renderHead();
    } else if (type === "inventory") {
      const h = S.byId[data.host_id];
      if (h) h.counts = data.counts;
      renderHead();
    }
  };
}

function setHosts(hosts) {
  S.hosts = hosts;
  S.byId = Object.fromEntries(hosts.map((h) => [h.id, h]));
  if (!S.activeId && hosts.length) S.activeId = hosts[0].id;
  if (S.activeId && !S.byId[S.activeId]) S.activeId = hosts[0]?.id || null;
  renderSidebar();
  const has = hosts.length > 0;
  $("#empty-state").hidden = has;
  $("#host-view").hidden = !has;
  if (has) {
    renderHead();
    if (S.activeId && !S.series[S.activeId]) {
      loadSeries(S.activeId).then(renderPanel);
    }
    renderPanel();
  }
}

/* ─────────────────────────────── sparklines ────────────────────────────── */

function spark(values, color, { max = null, height = 34, fill = true } = {}) {
  const v = values.filter((x) => x != null && !isNaN(x));
  if (v.length < 2) return `<svg class="spark"></svg>`;
  const hi = max ?? Math.max(...v, 1);
  const w = 100, step = w / (v.length - 1);
  const pts = v.map((x, i) => [i * step, height - (x / hi) * (height - 3) - 1.5]);
  const line = pts.map((p, i) => `${i ? "L" : "M"}${p[0].toFixed(2)},${p[1].toFixed(2)}`).join("");
  const area = `${line}L${w},${height}L0,${height}Z`;
  const id = "g" + Math.random().toString(36).slice(2, 8);
  return `<svg class="spark" viewBox="0 0 ${w} ${height}" preserveAspectRatio="none">
    ${fill ? `<defs><linearGradient id="${id}" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="${color}" stop-opacity=".32"/>
      <stop offset="100%" stop-color="${color}" stop-opacity="0"/>
    </linearGradient></defs><path d="${area}" fill="url(#${id})"/>` : ""}
    <path d="${line}" fill="none" stroke="${color}" stroke-width="1.4"
          vector-effect="non-scaling-stroke" stroke-linejoin="round"/>
  </svg>`;
}

/* ──────────────────────────────── overview ─────────────────────────────── */

/* Pull a scan the server already holds, but never trigger a fresh one from
   here -- the Overview should not kick off a 3-second scan on every host you
   click. `counts` comes from the server's search index, so it tells us
   whether there is anything cached to show. */
function ensureCachedInventory(hostId) {
  if (S.inventory[hostId] !== undefined) return;
  if (!(S.byId[hostId]?.counts?.package)) return;
  S.inventory[hostId] = null;
  api(`hosts/${hostId}/inventory`).then((inv) => {
    S.inventory[hostId] = inv;
    if (hostId === S.activeId && (S.tab === "overview" || S.tab === "apps")) renderPanel();
  }).catch(() => { S.inventory[hostId] = {}; });
}

function renderOverview(h) {
  ensureCachedInventory(h.id);
  // Metrics repaint every few seconds. Blowing away innerHTML while someone is
  // dragging across an IP address to copy it is maddening, so hold off.
  const selection = window.getSelection();
  if (selection && !selection.isCollapsed &&
      $('.panel[data-panel="overview"]')?.contains(selection.anchorNode)) return;
  const p = $('.panel[data-panel="overview"]');
  const m = h.metrics || {};
  const st = h.state?.status;

  if (st !== "online") {
    p.innerHTML = `<div class="empty"><div class="empty-inner">
      <div class="empty-glyph">${esc(h.icon)}</div>
      <h1>${esc(h.name)} is ${esc(st || "not connected")}</h1>
      <p>${esc(h.state?.error || "No connection to this host.")}</p>
      <div class="empty-actions">
        <button class="primary-btn" onclick="reconnect()">Connect</button>
        <button class="ghost-btn" onclick="editHost('${h.id}')">Edit host</button>
      </div></div></div>`;
    return;
  }

  const s = S.series[h.id] || [];
  const inv = S.inventory[h.id];
  const disks = m.disks || [];
  const nets = m.nets || [];
  const rxs = s.map((x) => x.rx), txs = s.map((x) => x.tx);
  const netMax = Math.max(...rxs, ...txs, 1024);

  p.innerHTML = `
  <div class="grid grid-3" style="margin-bottom:12px">
    <div class="card">
      <h3>CPU <span class="h3-extra">${esc(m.cpucount || "?")} cores</span></h3>
      <div class="big-metric"><b style="color:${sev(m.cpu_pct)}">${
        m.cpu_pct != null ? Math.round(m.cpu_pct) : "—"}</b><span>%</span></div>
      <div class="dim" style="font-size:11px;margin-top:3px">
        load ${(m.load || []).map((x) => x.toFixed(2)).join("  ")}</div>
      ${spark(s.map((x) => x.cpu), sev(m.cpu_pct), { max: 100 })}
    </div>

    <div class="card">
      <h3>Memory <span class="h3-extra">${bytes(m.mem?.total)}</span></h3>
      <div class="big-metric"><b style="color:${sev(m.mem?.pct)}">${
        m.mem?.pct != null ? Math.round(m.mem.pct) : "—"}</b><span>%</span></div>
      <div class="dim" style="font-size:11px;margin-top:3px">
        ${bytes(m.mem?.used)} used${m.mem?.swap_total
          ? ` · swap ${bytes(m.mem.swap_used)}/${bytes(m.mem.swap_total)}` : ""}</div>
      ${spark(s.map((x) => x.mem), sev(m.mem?.pct), { max: 100 })}
    </div>

    <div class="card">
      <h3>Network</h3>
      <div class="big-metric" style="gap:14px">
        <span><b style="font-size:18px;color:var(--green)">↓${
          bytes(nets.reduce((a, n) => a + (n.rx_bps || 0), 0))}</b><span>/s</span></span>
        <span><b style="font-size:18px;color:var(--accent)">↑${
          bytes(nets.reduce((a, n) => a + (n.tx_bps || 0), 0))}</b><span>/s</span></span>
      </div>
      <div class="dim" style="font-size:11px;margin-top:3px">${
        nets.map((n) => esc(n.iface)).join(", ") || "—"}</div>
      ${spark(rxs, "var(--green)", { max: netMax })}
    </div>

    ${speedCard(h)}
  </div>

  <div class="grid grid-2">
    <div class="card">
      <h3>Storage</h3>
      <table class="tbl" style="table-layout:fixed"><thead><tr>
        <th style="width:28%">Mount</th><th style="width:22%">Device</th>
        <th class="num" style="width:16%">Used</th>
        <th class="num" style="width:16%">Size</th>
        <th class="num" style="width:18%">%</th></tr></thead>
      <tbody>${disks.map((d) => `<tr>
        <td title="${esc(d.mount)}">${esc(d.mount)}</td>
        <td class="dim" title="${esc(d.dev)}">${esc(d.dev)}</td>
        <td class="num">${bytes(d.used)}</td><td class="num">${bytes(d.total)}</td>
        <td class="num" style="color:${sev(d.pct)};font-weight:700">${d.pct}%</td>
      </tr>`).join("") || `<tr><td colspan="5" class="dim">no filesystems reported</td></tr>`}
      </tbody></table>
    </div>

    <div class="card">
      <h3>System</h3>
      <dl class="kv">
        <dt>OS</dt><dd>${esc(m.os || "—")}</dd>
        <dt>Kernel</dt><dd>${esc(m.kernel || "—")}</dd>
        <dt>Arch</dt><dd>${esc(m.arch || "—")}</dd>
        <dt>CPU</dt><dd>${esc(m.cpumodel || "—")}</dd>
        <dt>Virt</dt><dd>${esc(m.virt || "—")}</dd>
        <dt>Uptime</dt><dd>${dur(m.uptime)}</dd>
        <dt title="Age of the machine itself, from the root filesystem's creation time">
          Age</dt><dd>${age(m.age)}${m.born
          ? ` <span class="dim">· ${new Date(m.born * 1000).toLocaleDateString()}</span>` : ""}</dd>
        <dt>Processes</dt><dd>${esc(m.procs ?? "—")}</dd>
        <dt>Logged in</dt><dd>${esc(m.users ?? "—")}</dd>
        ${m.temp_c ? `<dt>Temp</dt><dd>${m.temp_c}°C</dd>` : ""}
        <dt>Hostname</dt><dd>${esc(m.host || "—")}</dd>
      </dl>
      <div style="margin-top:10px">
        ${(m.ip4 || []).filter((a) => !a.addr.startsWith("127.")).map((a) =>
          `<span class="chip">${esc(a.iface)} ${esc(a.addr)}</span>`).join("")}
        ${(m.ip6 || []).slice(0, 2).map((a) =>
          `<span class="chip">${esc(a.addr)}</span>`).join("")}
        ${m.gw ? `<span class="chip">gw ${esc(m.gw)}</span>` : ""}
      </div>
      ${m.reboot_required ? `<div class="warn" style="margin-top:8px">⚠ reboot required</div>` : ""}
    </div>

    <div class="card">
      <h3>Top processes <span class="h3-extra">by CPU</span></h3>
      <table class="tbl"><thead><tr><th>Command</th><th>User</th>
        <th class="num">CPU</th><th class="num">RSS</th></tr></thead>
      <tbody>${(m.top || []).slice(0, 8).map((t) => `<tr>
        <td>${esc(t.cmd)}</td><td class="dim">${esc(t.user)}</td>
        <td class="num" style="color:${sev(t.cpu)}">${t.cpu.toFixed(1)}%</td>
        <td class="num">${bytes(t.rss)}</td></tr>`).join("")}
      </tbody></table>
    </div>

    <div class="card">
      <h3>Listening ports <span class="h3-extra">${
        inv ? (inv.ports || []).length + " open" : inv === null ? "loading" : "not scanned"}</span></h3>
      ${inv === null ? `<div class="loading">loading cached scan…</div>` : inv ? `<table class="tbl"><thead><tr><th>Port</th><th>Proto</th>
        <th>Address</th><th>Process</th></tr></thead><tbody>${
        (inv.ports || []).slice(0, 12).map((x) => `<tr>
          <td style="color:var(--accent);font-weight:600">${esc(x.port)}</td>
          <td class="dim">${esc(x.proto)}</td><td class="dim">${esc(x.addr)}</td>
          <td>${esc(x.proc || "—")}</td></tr>`).join("")
        }</tbody></table>`
        : `<div class="loading">Scan this host to see open ports.<br><br>
           <button class="ghost-btn" onclick="setTab('apps')">Scan now</button></div>`}
    </div>
  </div>`;
}

/* ─────────────────────────────── speed card ────────────────────────────── */

const mbps = (bps) => bps >= 1e9 ? (bps / 1e9).toFixed(2) + " Gbps"
  : bps >= 1e6 ? (bps / 1e6).toFixed(1) + " Mbps"
  : bps > 0 ? (bps / 1e3).toFixed(0) + " Kbps" : "—";

function speedCard(h) {
  const sp = h.speed;
  const busy = !!h.speed_running;
  return `<div class="card speed-card">
    <h3>Internet speed
      <span class="h3-extra">${sp?.source ? "via " + esc(sp.source) : "on this server"}</span></h3>
    ${busy ? `<div class="speed-busy">
        <span class="spin"></span> testing… <span class="dim">this takes under a minute</span>
      </div>`
    : sp && !sp.error ? `
      <div class="speed-nums">
        <span><b style="color:var(--green)">↓ ${mbps(sp.down_bps)}</b></span>
        <span><b style="color:var(--accent)">↑ ${mbps(sp.up_bps)}</b></span>
      </div>
      <div class="dim" style="font-size:11px;margin-top:4px">
        ${sp.latency_ms != null ? `${sp.latency_ms} ms` : ""}${sp.colo ? ` · edge ${esc(sp.colo)}` : ""}${
          sp.ip ? ` · ${esc(sp.ip)}` : ""}${sp.partial ? ` · <span class="warn">capped</span>` : ""}
      </div>
      <div class="dim" style="font-size:10.5px;margin-top:2px">
        checked ${ago(sp.ts)} · ${bytes(sp.bytes_down)} down</div>`
    : sp && sp.error ? `<div class="bad" style="font-size:11.5px">${esc(sp.error)}</div>
        <div class="dim" style="font-size:10.5px;margin-top:2px">tried ${ago(sp.ts)}</div>`
    : `<div class="dim" style="font-size:11.5px">Not measured yet.<br>
        Runs on the server, not this machine.</div>`}
    <div class="speed-run">
      <button class="ghost-btn sm" id="speed-go" ${busy ? "disabled" : ""}>
        ${busy ? "running…" : sp ? "run again" : "run test"}</button>
      <select class="fb-loc" id="speed-preset" ${busy ? "disabled" : ""}
              title="How much data the test transfers">
        <option value="quick">quick · 14MB</option>
        <option value="normal" selected>normal · 29MB</option>
        <option value="thorough">thorough · 104MB</option>
      </select>
    </div>
  </div>`;
}

async function runSpeedTest() {
  const h = S.byId[S.activeId];
  if (!h || h.speed_running) return;
  const preset = $("#speed-preset")?.value || "normal";
  h.speed_running = true;
  renderOverview(h);
  try {
    await api(`hosts/${h.id}/speedtest`, { method: "POST", body: { preset } });
  } catch (e) {
    h.speed_running = false; toast(e.message, "err"); renderOverview(h);
  }
}

/* ──────────────────────────────── terminal ─────────────────────────────── */

function renderTerminal(h) {
  const bar = $("#term-tabs");
  const mine = S.sessions.filter((s) => s.host_id === h.id);
  if (!mine.length) { newTerm(h.id); return; }
  if (!S.activeTerm[h.id] || !mine.find((s) => s.id === S.activeTerm[h.id]))
    S.activeTerm[h.id] = mine[0].id;

  bar.innerHTML = mine.map((s) => `
    <div class="term-tab ${s.id === S.activeTerm[h.id] ? "active" : ""}" data-sid="${s.id}">
      <span>${esc(s.title || "shell")}</span>
      <span class="x" data-close="${s.id}">✕</span>
    </div>`).join("");

  $$(".term-tab", bar).forEach((el) => {
    el.onclick = (e) => {
      if (e.target.dataset.close) { closeTerm(e.target.dataset.close); return; }
      S.activeTerm[h.id] = el.dataset.sid;
      renderTerminal(h);
    };
  });

  const host = $("#term-host");
  for (const s of mine) if (!S.terms[s.id]) mountTerm(s, host);
  for (const [sid, t] of Object.entries(S.terms)) {
    const visible = sid === S.activeTerm[h.id];
    t.el.hidden = !visible;
    if (visible) setTimeout(() => { t.fit.fit(); t.term.focus(); }, 10);
  }
}

function mountTerm(sess, host) {
  const el = document.createElement("div");
  el.className = "term-instance";
  host.appendChild(el);

  const term = new Terminal({
    fontFamily: getComputedStyle(document.body).getPropertyValue("--mono"),
    fontSize: S.settings.font_size || 13,
    theme: termTheme(), cursorBlink: true, scrollback: 10000,
    allowProposedApi: true, macOptionIsMeta: true,
  });
  const fit = new FitAddon.FitAddon();
  term.loadAddon(fit);
  try {
    // Open links in a fresh, unlinked context: noreferrer also severs
    // window.opener, so a page opened from a terminal cannot reach back.
    term.loadAddon(new WebLinksAddon.WebLinksAddon((event, uri) => {
      window.open(uri, "_blank", "noopener,noreferrer");
    }));
  } catch { /* links stay plain text if the addon is unavailable */ }
  term.open(el);
  fit.fit();

  const ws = new WebSocket(`ws://${location.host}/ws/term/${sess.id}?t=${TOKEN}`);
  ws.binaryType = "arraybuffer";
  ws.onmessage = (ev) => {
    if (typeof ev.data === "string") return;
    term.write(new Uint8Array(ev.data));
  };
  ws.onopen = () => ws.send(JSON.stringify({ t: "size", cols: term.cols, rows: term.rows }));
  ws.onclose = () => term.write("\r\n\x1b[38;5;244m[disconnected]\x1b[0m\r\n");

  term.onData((d) => { if (ws.readyState === 1) ws.send(new TextEncoder().encode(d)); });
  term.onResize(({ cols, rows }) => {
    if (ws.readyState === 1) ws.send(JSON.stringify({ t: "size", cols, rows }));
  });

  S.terms[sess.id] = { term, fit, ws, el, sess };
  new ResizeObserver(() => { if (!el.hidden) try { fit.fit(); } catch {} }).observe(el);
}

function fitActiveTerm() {
  const sid = S.activeTerm[S.activeId];
  const t = S.terms[sid];
  if (t) try { t.fit.fit(); t.term.focus(); } catch {}
}

async function newTerm(hostId, command, title) {
  const el = $("#term-host");
  const cols = Math.max(40, Math.floor(el.clientWidth / 8.4)) || 100;
  const rows = Math.max(10, Math.floor(el.clientHeight / 18)) || 30;
  try {
    const s = await api("sessions", { method: "POST",
      body: { host_id: hostId, cols, rows, command, title } });
    S.sessions.push(s);
    S.activeTerm[hostId] = s.id;
    if (S.tab !== "terminal") setTab("terminal"); else renderTerminal(S.byId[hostId]);
  } catch (e) { toast(e.message, "err"); }
}

async function closeTerm(sid) {
  const t = S.terms[sid];
  if (t) { try { t.ws.close(); t.term.dispose(); t.el.remove(); } catch {} delete S.terms[sid]; }
  S.sessions = S.sessions.filter((s) => s.id !== sid);
  api(`sessions/${sid}`, { method: "DELETE" }).catch(() => {});
  renderTerminal(S.byId[S.activeId]);
}

/* ────────────────────────────────── apps ───────────────────────────────── */

const APP_VIEWS = ["packages", "services", "docker", "runtimes", "ports"];
let appView = "packages", appFilter = "";

async function loadInventory(hostId, refresh = false) {
  const p = $('.panel[data-panel="apps"]');
  S.inventory[hostId] = null;               // "in flight", not "never fetched"
  p.innerHTML = `<div class="loading">${refresh ? "Scanning" : "Loading"} ${
    esc(S.byId[hostId].name)}… <br><span class="dim">packages, services, ports,
    containers, runtimes</span></div>`;
  try {
    S.inventory[hostId] = await api(
      `hosts/${hostId}/inventory${refresh ? "?refresh=1" : ""}`, { timeout: 240000 });
    if (refresh) toast(`Scanned ${S.byId[hostId].name}`, "ok");
  } catch (e) { toast(e.message, "err"); S.inventory[hostId] = {}; }
  renderApps(S.byId[hostId]);
}

function renderApps(h) {
  const p = $('.panel[data-panel="apps"]');
  const inv = S.inventory[h.id];

  // Never fetched on this page load: pull it. The server answers from its
  // cache unless the scan has gone stale, so this is usually instant -- and
  // the tab badge already told us there is something to show.
  if (inv === undefined) {
    if (h.state?.status === "online") { loadInventory(h.id, false); return; }
    p.innerHTML = `<div class="loading">Host is not connected.</div>`;
    return;
  }
  if (inv === null) { return; }              // fetch in flight; it re-renders

  if (!inv.packages && !inv.services) {
    if (h.state?.status !== "online") {
      p.innerHTML = `<div class="loading">Host is not connected.</div>`;
      return;
    }
    p.innerHTML = `<div class="empty"><div class="empty-inner">
      <div class="empty-glyph">⌸</div><h1>Nothing scanned yet</h1>
      <p>Fleet reads the package list, services, containers, open ports and
         language runtimes over the connection you already have.</p>
      <button class="primary-btn" onclick="loadInventory('${h.id}', true)">Scan ${esc(h.name)}</button>
    </div></div>`;
    return;
  }

  const rows = {
    packages: inv.packages || [], services: inv.services || [],
    docker: inv.docker || [], runtimes: inv.runtimes || [], ports: inv.ports || [],
  };
  const f = appFilter.toLowerCase();
  const match = (o) => !f || JSON.stringify(o).toLowerCase().includes(f);
  const shown = rows[appView].filter(match);
  const manual = new Set(inv.manual || []);

  const tables = {
    packages: () => `<table class="tbl"><thead><tr><th>Package</th><th>Version</th>
        <th>Description</th><th></th></tr></thead><tbody>${
      shown.slice(0, 600).map((x) => `<tr>
        <td style="font-weight:600">${esc(x.name)}${
          manual.has(x.name) ? ` <span class="chip on">explicit</span>` : ""}</td>
        <td class="dim">${esc(x.version)}</td>
        <td class="dim">${esc((x.desc || "").slice(0, 70))}</td>
        <td class="num"><button class="ghost-btn sm"
          onclick="pkgAction('remove', ['${esc(x.name)}'])">remove</button></td>
      </tr>`).join("")}</tbody></table>`,

    services: () => `<table class="tbl"><thead><tr><th>Service</th><th>State</th>
        <th>Description</th><th></th></tr></thead><tbody>${
      shown.slice(0, 400).map((x) => `<tr>
        <td style="font-weight:600">${esc(x.name)}</td>
        <td><span class="chip ${x.active === "active" ? "on" : ""}">${esc(x.active)}</span>
            <span class="dim">${esc(x.sub)}</span></td>
        <td class="dim">${esc((x.desc || "").slice(0, 60))}</td>
        <td class="num">
          <button class="ghost-btn sm" onclick="svcAction('${esc(x.name)}','restart')">restart</button>
          <button class="ghost-btn sm" onclick="svcAction('${esc(x.name)}','status')">status</button>
        </td></tr>`).join("")}</tbody></table>`,

    docker: () => shown.length ? `<table class="tbl"><thead><tr><th>Container</th>
        <th>Image</th><th>Status</th><th>Ports</th></tr></thead><tbody>${
      shown.map((x) => `<tr><td style="font-weight:600">${esc(x.name)}</td>
        <td class="dim">${esc(x.image)}</td>
        <td class="${/^Up/.test(x.status) ? "ok" : "dim"}">${esc(x.status)}</td>
        <td class="dim">${esc(x.ports)}</td></tr>`).join("")}</tbody></table>`
      : `<div class="loading">No containers — docker is not installed or has none.</div>`,

    runtimes: () => `<table class="tbl"><thead><tr><th>Tool</th><th>Version</th>
        <th>Path</th></tr></thead><tbody>${
      shown.map((x) => `<tr><td style="font-weight:600;color:var(--accent)">${esc(x.name)}</td>
        <td>${esc(x.version || "—")}</td><td class="dim">${esc(x.path)}</td></tr>`).join("")
      }</tbody></table>`,

    ports: () => `<table class="tbl"><thead><tr><th>Port</th><th>Proto</th>
        <th>Address</th><th>State</th><th>Process</th></tr></thead><tbody>${
      shown.map((x) => `<tr><td style="font-weight:700;color:var(--accent)">${esc(x.port)}</td>
        <td class="dim">${esc(x.proto)}</td><td class="dim">${esc(x.addr)}</td>
        <td class="dim">${esc(x.state)}</td><td>${esc(x.proc || "—")}</td></tr>`).join("")
      }</tbody></table>`,
  };

  p.innerHTML = `
    <div class="toolbar">
      ${APP_VIEWS.map((v) => `<button class="ghost-btn sm ${v === appView ? "primary-btn" : ""}"
        onclick="appView='${v}';renderApps(S.byId['${h.id}'])">${v}
        <span class="dim">${rows[v].length}</span></button>`).join("")}
      <input class="search-input" style="flex:1;min-width:160px" placeholder="filter ${appView}…"
             value="${esc(appFilter)}" oninput="appFilter=this.value;renderApps(S.byId['${h.id}'])">
      <span class="chip">${esc(inv.pkgmgr || "?")}</span>
      ${inv.updates ? `<span class="chip" style="color:var(--yellow)">${inv.updates} updates</span>` : ""}
      <button class="ghost-btn sm" onclick="installPrompt()">+ install</button>
      <button class="ghost-btn sm" onclick="pkgAction('update')">upgrade all</button>
      <button class="ghost-btn sm" onclick="loadInventory('${h.id}', true)">rescan</button>
      <span class="dim" style="font-size:10.5px">scanned ${ago(inv.collected)}</span>
    </div>
    <div class="card" style="padding:0;overflow:auto;max-height:calc(100vh - 230px)">
      ${tables[appView]()}
    </div>
    ${shown.length > 600 ? `<div class="dim" style="margin-top:8px">
       showing first 600 of ${shown.length} — narrow the filter to see more</div>` : ""}`;
}

async function pkgAction(action, pkgs) {
  const h = S.byId[S.activeId];
  try {
    const r = await api(`hosts/${h.id}/pkg`, { method: "POST",
      body: { action, pkgs, cols: 110, rows: 32 } });
    S.sessions.push(r.session);
    S.activeTerm[h.id] = r.session.id;
    setTab("terminal");
    toast(`Running: ${action} ${(pkgs || []).join(" ")}`);
  } catch (e) { toast(e.message, "err"); }
}

function installPrompt() {
  openModal("Install packages", `
    <div class="field"><label>Packages (space separated)</label>
      <input id="ip-pkgs" class="text-input mono" placeholder="nginx htop ripgrep" autofocus></div>
    <div class="hint dim">Runs in a live terminal on <b>${esc(S.byId[S.activeId].name)}</b>
      via ${esc(S.inventory[S.activeId]?.pkgmgr || "the detected package manager")}.</div>`,
    [{ label: "Install", primary: true, fn: () => {
        const v = $("#ip-pkgs").value.trim().split(/\s+/).filter(Boolean);
        if (v.length) { closeModal(); pkgAction("install", v); }
    } }]);
}

async function svcAction(name, action) {
  const h = S.byId[S.activeId];
  try {
    const r = await api(`hosts/${h.id}/service`, { method: "POST", body: { name, action } });
    openModal(`${action} ${name}`,
      `<pre class="out-pre">${esc((r.stdout || "") + (r.stderr || "") || "(no output)")}</pre>`,
      []);
    if (action !== "status") loadInventory(h.id, true);
  } catch (e) { toast(e.message, "err"); }
}

/* ─────────────────────────────── commands ──────────────────────────────── */

async function renderCommands(h) {
  const p = $('.panel[data-panel="commands"]');
  p.innerHTML = `<div class="loading">Loading…</div>`;
  let d;
  try { d = await api(`hosts/${h.id}/commands`); }
  catch (e) { p.innerHTML = `<div class="loading">${esc(e.message)}</div>`; return; }
  S.snippets = d.snippets || [];

  p.innerHTML = `
    <div class="card" style="margin-bottom:12px">
      <h3>Run a command <span class="h3-extra">↵ to run · shift+↵ for newline</span></h3>
      <textarea id="cmd-box" class="text-input mono" rows="2"
        placeholder="systemctl status nginx"></textarea>
      <div class="toolbar" style="margin:10px 0 0">
        <button class="primary-btn" onclick="runCmd()">Run on ${esc(h.name)}</button>
        <button class="ghost-btn" onclick="fanoutPrompt()">Run on many hosts…</button>
        <button class="ghost-btn" onclick="saveSnippetPrompt()">Save as snippet</button>
        <button class="ghost-btn" onclick="newTerm('${h.id}', $('#cmd-box').value || undefined)">
          Open in terminal</button>
      </div>
      <div id="cmd-out"></div>
    </div>

    <div class="grid grid-2">
      <div class="card">
        <h3>Frequently used on this host
          <span class="h3-extra">mined from shell history + your runs</span></h3>
        ${(d.top || []).length ? `<div class="list-pane" style="max-height:300px">${
          d.top.map((c, i) => `<div class="pick-row" data-top="${i}">
            <span style="overflow:hidden;text-overflow:ellipsis">${esc(c.cmd)}</span>
            <span class="chip">${esc(String(c.count))}×${
              c.source === "fleet" ? " here" : ""}</span>
          </div>`).join("")}</div>`
          : `<div class="dim">No history mined yet — scan this host from the Apps tab.</div>`}
      </div>

      <div class="card">
        <h3>Snippets <span class="h3-extra">shared across every host</span></h3>
        ${S.snippets.length ? `<div class="list-pane" style="max-height:300px">${
          S.snippets.map((sn, i) => `<div class="pick-row">
            <span data-snip="${i}" style="flex:1;overflow:hidden;text-overflow:ellipsis">
              <b>${esc(sn.name)}</b>
              <span class="dim">${esc(sn.command.slice(0, 46))}</span></span>
            <span class="icon-btn" data-snip-del="${esc(sn.id)}">✕</span>
          </div>`).join("")}</div>`
          : `<div class="dim">No snippets yet. Save a command you keep retyping.</div>`}
      </div>

      <div class="card" style="grid-column:1/-1">
        <h3>Recent runs</h3>
        <table class="tbl"><thead><tr><th>Command</th><th>Host</th>
          <th class="num">rc</th><th class="num">time</th><th class="num">when</th></tr></thead>
        <tbody>${(d.runs || []).map((r) => `<tr data-run="${esc(r.id)}" style="cursor:pointer">
          <td>${esc(r.command)}</td>
          <td class="dim">${esc(S.byId[r.host_id]?.name || r.host_id)}</td>
          <td class="num ${r.rc === 0 ? "ok" : "bad"}">${r.rc}</td>
          <td class="num dim">${r.duration_ms}ms</td>
          <td class="num dim">${ago(r.started)}</td></tr>`).join("")
          || `<tr><td colspan="5" class="dim">nothing yet</td></tr>`}
        </tbody></table>
      </div>
    </div>`;

  // Bound as listeners rather than inline handlers: these strings come from a
  // remote host's shell history, and interpolating them into an attribute is
  // exactly the shape that eventually breaks on a quote or an angle bracket.
  const panel = $('.panel[data-panel="commands"]');
  const tops = d.top || [];
  $$("[data-top]", panel).forEach((el) =>
    el.onclick = () => useCmd(tops[+el.dataset.top].cmd));
  $$("[data-snip]", panel).forEach((el) =>
    el.onclick = () => useCmd(S.snippets[+el.dataset.snip].command));
  $$("[data-snip-del]", panel).forEach((el) =>
    el.onclick = () => delSnippet(el.dataset.snipDel));
  $$("[data-run]", panel).forEach((el) =>
    el.onclick = () => showRun(el.dataset.run));

  const box = $("#cmd-box");
  box.onkeydown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); runCmd(); }
    if (e.key === "Escape") { e.preventDefault(); box.blur(); }
  };
  // Deliberately not focused on render: an auto-focused field swallows every
  // single-key shortcut. Press `i` (or click) to start typing.
}

function useCmd(c) { const b = $("#cmd-box"); if (b) { b.value = c; b.focus(); } }

async function runCmd() {
  const cmd = $("#cmd-box").value.trim();
  if (!cmd) return;
  const out = $("#cmd-out");
  out.innerHTML = `<div class="loading">running…</div>`;
  try {
    const r = await api(`hosts/${S.activeId}/run`, { method: "POST", body: { command: cmd } });
    out.innerHTML = `<div style="margin-top:10px">
      <div class="dim" style="font-size:11px;margin-bottom:5px">
        exit <b class="${r.rc === 0 ? "ok" : "bad"}">${r.rc}</b> · ${r.ms}ms</div>
      <pre class="out-pre">${esc((r.stdout || "") + (r.stderr || "") || "(no output)")}</pre></div>`;
  } catch (e) { out.innerHTML = `<div class="bad">${esc(e.message)}</div>`; }
}

async function showRun(id) {
  try {
    const r = await api(`runs/${id}`);
    openModal(r.command, `
      <div class="dim" style="font-size:11px;margin-bottom:6px">
        ${esc(S.byId[r.host_id]?.name || r.host_id)} ·
        exit <b class="${r.rc === 0 ? "ok" : "bad"}">${r.rc}</b> ·
        ${r.duration_ms}ms · ${ago(r.started)}</div>
      <pre class="out-pre" style="max-height:400px">${esc(r.output || "(no output)")}</pre>`,
      [{ label: "Run again", fn: () => { closeModal(); useCmd(r.command); runCmd(); } },
       { label: "Copy", fn: () => copyText(r.command) }]);
  } catch (e) { toast(e.message, "err"); }
}

function saveSnippetPrompt() {
  const cmd = $("#cmd-box").value.trim();
  if (!cmd) { toast("Nothing to save", "err"); return; }
  openModal("Save snippet", `
    <div class="field"><label>Name</label>
      <input id="sn-name" class="text-input" placeholder="restart web stack" autofocus></div>
    <div class="field"><label>Command</label>
      <textarea id="sn-cmd" class="text-input mono" rows="3">${esc(cmd)}</textarea></div>`,
    [{ label: "Save", primary: true, fn: async () => {
      await api("snippets", { method: "POST",
        body: { name: $("#sn-name").value || cmd.slice(0, 30), command: $("#sn-cmd").value } });
      closeModal(); toast("Snippet saved", "ok"); renderCommands(S.byId[S.activeId]);
    } }]);
}

async function delSnippet(id) {
  await api(`snippets/${id}`, { method: "DELETE" });
  renderCommands(S.byId[S.activeId]);
}

function fanoutPrompt() {
  const cmd = $("#cmd-box").value.trim();
  if (!cmd) { toast("Type a command first", "err"); return; }
  openModal("Run on multiple hosts", `
    <div class="field"><label>Command</label>
      <pre class="out-pre" style="max-height:90px">${esc(cmd)}</pre></div>
    <div class="field"><label>Hosts</label>
      <div id="fan-hosts">${S.hosts.map((h) => `
        <label class="pick-row" style="cursor:pointer">
          <span><input type="checkbox" value="${h.id}"
            ${h.state?.status === "online" ? "checked" : ""}> ${esc(h.icon)} ${esc(h.name)}</span>
          <span class="dot dot-${esc(h.state?.status || "idle")}"></span></label>`).join("")}</div>
    </div>
    <div id="fan-out"></div>`,
    [{ label: "Run", primary: true, fn: async () => {
      const ids = $$("#fan-hosts input:checked").map((i) => i.value);
      if (!ids.length) return;
      $("#fan-out").innerHTML = `<div class="loading">running on ${ids.length} hosts…</div>`;
      const r = await api("fanout", { method: "POST",
        body: { command: cmd, host_ids: ids }, timeout: 180000 });
      $("#fan-out").innerHTML = Object.entries(r.results).map(([id, x]) => `
        <div style="margin-top:10px"><div style="font-size:11px">
          <b>${esc(x.name)}</b> <span class="${x.rc === 0 ? "ok" : "bad"}">exit ${x.rc}</span>
          <span class="dim">· ${x.ms}ms</span></div>
        <pre class="out-pre" style="max-height:150px">${
          esc(((x.stdout || "") + (x.stderr || "")).trim() || "(no output)")}</pre></div>`).join("");
    } }]);
}

/* ─────────────────────────────── blueprints ────────────────────────────── */

const BP_CATS = ["packages", "docker_images", "runtimes", "services",
                 "npm_global", "pip_user", "cargo", "compose"];
let bpSelected = null, bpPlan = null;

async function renderBlueprints(h) {
  const p = $('.panel[data-panel="blueprint"]');
  try { S.blueprints = (await api("blueprints")).blueprints || []; }
  catch (e) { p.innerHTML = `<div class="loading">${esc(e.message)}</div>`; return; }

  const bp = S.blueprints.find((b) => b.id === bpSelected) || S.blueprints[0];
  bpSelected = bp?.id || null;

  p.innerHTML = `
  <div class="toolbar">
    <button class="primary-btn" onclick="captureBlueprint()">
      ⎘ Capture from ${esc(h.name)}</button>
    <span class="dim">A blueprint records what a host <i>has</i> — packages, images,
      globals, services — so another host can be brought up to match it.</span>
  </div>
  <div class="split">
    <div class="card list-pane">
      <h3>Blueprints <span class="h3-extra">${S.blueprints.length}</span></h3>
      ${S.blueprints.map((b) => `
        <div class="pick-row ${b.id === bpSelected ? "sel" : ""}"
             onclick="bpSelected='${b.id}';bpPlan=null;renderBlueprints(S.byId['${h.id}'])">
          <span style="overflow:hidden"><b>${esc(b.name)}</b><br>
            <span class="dim" style="font-size:10.5px">from ${esc(b.source_name)} · ${ago(b.created)}</span>
          </span>
          <span class="icon-btn" onclick="event.stopPropagation();delBlueprint('${b.id}')">✕</span>
        </div>`).join("") || `<div class="dim">None yet.</div>`}
    </div>
    <div id="bp-detail" class="card" style="overflow:auto"></div>
  </div>`;

  if (bp) renderBlueprintDetail(bp, h);
  else $("#bp-detail").innerHTML =
    `<div class="loading">Capture a blueprint to get started.</div>`;
}

function renderBlueprintDetail(bp, h) {
  const s = bp.spec || {};
  const counts = BP_CATS.map((c) => [c, (s[c] || []).length]).filter(([, n]) => n);
  const targets = S.hosts.filter((x) => x.id !== bp.source_host);

  $("#bp-detail").innerHTML = `
    <h3>${esc(bp.name)}
      <span class="h3-extra">captured from ${esc(bp.source_name)} · ${esc(s.source_os || "")}</span></h3>
    <div style="margin-bottom:12px">${counts.map(([c, n]) =>
      `<span class="chip">${esc(c.replace("_", " "))} <b>${n}</b></span>`).join("")}</div>

    <div class="field"><label>Apply to</label>
      <div class="row">
        <select id="bp-target" class="text-input">
          ${targets.map((t) => `<option value="${t.id}">${esc(t.icon)} ${esc(t.name)}
            — ${esc(t.hostname)}</option>`).join("")
            || `<option value="">no other hosts configured</option>`}
        </select>
        <button class="ghost-btn" style="flex:0 0 auto" onclick="planBlueprint('${bp.id}')">
          Preview changes</button>
      </div>
      <div class="hint">Nothing runs until you have seen the diff and the script.</div>
    </div>

    <div class="field"><label>Include</label>
      <div style="display:flex;flex-wrap:wrap;gap:10px">${BP_CATS.map((c) =>
        `<label style="font-size:11.5px"><input type="checkbox" class="bp-cat" value="${c}"
          ${(s[c] || []).length ? "checked" : ""}> ${esc(c.replace("_", " "))}</label>`).join("")}</div>
    </div>
    <div id="bp-plan"></div>`;
}

async function captureBlueprint() {
  const h = S.byId[S.activeId];
  openModal(`Capture blueprint from ${h.name}`, `
    <div class="field"><label>Name</label>
      <input id="bp-name" class="text-input" value="${esc(h.name)} baseline" autofocus></div>
    <div class="field">
      <label><input type="checkbox" id="bp-manual" checked> Explicitly-installed packages only</label>
      <div class="hint">Recommended. Skips the dependency closure, so the blueprint stays
        readable and portable to a different distro.</div>
    </div>
    <div class="hint dim">Reads the cached scan if there is one, otherwise scans now.</div>`,
    [{ label: "Capture", primary: true, fn: async () => {
      const name = $("#bp-name").value, manual = $("#bp-manual").checked;
      closeModal();
      toast("Capturing…");
      try {
        const bp = await api("blueprints/capture", { method: "POST",
          body: { host_id: h.id, name, manual_only: manual }, timeout: 240000 });
        bpSelected = bp.id; bpPlan = null;
        toast(`Captured ${bp.name}`, "ok");
        renderBlueprints(h);
      } catch (e) { toast(e.message, "err"); }
    } }]);
}

async function delBlueprint(id) {
  await api(`blueprints/${id}`, { method: "DELETE" });
  if (bpSelected === id) bpSelected = null;
  renderBlueprints(S.byId[S.activeId]);
}

async function planBlueprint(id) {
  const target = $("#bp-target").value;
  if (!target) { toast("No target host", "err"); return; }
  const cats = $$(".bp-cat:checked").map((c) => c.value);
  const out = $("#bp-plan");
  out.innerHTML = `<div class="loading">Scanning target and diffing…</div>`;
  try {
    bpPlan = await api(`blueprints/${id}/plan`, { method: "POST",
      body: { target, categories: cats }, timeout: 240000 });
  } catch (e) { out.innerHTML = `<div class="bad">${esc(e.message)}</div>`; return; }

  const sum = bpPlan.plan._summary || {};
  const total = Object.values(sum).reduce((a, b) => a + b, 0);
  out.innerHTML = `
    <div class="card" style="background:var(--darker-background);margin-top:6px">
      <h3>Plan for ${esc(bpPlan.target)}
        <span class="h3-extra">${esc(bpPlan.target_os)} · ${esc(bpPlan.target_pkgmgr)}</span></h3>
      ${total === 0 ? `<div class="ok">Target already matches this blueprint. Nothing to do.</div>`
      : `<div style="margin-bottom:10px">${Object.entries(sum).filter(([, n]) => n).map(([k, n]) =>
          `<span class="chip" style="color:var(--yellow)">+${n} ${esc(k.replace("_", " "))}</span>`
        ).join("")}</div>
      ${Object.entries(bpPlan.plan).filter(([k]) => !k.startsWith("_"))
        .filter(([, v]) => v.missing?.length).map(([k, v]) => `
        <details style="margin-bottom:6px"><summary style="cursor:pointer;font-size:11.5px">
          <b>${esc(k.replace("_", " "))}</b> <span class="dim">${v.missing.length} to add,
          ${v.present.length} already there</span></summary>
          <div style="padding:6px 0 2px">${v.missing.slice(0, 200).map((x) =>
            `<span class="chip">${esc(typeof x === "string" ? x : x.name)}</span>`).join("")}</div>
        </details>`).join("")}
      <div class="field" style="margin-top:12px"><label>Generated script</label>
        <pre class="out-pre" style="max-height:220px">${esc(bpPlan.script)}</pre></div>
      <div class="toolbar" style="margin:0">
        <button class="primary-btn" id="bp-apply">
          Apply to ${esc(bpPlan.target)}</button>
        <button class="ghost-btn" id="bp-copy">Copy script</button>
        <span class="dim">Runs in a live terminal — you can watch it and Ctrl-C.</span>
      </div>`}
    </div>`;

  const cp = $("#bp-copy");
  if (cp) cp.onclick = () => copyText(bpPlan.script);
  const ap = $("#bp-apply");
  if (ap) ap.onclick = () => applyBlueprint(id);
}

async function applyBlueprint(id) {
  const target = $("#bp-target").value;
  try {
    const r = await api(`blueprints/${id}/apply`, { method: "POST",
      body: { target, script: bpPlan.script, cols: 110, rows: 32 } });
    S.sessions.push(r.session);
    S.activeTerm[target] = r.session.id;
    await selectHost(target);
    setTab("terminal");
  } catch (e) { toast(e.message, "err"); }
}

function copyText(t) {
  navigator.clipboard.writeText(t).then(() => toast("Copied", "ok"),
    () => toast("Copy failed", "err"));
}

/* ──────────────────────────────── activity ─────────────────────────────── */

async function renderEvents() {
  const p = $('.panel[data-panel="events"]');
  try {
    const d = await api("events?n=100");
    p.innerHTML = `<div class="card"><h3>Activity</h3>
      <table class="tbl"><thead><tr><th class="num">When</th><th>Host</th>
        <th>Level</th><th>Message</th></tr></thead><tbody>${
      (d.events || []).map((e) => `<tr>
        <td class="num dim">${ago(e.ts)}</td>
        <td>${esc(S.byId[e.host_id]?.name || e.host_id || "—")}</td>
        <td class="${e.level === "warn" ? "warn" : "dim"}">${esc(e.level)}</td>
        <td>${esc(e.message)}</td></tr>`).join("")
        || `<tr><td colspan="4" class="dim">nothing yet</td></tr>`}
      </tbody></table></div>`;
  } catch (e) { p.innerHTML = `<div class="loading">${esc(e.message)}</div>`; }
}

/* ───────────────────────────── command palette ─────────────────────────── */

const KIND_GLYPH = { package: "▣", service: "⚙", port: "⇄", container: "◫",
                     image: "▤", runtime: "λ", user: "☺", compose: "⧉",
                     host: "⬢", command: "⚡", snippet: "★" };
let palIndex = 0, palResults = [], palTimer = null;

function openPalette(prefill = "") {
  $("#palette").hidden = false;
  const q = $("#palette-q");
  q.value = prefill; q.focus(); q.select();
  paletteSearch(prefill);
}
function closePalette() { $("#palette").hidden = true; }

async function paletteSearch(term) {
  term = term.trim();

  // A leading ">" switches the palette from "find things" to "do things".
  if (term.startsWith(">")) {
    const cmd = term.slice(1).trim();
    palResults = cmd ? [
      { _act: "run", name: cmd, detail: `Run on ${S.byId[S.activeId]?.name || "—"}`, kind: "command" },
      { _act: "runall", name: cmd, detail: `Run on all ${S.hosts.length} hosts`, kind: "command" },
      { _act: "term", name: cmd, detail: "Open in a new terminal", kind: "command" },
    ] : [];
    return paletteRender();
  }

  const hostHits = S.hosts.filter((h) =>
    !term || (h.name + h.hostname + (h.tags || []).join(" ") + h.group)
      .toLowerCase().includes(term.toLowerCase()))
    .map((h) => ({ _act: "host", host_id: h.id, name: h.name, kind: "host",
                   detail: `${h.user}@${h.hostname} · ${h.state?.status || "idle"}`,
                   host_icon: h.icon, host_color: h.color }));

  if (!term) { palResults = hostHits; return paletteRender(); }

  let hits = [];
  try { hits = (await api(`search?q=${encodeURIComponent(term)}&limit=60`)).results || []; }
  catch {}
  palResults = [...hostHits.slice(0, 4), ...hits.map((r) => ({ ...r, _act: "goto" }))];
  paletteRender();
}

function paletteRender() {
  palIndex = Math.max(0, Math.min(palIndex, palResults.length - 1));
  const box = $("#palette-results");
  if (!palResults.length) {
    box.innerHTML = `<div class="loading">No matches. Type <kbd>&gt;</kbd> to run a command.</div>`;
    return;
  }
  box.innerHTML = palResults.map((r, i) => `
    <div class="presult ${i === palIndex ? "sel" : ""}" data-i="${i}">
      <span style="color:var(--${esc(r.host_color || "blue")});text-align:center">${
        esc(r.host_icon || KIND_GLYPH[r.kind] || "•")}</span>
      <span><div class="pr-name">${esc(r.name)}</div>
        <div class="pr-detail">${esc(r.detail || "")}${
          r.host_name ? ` <span style="color:var(--accent)">on ${esc(r.host_name)}</span>` : ""}</div></span>
      <span class="pr-kind">${esc(r.kind || "")}</span>
    </div>`).join("");
  $$(".presult", box).forEach((el) => {
    el.onclick = () => { palIndex = +el.dataset.i; palettePick(); };
  });
  box.querySelector(".sel")?.scrollIntoView({ block: "nearest" });
}

async function palettePick(alt = false) {
  const r = palResults[palIndex];
  if (!r) return;
  closePalette();
  if (r._act === "host") return selectHost(r.host_id);
  if (r._act === "run") {
    setTab("commands");
    setTimeout(() => { const b = $("#cmd-box"); if (b) { b.value = r.name; runCmd(); } }, 120);
    return;
  }
  if (r._act === "runall") {
    setTab("commands");
    setTimeout(() => { const b = $("#cmd-box"); if (b) { b.value = r.name; fanoutPrompt(); } }, 120);
    return;
  }
  if (r._act === "term") return newTerm(S.activeId, r.name, r.name.split(" ")[0]);

  // A search hit: jump to the host that has it, and land on the right tab.
  await selectHost(r.host_id);
  if (r.kind === "package" || r.kind === "service" || r.kind === "port" ||
      r.kind === "container" || r.kind === "image" || r.kind === "runtime") {
    appView = { package: "packages", service: "services", port: "ports",
                container: "docker", image: "docker", runtime: "runtimes" }[r.kind];
    appFilter = r.name;
    setTab("apps");
  }
}

/* ──────────────────────────────── modal ────────────────────────────────── */

let modalActions = [];

function openModal(title, bodyHtml, actions = [], opts = {}) {
  $("#modal .modal-box").classList.toggle("wide", !!opts.wide);
  $("#modal-title").textContent = title;
  $("#modal-body").innerHTML = bodyHtml;
  modalActions = actions;
  $("#modal-foot").innerHTML = [
    ...actions.map((a, i) =>
      `<button class="${a.primary ? "primary-btn" : "ghost-btn"} ${a.danger ? "danger-btn" : ""}"
        data-i="${i}">${esc(a.label)}</button>`),
    `<button class="ghost-btn" data-close>Close</button>`,
  ].join("");
  $$("#modal-foot button").forEach((b) => {
    b.onclick = () => (b.hasAttribute("data-close") ? closeModal() : actions[+b.dataset.i].fn());
  });
  $("#modal").hidden = false;
  setTimeout(() => $("#modal-body [autofocus]")?.focus(), 30);
}
function closeModal() { $("#modal").hidden = true; S.vpnOpen = false; }

/* ───────────────────────────── host editor ─────────────────────────────── */

const COLORS = ["blue", "green", "yellow", "red", "magenta", "cyan", "foreground"];
let editIcon = "⬢", editColor = "blue", localKeys = [];

async function editHost(id) {
  const h = id ? S.byId[id] : null;
  editIcon = h?.icon || "⬢";
  editColor = h?.color || "blue";
  try { localKeys = (await api("keys")).keys || []; } catch { localKeys = []; }

  const icons = (window.__icons || ["⬢", "◆", "▲", "●", "⬟", "✦", "■", "⬜", "♥", "⚡", "☁", "⚙", "⚑", "◐"]);

  openModal(h ? `Edit ${h.name}` : "Add a host", `
    <div class="row">
      <div class="field" style="flex:2"><label>Name</label>
        <input id="e-name" class="text-input" value="${esc(h?.name || "")}"
               placeholder="hetzner-web-01" autofocus></div>
      <div class="field" style="flex:1"><label>Group</label>
        <input id="e-group" class="text-input" value="${esc(h?.group || "")}"
               placeholder="production"></div>
    </div>

    <div class="field"><label>Icon</label>
      <div class="icon-picker" id="e-icons">${icons.map((i) =>
        `<div class="icon-opt ${i === editIcon ? "sel" : ""}" data-icon="${i}">${i}</div>`).join("")}
      </div></div>

    <div class="field"><label>Colour</label>
      <div class="icon-picker" id="e-colors">${COLORS.map((c) =>
        `<div class="icon-opt ${c === editColor ? "sel" : ""}" data-color="${c}"
          style="color:var(--${c})">●</div>`).join("")}</div></div>

    <div class="row">
      <div class="field" style="flex:2"><label>Hostname or IP</label>
        <input id="e-hostname" class="text-input mono" value="${esc(h?.hostname || "")}"
               placeholder="203.0.113.10"></div>
      <div class="field" style="flex:1"><label>User</label>
        <input id="e-user" class="text-input mono" value="${esc(h?.user || "root")}"></div>
      <div class="field" style="flex:0 0 80px"><label>Port</label>
        <input id="e-port" class="text-input mono" value="${esc(h?.port || 22)}"></div>
    </div>

    <div class="field"><label>Authentication</label>
      <select id="e-auth" class="text-input">
        <option value="agent"    ${h?.auth === "agent" ? "selected" : ""}>SSH agent / default keys</option>
        <option value="key"      ${h?.auth === "key" ? "selected" : ""}>Specific private key</option>
        <option value="password" ${h?.auth === "password" ? "selected" : ""}>Password</option>
      </select></div>

    <div id="e-auth-extra"></div>

    <div class="row">
      <div class="field"><label>Jump host <span class="dim">(optional)</span></label>
        <input id="e-jump" class="text-input mono" value="${esc(h?.proxy_jump || "")}"
               placeholder="user@bastion:22"></div>
      <div class="field"><label>Tags</label>
        <input id="e-tags" class="text-input" value="${esc((h?.tags || []).join(", "))}"
               placeholder="web, eu"></div>
    </div>

    <div class="field"><label>Route through <span class="dim">(optional)</span></label>
      <select id="e-vpn" class="text-input">
        <option value="">Connect directly — no tunnel</option>
        ${(S.vpns || []).map((v) => `<option value="${esc(v.id)}"
          ${h?.vpn === v.id ? "selected" : ""}>${esc(v.name)} — ${esc(vpnKindName(v.kind))}</option>`).join("")}
      </select>
      <div class="hint">Fleet opens the tunnel before the SSH connection, so a box
        that only exists inside a VPN connects on its own.
        <a href="#" onclick="openVpnManager();return false"
           style="color:var(--accent)">Manage tunnels</a></div></div>

    <div class="field"><label>Notes</label>
      <textarea id="e-notes" class="text-input" rows="2">${esc(h?.notes || "")}</textarea></div>
    <div class="hint dim">Credentials go to your ${esc(S.secret_backend || "keyring")};
      they are never written to the ssh config or passed on a command line.</div>`,
    [
      ...(h ? [{ label: "Delete", danger: true, fn: async () => {
        if (!confirm(`Delete ${h.name}? Sessions and cached scans go with it.`)) return;
        await api(`hosts/${h.id}`, { method: "DELETE" });
        closeModal(); toast("Host deleted"); refresh();
      } }] : []),
      { label: h ? "Save" : "Add host", primary: true, fn: () => saveHost(h) },
    ]);

  $$("#e-icons .icon-opt").forEach((el) => el.onclick = () => {
    editIcon = el.dataset.icon;
    $$("#e-icons .icon-opt").forEach((x) => x.classList.toggle("sel", x === el));
  });
  $$("#e-colors .icon-opt").forEach((el) => el.onclick = () => {
    editColor = el.dataset.color;
    $$("#e-colors .icon-opt").forEach((x) => x.classList.toggle("sel", x === el));
  });
  $("#e-auth").onchange = () => authExtra(h);
  authExtra(h);
}

function authExtra(h) {
  const mode = $("#e-auth").value;
  const box = $("#e-auth-extra");
  if (mode === "key") {
    box.innerHTML = `
      <div class="field"><label>Private key</label>
        <select id="e-key" class="text-input mono">
          ${localKeys.map((k) => `<option value="${esc(k.path)}"
            ${h?.identity_file === k.path ? "selected" : ""}>${esc(k.name)} — ${
            esc((k.fingerprint || "").split(" ")[1] || "")}</option>`).join("")}
          <option value="__custom__">Other path…</option>
        </select>
        <input id="e-keypath" class="text-input mono" style="margin-top:6px"
               placeholder="~/.ssh/id_ed25519" value="${esc(h?.identity_file || "")}"
               ${localKeys.length ? "hidden" : ""}>
        <div class="hint">${localKeys.length ? "" : "No keys found in ~/.ssh — "}
          <a href="#" onclick="genKey();return false" style="color:var(--accent)">generate a new one</a></div>
      </div>
      <div class="field"><label>Key passphrase <span class="dim">(only if encrypted)</span></label>
        <input id="e-passphrase" type="password" class="text-input"
               placeholder="${h?.has_passphrase ? "•••••• saved" : "leave blank if none"}"></div>`;
    const sel = $("#e-key");
    if (sel) sel.onchange = () => {
      $("#e-keypath").hidden = sel.value !== "__custom__";
      if (sel.value !== "__custom__") $("#e-keypath").value = sel.value;
    };
  } else if (mode === "password") {
    box.innerHTML = `
      <div class="field"><label>Password</label>
        <input id="e-password" type="password" class="text-input"
               placeholder="${h?.has_password ? "•••••• saved — leave blank to keep" : ""}">
        <div class="hint">Stored in your ${esc(S.secret_backend || "keyring")}. Once connected you can
          ${h ? `<a href="#" onclick="installKeyFlow('${h.id}');return false"
             style="color:var(--accent)">install a key</a> and switch to key auth.`
             : "install a key and switch to key auth."}</div></div>`;
  } else {
    box.innerHTML = `<div class="hint dim" style="margin-bottom:12px">Uses your ssh-agent and the
      default identities in <code>~/.ssh</code>.</div>`;
  }
}

async function saveHost(h) {
  const auth = $("#e-auth").value;
  const body = {
    name: $("#e-name").value.trim(), group: $("#e-group").value.trim(),
    icon: editIcon, color: editColor,
    hostname: $("#e-hostname").value.trim(), user: $("#e-user").value.trim() || "root",
    port: parseInt($("#e-port").value) || 22, auth,
    proxy_jump: $("#e-jump").value.trim(), notes: $("#e-notes").value,
    vpn: $("#e-vpn")?.value || "",
    tags: $("#e-tags").value.split(",").map((t) => t.trim()).filter(Boolean),
  };
  if (!body.hostname) { toast("Hostname is required", "err"); return; }
  if (auth === "key") {
    const sel = $("#e-key");
    body.identity_file = (sel && sel.value !== "__custom__") ? sel.value : $("#e-keypath").value.trim();
    const pp = $("#e-passphrase")?.value;
    if (pp) body.passphrase = pp;
  }
  if (auth === "password") {
    const pw = $("#e-password")?.value;
    if (pw) body.password = pw;
    else if (!h?.has_password) { toast("Password is required", "err"); return; }
  }
  try {
    const saved = h
      ? await api(`hosts/${h.id}`, { method: "PUT", body })
      : await api("hosts", { method: "POST", body });
    closeModal();
    toast(h ? "Saved" : `Added ${saved.name} — connecting…`, "ok");
    await refresh();
    selectHost(saved.id);
  } catch (e) { toast(e.message, "err"); }
}

async function genKey() {
  try {
    const r = await api("keys/generate", { method: "POST", body: {} });
    if (!r.ok) return toast(r.error, "err");
    localKeys = (await api("keys")).keys || [];
    toast("Generated " + r.path, "ok");
    authExtra(null);
  } catch (e) { toast(e.message, "err"); }
}

async function installKeyFlow(hostId) {
  const keys = (await api("keys")).keys || [];
  if (!keys.length) return toast("No local keys — generate one first", "err");
  openModal("Install key on host", `
    <div class="field"><label>Key to install</label>
      <select id="ik-key" class="text-input mono">${keys.map((k) =>
        `<option value="${esc(k.path)}">${esc(k.name)}</option>`).join("")}</select>
      <div class="hint">Appends the public key to <code>~/.ssh/authorized_keys</code> over the
        connection you already have. Idempotent — running it twice changes nothing.</div></div>`,
    [{ label: "Install", primary: true, fn: async () => {
      const r = await api(`hosts/${hostId}/install-key`, { method: "POST",
        body: { key_path: $("#ik-key").value } });
      closeModal();
      toast(r.ok ? `Key ${r.result}` : r.error, r.ok ? "ok" : "err");
    } }]);
}

/* ───────────────────────────────── actions ─────────────────────────────── */

/* ═══════════════════════════════════ VPN ═══════════════════════════════ */

/* A tunnel is not a separate application here. A host names a profile, and
   opening that host's connection opens the tunnel first — so the sidebar strip
   is live state (what is up, and what is going through it) rather than a
   launcher you have to remember to press. */

const VPN_LABEL = { down: "down", connecting: "connecting", auth: "authenticating",
                    up: "up", error: "error" };
const VPN_DOT = { up: "online", error: "error", connecting: "connecting",
                  auth: "connecting", down: "idle" };
const VPN_PILL = { up: "online", error: "error", connecting: "connecting",
                   auth: "connecting", down: "" };

const vpnKindName = (k) => (k === "wireguard" ? "WireGuard" : "OpenVPN");
const vpnById = (id) => (S.vpns || []).find((v) => v.id === id);
const vpnStatus = (v) => (v && v.status && v.status.status) || "down";
const perSec = (n) => bytes(Math.round(n || 0)) + "/s";

/* ── the sidebar strip ── */

function renderVpnStrip() {
  const strip = $("#vpn-strip");
  if (!strip) return;
  const live = (S.vpns || []).filter((v) => vpnStatus(v) !== "down");
  strip.hidden = !live.length;
  if (!live.length) { strip.innerHTML = ""; return; }
  strip.innerHTML = live.map((v) => {
    const st = v.status || {}, s = vpnStatus(v);
    const right = s === "up"
      ? `↓${perSec(st.rx_rate)} ↑${perSec(st.tx_rate)}`
      : (VPN_LABEL[s] || s);
    return `<div class="vpn-row" data-vpn="${esc(v.id)}"
              title="${esc(vpnKindName(v.kind))} — ${esc(st.error || st.ip || st.detail || s)}">
      <span class="dot dot-${VPN_DOT[s] || "idle"}"></span>
      <span class="vpn-row-name">${esc(v.name)}</span>
      <span class="vpn-row-rate">${esc(right)}</span>
    </div>`;
  }).join("");
  $$(".vpn-row", strip).forEach((el) =>
    el.onclick = () => openVpnManager());
}

/* ── the manager ── */

function vpnManagerHTML() {
  const t = S.vpnTooling || {};
  const missing = [];
  if (!t.openvpn) missing.push("<code>openvpn</code>");
  if (!t.wireguard) missing.push("<code>wireguard-tools</code>");

  const elev = t.openvpn_elevation || t.wireguard_elevation;
  const cards = (S.vpns || []).map(vpnCard).join("") ||
    `<div class="dim" style="padding:18px 2px">No tunnels yet. Import a
      <code>.ovpn</code> or a WireGuard <code>.conf</code> and a host can then
      be told to connect through it.</div>`;

  return `
    ${missing.length ? `<div class="vpn-note warn-note">
      Not installed: ${missing.join(" and ")}. Fleet drives the real clients
      rather than shipping its own, so install the one your provider uses —
      <code>sudo pacman -S openvpn</code> or
      <code>sudo pacman -S wireguard-tools</code>.</div>` : ""}
    ${(t.pkexec && !t.polkit_agent && elev !== "sudo") ? `<div class="vpn-note warn-note">
      No polkit authentication agent is running, so <code>pkexec</code> has nowhere
      to ask for your password and a connect fails with “Not authorized”.
      <code>polkitd</code> being up is not enough — the agent is the part that
      draws the dialog. Start one:
      <pre class="out-pre">sudo pacman -S hyprpolkitagent
systemctl --user enable --now hyprpolkitagent</pre>
      Or skip polkit entirely with the sudo rule below.</div>` : ""}
    <div class="vpn-cards">${cards}</div>
    <details class="vpn-details">
      <summary>How Fleet gets root${elev === "sudo" ? " — using your sudo rule" : ""}</summary>
      <p>A tunnel means a tun device and a change to the routing table, which is
        root, and Fleet does not run as root. Every connect and disconnect goes
        through <code>${elev === "sudo" ? "sudo -n" : "pkexec"}</code>${
        elev === "pkexec" ? ", which is the desktop password prompt you see" : ""}.</p>
      ${elev === "sudo" ? "" : `<p>You can make it silent with a sudo rule, but
        be clear about what that grants: an OpenVPN <code>up</code> script and a
        WireGuard <code>PostUp</code> line both run as root, so a NOPASSWD rule
        for these two binaries is a NOPASSWD rule for anything. Fleet will not
        write it for you.</p>
      <pre class="out-pre">echo '${esc(t.sudoers || "")}' | \\
  sudo tee /etc/sudoers.d/fleet-vpn &amp;&amp; sudo chmod 440 /etc/sudoers.d/fleet-vpn</pre>`}
      <p class="dim">Credentials go to your ${esc(S.secret_backend || "keyring")} and
        are handed to <code>openvpn</code> over its management socket — never a
        file on disk, never a command line.</p>
    </details>`;
}

function vpnCard(v) {
  const st = v.status || {}, s = vpnStatus(v);
  const sum = v.summary || {};
  const up = s === "up";
  const busy = s === "connecting" || s === "auth";
  // Offering Connect for a client that is not installed is an invitation to
  // press a button that can only fail, so the card says so on the button.
  const t = S.vpnTooling || {};
  const client = v.kind === "wireguard" ? t.wireguard : t.openvpn;
  const pkg = v.kind === "wireguard" ? "wireguard-tools" : "openvpn";
  // What the card calls "Server" is where it will actually connect, which is
  // not the config's own `remote` once an override is set.
  const shown = (v.effective_remotes || []).length ? v.effective_remotes : (sum.remotes || []);
  const facts = [
    ["Server", (shown.length ? esc(shown.join(", ")) : "—") + (v.overridden
      ? ` <span class="chip" title="The config says ${esc((sum.remotes || []).join(", "))
          }">override</span>` : "")],
    ["Address", esc(st.ip || "—")],
    ["Interface", esc(st.iface || "—")],
    up ? ["Traffic", `↓${perSec(st.rx_rate)} ↑${perSec(st.tx_rate)}
            <span class="dim">· ${bytes(st.rx)} / ${bytes(st.tx)}</span>`]
       : ["Since", st.since ? ago(st.since) : "—"],
    ["Routes", (st.routes || []).length
      ? (st.routes || []).slice(0, 4).map((r) => `<code>${esc(r)}</code>`).join(" ")
      : "—"],
    ["Hosts", (v.hosts || []).length ? esc((v.hosts || []).join(", ")) :
      `<span class="dim">none — set “Route through” on a host</span>`],
  ];
  return `<div class="vpn-card ${up ? "up" : ""}">
    <div class="vpn-card-head">
      <span class="dot dot-${VPN_DOT[s] || "idle"}"></span>
      <b>${esc(v.name)}</b>
      <span class="chip">${esc(vpnKindName(v.kind))}</span>
      ${v.auto ? `<span class="chip" title="Opens when Fleet starts">auto</span>` : ""}
      <span class="pill ${VPN_PILL[s] || ""}">${esc(st.detail || VPN_LABEL[s] || s)}</span>
      <span class="spacer"></span>
      <button class="ghost-btn sm" data-act="log"  data-id="${esc(v.id)}">Log</button>
      <button class="ghost-btn sm" data-act="edit" data-id="${esc(v.id)}">Edit</button>
      <button class="${up ? "ghost-btn sm" : "primary-btn sm"}"
              data-act="${up ? "down" : "up"}" data-id="${esc(v.id)}"
              ${busy || (!up && !client) ? "disabled" : ""}
              title="${!client && !up ? `${pkg} is not installed` : ""}"
              >${busy ? "…" : up ? "Disconnect" : "Connect"}</button>
    </div>
    ${!client && !up ? `<div class="vpn-err">This tunnel needs the
      <code>${esc(pkg)}</code> package, which is not installed —
      <code>sudo pacman -S ${esc(pkg)}</code></div>` : ""}
    ${st.error ? `<div class="vpn-err">${esc(st.error)}</div>` : ""}
    <div class="vpn-facts">${facts.map(([k, val]) =>
      `<div><span class="vpn-fact-k">${esc(k)}</span><span class="vpn-fact-v">${val}</span></div>`
      ).join("")}</div>
  </div>`;
}

function bindVpnManager() {
  $$("#modal-body [data-act]").forEach((b) => b.onclick = async () => {
    const id = b.dataset.id;
    try {
      if (b.dataset.act === "edit") return vpnEditor(vpnById(id));
      if (b.dataset.act === "log") return vpnLog(id);
      b.disabled = true;
      if (b.dataset.act === "up") {
        await api(`vpn/${id}/up`, { method: "POST", body: {} });
        toast(`Opening ${vpnById(id)?.name}…`);
      } else {
        await api(`vpn/${id}/down`, { method: "POST", body: {} });
        toast(`${vpnById(id)?.name} disconnected`);
      }
      await refreshVpns();
    } catch (e) { toast(e.message, "err"); refreshVpns(); }
  });
}

function openVpnManager() {
  S.vpnOpen = true;
  openModal("VPN tunnels", vpnManagerHTML(),
    [{ label: "Add a tunnel", primary: true, fn: () => vpnEditor(null) }],
    { wide: true });
  bindVpnManager();
  refreshVpns();
}

/* Repaint the open manager in place: state arrives on the events socket while
   you are looking at it, and a modal that goes stale is worse than none. */
function repaintVpnManager() {
  if (!S.vpnOpen || $("#modal").hidden) return;
  const body = $("#modal-body");
  if (!body || !body.querySelector(".vpn-cards")) return;
  const open = $$("#modal-body details[open]").length > 0;
  body.innerHTML = vpnManagerHTML();
  if (open) $("#modal-body details")?.setAttribute("open", "");
  bindVpnManager();
}

async function refreshVpns() {
  try {
    const r = await api("vpn");
    S.vpns = r.vpns || [];
    S.vpnTooling = r.tooling || {};
  } catch { /* the manager keeps showing what it had */ }
  renderVpnStrip();
  repaintVpnManager();
  renderHead();
}

/* ── the editor ── */

async function vpnEditor(v) {
  vpnEditing = v || null;
  let config = "";
  if (v) {
    try { config = (await api(`vpn/${v.id}/config`)).config || ""; } catch {}
  }
  const sum = v?.summary || {};
  openModal(v ? `Edit ${v.name}` : "Add a VPN tunnel", `
    <div class="row">
      <div class="field" style="flex:2"><label>Name</label>
        <input id="v-name" class="text-input" value="${esc(v?.name || "")}"
               placeholder="office" autofocus></div>
      <div class="field" style="flex:1"><label>Type</label>
        <select id="v-kind" class="text-input">
          <option value="openvpn"   ${v?.kind !== "wireguard" ? "selected" : ""}>OpenVPN</option>
          <option value="wireguard" ${v?.kind === "wireguard" ? "selected" : ""}>WireGuard</option>
        </select></div>
    </div>

    <div class="field"><label>Configuration</label>
      <div class="vpn-pick">
        <input type="file" id="v-file" accept=".ovpn,.conf,.txt,text/plain">
        <span class="dim">or paste it below</span>
      </div>
      <textarea id="v-config" class="text-input mono vpn-config" rows="7" spellcheck="false"
        placeholder="client&#10;dev tun&#10;remote vpn.example.com 1194&#10;…">${esc(config)}</textarea>
      <div class="hint">The file is copied to
        <code>~/.config/fleet/vpn/</code> with mode 600. It is never sent anywhere.</div>
    </div>

    <div id="v-summary" class="vpn-summary"></div>

    <div class="field"><label>Server override <span class="dim">(optional)</span></label>
      <div class="row">
        <input id="v-ov-host" class="text-input mono" style="flex:3"
               value="${esc(v?.override?.host || "")}"
               placeholder="host or IP — blank keeps the config's">
        <input id="v-ov-port" class="text-input mono" style="flex:0 0 86px"
               value="${esc(v?.override?.port || "")}" placeholder="port">
        <select id="v-ov-proto" class="text-input" style="flex:0 0 128px">
          <option value="">protocol</option>
          <option value="udp" ${v?.override?.proto === "udp" ? "selected" : ""}>udp</option>
          <option value="tcp" ${v?.override?.proto === "tcp" ? "selected" : ""}>tcp</option>
        </select>
      </div>
      <div id="v-ov-preview"></div>
      <div class="hint">Same certificates and login, a different endpoint — for a
        provider that hands you one config and a page full of servers to pick from.
        Your imported file is left exactly as it came; Fleet writes the rewritten
        copy it actually runs.</div></div>

    <div id="v-creds"></div>

    <div class="field"><label>External files <span class="dim">(only if the config
      points at certificates beside it)</span></label>
      <input id="v-srcdir" class="text-input mono" value="${esc(v?.source_dir || "")}"
             placeholder="/home/you/vpn"></div>

    <label class="vpn-check"><input type="checkbox" id="v-auto"
      ${v?.auto ? "checked" : ""}> Open this tunnel when Fleet starts</label>

    <div class="field" style="margin-top:12px"><label>Notes</label>
      <textarea id="v-notes" class="text-input" rows="2">${esc(v?.notes || "")}</textarea></div>`,
    [
      ...(v ? [{ label: "Delete", danger: true, fn: () => vpnDelete(v) }] : []),
      { label: v ? "Save" : "Add tunnel", primary: true, fn: () => vpnSave(v) },
    ], { wide: true });

  $("#v-file").onchange = async (e) => {
    const f = e.target.files[0];
    if (!f) return;
    try {
      const text = await f.text();
      $("#v-config").value = text;
      if (!$("#v-name").value.trim())
        $("#v-name").value = f.name.replace(/\.(ovpn|conf|txt)$/i, "");
      // The two formats are unmistakable, so do not make the user classify it.
      if (/^\s*\[Interface\]/mi.test(text)) $("#v-kind").value = "wireguard";
      else if (/^\s*remote\s+\S/mi.test(text)) $("#v-kind").value = "openvpn";
      vpnAnalyse();
    } catch (err) { toast("Could not read that file: " + err.message, "err"); }
  };
  $("#v-config").oninput = () => {
    clearTimeout(vpnEditor.t);
    vpnEditor.t = setTimeout(vpnAnalyse, 350);
  };
  $("#v-kind").onchange = () => { vpnOverrideFields(); vpnAnalyse(); };
  ["v-ov-host", "v-ov-port"].forEach((id) => $("#" + id).oninput = () => {
    clearTimeout(vpnEditor.t);
    vpnEditor.t = setTimeout(vpnAnalyse, 350);
  });
  $("#v-ov-proto").onchange = vpnAnalyse;
  vpnOverrideFields();
  vpnCreds(sum);
  if (config) vpnAnalyse(); else $("#v-summary").innerHTML = "";
}

/* WireGuard is UDP by definition, so offering to override the protocol would
   only be a way to get an error back. */
function vpnOverrideFields() {
  const wg = $("#v-kind")?.value === "wireguard";
  const sel = $("#v-ov-proto");
  if (!sel) return;
  sel.disabled = wg;
  sel.title = wg ? "WireGuard is always UDP" : "";
  if (wg) sel.value = "";
}

function vpnOverride() {
  return { host: $("#v-ov-host")?.value.trim() || "",
           port: $("#v-ov-port")?.value.trim() || "",
           proto: $("#v-ov-proto")?.disabled ? "" : ($("#v-ov-proto")?.value || "") };
}

/* Read the config back and say what it will do — including which directives
   run a program as root, because that is the part a pasted file can hide. */
async function vpnAnalyse() {
  const box = $("#v-summary");
  if (!box) return;
  const text = $("#v-config").value;
  if (!text.trim()) { box.innerHTML = ""; return; }
  let r;
  try {
    r = await api("vpn/analyse", { method: "POST",
      body: { kind: $("#v-kind").value, config: text, override: vpnOverride() } });
  } catch (e) { box.innerHTML = `<div class="vpn-note err-note">${esc(e.message)}</div>`; return; }
  const ovBox = $("#v-ov-preview");
  if (ovBox) {
    // Show the rewrite itself rather than a claim about it: the line that goes
    // into the file is the only thing worth checking before you connect.
    ovBox.innerHTML = (r.override_changes || []).length
      ? `<div class="vpn-note"><div class="dim" style="margin-bottom:4px">The config
           Fleet will run:</div><pre class="out-pre">${esc(r.override_changes.join("\n"))}</pre></div>`
      : "";
  }
  if (r.problem) {
    box.innerHTML = `<div class="vpn-note err-note">${esc(r.problem)}</div>`;
    vpnCreds({});
    return;
  }
  const s = r.summary || {};
  const bits = [];
  if ((s.remotes || []).length)
    bits.push(`<div><span class="vpn-fact-k">Server</span><span class="vpn-fact-v">${
      esc(s.remotes.join(", "))}</span></div>`);
  if ((s.addresses || []).length)
    bits.push(`<div><span class="vpn-fact-k">Address</span><span class="vpn-fact-v">${
      esc(s.addresses.join(", "))}</span></div>`);
  if ((s.allowed_ips || []).length)
    bits.push(`<div><span class="vpn-fact-k">Routes</span><span class="vpn-fact-v">${
      esc(s.allowed_ips.join(", "))}</span></div>`);
  if ((s.inline || []).length)
    bits.push(`<div><span class="vpn-fact-k">Inline</span><span class="vpn-fact-v">${
      esc(s.inline.join(", "))}</span></div>`);
  bits.push(`<div><span class="vpn-fact-k">Login</span><span class="vpn-fact-v">${
    s.needs_auth ? "username and password" : "certificate / key only"}</span></div>`);

  box.innerHTML = `<div class="vpn-facts">${bits.join("")}</div>
    ${(s.external || []).length ? `<div class="vpn-note warn-note">
      This config points at files next to it —
      ${s.external.map((f) => `<code>${esc(f)}</code>`).join(", ")}. Give the
      directory they live in below, or export a self-contained config with the
      certificates inline.</div>` : ""}
    ${(s.risky || []).length ? `<div class="vpn-note warn-note">
      Runs as root when the tunnel comes up:
      <pre class="out-pre" style="margin-top:6px">${esc(s.risky.join("\n"))}</pre>
      That is normal for a config that sets DNS — but it is your machine's root,
      so read it before you save.</div>` : ""}`;
  vpnCreds(s);
}

/* Credential fields depend on what the config actually asks for, so they are
   rebuilt every time the config is re-read. Two things therefore have to
   survive that rebuild: what is already saved on the profile, and whatever the
   user has half-typed into the box a moment ago. */
let vpnEditing = null;

function vpnCreds(sum) {
  const box = $("#v-creds");
  if (!box) return;
  const v = vpnEditing;
  const keep = { user: $("#v-user")?.value, pass: $("#v-pass")?.value,
                 pp: $("#v-pp")?.value };
  const kind = $("#v-kind")?.value || "openvpn";
  if (kind === "wireguard") {
    box.innerHTML = `<div class="hint dim" style="margin-bottom:12px">WireGuard
      authenticates with the key in the config itself — nothing else to enter.</div>`;
    return;
  }
  box.innerHTML = `
    ${sum?.needs_auth === false ? "" : `<div class="row">
      <div class="field"><label>VPN username</label>
        <input id="v-user" class="text-input" value="${esc(keep.user ?? v?.username ?? "")}"
               placeholder="${sum?.needs_auth ? "required by this config" : "if the server asks for one"}"></div>
      <div class="field"><label>VPN password</label>
        <input id="v-pass" type="password" class="text-input" value="${esc(keep.pass || "")}"
               placeholder="${v?.has_password ? "•••••• saved — leave blank to keep" : ""}"></div>
    </div>`}
    <div class="field"><label>Private key passphrase <span class="dim">(only if the
      key in the config is encrypted)</span></label>
      <input id="v-pp" type="password" class="text-input" value="${esc(keep.pp || "")}"
             placeholder="${v?.has_passphrase ? "•••••• saved" : "leave blank if none"}"></div>`;
}

async function vpnSave(v) {
  const body = {
    name: $("#v-name").value.trim(),
    kind: $("#v-kind").value,
    auto: $("#v-auto").checked,
    notes: $("#v-notes").value,
    source_dir: $("#v-srcdir").value.trim(),
    override: vpnOverride(),
  };
  const text = $("#v-config").value;
  if (!body.name) return toast("Give the tunnel a name", "err");
  // On an edit an untouched config is resent unchanged, which is harmless and
  // keeps the summary in step with what is actually on disk.
  if (!text.trim()) return toast("A configuration is required", "err");
  body.config = text;
  const user = $("#v-user")?.value, pass = $("#v-pass")?.value, pp = $("#v-pp")?.value;
  if (user !== undefined) body.username = user;
  if (pass) body.password = pass;
  if (pp) body.passphrase = pp;
  try {
    const saved = v ? await api(`vpn/${v.id}`, { method: "PUT", body })
                    : await api("vpn", { method: "POST", body });
    toast(saved.restart_needed
      ? "Saved — reconnect the tunnel for the new server to take effect"
      : v ? "Saved" : `Added ${saved.name}`, "ok");
    await refreshVpns();
    openVpnManager();
  } catch (e) { toast(e.message, "err"); }
}

async function vpnDelete(v) {
  const using = (v.hosts || []).length;
  if (!confirm(`Delete the tunnel ${v.name}?` + (using
    ? `\n\n${using} host(s) route through it and will go back to connecting directly.` : "")))
    return;
  try {
    await api(`vpn/${v.id}?force=1`, { method: "DELETE", body: { force: true } });
    toast("Tunnel deleted");
    await refresh();
    await refreshVpns();
    openVpnManager();
  } catch (e) { toast(e.message, "err"); }
}

async function vpnLog(id) {
  const v = vpnById(id);
  try {
    const r = await api(`vpn/${id}/log`);
    openModal(`${v?.name || "Tunnel"} — log`,
      r.lines?.length
        ? `<pre class="out-pre">${esc(r.lines.join("\n"))}</pre>`
        : `<div class="dim">Nothing logged yet — the tunnel has not been started
             in this session.</div>`,
      [{ label: "Back", fn: () => openVpnManager() }], { wide: true });
  } catch (e) { toast(e.message, "err"); }
}

async function reconnect() {
  const h = S.byId[S.activeId];
  toast(`Connecting to ${h.name}…`);
  try {
    const st = await api(`hosts/${h.id}/connect`, { method: "POST", body: { force: true } });
    toast(st.status === "online" ? `${h.name} online` : st.error,
          st.status === "online" ? "ok" : "err");
    refresh();
  } catch (e) { toast(e.message, "err"); }
}

async function importSsh() {
  try {
    const pre = await api("hosts/preview-import");
    if (!pre.hosts.length) return toast("Nothing to import from ~/.ssh/config", "err");
    openModal("Import from ~/.ssh/config", `
      <p class="dim" style="margin-top:0">Found ${pre.hosts.length} host(s). Ones you already
        have are skipped.</p>
      ${pre.hosts.map((h) => `<div class="pick-row">
        <span><b>${esc(h.name)}</b> <span class="dim">${esc(h.user)}@${esc(h.hostname)}:${h.port}</span></span>
        <span class="chip">${esc(h.auth)}</span></div>`).join("")}`,
      [{ label: "Import all", primary: true, fn: async () => {
        const r = await api("hosts/import", { method: "POST", body: {} });
        closeModal();
        toast(`Imported ${r.added.length} host(s)`, "ok");
        refresh();
      } }]);
  } catch (e) { toast(e.message, "err"); }
}

/* ────────────────────────────────── init ──────────────────────────────── */

async function refresh() {
  const st = await api("state");
  S.settings = st.settings;
  S.desktop = st.desktop;
  S.secret_backend = st.secret_backend;
  S.sessions = st.sessions || [];
  S.vpns = st.vpns || [];
  S.vpnTooling = st.vpn_tooling || {};
  window.__icons = st.icons;
  applyTheme(st.theme);
  setHosts(st.hosts);
  renderVpnStrip();
}

const TAB_KEYS = { o: "overview", t: "terminal", f: "files", a: "apps",
                   c: "commands", b: "blueprint", v: "events" };

/* Single letters, Omarchy/vim style. They fire only when you are not typing
   and not inside a terminal -- a shell must receive every keystroke, so the
   Alt+<key> forms below stay available everywhere as the way out. */
function bindKeys() {
  document.addEventListener("keydown", (e) => {
    const inTerm = !!e.target.closest(".term-instance");
    const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName) ||
                   e.target.isContentEditable;
    const mod = e.ctrlKey || e.metaKey;
    const paletteOpen = !$("#palette").hidden;
    const modalOpen = !$("#modal").hidden;
    const k = e.key;

    /* ---- always available, even from inside a terminal ---- */
    if (k === "Escape") {
      if (paletteOpen) return closePalette();
      if (modalOpen) return closeModal();
      // Always a way back out of a text field to the shortcuts.
      if (typing) { e.target.blur(); return; }
    }
    if (mod && k.toLowerCase() === "k" && !e.shiftKey) {
      e.preventDefault(); return openPalette();
    }
    if (mod && e.shiftKey && k.toLowerCase() === "t") {
      e.preventDefault(); return newTerm(S.activeId);
    }
    if (mod && k.toLowerCase() === "r" && !inTerm) { e.preventDefault(); return reconnect(); }
    if (e.altKey && /^[1-9]$/.test(k)) {
      const h = S.hosts[+k - 1];
      if (h) { e.preventDefault(); selectHost(h.id); }
      return;
    }
    if (e.altKey && TAB_KEYS[k.toLowerCase()]) {
      e.preventDefault(); return setTab(TAB_KEYS[k.toLowerCase()]);
    }

    if (typing || inTerm || paletteOpen || modalOpen || mod || e.altKey) return;

    /* ---- bare keys ---- */
    if (k === "?") { e.preventDefault(); return showKeyHelp(); }
    if (k === "/") { e.preventDefault(); return openPalette(); }
    if (/^[1-9]$/.test(k)) {
      const h = S.hosts[+k - 1];
      if (h) { e.preventDefault(); selectHost(h.id); }
      return;
    }
    if (TAB_KEYS[k]) { e.preventDefault(); return setTab(TAB_KEYS[k]); }
    if (k === "i" && S.tab === "commands") {
      e.preventDefault(); $("#cmd-box")?.focus(); return;
    }
    if (k === "r") { e.preventDefault(); return reconnect(); }
    if (k === "V") { e.preventDefault(); return openVpnManager(); }
    if (k === "n") { e.preventDefault(); return newTerm(S.activeId); }
    if (k === "s" && S.tab === "overview") { e.preventDefault(); return runSpeedTest(); }
    if (k === "R" && S.tab === "apps") { e.preventDefault(); return loadInventory(S.activeId, true); }

    /* ---- file browser: hjkl, and y/p for copy/paste ---- */
    if (S.tab !== "files") return;
    const rows = fbSorted();
    const move = (d) => {
      if (!rows.length) return;
      FB.cursor = Math.max(0, Math.min(rows.length - 1, (FB.cursor ?? -1) + d));
      renderFiles();
      $(`.fb-tbl tr.fb-cursor`)?.scrollIntoView({ block: "nearest" });
    };
    const at = () => rows[FB.cursor ?? -1];

    if (k === "j" || k === "ArrowDown") { e.preventDefault(); return move(1); }
    if (k === "k" || k === "ArrowUp") { e.preventDefault(); return move(-1); }
    if (k === "g") { e.preventDefault(); FB.cursor = 0; return renderFiles(); }
    if (k === "G") { e.preventDefault(); FB.cursor = rows.length - 1; return renderFiles(); }
    if (k === "h" || k === "Backspace" || k === "ArrowLeft") {
      e.preventDefault(); return fbLoad(FB.host, fbParent(FB.path));
    }
    if (k === "l" || k === "Enter" || k === "ArrowRight") {
      e.preventDefault();
      const en = at();
      if (!en) return;
      return en.kind === "dir" ? fbLoad(FB.host, fbJoin(FB.path, en.name)) : fbEdit(en);
    }
    if (k === "x" || k === " ") {
      e.preventDefault();
      const en = at();
      if (!en) return;
      FB.sel.has(en.name) ? FB.sel.delete(en.name) : FB.sel.add(en.name);
      return renderFiles();
    }
    if (k === "A") {
      e.preventDefault();
      if (FB.sel.size === rows.length) FB.sel.clear();
      else rows.forEach((x) => FB.sel.add(x.name));
      return renderFiles();
    }
    if (k === "y") { e.preventDefault(); if (FB.sel.size) fbClip(false); return; }
    if (k === "m") { e.preventDefault(); if (FB.sel.size) fbClip(true); return; }
    if (k === "p") { e.preventDefault(); if (FB.clip) fbPaste(); return; }
    if (k === "u") { e.preventDefault(); return fbPickUpload(); }
    if (k === "d") { e.preventDefault(); if (FB.sel.size) fbDownload(); return; }
    if (k === ".") { e.preventDefault(); FB.showHidden = !FB.showHidden; return renderFiles(); }
    if (k === "N") { e.preventDefault(); return fbMkdir(); }
  });

  const q = $("#palette-q");
  q.addEventListener("input", () => {
    clearTimeout(palTimer);
    palTimer = setTimeout(() => { palIndex = 0; paletteSearch(q.value); }, 110);
  });
  q.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown") { e.preventDefault(); palIndex++; paletteRender(); }
    else if (e.key === "ArrowUp") { e.preventDefault(); palIndex--; paletteRender(); }
    else if (e.key === "Enter") { e.preventDefault(); palettePick(); }
    else if (e.key === "Tab") { e.preventDefault(); palettePick(true); }
  });
  $("#palette").addEventListener("click", (e) => {
    if (e.target.id === "palette") closePalette();
  });
  $("#modal").addEventListener("click", (e) => { if (e.target.id === "modal") closeModal(); });
}

const KEY_HELP = [
  ["Navigation", [
    ["1 – 9", "Jump to host"], ["o", "Overview"], ["t", "Terminal"], ["f", "Files"],
    ["a", "Apps"], ["c", "Commands"], ["b", "Blueprints"], ["v", "Activity"],
    ["/", "Search everything"], ["?", "This list"],
  ]],
  ["Actions", [
    ["n", "New shell on this host"], ["r", "Reconnect this host"],
    ["s", "Run speed test (Overview)"], ["R", "Rescan host (Apps)"],
    ["i", "Type a command (Commands)"], ["V", "VPN tunnels"],
    ["esc", "Close dialog, or leave a text field"],
  ]],
  ["Files", [
    ["j / k", "Move down / up"], ["h / l", "Parent / open"],
    ["g / G", "First / last"], ["x or space", "Select"], ["A", "Select all"],
    ["y", "Copy"], ["m", "Cut"], ["p", "Paste here"],
    ["d", "Download"], ["u", "Upload"], ["N", "New folder"], [".", "Toggle hidden"],
  ]],
  ["Works inside a terminal too", [
    ["ctrl+k", "Search everything"], ["alt+o…v", "Switch tab"],
    ["alt+1…9", "Jump to host"], ["ctrl+shift+t", "New shell"],
  ]],
];

function showKeyHelp() {
  openModal("Keyboard shortcuts", `
    <div class="keys-grid">${KEY_HELP.map(([title, rows]) => `
      <div class="keys-sec"><h4>${esc(title)}</h4>
        ${rows.map(([k, d]) =>
          `<div class="keys-row"><kbd>${esc(k)}</kbd><span>${esc(d)}</span></div>`).join("")}
      </div>`).join("")}</div>
    <div class="hint dim" style="margin-top:14px">
      Single letters work whenever you are not typing and not focused in a
      terminal — a shell has to receive every keystroke, so the
      <kbd>alt</kbd> forms above are the way out of one.</div>`,
    [], { wide: true });
}

function bindUI() {
  $$(".tab").forEach((t) => t.onclick = () => setTab(t.dataset.tab));
  $("#btn-search").onclick = () => openPalette();
  $("#btn-keys").onclick = showKeyHelp;
  $("#btn-add").onclick = () => editHost(null);
  $("#empty-add").onclick = () => editHost(null);
  $("#btn-import").onclick = importSsh;
  $("#btn-vpn").onclick = () => openVpnManager();
  $("#empty-import").onclick = importSsh;
  $("#btn-edit").onclick = () => editHost(S.activeId);
  $("#btn-reconnect").onclick = reconnect;
  $("#modal-close").onclick = closeModal;
  $("#term-new").onclick = () => newTerm(S.activeId);

  // Overview is rebuilt from scratch several times a minute, so its controls
  // are delegated from the panel rather than bound to the elements.
  $('.panel[data-panel="overview"]').addEventListener("click", (e) => {
    if (e.target.closest("#speed-go")) { e.preventDefault(); runSpeedTest(); }
  });
  window.addEventListener("resize", () => { if (S.tab === "terminal") fitActiveTerm(); });
}

(async function main() {
  bindUI(); bindKeys();
  try { await refresh(); } catch (e) { toast("Cannot reach the Fleet server: " + e.message, "err"); }
  applyBarInset();

  // Deep link: ?tab=apps&host=<name> opens straight to a view, which is handy
  // for a keybinding or a bookmark that lands on one server's package list.
  const qs = new URLSearchParams(location.search);
  const wantHost = qs.get("host");
  if (wantHost) {
    const h = S.hosts.find((x) => x.name === wantHost || x.id === wantHost);
    if (h) await selectHost(h.id);
  }
  const wantTab = qs.get("tab");
  if (wantTab && $(`.tab[data-tab="${CSS.escape(wantTab)}"]`)) setTab(wantTab);
  if (qs.get("vpn") === "1") openVpnManager();
  connectWS();
  setInterval(() => { if (S.tab === "events") renderEvents(); }, 15000);
})();

/* ═══════════════════════════════ file browser ═══════════════════════════ */

const FB = {
  host: null, path: "~", entries: [], sel: new Set(), df: null, user: "",
  showHidden: false, sort: "name", asc: true, loading: false, error: "",
  now: null, nowAt: 0, cursor: -1,
  clip: null,            // { host, hostName, paths, move }
  jobs: [],
};

const LOCAL_ID = "this-computer";
const fbHostName = (id) => (id === LOCAL_ID || !id)
  ? "This computer" : (S.byId[id]?.name || id);

const GLYPH = { dir: "▸", file: "·", link: "→", special: "◇" };

function fbJoin(dir, name) {
  if (dir === "/") return "/" + name;
  return dir.replace(/\/+$/, "") + "/" + name;
}
const fbParent = (p) => {
  const q = p.replace(/\/+$/, "");
  const i = q.lastIndexOf("/");
  return i <= 0 ? "/" : q.slice(0, i);
};

let fbSeq = 0;

async function fbLoad(hostId, path, push = true) {
  FB.host = hostId ?? FB.host ?? S.activeId;
  FB.loading = true; FB.error = ""; FB.sel.clear(); FB.cursor = -1;
  const seq = ++fbSeq;                 // only the newest navigation may paint
  renderFiles();
  try {
    const r = await api(`files/list?host=${encodeURIComponent(FB.host)}` +
                        `&path=${encodeURIComponent(path ?? FB.path)}`,
                        { timeout: 60000 });
    if (seq !== fbSeq) return;
    if (r.error) { FB.error = r.error; }
    else {
      FB.path = r.path || path;
      FB.entries = r.entries || [];
      FB.df = r.df; FB.user = r.user;
      FB.truncated = !!r.truncated; FB.total = r.total ?? FB.entries.length;
      FB.now = r.now; FB.nowAt = Date.now() / 1000;
    }
  } catch (e) {
    if (seq !== fbSeq) return;
    FB.error = e.message;
  }
  if (seq !== fbSeq) return;
  FB.loading = false;
  renderFiles();
}

function fbSorted() {
  const e = FB.entries.filter((x) => FB.showHidden || !x.name.startsWith("."));
  const dir = FB.asc ? 1 : -1;
  const key = FB.sort;
  return e.sort((a, b) => {
    // Directories always lead, whichever column is sorted -- that is what
    // makes a deep tree navigable rather than a wall of mixed rows.
    if ((a.kind === "dir") !== (b.kind === "dir")) return a.kind === "dir" ? -1 : 1;
    let v;
    if (key === "size") v = a.size - b.size;
    else if (key === "mtime") v = a.mtime - b.mtime;
    else if (key === "owner") v = a.owner.localeCompare(b.owner);
    else v = a.name.localeCompare(b.name, undefined, { numeric: true, sensitivity: "base" });
    return v * dir;
  });
}

function fbCrumbs() {
  const p = FB.path || "/";
  const parts = p.split("/").filter(Boolean);
  let acc = "";
  const out = [`<span class="crumb" data-go="/">/</span>`];
  parts.forEach((seg, i) => {
    acc += "/" + seg;
    out.push(`<span class="crumb-sep">/</span>` +
      `<span class="crumb ${i === parts.length - 1 ? "last" : ""}" data-go="${esc(acc)}">${esc(seg)}</span>`);
  });
  return out.join("");
}

function renderFiles() {
  const p = $('.panel[data-panel="files"]');
  const rows = fbSorted();
  const selN = FB.sel.size;
  const locOpts = [{ id: LOCAL_ID, name: "This computer" },
                   ...S.hosts.map((h) => ({ id: h.id, name: h.name }))];

  p.innerHTML = `
  <div class="fb">
    <div class="fb-bar">
      <select class="fb-loc" id="fb-host">
        ${locOpts.map((o) => `<option value="${o.id}" ${o.id === FB.host ? "selected" : ""}>
          ${esc(o.name)}</option>`).join("")}
      </select>
      <button class="ghost-btn sm" id="fb-up" title="Parent directory (Backspace)">↑</button>
      <button class="ghost-btn sm" id="fb-home" title="Home directory">home</button>
      <div class="fb-path" id="fb-crumbs">${fbCrumbs()}</div>
      <button class="ghost-btn sm" id="fb-goto" title="Type a path">path…</button>
      <button class="ghost-btn sm" id="fb-hidden">${FB.showHidden ? "✓ " : ""}hidden</button>
      <button class="ghost-btn sm" id="fb-mkdir">new folder</button>
      <button class="ghost-btn sm" id="fb-upload">upload…</button>
      <button class="ghost-btn sm" id="fb-refresh">refresh</button>
      <button class="ghost-btn sm" id="fb-term" title="Open a shell in this directory">shell here</button>
    </div>

    ${selN ? `<div class="fb-actions">
      <b>${selN}</b> selected
      <button class="ghost-btn sm" id="fb-copy">copy</button>
      <button class="ghost-btn sm" id="fb-cut">cut</button>
      <button class="ghost-btn sm" id="fb-dl">download</button>
      ${selN === 1 ? `<button class="ghost-btn sm" id="fb-rename">rename</button>
        <button class="ghost-btn sm" id="fb-edit">edit</button>
        <button class="ghost-btn sm" id="fb-chmod">permissions</button>` : ""}
      <button class="ghost-btn sm danger-btn" id="fb-del">delete</button>
      <button class="ghost-btn sm" id="fb-clear">clear selection</button>
    </div>` : ""}

    ${FB.clip ? `<div class="fb-actions fb-clip">
      <b>${FB.clip.paths.length}</b> item${FB.clip.paths.length === 1 ? "" : "s"}
      ${FB.clip.move ? "cut" : "copied"} from <b>${esc(FB.clip.hostName)}</b>
      <button class="primary-btn" id="fb-paste" style="padding:3px 10px;font-size:11px">
        paste into ${esc(FB.path.split("/").pop() || "/")}</button>
      <button class="ghost-btn sm" id="fb-clip-clear">clear</button>
    </div>` : ""}

    ${FB.jobs.length ? `<div class="jobs">${FB.jobs.map(jobRow).join("")}</div>` : ""}

    <div class="fb-table-wrap" id="fb-wrap">
      ${FB.loading ? `<div class="loading">Loading ${esc(FB.path)}…</div>`
        : FB.error ? `<div class="loading bad">${esc(FB.error)}</div>`
        : `<table class="fb-tbl">
        <thead><tr>
          <th class="fb-check"><input type="checkbox" id="fb-all"
              ${rows.length && selN === rows.length ? "checked" : ""}></th>
          <th data-sort="name">Name${FB.sort === "name" ? (FB.asc ? " ↑" : " ↓") : ""}</th>
          <th data-sort="size" class="num">Size${FB.sort === "size" ? (FB.asc ? " ↑" : " ↓") : ""}</th>
          <th data-sort="mtime" class="num">Modified${FB.sort === "mtime" ? (FB.asc ? " ↑" : " ↓") : ""}</th>
          <th>Perms</th>
          <th data-sort="owner">Owner</th>
        </tr></thead>
        <tbody>${rows.map((e, i) => `
          <tr data-name="${esc(e.name)}" class="${FB.sel.has(e.name) ? "sel" : ""}">
            <td class="fb-check"><input type="checkbox" data-pick="${esc(e.name)}"
                ${FB.sel.has(e.name) ? "checked" : ""}></td>
            <td><span class="fb-name ${e.kind}${e.exec ? " exec" : ""}">
              <span class="fb-glyph">${GLYPH[e.kind] || "·"}</span>
              <span class="nm" data-open="${esc(e.name)}">${esc(e.name)}</span>
              ${e.link ? `<span class="fb-link-to">→ ${esc(e.link)}</span>` : ""}
            </span></td>
            <td class="num dim">${e.kind === "dir" ? "—" : bytes(e.size)}</td>
            <td class="num dim">${fbAgo(e.mtime)}</td>
            <td class="dim">${esc(e.perms)}</td>
            <td class="dim">${esc(e.owner)}</td>
          </tr>`).join("") ||
          `<tr><td colspan="6" class="dim" style="padding:18px;text-align:center">
             empty directory</td></tr>`}
        </tbody></table>`}
    </div>

    <div class="fb-foot">
      <span>${rows.length} shown${FB.entries.length !== rows.length
        ? ` · ${FB.entries.length - rows.length} hidden` : ""}${
        FB.truncated ? ` · <span class="warn">listing capped at ${
          FB.entries.length} of ${FB.total}</span>` : ""}</span>
      ${FB.df ? `<span>disk ${bytes(FB.df.used)} / ${bytes(FB.df.total)}
         · <b style="color:${sev(FB.df.total ? FB.df.used / FB.df.total * 100 : 0)}">
         ${bytes(FB.df.avail)} free</b></span>` : ""}
      ${FB.user ? `<span>as ${esc(FB.user)}</span>` : ""}
      <span class="dim">drag files onto the list to upload</span>
    </div>
  </div>`;

  bindFiles();
}

/* File ages are measured against the host's clock, carried forward by however
   long ago we sampled it. Without this, any clock skew between this machine
   and a server shows up as files modified in the future. */
function fbAgo(ts) {
  if (!ts) return "—";
  const ref = FB.now ? FB.now + (Date.now() / 1000 - FB.nowAt) : Date.now() / 1000;
  const s = Math.floor(ref - ts);
  if (s < 0) return "just now";
  if (s < 60) return s + "s ago";
  if (s < 3600) return Math.floor(s / 60) + "m ago";
  if (s < 86400) return Math.floor(s / 3600) + "h ago";
  if (s < 86400 * 365) return Math.floor(s / 86400) + "d ago";
  return Math.floor(s / (86400 * 365)) + "y ago";
}

function jobRow(j) {
  const pct = j.pct != null ? j.pct : (j.status === "done" ? 100 : 0);
  return `<div class="job ${j.status}">
    <span>${esc(j.label)}${j.error ? ` — <span class="bad">${esc(j.error)}</span>` : ""}</span>
    <span class="dim">${j.status === "running"
      ? `${bytes(j.done)}${j.total ? " / " + bytes(j.total) : ""}${j.rate ? " · " + bytes(j.rate) + "/s" : ""}`
      : j.status === "done" ? `${bytes(j.done)} in ${j.elapsed}s` : j.status}</span>
    ${j.status === "running"
      ? `<button class="icon-btn" data-cancel="${j.id}" title="Cancel">✕</button>`
      : `<button class="icon-btn" data-dismiss="${j.id}">✕</button>`}
    <div class="job-bar"><div class="job-fill" style="width:${pct}%;
      background:${j.status === "error" ? "var(--red)" : j.status === "done" ? "var(--green)" : "var(--accent)"}"></div></div>
  </div>`;
}

function bindFiles() {
  const $$p = (s) => $$(s, $('.panel[data-panel="files"]'));
  const g = (id) => $("#" + id);

  g("fb-host").onchange = (e) => { FB.path = "~"; fbLoad(e.target.value, "~"); };
  g("fb-up").onclick = () => fbLoad(FB.host, fbParent(FB.path));
  g("fb-home").onclick = () => fbLoad(FB.host, "~");
  g("fb-refresh").onclick = () => fbLoad(FB.host, FB.path);
  g("fb-hidden").onclick = () => { FB.showHidden = !FB.showHidden; renderFiles(); };
  g("fb-mkdir").onclick = fbMkdir;
  g("fb-upload").onclick = fbPickUpload;
  g("fb-goto").onclick = fbGotoPrompt;
  g("fb-term").onclick = () => {
    if (FB.host === LOCAL_ID) return toast("Open a terminal on a host, not this computer", "err");
    newTerm(FB.host, `cd ${JSON.stringify(FB.path)} && exec $SHELL -l`, FB.path.split("/").pop() || "/");
  };

  $$p(".crumb").forEach((c) => c.onclick = () => fbLoad(FB.host, c.dataset.go));
  $$p("th[data-sort]").forEach((th) => th.onclick = () => {
    const k = th.dataset.sort;
    if (FB.sort === k) FB.asc = !FB.asc; else { FB.sort = k; FB.asc = true; }
    renderFiles();
  });
  $$p("[data-open]").forEach((el) => el.onclick = () => {
    const e = FB.entries.find((x) => x.name === el.dataset.open);
    if (!e) return;
    if (e.kind === "dir" || (e.kind === "link" && !e.link.includes(".")))
      fbLoad(FB.host, fbJoin(FB.path, e.name));
    else fbEdit(e);
  });
  $$p("[data-pick]").forEach((cb) => cb.onchange = () => {
    cb.checked ? FB.sel.add(cb.dataset.pick) : FB.sel.delete(cb.dataset.pick);
    renderFiles();
  });
  const all = g("fb-all");
  if (all) all.onchange = () => {
    FB.sel.clear();
    if (all.checked) fbSorted().forEach((e) => FB.sel.add(e.name));
    renderFiles();
  };

  const on = (id, fn) => { const el = g(id); if (el) el.onclick = fn; };
  on("fb-clear", () => { FB.sel.clear(); renderFiles(); });
  on("fb-copy", () => fbClip(false));
  on("fb-cut", () => fbClip(true));
  on("fb-paste", fbPaste);
  on("fb-clip-clear", () => { FB.clip = null; renderFiles(); });
  on("fb-del", fbDelete);
  on("fb-dl", fbDownload);
  on("fb-rename", fbRename);
  on("fb-chmod", fbChmod);
  on("fb-edit", () => {
    const e = FB.entries.find((x) => x.name === [...FB.sel][0]);
    if (e) fbEdit(e);
  });

  $$p("[data-cancel]").forEach((b) => b.onclick = () =>
    api(`files/jobs/${b.dataset.cancel}/cancel`, { method: "POST" }).catch(() => {}));
  $$p("[data-dismiss]").forEach((b) => b.onclick = () => {
    FB.jobs = FB.jobs.filter((j) => j.id !== b.dataset.dismiss);
    renderFiles();
  });

  // Drag and drop straight onto the listing.
  const wrap = g("fb-wrap");
  if (wrap) {
    let depth = 0;
    const show = (on) => {
      let o = wrap.querySelector(".fb-drop");
      if (on && !o) {
        o = document.createElement("div");
        o.className = "fb-drop";
        o.textContent = `Drop to upload into ${FB.path}`;
        wrap.appendChild(o);
      } else if (!on && o) o.remove();
    };
    wrap.addEventListener("dragenter", (e) => { e.preventDefault(); depth++; show(true); });
    wrap.addEventListener("dragover", (e) => e.preventDefault());
    wrap.addEventListener("dragleave", () => { if (--depth <= 0) { depth = 0; show(false); } });
    wrap.addEventListener("drop", (e) => {
      e.preventDefault(); depth = 0; show(false);
      const fs = [...(e.dataTransfer?.files || [])];
      if (fs.length) fbUpload(fs);
    });
  }
}

/* ───────────────────────────── file actions ────────────────────────────── */

const fbSelPaths = () => [...FB.sel].map((n) => fbJoin(FB.path, n));

function fbClip(move) {
  FB.clip = { host: FB.host, hostName: fbHostName(FB.host), paths: fbSelPaths(), move };
  FB.sel.clear();
  toast(`${FB.clip.paths.length} item(s) ${move ? "cut" : "copied"} — open a destination and paste`);
  renderFiles();
}

async function fbPaste() {
  const c = FB.clip;
  if (!c) return;
  if (c.host === FB.host && c.paths.some((p) => fbParent(p) === FB.path) && !c.move)
    { toast("Source and destination are the same folder", "err"); return; }
  try {
    const job = await api("files/transfer", { method: "POST", body: {
      src_host: c.host, paths: c.paths, dst_host: FB.host, dst_dir: FB.path, move: c.move } });
    FB.jobs = [job, ...FB.jobs.filter((j) => j.id !== job.id)].slice(0, 6);
    if (c.move) FB.clip = null;
    renderFiles();
  } catch (e) { toast(e.message, "err"); }
}

async function fbDelete() {
  const paths = fbSelPaths();
  const names = [...FB.sel];
  openModal(`Delete ${paths.length} item${paths.length === 1 ? "" : "s"}`, `
    <p style="margin-top:0">Permanently delete from
      <b>${esc(fbHostName(FB.host))}</b>:</p>
    <pre class="out-pre" style="max-height:200px">${esc(names.join("\n"))}</pre>
    <p class="dim" style="font-size:11.5px">Directories are removed recursively.
      There is no undo and nothing goes to a trash folder.</p>`,
    [{ label: "Delete", danger: true, primary: true, fn: async () => {
      closeModal();
      try {
        const r = await api("files/delete", { method: "POST",
          body: { host: FB.host, paths } });
        r.ok ? toast(`Deleted ${r.deleted} item(s)`, "ok") : toast(r.error, "err");
      } catch (e) { toast(e.message, "err"); }
      fbLoad(FB.host, FB.path);
    } }]);
}

function fbDownload() {
  for (const name of FB.sel) {
    const e = FB.entries.find((x) => x.name === name);
    if (!e) continue;
    const qs = new URLSearchParams({ t: TOKEN, host: FB.host, path: fbJoin(FB.path, name) });
    if (e.kind === "dir") qs.set("dir", "1"); else qs.set("size", String(e.size));
    const a = document.createElement("a");
    a.href = "/api/files/download?" + qs.toString();
    a.download = e.kind === "dir" ? name + ".tar.gz" : name;
    document.body.appendChild(a); a.click(); a.remove();
  }
  toast(`Downloading ${FB.sel.size} item(s) — directories arrive as .tar.gz`);
}

function fbMkdir() {
  openModal("New folder", `
    <div class="field"><label>Name</label>
      <input id="fb-newdir" class="text-input mono" placeholder="new-folder" autofocus></div>
    <div class="hint dim">Created in ${esc(FB.path)} on ${esc(fbHostName(FB.host))}.</div>`,
    [{ label: "Create", primary: true, fn: async () => {
      const n = $("#fb-newdir").value.trim();
      if (!n) return;
      closeModal();
      const r = await api("files/mkdir", { method: "POST",
        body: { host: FB.host, path: fbJoin(FB.path, n) } });
      r.ok ? fbLoad(FB.host, FB.path) : toast(r.error, "err");
    } }]);
}

function fbRename() {
  const old = [...FB.sel][0];
  openModal(`Rename ${old}`, `
    <div class="field"><label>New name</label>
      <input id="fb-rn" class="text-input mono" value="${esc(old)}" autofocus></div>
    <div class="hint dim">A path with slashes moves the item instead of renaming it.</div>`,
    [{ label: "Rename", primary: true, fn: async () => {
      const n = $("#fb-rn").value.trim();
      if (!n || n === old) return closeModal();
      closeModal();
      const dst = n.startsWith("/") ? n : fbJoin(FB.path, n);
      const r = await api("files/rename", { method: "POST",
        body: { host: FB.host, src: fbJoin(FB.path, old), dst } });
      r.ok ? fbLoad(FB.host, FB.path) : toast(r.error || "rename failed", "err");
    } }]);
}

function fbChmod() {
  const name = [...FB.sel][0];
  const e = FB.entries.find((x) => x.name === name);
  openModal(`Permissions — ${name}`, `
    <div class="field"><label>Octal mode</label>
      <input id="fb-mode" class="text-input mono" placeholder="644" autofocus></div>
    <div class="hint dim">Currently <code>${esc(e?.perms || "")}</code>.
      Common: 644 files, 755 executables and directories, 600 secrets.</div>`,
    [{ label: "Apply", primary: true, fn: async () => {
      const m = $("#fb-mode").value.trim();
      closeModal();
      const r = await api("files/chmod", { method: "POST",
        body: { host: FB.host, path: fbJoin(FB.path, name), mode: m } });
      r.ok ? fbLoad(FB.host, FB.path) : toast(r.error || "chmod failed", "err");
    } }]);
}

function fbGotoPrompt() {
  openModal("Go to path", `
    <div class="field"><label>Path on ${esc(fbHostName(FB.host))}</label>
      <input id="fb-goto-p" class="text-input mono" value="${esc(FB.path)}" autofocus></div>`,
    [{ label: "Go", primary: true, fn: () => {
      const v = $("#fb-goto-p").value.trim();
      closeModal(); if (v) fbLoad(FB.host, v);
    } }]);
}

/* ─────────────────────────────── editor ────────────────────────────────── */

async function fbEdit(entry) {
  const path = fbJoin(FB.path, entry.name);
  toast(`Opening ${entry.name}…`);
  let r;
  try {
    r = await api(`files/read?host=${encodeURIComponent(FB.host)}&path=${encodeURIComponent(path)}`);
  } catch (e) { return toast(e.message, "err"); }
  if (!r.ok) {
    return openModal(entry.name, `<p class="dim">${esc(r.error)}</p>
      <p class="dim" style="font-size:11.5px">Use <b>download</b> to fetch it instead.</p>`, []);
  }
  openModal(`${entry.name} — ${fbHostName(FB.host)}`, `
    <div class="dim" style="font-size:11px;margin-bottom:6px">
      ${esc(path)} · ${bytes(r.bytes)} · ${esc(entry.perms)} · ${esc(entry.owner)}</div>
    <textarea id="fb-editor" class="editor-area" spellcheck="false">${esc(r.text)}</textarea>
    <div class="hint dim">Saving keeps the previous contents alongside as
      <code>${esc(entry.name)}.fleet.bak</code>.</div>`,
    [{ label: "Save", primary: true, fn: async () => {
      const text = $("#fb-editor").value;
      const res = await api("files/write", { method: "POST",
        body: { host: FB.host, path, text } });
      if (res.ok) { closeModal(); toast(`Saved ${entry.name} (${bytes(res.bytes)})`, "ok");
                    fbLoad(FB.host, FB.path); }
      else toast(res.error || "write failed", "err");
    } }]);
}

/* ─────────────────────────────── uploads ──────────────────────────────── */

function fbPickUpload() {
  const inp = document.createElement("input");
  inp.type = "file"; inp.multiple = true;
  inp.onchange = () => { if (inp.files.length) fbUpload([...inp.files]); };
  inp.click();
}

function fbUpload(fileList) {
  // XHR rather than fetch: it is the only way to get real upload progress,
  // which matters when you drop a 200MB tarball onto a VPS.
  const dir = FB.path, host = FB.host;
  for (const f of fileList) {
    const job = { id: "up-" + Math.random().toString(36).slice(2, 8), kind: "upload",
                  label: `Upload ${f.name} → ${fbHostName(host)}`, status: "running",
                  total: f.size, done: 0, error: "", elapsed: 0, rate: 0, pct: 0 };
    FB.jobs = [job, ...FB.jobs].slice(0, 6);
    renderFiles();
    const started = Date.now();

    const xhr = new XMLHttpRequest();
    const qs = new URLSearchParams({ t: TOKEN, host, path: fbJoin(dir, f.name) });
    xhr.open("POST", "/api/files/upload?" + qs.toString());
    xhr.setRequestHeader("Content-Type", "application/octet-stream");
    xhr.upload.onprogress = (e) => {
      job.done = e.loaded;
      job.pct = e.total ? Math.round(e.loaded / e.total * 100) : 0;
      job.elapsed = +((Date.now() - started) / 1000).toFixed(1);
      job.rate = job.elapsed > 0.3 ? Math.round(job.done / job.elapsed) : 0;
      if (S.tab === "files") renderFiles();
    };
    xhr.onload = () => {
      let r = {}; try { r = JSON.parse(xhr.responseText); } catch {}
      job.status = xhr.status === 200 && r.ok ? "done" : "error";
      job.error = r.error || (xhr.status !== 200 ? "HTTP " + xhr.status : "");
      job.done = job.total;
      job.elapsed = +((Date.now() - started) / 1000).toFixed(1);
      if (job.status === "done" && host === FB.host && dir === FB.path) fbLoad(FB.host, FB.path);
      else renderFiles();
    };
    xhr.onerror = () => { job.status = "error"; job.error = "network error"; renderFiles(); };
    xhr.send(f);
  }
}
