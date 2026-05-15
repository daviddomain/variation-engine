const PARAMETER_DEFINITIONS = [
  { id: "micropitch_cents", label: "Micropitch cents", step: "0.25", mode: "range" },
  { id: "timing_shift_ms", label: "Timing shift ms", step: "0.1", mode: "range" },
  { id: "gain_db", label: "Gain dB", step: "0.1", mode: "range" },
  { id: "attack_amount", label: "Attack amount", step: "0.01", mode: "range" },
  { id: "brightness_amount", label: "Brightness amount", step: "0.01", mode: "range" },
  { id: "decay_amount", label: "Decay amount", step: "0.01", mode: "range" },
  { id: "stereo_balance_amount", label: "Stereo balance amount", step: "0.01", mode: "range" },
  { id: "saturation_amount", label: "Saturation amount", step: "0.01", mode: "single" },
];

const NOTE_PATTERN = /^[A-Ga-g](?:#|b)?-?\d+$/;

const state = {
  categories: [],
  samples: [],
  recipeRanges: {},
  parameterLimits: {},
  currentRanges: {},
  rendering: false,
};

const categorySelect = document.querySelector("#category");
const sampleSelect = document.querySelector("#sample");
const sourceNoteInput = document.querySelector("#source-note");
const seedInput = document.querySelector("#seed");
const renderButton = document.querySelector("#render-button");
const resetRangesButton = document.querySelector("#reset-ranges");
const statusPanel = document.querySelector(".status-panel");
const sliderList = document.querySelector("#slider-list");
const analysisPreview = document.querySelector("#analysis-preview");
const renderedOutput = document.querySelector("#rendered-output");
const outputDir = document.querySelector("#output-dir");
const padButtons = Array.from(document.querySelectorAll(".pads-grid button"));

function isLikelyNoteName(value) {
  return NOTE_PATTERN.test(value.trim());
}

function clampRange(values, limits) {
  const minValue = Math.min(Number(values[0]), Number(values[1]));
  const maxValue = Math.max(Number(values[0]), Number(values[1]));
  return [
    Math.max(Number(limits[0]), minValue),
    Math.min(Number(limits[1]), maxValue),
  ];
}

function nextParameterRanges() {
  const ranges = {};
  for (const definition of PARAMETER_DEFINITIONS) {
    const current = state.currentRanges[definition.id];
    if (!current) {
      continue;
    }

    ranges[definition.id] = current.slice();
  }
  return ranges;
}

function renderRequestPayload() {
  return {
    category_id: categorySelect.value,
    sample_path: sampleSelect.value,
    source_note: sourceNoteInput.value.trim(),
    seed: Number.parseInt(seedInput.value, 10),
    parameter_ranges: nextParameterRanges(),
  };
}

function setStatus(message) {
  statusPanel.textContent = message;
}

function writeJsonOutput(value) {
  renderedOutput.value = value ? JSON.stringify(value, null, 2) : "";
}

function setOutputDir(value) {
  outputDir.textContent = `Output directory: ${value || "-"}`;
}

function updateRenderButton() {
  const hasCategory = categorySelect.value !== "";
  const hasSample = sampleSelect.value !== "";
  const hasNote = isLikelyNoteName(sourceNoteInput.value);
  renderButton.disabled = state.rendering || !hasCategory || !hasSample || !hasNote;
}

function fillSelect(select, items, emptyLabel) {
  select.innerHTML = "";
  if (items.length === 0) {
    const emptyOption = document.createElement("option");
    emptyOption.value = "";
    emptyOption.textContent = emptyLabel;
    select.appendChild(emptyOption);
    return;
  }

  for (const item of items) {
    const option = document.createElement("option");
    option.value = item.id || item.path;
    option.textContent = item.label;
    select.appendChild(option);
  }
}

function resetAnalysisPreview() {
  const values = ["-", "-", "-", "-", "-", "-"];
  Array.from(analysisPreview.querySelectorAll("dd")).forEach((item, index) => {
    item.textContent = values[index];
  });
}

function setAnalysisPreview(summary) {
  const values = [
    summary.estimated_note_name || "-",
    formatMaybeNumber(summary.pitch_confidence, 3),
    summary.suggested_profile || "-",
    formatDuration(summary.duration_seconds),
    summary.sample_rate ? `${summary.sample_rate} Hz` : "-",
    summary.channels ?? "-",
  ];

  Array.from(analysisPreview.querySelectorAll("dd")).forEach((item, index) => {
    item.textContent = values[index];
  });
}

function formatMaybeNumber(value, digits) {
  return typeof value === "number" ? value.toFixed(digits) : "-";
}

function formatDuration(value) {
  return typeof value === "number" ? `${value.toFixed(3)} s` : "-";
}

function resetPads() {
  for (const button of padButtons) {
    button.disabled = true;
    button.dataset.audioUrl = "";
    button.classList.remove("is-active");
  }
}

function activatePads(audioUrls) {
  padButtons.forEach((button, index) => {
    const audioUrl = audioUrls[index];
    button.dataset.audioUrl = audioUrl || "";
    button.disabled = !audioUrl;
    button.classList.toggle("is-active", Boolean(audioUrl));
  });
}

function setRangesFromRecipe() {
  state.currentRanges = {};
  for (const definition of PARAMETER_DEFINITIONS) {
    const recipeRange = state.recipeRanges[definition.id];
    const limits = state.parameterLimits[definition.id];
    if (!recipeRange || !limits) {
      continue;
    }

    state.currentRanges[definition.id] = clampRange(recipeRange, limits);
  }
  renderSliders();
}

function renderSliders() {
  sliderList.innerHTML = "";
  for (const definition of PARAMETER_DEFINITIONS) {
    const limits = state.parameterLimits[definition.id];
    const values = state.currentRanges[definition.id];
    if (!limits || !values) {
      continue;
    }

    const group = document.createElement("div");
    group.className = "slider-group";
    group.dataset.parameter = definition.id;

    const label = document.createElement("label");
    label.textContent = definition.label;
    group.appendChild(label);

    const valueText = document.createElement("div");
    valueText.className = "slider-value";
    group.appendChild(valueText);

    const row = document.createElement("div");
    row.className = "range-row";
    group.appendChild(row);

    if (definition.mode === "single") {
      row.appendChild(createRangeInput(definition, 1, limits, values[1]));
    } else {
      row.appendChild(createRangeInput(definition, 0, limits, values[0]));
      row.appendChild(createRangeInput(definition, 1, limits, values[1]));
    }

    sliderList.appendChild(group);
    updateSliderValueText(definition.id);
  }

  resetRangesButton.disabled = sliderList.children.length === 0;
}

function createRangeInput(definition, index, limits, value) {
  const input = document.createElement("input");
  input.type = "range";
  input.min = String(limits[0]);
  input.max = String(limits[1]);
  input.step = definition.step;
  input.value = String(value);
  input.dataset.parameter = definition.id;
  input.dataset.index = String(index);
  input.addEventListener("input", onSliderInput);
  return input;
}

function onSliderInput(event) {
  const input = event.target;
  const parameter = input.dataset.parameter;
  const index = Number.parseInt(input.dataset.index, 10);
  const values = state.currentRanges[parameter].slice();
  values[index] = Number.parseFloat(input.value);
  state.currentRanges[parameter] = clampRange(values, state.parameterLimits[parameter]);
  syncSliderInputs(parameter);
  updateSliderValueText(parameter);
}

function syncSliderInputs(parameter) {
  const values = state.currentRanges[parameter];
  sliderList.querySelectorAll(`[data-parameter="${parameter}"][type="range"]`).forEach((input) => {
    input.value = String(values[Number.parseInt(input.dataset.index, 10)]);
  });
}

function updateSliderValueText(parameter) {
  const group = sliderList.querySelector(`[data-parameter="${parameter}"].slider-group`);
  const valueText = group?.querySelector(".slider-value");
  const values = state.currentRanges[parameter];
  if (!valueText || !values) {
    return;
  }

  valueText.textContent = `${formatSliderValue(values[0])} to ${formatSliderValue(values[1])}`;
}

function formatSliderValue(value) {
  return Number.parseFloat(value).toFixed(2).replace(/\.?0+$/, "");
}

async function fetchJson(url, options) {
  const response = await fetch(url, options);
  const body = await response.json();
  if (!response.ok) {
    throw new Error(body.error || `Request failed with status ${response.status}`);
  }
  return body;
}

async function loadInitialState() {
  try {
    state.categories = await fetchJson("/api/categories");
    fillSelect(categorySelect, state.categories, "No categories found");
    const defaultCategory = state.categories.find((item) => item.id === "plucked_string");
    categorySelect.value = defaultCategory?.id || state.categories[0]?.id || "";
    await loadCategoryState();
  } catch (error) {
    setStatus(`Error: ${error.message}`);
    updateRenderButton();
  }
}

async function loadCategoryState() {
  const category = categorySelect.value;
  resetPads();
  resetAnalysisPreview();
  writeJsonOutput(null);
  setOutputDir(null);
  sourceNoteInput.value = "";
  setStatus("Loading category...");
  updateRenderButton();

  if (!category) {
    state.samples = [];
    fillSelect(sampleSelect, [], "No category selected");
    setStatus("Select a category.");
    return;
  }

  try {
    const [samples, recipe] = await Promise.all([
      fetchJson(`/api/samples?category=${encodeURIComponent(category)}`),
      fetchJson(`/api/render-recipe?category=${encodeURIComponent(category)}`),
    ]);
    state.samples = samples;
    state.recipeRanges = recipe.ranges || {};
    state.parameterLimits = recipe.parameter_limits || {};
    fillSelect(sampleSelect, state.samples, "No WAV samples found");
    setRangesFromRecipe();
    setStatus(samples.length > 0 ? "Category loaded." : "Category loaded. Add WAV samples to render.");
    updateRenderButton();
    if (sampleSelect.value) {
      await analyzeSelectedSample();
    }
  } catch (error) {
    setStatus(`Error: ${error.message}`);
    updateRenderButton();
  }
}

async function analyzeSelectedSample() {
  const samplePath = sampleSelect.value;
  resetPads();
  writeJsonOutput(null);
  setOutputDir(null);
  resetAnalysisPreview();
  updateRenderButton();

  if (!samplePath) {
    setStatus("Select a sample.");
    return;
  }

  try {
    setStatus("Analyzing sample...");
    const body = await fetchJson(`/api/analyze?sample_path=${encodeURIComponent(samplePath)}`);
    setAnalysisPreview(body.summary);
    if (body.summary.estimated_note_name) {
      sourceNoteInput.value = body.summary.estimated_note_name;
    }
    setStatus("Analysis loaded.");
  } catch (error) {
    setStatus(`Error: ${error.message}`);
  } finally {
    updateRenderButton();
  }
}

async function renderSelectedSample() {
  if (renderButton.disabled) {
    return;
  }

  try {
    state.rendering = true;
    resetPads();
    writeJsonOutput(null);
    setOutputDir(null);
    setStatus("Rendering...");
    updateRenderButton();

    const body = await fetchJson("/api/render", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(renderRequestPayload()),
    });
    writeJsonOutput(body);
    setOutputDir(body.output_dir);
    activatePads(body.audio_urls || []);
    setStatus("Render complete.");
  } catch (error) {
    setStatus(`Error: ${error.message}`);
  } finally {
    state.rendering = false;
    updateRenderButton();
  }
}

function playPadAudio(event) {
  const audioUrl = event.currentTarget.dataset.audioUrl;
  if (!audioUrl) {
    return;
  }

  new Audio(audioUrl).play().catch((error) => {
    setStatus(`Error: ${error.message}`);
  });
}

categorySelect.addEventListener("change", loadCategoryState);
sampleSelect.addEventListener("change", analyzeSelectedSample);
sourceNoteInput.addEventListener("input", updateRenderButton);
seedInput.addEventListener("input", updateRenderButton);
renderButton.addEventListener("click", renderSelectedSample);
resetRangesButton.addEventListener("click", setRangesFromRecipe);
padButtons.forEach((button) => button.addEventListener("click", playPadAudio));

resetPads();
resetAnalysisPreview();
loadInitialState();
