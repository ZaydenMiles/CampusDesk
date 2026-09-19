import { $, api, busy, deptBadge, el, fill, initPage, priorityBadge, statusBadge, toast } from "/static/common.js";

const SAMPLES = [
  { location: "VMS Building, 3rd floor restroom", subject: "Toilet blocked on 3rd floor",
    description: "The toilet in the men's restroom is blocked and water is not draining." },
  { location: "Library, 2nd floor", subject: "Wi-Fi not working in the library",
    description: "Cannot connect to the campus wifi since this morning. Other students have the same problem." },
  { location: "SM Building, room 402", subject: "Classroom door is locked",
    description: "Our 9:00 class is waiting outside, the room is locked and nobody has the key." },
  { location: "CL Building, room 201", subject: "Water leak from ceiling",
    description: "Water is dripping from the ceiling next to the whiteboard. There is a puddle on the floor." },
];

const form = $("report-form");

function useSample(sample) {
  for (const [name, value] of Object.entries(sample)) form.elements[name].value = value;
  if (!form.elements.name.value) form.elements.name.value = "Lwin";
  updateCounter();
  clearErrors();
}

function updateCounter() {
  $("counter").textContent = `${form.elements.description.value.length} / 5000`;
}

function clearErrors() {
  for (const field of form.querySelectorAll(".field")) {
    field.classList.remove("invalid");
    field.querySelector(".field-error")?.remove();
  }
}

const FRIENDLY = {
  name: "Please enter your name.",
  email: "Please enter a valid email address, e.g. name@university.edu.",
  location: "Tell us where the problem is.",
  subject: "Give it a short title (at least 5 characters).",
  description: "Describe the problem in a sentence or two (at least 10 characters).",
};

function showErrors(detail) {
  clearErrors();
  for (const problem of detail) {
    const name = problem.loc.at(-1);
    const field = form.querySelector(`[data-field="${name}"]`);
    if (!field || field.classList.contains("invalid")) continue;
    field.classList.add("invalid");
    field.append(el("div", { class: "field-error" }, FRIENDLY[name] || problem.msg));
  }
  form.querySelector(".invalid input, .invalid textarea")?.focus();
}

function showConfirmation(result, email) {
  try { localStorage.setItem("campusdesk:last", JSON.stringify({ id: result.ticket_id, email })); } catch {}

  const speed = result.routed_in_ms < 100 ? "instantly"
    : `in ${(result.routed_in_ms / 1000).toFixed(1)} s`;
  fill($("done-card"),
    el("div", { class: "success-icon" }, "✓"),
    el("div", { class: "muted small" }, "Report received"),
    el("div", { class: "ticket-no" }, `#${result.ticket_id}`),
    el("p", { class: "muted" }, `Freshdesk categorised and routed it ${speed}. `,
      "Save this number to track your report."),
    el("div", { class: "facts" },
      el("div", { class: "fact" }, el("div", { class: "label" }, "Department"), deptBadge(result.department)),
      el("div", { class: "fact" }, el("div", { class: "label" }, "Priority"), priorityBadge(result.priority)),
      el("div", { class: "fact" }, el("div", { class: "label" }, "Status"), statusBadge(result.status)),
    ),
    result.priority === "Urgent"
      ? el("div", { class: "callout", style: "margin-bottom:16px" },
          el("span", {}, "Marked urgent: the team must fix this within one hour."))
      : null,
    el("div", { class: "actions" },
      el("a", { class: "btn btn-primary", href: `/track?id=${result.ticket_id}` }, "Track this report →"),
      el("button", { class: "btn btn-ghost", type: "button", onclick: reset }, "Report another problem"),
    ),
  );
  $("form-card").classList.add("hidden");
  $("done-card").classList.remove("hidden");
}

function reset() {
  form.reset();
  updateCounter();
  $("done-card").classList.add("hidden");
  $("form-card").classList.remove("hidden");
  form.elements.name.focus();
}

document.querySelectorAll("[data-sample]").forEach((chip) =>
  chip.addEventListener("click", () => useSample(SAMPLES[chip.dataset.sample])));

form.elements.description.addEventListener("input", updateCounter);

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const report = Object.fromEntries(new FormData(form));
  try {
    const result = await busy($("submit"), "Sending to Freshdesk…",
      () => api("/api/reports", { method: "POST", body: JSON.stringify(report) }));
    showConfirmation(result, report.email);
  } catch (error) {
    if (error.status === 422 && Array.isArray(error.detail)) showErrors(error.detail);
    else toast(error.message);
  }
});

initPage();
