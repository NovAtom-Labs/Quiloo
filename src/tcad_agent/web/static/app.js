const promptInput = document.querySelector("#prompt");
const backendInput = document.querySelector("#backend");
const submitButton = document.querySelector("#submit");
const approveButton = document.querySelector("#approve");
const runButton = document.querySelector("#run");
const statusPanel = document.querySelector("#status-panel");
const resultsPanel = document.querySelector("#results-panel");
const stateLabel = document.querySelector("#state");
const warning = document.querySelector("#warning");
const questions = document.querySelector("#questions");
const plan = document.querySelector("#plan");
const validation = document.querySelector("#validation");
const report = document.querySelector("#report");

let current = null;

async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: {"Content-Type": "application/json"},
    ...options,
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.message || data.detail || "Request failed");
  return data;
}

function render(view) {
  current = view;
  statusPanel.classList.remove("hidden");
  stateLabel.textContent = view.state.replaceAll("_", " ");
  warning.textContent = (view.warnings || []).join(" · ");
  plan.textContent = view.plan ? JSON.stringify(view.plan, null, 2) : "";
  questions.replaceChildren();
  for (const item of view.questions || []) {
    const wrapper = document.createElement("label");
    wrapper.textContent = item.prompt;
    const input = document.createElement("input");
    input.dataset.field = item.field;
    wrapper.appendChild(input);
    questions.appendChild(wrapper);
  }
  approveButton.classList.toggle("hidden", view.state !== "user_confirmation_required");
  runButton.classList.toggle("hidden", view.state !== "compiled");
  if (view.validation) {
    resultsPanel.classList.remove("hidden");
    validation.textContent = JSON.stringify(view.validation, null, 2);
  }
  if (view.bundle_path) {
    report.classList.remove("hidden");
    report.href = `/api/requests/${view.id}/artifacts/report.md`;
  }
}

submitButton.addEventListener("click", async () => {
  try {
    render(await request("/api/requests", {
      method: "POST",
      body: JSON.stringify({prompt: promptInput.value, backend: backendInput.value}),
    }));
  } catch (error) { warning.textContent = error.message; statusPanel.classList.remove("hidden"); }
});

questions.addEventListener("change", async () => {
  if (!current || current.state !== "needs_clarification") return;
  const answers = [...questions.querySelectorAll("input")]
    .filter((input) => input.value.trim())
    .map((input) => ({field: input.dataset.field, value: input.value.trim()}));
  if (answers.length !== questions.querySelectorAll("input").length) return;
  render(await request(`/api/requests/${current.id}/answers`, {
    method: "POST", body: JSON.stringify({answers}),
  }));
});

approveButton.addEventListener("click", async () => {
  render(await request(`/api/requests/${current.id}/approve`, {
    method: "POST", body: JSON.stringify({plan_digest: current.plan_digest}),
  }));
});

runButton.addEventListener("click", async () => {
  render(await request(`/api/requests/${current.id}/run`, {method: "POST"}));
});
