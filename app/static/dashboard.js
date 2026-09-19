// Staff dashboard: the whole service desk at a glance, refreshed every 15 s.
import { $, api, busy, deptBadge, el, formatTime, initPage, priorityBadge,
         relative, slug, statusBadge, toast } from "/static/common.js";

let lastLoaded = null;

// A list of labelled bars; each bar's width is its share of the biggest.
function bars(id, counts, classPrefix) {
  const entries = Object.entries(counts).sort((a, b) => b[1] - a[1]);
  const max = Math.max(1, ...entries.map(([, n]) => n));
  $(id).replaceChildren(...(entries.length ? entries.map(([name, n]) =>
    el("li", {},
      el("div", { class: "row" }, el("span", {}, name), el("b", {}, n)),
      el("div", { class: "track" },
        el("div", { class: `fill ${classPrefix ? `${classPrefix}-${slug(name)}` : ""}`,
                    style: `width:${(n / max) * 100}%` }))))
    : [el("li", { class: "muted small" }, "No reports yet.")]));
}

function table(id, rows, columns) {
  const head = el("tr", {}, columns.map(([label]) => el("th", {}, label)));
  const body = rows.length
    ? rows.map((row) => el("tr", {}, columns.map(([, cell]) => el("td", {}, cell(row)))))
    : [el("tr", {}, el("td", { class: "empty", colspan: columns.length }, "Nothing here. 🎉"))];
  $(id).replaceChildren(el("thead", {}, head), el("tbody", {}, body));
}

async function load() {
  const d = await api("/api/dashboard");
  $("kpi-total").textContent = d.total;
  $("kpi-open").textContent = d.summary.open;
  $("kpi-urgent").textContent = d.summary.urgent_open;
  $("kpi-overdue").textContent = d.summary.overdue;
  $("kpi-overdue-card").classList.toggle("alert", d.summary.overdue > 0);

  bars("by-department", d.by_department, "dept");
  bars("by-status", d.by_status, "st");
  bars("by-priority", d.by_priority, "pri");

  table("overdue", d.overdue, [
    ["#", (r) => r.ticket_id],
    ["Report", (r) => r.subject],
    ["Department", (r) => deptBadge(r.department)],
    ["Status", (r) => statusBadge(r.status)],
    ["Was due", (r) => (r.due_by ? relative(r.due_by) : "—")],
  ]);
  table("recent", d.recent, [
    ["#", (r) => r.ticket_id],
    ["Report", (r) => r.subject],
    ["Department", (r) => deptBadge(r.department)],
    ["Priority", (r) => priorityBadge(r.priority)],
    ["Status", (r) => statusBadge(r.status)],
    ["Reported", (r) => formatTime(r.created_at)],
  ]);
  lastLoaded = Date.now();
  showUpdated();
}

function showUpdated() {
  if (!lastLoaded) return;
  const seconds = Math.round((Date.now() - lastLoaded) / 1000);
  $("updated").textContent = seconds < 5 ? "Updated just now" : `Updated ${seconds} s ago`;
}

$("refresh").addEventListener("click", (event) =>
  busy(event.currentTarget, "Refreshing…", load).catch((e) => toast(e.message)));

(async () => {
  const mode = await initPage();
  if (mode.demo) $("source").textContent = "Demo mode · pretend Freshdesk in memory";
  else if (mode.helpdesk) $("source").textContent = `Live from ${mode.helpdesk} · last 30 days`;
  load().catch((e) => toast(e.message));
  setInterval(() => { if (document.visibilityState === "visible") load().catch(() => {}); }, 15000);
  setInterval(showUpdated, 1000);
})();
