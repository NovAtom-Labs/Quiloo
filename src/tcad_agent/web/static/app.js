"use strict";

const STAGES = ["request", "clarify", "review", "results"];
const PAGE_COPY = {
  request: ["Simulation workflow", "Define the device study", "Specify geometry, materials, contacts, physics, operating conditions, and required outputs."],
  clarify: ["Required inputs", "Resolve material and boundary conditions", "Provide only the missing values that materially change the experiment."],
  review: ["Execution plan", "Review the normalized simulation plan", "Confirm the structure, models, outputs, backend, and limitations before execution."],
  results: ["Simulation results", "Inspect validated device results", "Review spatial fields, operating points, validation checks, and the exact simulated structure."],
};

const promptInput = document.querySelector("#prompt");
const backendInput = document.querySelector("#backend");
const backendDescription = document.querySelector("#backend-description");
const submitButton = document.querySelector("#submit");
const answerButton = document.querySelector("#answer");
const approveButton = document.querySelector("#approve");
const runButton = document.querySelector("#run");
const stateLabel = document.querySelector("#state");
const clarifyState = document.querySelector("#clarify-state");
const warning = document.querySelector("#warning");
const questions = document.querySelector("#questions");
const resolvedAnswers = document.querySelector("#resolved-answers");
const requestContext = document.querySelector("#request-context");
const planSummary = document.querySelector("#plan-summary");
const reviewDetails = document.querySelector("#review-details");
const planDigest = document.querySelector("#plan-digest");
const plan = document.querySelector("#plan");
const validationStatus = document.querySelector("#validation-status");
const validationList = document.querySelector("#validation-list");
const validationDetails = document.querySelector("#validation-details");
const validation = document.querySelector("#validation");
const artifacts = document.querySelector("#artifacts");
const artifactLinks = document.querySelector("#artifact-links");
const resultsLoading = document.querySelector("#results-loading");
const resultsWorkspace = document.querySelector("#results-workspace");
const progressStages = [...document.querySelectorAll("#workflow-progress li")];
const workflowPages = [...document.querySelectorAll("[data-workflow-page]")];
const resultsCache = new Map();

let current = null;
let displayedStage = "request";

async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: {"Content-Type": "application/json"},
    ...options,
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.message || data.detail || "Request failed");
  return data;
}

function setHidden(node, hidden) {
  node.classList.toggle("hidden", hidden);
}

function showNotice(message, kind = "warning") {
  warning.textContent = message || "";
  warning.dataset.kind = kind;
  setHidden(warning, !message);
}

