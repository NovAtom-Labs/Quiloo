(() => {
  "use strict";

  const SVG_NS = "http://www.w3.org/2000/svg";
  const state = {payload: null, field: "", scale: "linear", zoom: 1, pan: 50};

  const element = (id) => document.getElementById(id);

  function formatNumber(value, digits = 5) {
    const number = Number(value);
    if (!Number.isFinite(number)) return String(value);
    const absolute = Math.abs(number);
    if (absolute >= 1e5 || (absolute > 0 && absolute < 1e-3)) {
      return number.toExponential(3).replace("e+", "e");
    }
    return Number(number.toPrecision(digits)).toString();
  }

  function label(value) {
    return String(value || "")
      .replaceAll("_", " ")
      .replaceAll("-", " ")
      .replace(/\b\w/g, (letter) => letter.toUpperCase());
  }

  function positionLabel(meters) {
    const absolute = Math.abs(meters);
    if (absolute >= 1e-3) return `${formatNumber(meters * 1e3)} mm`;
    if (absolute >= 1e-6) return `${formatNumber(meters * 1e6)} µm`;
    if (absolute >= 1e-9) return `${formatNumber(meters * 1e9)} nm`;
    return `${formatNumber(meters)} m`;
  }

  function svgNode(name, attributes = {}, text = "") {
    const node = document.createElementNS(SVG_NS, name);
    for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, String(value));
    if (text) node.textContent = text;
    return node;
  }

  function summaryCard(name, value, detail = "") {
    const card = document.createElement("article");
    card.className = "summary-card result-metric";
    const heading = document.createElement("span");
    heading.textContent = name;
    const primary = document.createElement("strong");
    primary.textContent = value;
    card.append(heading, primary);
    if (detail) {
      const secondary = document.createElement("small");
      secondary.textContent = detail;
      card.appendChild(secondary);
    }
    return card;
  }

  function renderOverview() {
    const overview = element("results-overview");
    const {result, validation} = state.payload;
    const points = result.bias_points || [];
    const fields = Object.keys(result.fields || {});
    const passed = (validation.checks || []).filter((check) => check.status === "passed").length;
    overview.replaceChildren(
      summaryCard("Backend", String(result.backend || "").toUpperCase(), result.simulator_version || "Version unavailable"),
      summaryCard("Run status", label(result.status), `${points.length} operating point${points.length === 1 ? "" : "s"}`),
      summaryCard("Spatial fields", String(fields.length), fields.map(label).join(", ")),
      summaryCard("Validation", label(validation.overall), `${passed} of ${(validation.checks || []).length} checks passed`),
    );

    const builtIn = (validation.checks || []).find((check) => check.id === "built-in-potential-reference");
    if (builtIn?.measured_value !== undefined) {
      overview.appendChild(summaryCard("Potential range", `${formatNumber(builtIn.measured_value)} V`, String(builtIn.limit || "Reviewed reference")));
    }
    const equilibriumCurrent = (validation.checks || []).find((check) => check.id === "equilibrium-terminal-current");
    if (equilibriumCurrent?.measured_value !== undefined) {
      overview.appendChild(summaryCard("Max equilibrium current", `${formatNumber(equilibriumCurrent.measured_value)} A/m²`, `Limit ${equilibriumCurrent.limit} A/m²`));
    }
  }

  function renderBiasResults() {
    const body = element("bias-results");
    body.replaceChildren();
    for (const point of state.payload.result.bias_points || []) {
      const currents = Object.entries(point.terminal_currents_a_per_m2 || {});
      if (!currents.length) currents.push(["No terminal current", null]);
      for (const [terminal, current] of currents) {
        const row = document.createElement("tr");
        const values = [
          `${formatNumber(point.bias_v)} V`,
          label(terminal),
          current === null ? "Unavailable" : `${formatNumber(current)} A/m²`,
          point.converged ? "Yes" : "No",
        ];
        for (const value of values) {
          const cell = document.createElement("td");
          cell.textContent = value;
          row.appendChild(cell);
        }
        body.appendChild(row);
      }
    }
  }

  function renderDevice() {
    const target = element("result-device-summary");
    const experiment = state.payload.experiment;
    target.replaceChildren();
    for (const region of experiment.regions || []) {
      const item = document.createElement("article");
      const title = document.createElement("strong");
      title.textContent = label(region.id);
      const material = document.createElement("span");
      material.textContent = label(region.material);
      const start = Number(region.x0?.magnitude_si);
      const end = Number(region.x1?.magnitude_si);
      const extent = document.createElement("small");
      extent.textContent = Number.isFinite(start) && Number.isFinite(end)
        ? `${positionLabel(start)} to ${positionLabel(end)}`
        : "Extent unavailable";
      const profile = (experiment.profiles || []).find((entry) => entry.region === region.id);
      const doping = document.createElement("small");
      doping.textContent = profile
        ? `${label(profile.species)} · ${formatNumber(Number(profile.value?.magnitude_si) / 1e6)} cm⁻³`
        : "No declared doping";
      item.append(title, material, extent, doping);
      target.appendChild(item);
    }
  }

  function fieldPoints() {
    const series = state.payload.result.fields?.[state.field];
    if (!series) return [];
    return (series.positions_m || [])
      .map((position, index) => ({position: Number(position), value: Number(series.values[index]), index}))
      .filter((point) => Number.isFinite(point.position) && Number.isFinite(point.value));
  }

  function visiblePoints(points) {
    if (points.length < 2 || state.zoom <= 1) return points;
    const minimum = points[0].position;
    const maximum = points.at(-1).position;
    const fullSpan = maximum - minimum;
    const span = fullSpan / state.zoom;
    const start = minimum + (fullSpan - span) * (state.pan / 100);
    const end = start + span;
    const selected = points.filter((point) => point.position >= start && point.position <= end);
    return selected.length >= 2 ? selected : points;
  }

  function addAxis(svg, dimensions, minimum, maximum, horizontal, formatter) {
    const {left, top, width, height} = dimensions;
    for (let index = 0; index <= 5; index += 1) {
      const fraction = index / 5;
      const coordinate = horizontal ? left + width * fraction : top + height * (1 - fraction);
      const value = minimum + (maximum - minimum) * fraction;
      svg.appendChild(svgNode("line", horizontal
        ? {x1: coordinate, y1: top, x2: coordinate, y2: top + height, class: "chart-grid"}
        : {x1: left, y1: coordinate, x2: left + width, y2: coordinate, class: "chart-grid"}));
      svg.appendChild(svgNode("text", horizontal
        ? {x: coordinate, y: top + height + 27, class: "chart-tick", "text-anchor": "middle"}
        : {x: left - 14, y: coordinate + 4, class: "chart-tick", "text-anchor": "end"}, formatter(value)));
    }
  }

  function renderChart() {
    const svg = element("field-chart");
    const tooltip = element("chart-tooltip");
    svg.replaceChildren();
    tooltip.classList.add("hidden");
    const allPoints = fieldPoints();
    const points = visiblePoints(allPoints);
    if (points.length < 2) {
      svg.appendChild(svgNode("text", {x: 480, y: 215, class: "chart-empty", "text-anchor": "middle"}, "This field does not contain enough finite samples."));
      return;
    }

    let useLog = state.scale === "log";
    if (useLog && points.some((point) => point.value <= 0)) {
      useLog = false;
      state.scale = "linear";
      element("field-scale").value = "linear";
    }
    const transformed = points.map((point) => ({...point, plotted: useLog ? Math.log10(point.value) : point.value}));
    const xMinimum = transformed[0].position;
    const xMaximum = transformed.at(-1).position;
    let yMinimum = Math.min(...transformed.map((point) => point.plotted));
    let yMaximum = Math.max(...transformed.map((point) => point.plotted));
    if (yMinimum === yMaximum) {
      const padding = Math.abs(yMinimum || 1) * 0.05;
      yMinimum -= padding;
      yMaximum += padding;
    }

    const dimensions = {left: 92, top: 24, width: 836, height: 330};
    const x = (value) => dimensions.left + ((value - xMinimum) / (xMaximum - xMinimum)) * dimensions.width;
    const y = (value) => dimensions.top + (1 - (value - yMinimum) / (yMaximum - yMinimum)) * dimensions.height;
    addAxis(svg, dimensions, xMinimum, xMaximum, true, positionLabel);
    addAxis(svg, dimensions, yMinimum, yMaximum, false, (value) => formatNumber(value));
    svg.appendChild(svgNode("line", {x1: dimensions.left, y1: dimensions.top + dimensions.height, x2: dimensions.left + dimensions.width, y2: dimensions.top + dimensions.height, class: "chart-axis"}));
    svg.appendChild(svgNode("line", {x1: dimensions.left, y1: dimensions.top, x2: dimensions.left, y2: dimensions.top + dimensions.height, class: "chart-axis"}));
    svg.appendChild(svgNode("text", {x: dimensions.left + dimensions.width / 2, y: 414, class: "chart-label", "text-anchor": "middle"}, "Device position"));
    const series = state.payload.result.fields[state.field];
    svg.appendChild(svgNode("text", {x: 18, y: dimensions.top + dimensions.height / 2, class: "chart-label", transform: `rotate(-90 18 ${dimensions.top + dimensions.height / 2})`, "text-anchor": "middle"}, useLog ? `log₁₀(${series.unit})` : series.unit));
    const path = transformed.map((point, index) => `${index ? "L" : "M"} ${x(point.position)} ${y(point.plotted)}`).join(" ");
    svg.appendChild(svgNode("path", {d: path, class: "field-line"}));

    const crosshair = svgNode("line", {class: "chart-crosshair hidden"});
    const marker = svgNode("circle", {r: 5, class: "chart-marker hidden"});
    svg.append(crosshair, marker);
    const hitArea = svgNode("rect", {x: dimensions.left, y: dimensions.top, width: dimensions.width, height: dimensions.height, class: "chart-hit-area"});
    svg.appendChild(hitArea);
    hitArea.addEventListener("pointermove", (event) => {
      const bounds = svg.getBoundingClientRect();
      const pointerX = ((event.clientX - bounds.left) / bounds.width) * 960;
      const targetPosition = xMinimum + ((pointerX - dimensions.left) / dimensions.width) * (xMaximum - xMinimum);
      const nearest = transformed.reduce((best, point) => Math.abs(point.position - targetPosition) < Math.abs(best.position - targetPosition) ? point : best);
      const markerX = x(nearest.position);
      const markerY = y(nearest.plotted);
      crosshair.setAttribute("x1", markerX);
      crosshair.setAttribute("x2", markerX);
      crosshair.setAttribute("y1", dimensions.top);
      crosshair.setAttribute("y2", dimensions.top + dimensions.height);
      marker.setAttribute("cx", markerX);
      marker.setAttribute("cy", markerY);
      crosshair.classList.remove("hidden");
      marker.classList.remove("hidden");
      tooltip.replaceChildren();
      const name = document.createElement("strong");
      name.textContent = label(state.field);
      const position = document.createElement("span");
      position.textContent = positionLabel(nearest.position);
      const value = document.createElement("span");
      value.textContent = `${formatNumber(nearest.value)} ${series.unit}`;
      tooltip.append(name, position, value);
      tooltip.style.left = `${Math.min(82, Math.max(12, (markerX / 960) * 100))}%`;
      tooltip.style.top = `${Math.min(78, Math.max(8, (markerY / 430) * 100))}%`;
      tooltip.classList.remove("hidden");
    });
    hitArea.addEventListener("pointerleave", () => {
      crosshair.classList.add("hidden");
      marker.classList.add("hidden");
      tooltip.classList.add("hidden");
    });
  }

  function renderFieldStats() {
    const points = fieldPoints();
    const target = element("field-stats");
    const series = state.payload.result.fields[state.field];
    if (!points.length || !series) {
      target.replaceChildren();
      return;
    }
    const values = points.map((point) => point.value);
    target.replaceChildren(
      summaryCard("Minimum", formatNumber(Math.min(...values)), series.unit),
      summaryCard("Maximum", formatNumber(Math.max(...values)), series.unit),
      summaryCard("Samples", String(points.length), `${positionLabel(points[0].position)} to ${positionLabel(points.at(-1).position)}`),
    );
  }

  function renderFieldTable() {
    const body = element("field-data");
    const search = element("field-search").value.trim().toLowerCase();
    const series = state.payload.result.fields[state.field];
    body.replaceChildren();
    if (!series) return;
    let shown = 0;
    for (const point of fieldPoints()) {
      const position = positionLabel(point.position);
      const value = formatNumber(point.value, 7);
      if (search && !`${point.index} ${position} ${value} ${series.unit}`.toLowerCase().includes(search)) continue;
      const row = document.createElement("tr");
      for (const item of [point.index, position, value, series.unit]) {
        const cell = document.createElement("td");
        cell.textContent = String(item);
        row.appendChild(cell);
      }
      body.appendChild(row);
      shown += 1;
      if (shown >= 500) break;
    }
  }

  function renderSelectedField() {
    renderChart();
    renderFieldStats();
    renderFieldTable();
  }

  function bindControls() {
    const selector = element("field-selector");
    const scale = element("field-scale");
    const zoom = element("field-zoom");
    const pan = element("field-pan");
    const reset = element("reset-chart");
    const search = element("field-search");
    if (selector.dataset.bound) return;
    selector.dataset.bound = "true";
    selector.addEventListener("change", () => {
      state.field = selector.value;
      scale.value = "linear";
      state.scale = "linear";
      search.value = "";
      renderSelectedField();
    });
    scale.addEventListener("change", () => {
      state.scale = scale.value;
      renderSelectedField();
    });
    zoom.addEventListener("input", () => {
      state.zoom = Number(zoom.value);
      renderChart();
    });
    pan.addEventListener("input", () => {
      state.pan = Number(pan.value);
      renderChart();
    });
    reset.addEventListener("click", () => {
      state.zoom = 1;
      state.pan = 50;
      state.scale = "linear";
      zoom.value = "1";
      pan.value = "50";
      scale.value = "linear";
      renderSelectedField();
    });
    search.addEventListener("input", renderFieldTable);
  }

  function render(payload) {
    state.payload = payload;
    const selector = element("field-selector");
    const names = Object.keys(payload.result.fields || {});
    selector.replaceChildren();
    for (const name of names) {
      const option = document.createElement("option");
      option.value = name;
      option.textContent = label(name);
      selector.appendChild(option);
    }
    state.field = names.includes(state.field) ? state.field : (names[0] || "");
    selector.value = state.field;
    renderOverview();
    renderBiasResults();
    renderDevice();
    bindControls();
    renderSelectedField();
  }

  window.TcadResultsViewer = {render};
})();
