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

export function fill(node, ...children) {
  node.replaceChildren(...children.flat().filter((c) => c !== null && c !== undefined && c !== false));
}

export const slug = (text) => String(text || "unassigned").toLowerCase().replace(/\s+/g, "-");

export const STAGES = ["Open", "Assigned", "In Progress", "Resolved", "Closed"];

export function deptBadge(department) {
  const name = department || "Awaiting triage";
  return el("span", { class: `badge dept-${slug(department)}` }, name);
}

export function priorityBadge(priority) {
  return el("span", { class: `badge pri-${slug(priority)}` },
    priority);
}

export function statusBadge(status) {
  return el("span", { class: `badge st-${slug(status)}` }, status);
}

export function formatTime(iso) {
  return new Date(iso).toLocaleString([], {
    day: "numeric", month: "short", hour: "2-digit", minute: "2-digit",
  });
}

export function relative(iso) {
  const minutes = Math.round((new Date(iso) - Date.now()) / 60000);
  const size = Math.abs(minutes);
  const text = size < 60 ? `${size} min`
    : size < 48 * 60 ? `${Math.round(size / 60)} h`
    : `${Math.round(size / 1440)} days`;
  return minutes >= 0 ? `in ${text}` : `${text} ago`;
}

let toastTimer;
export function toast(message) {
  let box = document.querySelector(".toast");
  if (!box) box = document.body.appendChild(el("div", { class: "toast", role: "status" }));
  box.textContent = message;
  box.classList.remove("hidden");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => box.classList.add("hidden"), 3500);
}

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