function formatLabel(value) {
  return String(value || "")
    .replaceAll("_", " ")
    .replaceAll("-", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatNumber(value) {
  if (!Number.isFinite(value)) return String(value);
  const absolute = Math.abs(value);
  if (absolute >= 1e6 || (absolute > 0 && absolute < 1e-3)) {
    return value.toExponential(3).replace(/\.0+e/, "e").replace(/(\.\d*?)0+e/, "$1e").replace("e+", "e");
  }
  return Number(value.toPrecision(6)).toString();
}

function formatQuantity(value) {
  if (value && typeof value === "object" && "magnitude_si" in value && "si_unit" in value) {
    const magnitude = Number(value.magnitude_si);
    if (value.si_unit === "meter") {
      if (Math.abs(magnitude) >= 1e-3) return `${formatNumber(magnitude * 1e3)} mm`;
      if (Math.abs(magnitude) >= 1e-6) return `${formatNumber(magnitude * 1e6)} µm`;
      if (Math.abs(magnitude) >= 1e-9) return `${formatNumber(magnitude * 1e9)} nm`;
    }
    if (value.si_unit === "1 / meter ** 3") return `${formatNumber(magnitude / 1e6)} cm⁻³`;
    if (value.si_unit === "kelvin") return `${formatNumber(magnitude)} K`;
    if (value.si_unit === "kilogram * meter ** 2 / ampere / second ** 3") return `${formatNumber(magnitude)} V`;
    if (value.si_unit === "kilogram * meter ** 2 / second ** 2") return `${formatNumber(magnitude / 1.602176634e-19)} eV`;
    return `${formatNumber(magnitude)} ${value.si_unit}`;
  }
  return formatLabel(value);
}

function activeStage(view) {
  if (!view) return "request";
  const state = view.state;
  if (state === "needs_clarification") return "clarify";
  if (state === "failed") {
    if (view.validation || view.bundle_path) return "results";
    if (view.spec || view.plan) return "review";
    return "request";
  }
  if (["spec_drafted", "spec_validated", "user_confirmation_required", "compiled"].includes(state)) return "review";
  if (["running", "validating", "completed"].includes(state)) return "results";
  return "request";
}

function parseLocation() {
  const match = window.location.pathname.match(/^\/requests\/([0-9a-f-]{36})\/(request|clarify|review|results)$/i);
  return match ? {id: match[1], stage: match[2]} : {id: null, stage: "request"};
}

function workflowPath(stage) {
  return current ? `/requests/${current.id}/${stage}` : "/simulate";
}

function updatePageCopy(stage) {
  const [eyebrow, title, copy] = PAGE_COPY[stage];
  document.querySelector("#page-eyebrow").textContent = eyebrow;
  document.querySelector("#page-title").textContent = title;
  document.querySelector("#page-copy").textContent = copy;
  document.title = `${formatLabel(stage)} · Quiloo TCAD`;
}

function showPage(stage, historyMode = null) {
  const maximum = STAGES.indexOf(activeStage(current));
  const requested = STAGES.indexOf(stage);
  displayedStage = requested <= maximum || !current ? stage : activeStage(current);
  for (const page of workflowPages) setHidden(page, page.dataset.workflowPage !== displayedStage);
  updatePageCopy(displayedStage);
  renderProgress();
  if (historyMode) {
    window.history[historyMode]({requestId: current?.id || null, stage: displayedStage}, "", workflowPath(displayedStage));
  }
  window.scrollTo({top: 0, behavior: "smooth"});
}

function renderProgress() {
  const maximum = STAGES.indexOf(activeStage(current));
  for (const item of progressStages) {
    const index = STAGES.indexOf(item.dataset.stage);
    item.classList.toggle("is-active", item.dataset.stage === displayedStage);
    item.classList.toggle("is-complete", Boolean(current) && index < maximum);
    const button = item.querySelector("button");
    button.disabled = !current ? index > 0 : index > maximum;
  }
}

function summaryCard(label, value, detail = "") {
  const card = document.createElement("article");
  card.className = "summary-card";
  const name = document.createElement("span");
  name.textContent = label;
  const primary = document.createElement("strong");
  primary.textContent = value;
  card.append(name, primary);
  if (detail) {
    const secondary = document.createElement("small");
    secondary.textContent = detail;
    card.appendChild(secondary);
  }
  return card;
}

function reviewGroup(title, entries) {
  const group = document.createElement("section");
  group.className = "review-group";
  const heading = document.createElement("h4");
  heading.textContent = title;
  group.appendChild(heading);
  for (const [label, value] of entries) {
    const row = document.createElement("div");
    row.className = "review-row";
    const name = document.createElement("span");
    name.textContent = label;
    const detail = document.createElement("strong");
    detail.textContent = value;
    row.append(name, detail);
    group.appendChild(row);
  }
  return group;
}

function regionThickness(region) {
  const start = Number(region.x0?.magnitude_si);
  const end = Number(region.x1?.magnitude_si);
  if (!Number.isFinite(start) || !Number.isFinite(end)) return "Not specified";
  return formatQuantity({magnitude_si: end - start, si_unit: "meter"});
}

function studyReview(study) {
  const entries = [["Mode", formatLabel(study.kind || "Not specified")]];
  if (study.kind === "dc") {
    entries.push(
      ["Driven contact", formatLabel(study.contact || "Not specified")],
      ["Sweep", `${formatQuantity(study.start)} to ${formatQuantity(study.stop)}`],
      ["Step", formatQuantity(study.step)],
    );
  } else if (study.kind === "equilibrium") {
    entries.push(["External bias", "None"]);
  }
  return reviewGroup("Study", entries);
}

function renderRequest(view) {
  if (!view) return;
  promptInput.value = view.prompt || "";
  backendInput.value = view.backend || "devsim";
  renderBackendDescription();
}

function renderQuestions(view) {
  questions.replaceChildren();
  resolvedAnswers.replaceChildren();
  requestContext.textContent = view?.prompt || "No active research request.";
  const waiting = view?.state === "needs_clarification";
  for (const item of view?.questions || []) {
    const wrapper = document.createElement("label");
    wrapper.className = "question-field";
    const label = document.createElement("span");
    label.textContent = item.prompt;
    const input = document.createElement("input");
    input.dataset.field = item.field;
    input.name = item.field;
    input.autocomplete = "off";
    input.placeholder = `Enter ${formatLabel(item.field.split(".").at(-1))}`;
    wrapper.append(label, input);
    questions.appendChild(wrapper);
  }
  for (const [field, value] of Object.entries(view?.clarification_answers || {})) {
    resolvedAnswers.appendChild(reviewGroup("Resolved input", [[formatLabel(field), value]]));
  }
  if (!waiting && !resolvedAnswers.children.length) {
    const message = document.createElement("p");
    message.className = "empty-state";
    message.textContent = "This request did not require additional clarification.";
    resolvedAnswers.appendChild(message);
  }
  setHidden(questions, !waiting);
  setHidden(answerButton, !waiting);
  setHidden(resolvedAnswers, waiting);
  clarifyState.textContent = waiting ? "Waiting" : "Resolved";
  clarifyState.dataset.status = waiting ? "needs_clarification" : "completed";
  updateAnswerReadiness();
}

function collectAnswers() {
  return [...questions.querySelectorAll("input")]
    .filter((input) => input.value.trim())
    .map((input) => ({field: input.dataset.field, value: input.value.trim()}));
}

function updateAnswerReadiness() {
  const inputs = [...questions.querySelectorAll("input")];
  answerButton.disabled = inputs.length === 0 || inputs.some((input) => !input.value.trim());
}

function renderPlan(view) {
  const spec = view?.spec || view?.plan?.spec;
  planSummary.replaceChildren();
  reviewDetails.replaceChildren();
  if (!spec) return;
  const regions = spec.regions || [];
  const profiles = spec.profiles || [];
  const contacts = spec.contacts || [];
  const equations = spec.physics?.equations || [];
  const models = spec.physics?.models || [];
  const observables = spec.observables || [];
  const study = spec.study || {};
  const materials = [...new Set(regions.map((region) => formatLabel(region.material)))];
  planSummary.append(
    summaryCard("Backend", String(view.backend).toUpperCase(), view.backend === "devsim" ? "Local deterministic runner" : "Licensed remote runner"),
    summaryCard("Structure", `${regions.length} region${regions.length === 1 ? "" : "s"}`, `${materials.join(", ") || "Material not specified"} · ${spec.dimension || 1}D · ${contacts.length} contacts`),
    summaryCard("Physics", formatQuantity(spec.physics?.temperature || "Not specified"), `${models.length} declared models`),
    summaryCard("Study", formatLabel(study.kind || "Not specified"), study.kind === "equilibrium" ? "No external bias sweep" : "Bounded bias study"),
  );
  if (spec.metadata?.limitation) planSummary.append(summaryCard("Declared limitation", "Approximation in use", spec.metadata.limitation));
  reviewDetails.replaceChildren(
    reviewGroup("Geometry", regions.map((region) => [formatLabel(region.id), `${formatLabel(region.material)} · ${regionThickness(region)} · mesh ${formatQuantity(region.mesh_spacing || "Not specified")}`])),
    reviewGroup("Doping", profiles.map((profile) => [formatLabel(profile.region), `${formatLabel(profile.species)} · ${formatQuantity(profile.value)}`])),
    reviewGroup("Contacts", contacts.map((contact) => [formatLabel(contact.id), `${formatLabel(contact.kind)} · ${formatLabel(contact.location)}${contact.work_function ? ` · ${formatQuantity(contact.work_function)}` : ""}`])),
    studyReview(study),
    reviewGroup("Physics and outputs", [
      ["Equations", equations.map(formatLabel).join(", ") || "None declared"],
      ["Models", models.map(formatLabel).join(", ") || "None declared"],
      ["Observables", observables.map(formatLabel).join(", ") || "None declared"],
    ]),
  );
  planDigest.textContent = view.plan_digest || "Not generated";
  plan.textContent = JSON.stringify(view.plan || {spec}, null, 2);
  stateLabel.textContent = formatLabel(view.state);
  stateLabel.dataset.status = view.state;
  setHidden(approveButton, view.state !== "user_confirmation_required");
  setHidden(runButton, view.state !== "compiled");
}

function renderValidation(view) {
  validationList.replaceChildren();
  const report = view?.validation;
  validationStatus.textContent = report?.overall ? formatLabel(report.overall) : formatLabel(view?.state || "pending");
  validationStatus.dataset.status = report?.overall || view?.state || "pending";
  for (const check of report?.checks || []) {
    const row = document.createElement("article");
    row.className = "validation-row";
    const indicator = document.createElement("span");
    indicator.className = "check-indicator";
    indicator.dataset.status = check.status;
    const content = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = formatLabel(check.id);
    const message = document.createElement("p");
    message.textContent = check.message;
    content.append(title, message);
    const status = document.createElement("span");
    status.className = "check-status";
    status.textContent = formatLabel(check.status);
    row.append(indicator, content, status);
    validationList.appendChild(row);
  }
  validation.textContent = report ? JSON.stringify(report, null, 2) : "";
  setHidden(validationDetails, !report);
  artifactLinks.replaceChildren();
  setHidden(artifacts, !view?.bundle_path);
  if (view?.bundle_path) {
    const files = [
      ["Research report", "report.md"],
      ["Canonical results", "results/canonical.json"],
      ["Normalized field data", "results/fields.csv"],
      ["Static field plots", "results/field-plots.svg"],
      ["Validation record", "validation/report.json"],
      ["Evidence manifest", "manifest.json"],
      ["Event ledger", "events.jsonl"],
    ];
    for (const [name, path] of files) {
      const link = document.createElement("a");
      link.textContent = name;
      link.href = `/api/requests/${view.id}/artifacts/${path}`;
      artifactLinks.appendChild(link);
    }
  }
}

async function renderResults(view) {
  renderValidation(view);
  if (!view?.bundle_path) {
    resultsLoading.textContent = view?.error_message || "The simulator is still preparing result evidence.";
    setHidden(resultsLoading, false);
    setHidden(resultsWorkspace, true);
    return;
  }
  resultsLoading.textContent = "Loading normalized simulator evidence…";
  setHidden(resultsLoading, false);
  try {
    if (!resultsCache.has(view.id)) {
      resultsCache.set(view.id, await request(`/api/requests/${view.id}/results`));
    }
    window.TcadResultsViewer.render(resultsCache.get(view.id));
    setHidden(resultsWorkspace, false);
    setHidden(resultsLoading, true);
  } catch (error) {
    resultsLoading.textContent = error.message;
    setHidden(resultsWorkspace, true);
  }
}

function render(view, stage = activeStage(view), historyMode = null) {
  current = view;
  renderRequest(view);
  renderQuestions(view);
  renderPlan(view);
  void renderResults(view);
  const messages = [...(view?.warnings || [])].map(formatLabel);
  if (view?.error_message) messages.push(view.error_message);
  showNotice(messages.join(" · "), view?.error_message ? "error" : "warning");
  showPage(stage, historyMode);
}

async function perform(button, pendingText, operation) {
  const original = button.textContent;
  button.disabled = true;
  button.textContent = pendingText;
  showNotice("");
  try {
    const view = await operation();
    render(view, activeStage(view), "pushState");
  } catch (error) {
    showNotice(error.message, "error");
  } finally {
    button.textContent = original;
    if (button === answerButton) updateAnswerReadiness();
    else button.disabled = false;
  }
}

function renderBackendDescription() {
  const sentaurus = backendInput.value === "sentaurus";
  backendDescription.textContent = sentaurus ? "Compilation ready · Licensed execution required" : "Ready for local execution";
  document.querySelector(".backend-dot").dataset.backend = backendInput.value;
}

backendInput.addEventListener("change", renderBackendDescription);
questions.addEventListener("input", updateAnswerReadiness);
document.querySelector("#workflow-progress").addEventListener("click", (event) => {
  const button = event.target.closest("[data-stage-target]");
  if (button && !button.disabled) showPage(button.dataset.stageTarget, "pushState");
});

submitButton.addEventListener("click", async () => {
  if (!promptInput.value.trim()) {
    showNotice("Describe the requested device study before building a plan.", "error");
    return;
  }
  await perform(submitButton, "Building plan…", () => request("/api/requests", {
    method: "POST",
    body: JSON.stringify({prompt: promptInput.value.trim(), backend: backendInput.value}),
  }));
});

answerButton.addEventListener("click", async () => {
  const answers = collectAnswers();
  const count = questions.querySelectorAll("input").length;
  if (!current || current.state !== "needs_clarification" || answers.length !== count) return;
  await perform(answerButton, "Preparing plan…", () => request(`/api/requests/${current.id}/answers`, {
    method: "POST",
    body: JSON.stringify({answers}),
  }));
});

approveButton.addEventListener("click", async () => {
  if (!current?.plan_digest) return;
  await perform(approveButton, "Compiling…", () => request(`/api/requests/${current.id}/approve`, {
    method: "POST",
    body: JSON.stringify({plan_digest: current.plan_digest}),
  }));
});

runButton.addEventListener("click", async () => {
  if (!current) return;
  await perform(runButton, "Running simulation…", () => request(`/api/requests/${current.id}/run`, {method: "POST"}));
});

async function restoreLocation() {
  const route = parseLocation();
  if (!route.id) {
    current = null;
    showNotice("");
    showPage("request");
    renderProgress();
    renderBackendDescription();
    return;
  }
  try {
    render(await request(`/api/requests/${route.id}`), route.stage);
  } catch (error) {
    current = null;
    showPage("request", "replaceState");
    showNotice(error.message, "error");
  }
}

window.addEventListener("popstate", () => void restoreLocation());
void restoreLocation();
