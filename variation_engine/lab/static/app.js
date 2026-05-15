const categorySelect = document.querySelector("#category");
const sampleSelect = document.querySelector("#sample");
const statusPanel = document.querySelector(".status-panel");

function updatePlaceholderSample() {
  const category = categorySelect.value;
  sampleSelect.innerHTML = "";

  const option = document.createElement("option");
  option.value = "";
  option.textContent = `samples/${category}/`;
  sampleSelect.appendChild(option);

  statusPanel.textContent = "Ready. Rendering is not wired in this skeleton.";
}

categorySelect.addEventListener("change", updatePlaceholderSample);
updatePlaceholderSample();
