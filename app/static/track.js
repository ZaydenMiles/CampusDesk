// Track page: one report's progress, deadline and history.
import { $, api, busy, deptBadge, el, fill, formatTime, initPage, priorityBadge,
         relative, STAGES, statusBadge, toast } from "/static/common.js";

const form = $("track-form");
let current = null;          // { id, email } of the report on screen
let demo = false;
let refreshTimer = null;

// ---------------------------------------------------------- rendering
function stepper(status) {
  const at = STAGES.indexOf(status);
  return el("div", { class: "stepper" }, STAGES.map((stage, i) =>
    el("div", { class: `step ${i < at ? "done" : i === at ? "current" : ""}` },
      el("div", { class: "dot" }, i < at ? "✓" : i + 1),
      stage)));
}

function deadline(report) {
  if (!report.due_by || ["Resolved", "Closed"].includes(report.status)) return "—";
  const late = new Date(report.due_by) < Date.now();
  return el("span", { style: late ? "color:var(--danger);font-weight:600" : "" },
    late ? `Overdue by ${relative(report.due_by).replace(" ago", "")}` : `Fix due ${relative(report.due_by)}`);
}

function timeline(events) {
  if (!events.length) return el("p", { class: "muted small" }, "No updates recorded yet.");
  return el("ul", { class: "timeline" }, events.map((e) =>
    el("li", {},
      el("div", {}, el("b", {}, e.status || "Update"),
        e.group_name ? ` · ${e.group_name}` : "", e.agent ? ` · ${e.agent}` : ""),
      el("div", { class: "when" }, formatTime(e.received_at)))));
}

function render(report) {
  fill($("result-card"),
    el("div", { class: "card-head" },
      el("div", {},
        el("div", { class: "muted small" }, `Report #${report.ticket_id}`),
        el("h2", {}, report.subject)),
      statusBadge(report.status)),
    STAGES.includes(report.status) ? stepper(report.status) : null,
    report.is_escalated
      ? el("div", { class: "callout", style: "margin-bottom:16px" }, "🚨",
          el("span", {}, "Escalated: this report missed its deadline and a supervisor has been alerted."))
      : null,
    el("div", { class: "facts" },
      el("div", { class: "fact" }, el("div", { class: "label" }, "Department"), deptBadge(report.department)),
      el("div", { class: "fact" }, el("div", { class: "label" }, "Priority"), priorityBadge(report.priority)),
      el("div", { class: "fact" }, el("div", { class: "label" }, "Deadline"), deadline(report))),
    el("h3", { style: "margin:4px 0 12px" }, "History"),
    timeline(report.timeline),
    el("div", { class: "actions", style: "margin-top:8px" },
      el("span", { class: "muted small", style: "align-self:center" },
        `Reported ${formatTime(report.created_at)} · refreshes every 10 s`),
      demo && report.status !== "Closed"
        ? el("button", { class: "btn btn-ghost", type: "button", onclick: advance },
            "Demo: agent moves it to the next status")
        : null),
  );
}

// -------------------------------------------------------------- data
async function load({ quiet = false } = {}) {
  if (!current) return;
  try {
    const report = await api(`/api/reports/${current.id}/track`,
      { method: "POST", body: JSON.stringify({ email: current.email }) });
    render(report);
  } catch (error) {
    if (quiet) return;                       // a failed background refresh stays silent
    $("result-card").replaceChildren(el("div", { class: "empty" }, error.message));
  }
}

async function advance(event) {
  await busy(event.currentTarget, "Updating…",
    () => api(`/api/demo/reports/${current.id}/advance`, { method: "POST" }));
  await load();
}

// Refresh while the tab is visible, so a status changed by staff in
// Freshdesk (and pushed to us by webhook) appears without clicking.
function autoRefresh() {
  clearInterval(refreshTimer);
  refreshTimer = setInterval(() => {
    if (document.visibilityState === "visible") load({ quiet: true });
  }, 10000);
}

// -------------------------------------------------------------- events
form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const id = form.elements.ticket.value.trim().replace(/^#/, "");
  const email = form.elements.email.value.trim();
  if (!/^\d+$/.test(id) || !email) return toast("Enter the report number and your email.");
  current = { id, email };
  try { localStorage.setItem("campusdesk:last", JSON.stringify(current)); } catch {}
  await busy($("find"), "Looking…", () => load());
  autoRefresh();
});

// Arriving from the Report page (/track?id=42): fill in the number, and the
// email this browser remembered. The email is never put in any URL.
(async () => {
  demo = (await initPage()).demo;
  let saved = null;
  try { saved = JSON.parse(localStorage.getItem("campusdesk:last")); } catch {}
  const id = new URLSearchParams(location.search).get("id") || saved?.id;
  if (id) form.elements.ticket.value = id;
  if (saved?.email && String(saved.id) === String(id)) {
    form.elements.email.value = saved.email;
    form.requestSubmit();
  }
})();
