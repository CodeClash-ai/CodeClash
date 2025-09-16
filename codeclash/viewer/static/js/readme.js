// Readme functionality for CodeClash Trajectory Viewer

let readmeTimeout = null;
let readmeTextarea = null;
let readmeStatus = null;

function loadReadme() {
  const urlParams = new URLSearchParams(window.location.search);
  const folder = urlParams.get("folder");

  if (!folder) return;

  fetch("/load-readme?folder=" + encodeURIComponent(folder))
    .then((response) => response.json())
    .then((data) => {
      if (data.success) {
        readmeTextarea.value = data.content;
        readmeStatus.textContent = "Loaded";
        readmeStatus.className = "readme-status";
      } else {
        readmeStatus.textContent = "Error loading: " + data.error;
        readmeStatus.className = "readme-status error";
      }
    })
    .catch((error) => {
      console.error("Error loading readme:", error);
      readmeStatus.textContent = "Error loading readme";
      readmeStatus.className = "readme-status error";
    });
}

function saveReadme() {
  const urlParams = new URLSearchParams(window.location.search);
  const folder = urlParams.get("folder");

  if (!folder) return;

  readmeStatus.textContent = "Saving...";
  readmeStatus.className = "readme-status saving";

  fetch("/save-readme", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      selected_folder: folder,
      content: readmeTextarea.value,
    }),
  })
    .then((response) => response.json())
    .then((data) => {
      if (data.success) {
        readmeStatus.textContent = "Saved";
        readmeStatus.className = "readme-status saved";
      } else {
        readmeStatus.textContent = "Error: " + data.error;
        readmeStatus.className = "readme-status error";
      }
    })
    .catch((error) => {
      console.error("Error saving readme:", error);
      readmeStatus.textContent = "Error saving";
      readmeStatus.className = "readme-status error";
    });
}

function setupReadmeAutosave() {
  readmeTextarea = document.getElementById("readme-textarea");
  readmeStatus = document.getElementById("readme-status");

  if (!readmeTextarea || !readmeStatus) return;

  // Load existing content
  loadReadme();

  // Setup autosave on input
  readmeTextarea.addEventListener("input", function () {
    // Clear existing timeout
    if (readmeTimeout) {
      clearTimeout(readmeTimeout);
    }

    // Set new timeout for autosave (1 second delay)
    readmeTimeout = setTimeout(saveReadme, 1000);

    // Show typing indicator
    readmeStatus.textContent = "Typing...";
    readmeStatus.className = "readme-status";
  });
}
