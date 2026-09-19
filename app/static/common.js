// CampusDesk: helpers shared by all three pages.
// Loaded as an ES module (<script type="module">), so each page imports
// exactly what it uses. No framework, no build step.

// ---------------------------------------------------------------- API
// Calls our FastAPI backend. On an error it throws, carrying the server's
// "detail" message so the page can show something useful.
export async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const body = response.status === 204 ? null : await response.json();
  if (!response.ok) {
    const error = new Error(typeof body?.detail === "string" ? body.detail : "Something went wrong");
    error.status = response.status;
    error.detail = body?.detail;
    throw error;
  }
  return body;
}

// --------------------------------------------------------------- DOM
// Builds an element. Text always goes in through textContent, never
// innerHTML, so a report containing <script> is shown as plain text (no XSS).
export function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (key === "class") node.className = value;
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value);
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

export const $ = (id) => document.getElementById(id);

// Replaces everything inside `node`. Unlike node.replaceChildren(), it skips
// null/false, so optional parts can be written as  condition ? el(...) : null
export function fill(node, ...children) {
  node.replaceChildren(...children.flat().filter((c) => c !== null && c !== undefined && c !== false));
}

// "IT Support" -> "it-support", used to pick a CSS colour class.
export const slug = (text) => String(text || "unassigned").toLowerCase().replace(/\s+/g, "-");

// --------------------------------------------------------- vocabulary
export const DEPARTMENTS = {
  "Maintenance": "🔧",
  "Security": "🛡️",
  "IT Support": "💻",
  "Service Desk": "🗂️",
};

// The lifecycle every report moves through, in order.
export const STAGES = ["Open", "Assigned", "In Progress", "Resolved", "Closed"];

export function deptBadge(department) {
  const name = department || "Awaiting triage";
  return el("span", { class: `badge dept-${slug(department)}` },
    el("span", {}, DEPARTMENTS[department] || "⏳"), el("span", {}, name));
}

export function priorityBadge(priority) {
  return el("span", { class: `badge pri-${slug(priority)}` },
    priority === "Urgent" ? "⚠️ Urgent" : priority);
}

export function statusBadge(status) {
  return el("span", { class: `badge st-${slug(status)}` }, status);
}

// ------------------------------------------------------------- time
export function formatTime(iso) {
  return new Date(iso).toLocaleString([], {
    day: "numeric", month: "short", hour: "2-digit", minute: "2-digit",
  });
}

// "in 45 min", "3 h ago", "in 2 days"
export function relative(iso) {
  const minutes = Math.round((new Date(iso) - Date.now()) / 60000);
  const size = Math.abs(minutes);
  const text = size < 60 ? `${size} min`
    : size < 48 * 60 ? `${Math.round(size / 60)} h`
    : `${Math.round(size / 1440)} days`;
  return minutes >= 0 ? `in ${text}` : `${text} ago`;
}

// ------------------------------------------------------------ feedback
let toastTimer;
export function toast(message) {
  let box = document.querySelector(".toast");
  if (!box) box = document.body.appendChild(el("div", { class: "toast", role: "status" }));
  box.textContent = message;
  box.classList.remove("hidden");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => box.classList.add("hidden"), 3500);
}

// Puts a spinner in a button while `work` runs, and stops double clicks.
export async function busy(button, label, work) {
  const original = button.innerHTML;
  button.disabled = true;
  button.replaceChildren(el("span", { class: "spinner" }), label);
  try {
    return await work();
  } finally {
    button.disabled = false;
    button.innerHTML = original;
  }
}

// ---------------------------------------------------------- page shell
// Every page calls this once: highlights the current menu item and shows
// the demo banner when the backend runs with DEMO_MODE=1.
export async function initPage() {
  for (const link of document.querySelectorAll(".nav a")) {
    if (link.getAttribute("href") === location.pathname) link.setAttribute("aria-current", "page");
  }
  try {
    const mode = await api("/api/mode");
    if (mode.demo) {
      document.body.prepend(el("div", { class: "demo-banner" },
        "Demo mode: a pretend Freshdesk running in memory. Nothing is sent anywhere."));
    }
    return mode;
  } catch {
    return { demo: false };
  }
}
