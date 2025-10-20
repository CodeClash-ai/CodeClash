// Game Picker JavaScript

function openGame(gameName) {
  // Navigate to the viewer with the selected game
  // In static mode, use path-based URLs; in dynamic mode, use query parameters
  const isStatic = document.body.hasAttribute("data-static-mode");
  if (isStatic) {
    // For static mode, encode each path segment separately to preserve slashes
    const pathSegments = gameName
      .split("/")
      .map((segment) => encodeURIComponent(segment));
    const url = `/game/${pathSegments.join("/")}.html`;
    window.location.href = url;
  } else {
    const url = `/?folder=${encodeURIComponent(gameName)}`;
    window.location.href = url;
  }
}

function openGameInNewTab(gameName) {
  // Open the viewer in a new tab with the selected game
  // In static mode, use path-based URLs; in dynamic mode, use query parameters
  const isStatic = document.body.hasAttribute("data-static-mode");
  if (isStatic) {
    // For static mode, encode each path segment separately to preserve slashes
    const pathSegments = gameName
      .split("/")
      .map((segment) => encodeURIComponent(segment));
    const url = `/game/${pathSegments.join("/")}.html`;
    window.open(url, "_blank");
  } else {
    const url = `/?folder=${encodeURIComponent(gameName)}`;
    window.open(url, "_blank");
  }
}

function handleGameClick(event, gameName) {
  // Handle different types of clicks for Open button
  if (event.button === 1 || event.ctrlKey || event.metaKey) {
    // Middle click, Ctrl+click, or Cmd+click - open in new tab
    event.preventDefault();
    openGameInNewTab(gameName);
  } else if (event.button === 0) {
    // Left click - open in same tab
    openGame(gameName);
  }
}

function toggleGameSelection(gameName, forceState = null) {
  // Toggle the checkbox for this game
  const checkbox = document.querySelector(`input[data-path="${gameName}"]`);
  if (checkbox) {
    if (forceState !== null) {
      checkbox.checked = forceState;
    } else {
      checkbox.checked = !checkbox.checked;
    }
  }
}

function handleRowClick(event, gameName) {
  // Check if click is on checkbox or in checkbox area
  const checkbox = event.target.closest('input[type="checkbox"]');
  const checkboxCell = event.target.closest(".checkbox-cell");

  // Check if click is on name column content (session name)
  const sessionNameCell = event.target.closest(".session-name-cell");
  const sessionNameContent = event.target.closest(".game-name");

  // Check if click is on action buttons (these have their own handlers)
  const actionButton = event.target.closest(".action-cell button");

  if (checkbox || checkboxCell) {
    // Click is on checkbox or in checkbox area - handle selection
    event.stopPropagation();

    if (checkbox) {
      // Direct checkbox click - handle shift-click range selection
      handleCheckboxClick(event, gameName);
    } else {
      // Click in checkbox area but not on checkbox - toggle selection
      toggleGameSelection(gameName);
    }
  } else if (sessionNameCell && sessionNameContent) {
    // Click is on the session name content - open game
    if (event.button === 1 || event.ctrlKey || event.metaKey) {
      // Middle click, Ctrl+click, or Cmd+click - open in new tab
      event.preventDefault();
      openGameInNewTab(gameName);
    } else if (event.button === 0) {
      // Left click - open in same tab
      openGame(gameName);
    }
  } else if (actionButton) {
    // Click is on action button - let the button handle it (don't interfere)
    return;
  } else {
    // Click is elsewhere - do nothing (changed behavior)
    return;
  }
}

// Shift-click range selection variables
let lastClickedCheckbox = null;

function handleCheckboxClick(event, gameName) {
  const checkbox = event.target;

  if (event.shiftKey && lastClickedCheckbox) {
    // Shift-click: select range
    event.preventDefault();
    // Use the state the checkbox will have after the click (opposite of current)
    const targetState = !checkbox.checked;
    checkbox.checked = targetState; // Apply the click manually since we prevented default
    selectRange(lastClickedCheckbox, gameName, targetState);
  } else {
    // Regular click: just update last clicked
    lastClickedCheckbox = gameName;
  }
}

function selectRange(startGameName, endGameName, checked) {
  // Get all game checkboxes in order
  const allCheckboxes = Array.from(
    document.querySelectorAll("input[data-path]"),
  );
  const startIndex = allCheckboxes.findIndex(
    (cb) => cb.getAttribute("data-path") === startGameName,
  );
  const endIndex = allCheckboxes.findIndex(
    (cb) => cb.getAttribute("data-path") === endGameName,
  );

  if (startIndex === -1 || endIndex === -1) return;

  // Determine the range (handle both directions)
  const minIndex = Math.min(startIndex, endIndex);
  const maxIndex = Math.max(startIndex, endIndex);

  // Set all checkboxes in the range to the same state
  for (let i = minIndex; i <= maxIndex; i++) {
    allCheckboxes[i].checked = checked;
  }
}

function toggleFolder(folderPath) {
  // Toggle the collapsed state of a folder
  const folderRow = document.querySelector(`[data-path="${folderPath}"]`);
  if (!folderRow) return;

  const currentState = folderStates.get(folderPath) || "collapsed";
  const newState = currentState === "collapsed" ? "expanded" : "collapsed";
  folderStates.set(folderPath, newState);

  // Save the updated state to localStorage
  saveFolderStates();

  if (newState === "expanded") {
    // Expand folder - show only direct children
    folderRow.classList.remove("collapsed");

    // Show only direct children (one level down) and restore their states
    const allRows = document.querySelectorAll(".game-row");
    allRows.forEach((row) => {
      const rowPath = row.getAttribute("data-path");
      if (rowPath && rowPath.startsWith(folderPath + "/")) {
        // Check if this is a direct child (not a grandchild)
        const relativePath = rowPath.substring(folderPath.length + 1);
        if (!relativePath.includes("/")) {
          // This is a direct child, show it only if it passes current filters
          if (shouldRowBeVisible(row)) {
            row.style.display = "";
          } else {
            row.style.display = "none";
          }

          // If this is a folder, restore its individual state
          if (row.classList.contains("intermediate-folder")) {
            const childState = folderStates.get(rowPath) || "collapsed";
            if (childState === "expanded") {
              // This child was expanded, so expand it and show its children
              row.classList.remove("collapsed");
              showChildrenOfFolder(rowPath);
            } else {
              // This child was collapsed, so collapse it and hide its children
              row.classList.add("collapsed");
              hideChildrenOfFolder(rowPath);
            }
          }
        }
      }
    });
  } else {
    // Collapse folder - hide all children
    folderRow.classList.add("collapsed");

    hideChildrenOfFolder(folderPath);
  }
}

function hideChildrenOfFolder(folderPath) {
  // Hide all descendant rows of a folder
  const allRows = document.querySelectorAll(".game-row");
  allRows.forEach((row) => {
    const rowPath = row.getAttribute("data-path");
    if (rowPath && rowPath.startsWith(folderPath + "/")) {
      row.style.display = "none";
    }
  });
}

function showChildrenOfFolder(folderPath) {
  // Show all descendant rows of a folder, respecting their individual states and current filters
  const allRows = document.querySelectorAll(".game-row");
  allRows.forEach((row) => {
    const rowPath = row.getAttribute("data-path");
    if (rowPath && rowPath.startsWith(folderPath + "/")) {
      // Check if this is a direct child or a descendant
      const relativePath = rowPath.substring(folderPath.length + 1);

      if (!relativePath.includes("/")) {
        // This is a direct child - show it only if it passes current filters
        if (shouldRowBeVisible(row)) {
          row.style.display = "";
        }
      } else {
        // This is a grandchild or deeper - check if its parent is visible and expanded
        const parentPath = rowPath.substring(0, rowPath.lastIndexOf("/"));
        const parentRow = document.querySelector(`[data-path="${parentPath}"]`);

        if (parentRow && parentRow.style.display !== "none") {
          // Parent is visible, check if it's expanded
          const parentState = folderStates.get(parentPath) || "collapsed";
          if (parentState === "expanded") {
            // Parent is expanded, so show this child only if it passes current filters
            if (shouldRowBeVisible(row)) {
              row.style.display = "";
            }
          } else {
            // Parent is collapsed, so hide this child
            row.style.display = "none";
          }
        } else {
          // Parent is hidden, so hide this child too
          row.style.display = "none";
        }
      }
    }
  });
}

function toggleSelectAll(selectAllCheckbox) {
  // Toggle all game checkboxes
  const gameCheckboxes = document.querySelectorAll("input[data-path]");
  gameCheckboxes.forEach((checkbox) => {
    checkbox.checked = selectAllCheckbox.checked;
  });
}

// Modal functions
function openBulkActionsModal() {
  const selectedCheckboxes = document.querySelectorAll(
    "input[data-path]:checked",
  );
  if (selectedCheckboxes.length === 0) {
    alert("Please select at least one game folder first.");
    return;
  }

  const modal = document.getElementById("bulk-actions-modal");
  modal.style.display = "flex";
  // Clear previous content and warning
  document.getElementById("bulk-actions-textarea").value = "";
  hideModalWarning();
}

function closeBulkActionsModal() {
  const modal = document.getElementById("bulk-actions-modal");
  modal.style.display = "none";
  document.getElementById("bulk-actions-textarea").value = "";
  hideModalWarning();
}

function closeBulkActionsModalOnOverlay(event) {
  if (event.target === event.currentTarget) {
    closeBulkActionsModal();
  }
}

function showModalWarning(message) {
  const warning = document.getElementById("modal-warning");
  const warningText = document.getElementById("modal-warning-text");
  warningText.textContent = message;
  warning.classList.add("show");
}

function hideModalWarning() {
  document.getElementById("modal-warning").classList.remove("show");
}

function fillTextareaWithPaths() {
  const selectedCheckboxes = document.querySelectorAll(
    "input[data-path]:checked",
  );

  if (selectedCheckboxes.length === 0) {
    showModalWarning(
      "No folders selected. Please select folders from the table first.",
    );
    document.getElementById("bulk-actions-textarea").value = "";
    return;
  }

  hideModalWarning();
  const paths = Array.from(selectedCheckboxes).map((checkbox) =>
    checkbox.getAttribute("data-path"),
  );
  document.getElementById("bulk-actions-textarea").value = paths.join(" ");
}

function copyToClipboard(text) {
  // Modern clipboard API (requires HTTPS or localhost)
  if (navigator.clipboard && window.isSecureContext) {
    return navigator.clipboard.writeText(text);
  } else {
    // Fallback for non-HTTPS environments
    return new Promise((resolve, reject) => {
      // Create a temporary textarea element
      const textArea = document.createElement("textarea");
      textArea.value = text;
      textArea.style.position = "fixed";
      textArea.style.left = "-999999px";
      textArea.style.top = "-999999px";
      document.body.appendChild(textArea);
      textArea.focus();
      textArea.select();

      try {
        // Use the older execCommand API
        const successful = document.execCommand("copy");
        if (successful) {
          resolve();
        } else {
          reject(new Error("execCommand copy failed"));
        }
      } catch (err) {
        reject(err);
      } finally {
        document.body.removeChild(textArea);
      }
    });
  }
}

function showCopyMessage(message) {
  // Create temporary message element
  const messageDiv = document.createElement("div");
  messageDiv.textContent = message;
  messageDiv.style.cssText = `
    position: fixed;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    background-color: var(--success-color);
    color: white;
    padding: 1rem 2rem;
    border-radius: 0.5rem;
    z-index: 1000;
    font-weight: 500;
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
  `;

  document.body.appendChild(messageDiv);

  // Remove after 2 seconds
  setTimeout(() => {
    document.body.removeChild(messageDiv);
  }, 2000);
}

function fillTextareaWithFoldernames() {
  const selectedCheckboxes = document.querySelectorAll(
    "input[data-path]:checked",
  );

  if (selectedCheckboxes.length === 0) {
    showModalWarning(
      "No folders selected. Please select folders from the table first.",
    );
    document.getElementById("bulk-actions-textarea").value = "";
    return;
  }

  hideModalWarning();
  const folderNames = Array.from(selectedCheckboxes).map((checkbox) => {
    const fullPath = checkbox.getAttribute("data-path");
    return fullPath.split("/").pop();
  });
  document.getElementById("bulk-actions-textarea").value =
    folderNames.join(" ");
}

function fillTextareaWithS3RmCommands() {
  const selectedCheckboxes = document.querySelectorAll(
    "input[data-path]:checked",
  );

  if (selectedCheckboxes.length === 0) {
    showModalWarning(
      "No folders selected. Please select folders from the table first.",
    );
    document.getElementById("bulk-actions-textarea").value = "";
    return;
  }

  hideModalWarning();
  const paths = Array.from(selectedCheckboxes).map((checkbox) =>
    checkbox.getAttribute("data-path"),
  );

  const commands = paths.map((path) => {
    const encodedPath = path.replace(/\\/g, "/");
    return `aws s3 rm s3://codeclash/logs/${encodedPath}/ --recursive`;
  });

  document.getElementById("bulk-actions-textarea").value = commands.join("\n");
}

function fillTextareaWithAWSResubmitCommands() {
  const selectedCheckboxes = document.querySelectorAll(
    "input[data-path]:checked",
  );

  if (selectedCheckboxes.length === 0) {
    showModalWarning(
      "No folders selected. Please select folders from the table first.",
    );
    document.getElementById("bulk-actions-textarea").value = "";
    return;
  }

  hideModalWarning();
  const folderNames = Array.from(selectedCheckboxes).map((checkbox) => {
    const fullPath = checkbox.getAttribute("data-path");
    return fullPath.split("/").pop();
  });

  const commands = folderNames.map((folderName) => {
    return `aws/run_job.py -- main.py --config-file configs/main/${folderName}.yaml`;
  });

  document.getElementById("bulk-actions-textarea").value = commands.join("\n");
}

function copyFromModal() {
  const textarea = document.getElementById("bulk-actions-textarea");
  const text = textarea.value;

  if (text) {
    copyToClipboard(text)
      .then(() => {
        const btn = document.getElementById("modal-copy-btn");
        const originalHtml = btn.innerHTML;
        btn.classList.add("copied");
        btn.innerHTML = '<i class="bi bi-check-lg"></i> Copied!';

        setTimeout(() => {
          btn.classList.remove("copied");
          btn.innerHTML = originalHtml;
        }, 2000);
      })
      .catch((err) => {
        console.error("Failed to copy:", err);
      });
  }
}

// Close modal and dropdowns on Escape key
document.addEventListener("keydown", function (event) {
  if (event.key === "Escape") {
    const modal = document.getElementById("bulk-actions-modal");
    const modelDropdown = document.getElementById("model-filter-options");

    if (modal && modal.style.display === "flex") {
      closeBulkActionsModal();
    } else if (modelDropdown && modelDropdown.style.display === "block") {
      modelDropdown.style.display = "none";
    }
  }
});

// Keyboard navigation state
let currentSelectedIndex = -1;
let allNavigableRows = [];

// Initialize functionality on page load
document.addEventListener("DOMContentLoaded", function () {
  console.log("Game Picker initialized");
  console.log("Available keyboard shortcuts:");
  console.log("  Shift + Click: Range select checkboxes");
  console.log("  Escape: Close move dialog");
  console.log("  Arrow keys / hjkl: Navigate");
  console.log("  Enter: Open selected game");

  // Load saved folder states or collapse all by default
  const hasSavedStates = loadFolderStates();
  if (hasSavedStates) {
    applyFolderStates();
  } else {
    collapseAllFolders();
  }

  // Initialize keyboard navigation
  initializeKeyboardNavigation();

  // Initialize filters
  initializeFilters();

  // Add listener to game filter to save changes
  const gameFilter = document.getElementById("game-filter");
  if (gameFilter) {
    gameFilter.addEventListener("change", saveFilters);
  }

  // Close model dropdown when clicking outside
  document.addEventListener("click", (event) => {
    const dropdown = document.getElementById("model-filter-dropdown");
    const options = document.getElementById("model-filter-options");
    if (
      dropdown &&
      !dropdown.contains(event.target) &&
      options.style.display === "block"
    ) {
      options.style.display = "none";
    }
  });
});

// Track individual folder states
const folderStates = new Map();

// LocalStorage key for persisting folder states
const FOLDER_STATES_KEY = "picker_folder_states";

function saveFolderStates() {
  // Convert Map to object for storage
  const statesObj = Object.fromEntries(folderStates);
  try {
    localStorage.setItem(FOLDER_STATES_KEY, JSON.stringify(statesObj));
  } catch (e) {
    console.error("Failed to save folder states:", e);
  }
}

function loadFolderStates() {
  try {
    const stored = localStorage.getItem(FOLDER_STATES_KEY);
    if (stored) {
      const statesObj = JSON.parse(stored);
      // Convert object back to Map
      Object.entries(statesObj).forEach(([key, value]) => {
        folderStates.set(key, value);
      });
      return true;
    }
  } catch (e) {
    console.error("Failed to load folder states:", e);
  }
  return false;
}

function collapseAllFolders() {
  // Find all intermediate folder rows and collapse them
  const folderRows = document.querySelectorAll(".intermediate-folder");
  folderRows.forEach((folderRow) => {
    const folderPath = folderRow.getAttribute("data-path");
    if (folderPath) {
      // Set initial state to collapsed
      folderStates.set(folderPath, "collapsed");

      // Collapse the folder
      folderRow.classList.add("collapsed");

      // Hide all children of this folder
      hideChildrenOfFolder(folderPath);
    }
  });

  console.log(`Collapsed ${folderRows.length} folders on startup`);
}

function applyFolderStates() {
  // Apply loaded folder states to the UI
  const folderRows = document.querySelectorAll(".intermediate-folder");
  folderRows.forEach((folderRow) => {
    const folderPath = folderRow.getAttribute("data-path");
    if (folderPath) {
      const state = folderStates.get(folderPath) || "collapsed";

      if (state === "expanded") {
        folderRow.classList.remove("collapsed");
        showChildrenOfFolder(folderPath);
      } else {
        folderRow.classList.add("collapsed");
        hideChildrenOfFolder(folderPath);
      }
    }
  });

  console.log(`Applied folder states from localStorage`);
}

// Keyboard Navigation Functions
function initializeKeyboardNavigation() {
  updateNavigableRows();

  // Add keyboard event listener
  document.addEventListener("keydown", handleKeyboardNavigation);

  // Select first visible row by default
  if (allNavigableRows.length > 0) {
    setSelectedRow(0);
  }
}

function updateNavigableRows() {
  // Get all visible rows (both games and folders)
  allNavigableRows = Array.from(document.querySelectorAll(".game-row")).filter(
    (row) => row.style.display !== "none",
  );
}

function setSelectedRow(index) {
  // Remove previous selection
  if (
    currentSelectedIndex >= 0 &&
    currentSelectedIndex < allNavigableRows.length
  ) {
    allNavigableRows[currentSelectedIndex].classList.remove(
      "keyboard-selected",
    );
  }

  // Set new selection
  currentSelectedIndex = index;
  if (
    currentSelectedIndex >= 0 &&
    currentSelectedIndex < allNavigableRows.length
  ) {
    const selectedRow = allNavigableRows[currentSelectedIndex];
    selectedRow.classList.add("keyboard-selected");

    // Scroll into view if needed
    selectedRow.scrollIntoView({
      behavior: "smooth",
      block: "nearest",
    });
  }
}

function handleKeyboardNavigation(event) {
  // Don't handle keyboard navigation if a dialog is open or input is focused
  const modal = document.getElementById("bulk-actions-modal");
  const modelDropdown = document.getElementById("model-filter-options");
  if (
    (modal && modal.style.display === "flex") ||
    (modelDropdown && modelDropdown.style.display === "block") ||
    document.activeElement.tagName === "INPUT" ||
    document.activeElement.tagName === "SELECT"
  ) {
    return;
  }

  // Don't handle if no navigable rows
  if (allNavigableRows.length === 0) {
    return;
  }

  let handled = false;

  switch (event.key) {
    case "ArrowUp":
    case "k":
      event.preventDefault();
      navigateUp();
      handled = true;
      break;

    case "ArrowDown":
    case "j":
      event.preventDefault();
      navigateDown();
      handled = true;
      break;

    case "ArrowLeft":
    case "h":
      event.preventDefault();
      navigateLeft();
      handled = true;
      break;

    case "ArrowRight":
    case "l":
      event.preventDefault();
      navigateRight();
      handled = true;
      break;

    case "Enter":
      event.preventDefault();
      activateSelectedRow();
      handled = true;
      break;
  }

  if (handled) {
    // Update navigable rows in case visibility changed
    updateNavigableRows();
  }
}

function navigateUp() {
  if (currentSelectedIndex > 0) {
    setSelectedRow(currentSelectedIndex - 1);
  }
}

function navigateDown() {
  if (currentSelectedIndex < allNavigableRows.length - 1) {
    setSelectedRow(currentSelectedIndex + 1);
  }
}

function navigateLeft() {
  if (
    currentSelectedIndex >= 0 &&
    currentSelectedIndex < allNavigableRows.length
  ) {
    const selectedRow = allNavigableRows[currentSelectedIndex];
    const folderPath = selectedRow.getAttribute("data-path");

    // If it's a folder and it's expanded, collapse it
    if (selectedRow.classList.contains("intermediate-folder")) {
      const currentState = folderStates.get(folderPath) || "collapsed";
      if (currentState === "expanded") {
        toggleFolder(folderPath);
        updateNavigableRows();
        // Keep selection on the same row after collapse
        const newIndex = allNavigableRows.findIndex(
          (row) => row.getAttribute("data-path") === folderPath,
        );
        if (newIndex >= 0) {
          setSelectedRow(newIndex);
        }
      }
    }
  }
}

function navigateRight() {
  if (
    currentSelectedIndex >= 0 &&
    currentSelectedIndex < allNavigableRows.length
  ) {
    const selectedRow = allNavigableRows[currentSelectedIndex];
    const folderPath = selectedRow.getAttribute("data-path");

    // If it's a folder and it's collapsed, expand it
    if (selectedRow.classList.contains("intermediate-folder")) {
      const currentState = folderStates.get(folderPath) || "collapsed";
      if (currentState === "collapsed") {
        toggleFolder(folderPath);
        updateNavigableRows();
        // Keep selection on the same row after expand
        const newIndex = allNavigableRows.findIndex(
          (row) => row.getAttribute("data-path") === folderPath,
        );
        if (newIndex >= 0) {
          setSelectedRow(newIndex);
        }
      }
    }
  }
}

function activateSelectedRow() {
  if (
    currentSelectedIndex >= 0 &&
    currentSelectedIndex < allNavigableRows.length
  ) {
    const selectedRow = allNavigableRows[currentSelectedIndex];
    const folderPath = selectedRow.getAttribute("data-path");

    if (selectedRow.classList.contains("intermediate-folder")) {
      // Toggle folder
      toggleFolder(folderPath);
      updateNavigableRows();
      // Keep selection on the same row after toggle
      const newIndex = allNavigableRows.findIndex(
        (row) => row.getAttribute("data-path") === folderPath,
      );
      if (newIndex >= 0) {
        setSelectedRow(newIndex);
      }
    } else if (selectedRow.classList.contains("game-folder")) {
      // Open game
      openGame(folderPath);
    }
  }
}

// Filtering functionality
let allGameRows = [];
let uniqueGames = new Set();
let uniqueModels = new Set();
let selectedModels = new Set();
let selectedDate = null;

function shouldRowBeVisible(row) {
  const gameFilter =
    document.getElementById("game-filter")?.value.toLowerCase() || "";

  if (row.classList.contains("game-folder")) {
    // Check game name filter
    if (gameFilter) {
      const gameNameElement = row.querySelector(".game-name-text");
      const gameName = gameNameElement
        ? gameNameElement.textContent.toLowerCase()
        : "";
      if (!gameName.includes(gameFilter)) {
        return false;
      }
    }

    // Check model filter - if models are selected, row must have ALL of them (intersection)
    if (selectedModels.size > 0) {
      const modelTags = row.querySelectorAll(".model-tag");
      const rowModels = new Set(
        Array.from(modelTags).map((tag) => tag.textContent.trim()),
      );
      const hasAllModels = Array.from(selectedModels).every((model) =>
        rowModels.has(model),
      );
      if (!hasAllModels) {
        return false;
      }
    }

    // Check date filter - if a date is selected, row must match that date
    if (selectedDate) {
      const dateElement = row.querySelector(".date-text");
      if (dateElement) {
        const dateText = dateElement.textContent.trim();
        // Extract just the YYYY-MM-DD part
        const rowDate = dateText.split(" ")[0];
        if (rowDate !== selectedDate) {
          return false;
        }
      } else {
        // Row has no date, so it doesn't match
        return false;
      }
    }

    return true;
  } else {
    // For intermediate folders, check if any child game folders should be visible
    const folderPath = row.getAttribute("data-path");
    const childGameRows = document.querySelectorAll(
      `.game-row.game-folder[data-path^="${folderPath}/"]`,
    );
    return Array.from(childGameRows).some((childRow) =>
      shouldRowBeVisible(childRow),
    );
  }
}

function initializeFilters() {
  // Collect all game rows and extract unique values
  allGameRows = Array.from(document.querySelectorAll(".game-row.game-folder"));

  allGameRows.forEach((row) => {
    // Extract game name
    const gameNameElement = row.querySelector(".game-name-text");
    if (gameNameElement && gameNameElement.textContent.trim()) {
      uniqueGames.add(gameNameElement.textContent.trim());
    }

    // Extract model names
    const modelTags = row.querySelectorAll(".model-tag");
    modelTags.forEach((tag) => {
      if (tag.textContent.trim()) {
        uniqueModels.add(tag.textContent.trim());
      }
    });
  });

  // Populate filter dropdowns
  populateGameFilter();
  populateModelFilter();

  // Load saved filters from localStorage
  const hasFilters = loadFilters();
  if (hasFilters) {
    // Apply the loaded filters
    applyFilters();
  }
}

function populateGameFilter() {
  const gameFilter = document.getElementById("game-filter");
  if (!gameFilter) return;

  // Clear existing options except "All Games"
  gameFilter.innerHTML = '<option value="">All Games</option>';

  // Add unique games
  Array.from(uniqueGames)
    .sort()
    .forEach((game) => {
      const option = document.createElement("option");
      option.value = game;
      option.textContent = game;
      gameFilter.appendChild(option);
    });
}

function populateModelFilter() {
  const modelFilterList = document.getElementById("model-filter-list");
  if (!modelFilterList) return;

  // Clear existing options
  modelFilterList.innerHTML = "";

  // Add unique models as clickable options
  Array.from(uniqueModels)
    .sort()
    .forEach((model) => {
      const option = document.createElement("div");
      option.className = "model-filter-option";
      option.textContent = model;
      option.onclick = (e) => toggleModelSelection(e, model);
      modelFilterList.appendChild(option);
    });
}

function applyFilters() {
  // Get all game rows (both game folders and intermediate folders)
  const allRows = document.querySelectorAll(".game-row");

  allRows.forEach((row) => {
    if (shouldRowBeVisible(row)) {
      // Check if this row should be visible based on parent folder states
      const rowPath = row.getAttribute("data-path");
      let shouldShowBasedOnParents = true;

      if (rowPath && rowPath.includes("/")) {
        let currentPath = rowPath;

        // Walk up the parent hierarchy
        while (currentPath.includes("/")) {
          const parentPath = currentPath.substring(
            0,
            currentPath.lastIndexOf("/"),
          );
          const parentState = folderStates.get(parentPath) || "collapsed";

          if (parentState === "collapsed") {
            shouldShowBasedOnParents = false;
            break;
          }

          currentPath = parentPath;
        }
      }

      row.style.display = shouldShowBasedOnParents ? "" : "none";
    } else {
      row.style.display = "none";
    }
  });

  // Update keyboard navigation after filtering
  updateNavigableRows();
}

function clearFilters() {
  document.getElementById("game-filter").value = "";
  selectedModels.clear();
  selectedDate = null;
  updateModelFilterDisplay();
  updateDateFilterDisplay();
  saveFilters();

  // Reapply the current folder states without any filters
  applyFilters();
}

function setGameFilter(gameName) {
  const gameFilter = document.getElementById("game-filter");
  if (gameFilter) {
    gameFilter.value = gameName;
    saveFilters();
    applyFilters();
  }
}

function toggleModelSelection(event, modelName) {
  event.stopPropagation();

  if (selectedModels.has(modelName)) {
    selectedModels.delete(modelName);
  } else {
    selectedModels.add(modelName);
  }

  updateModelFilterDisplay();
  saveFilters();
  applyFilters();
}

function clearModelSelection(event) {
  event.stopPropagation();
  selectedModels.clear();
  updateModelFilterDisplay();
  saveFilters();
  applyFilters();
}

function updateModelFilterDisplay() {
  const displayElement = document.getElementById("model-filter-display");
  const options = document.querySelectorAll(".model-filter-option");

  if (selectedModels.size === 0) {
    displayElement.textContent = "All Models";
  } else if (selectedModels.size === 1) {
    displayElement.textContent = Array.from(selectedModels)[0];
  } else {
    displayElement.textContent = `${selectedModels.size} models selected`;
  }

  // Update visual state of options
  options.forEach((option) => {
    if (selectedModels.has(option.textContent)) {
      option.classList.add("selected");
    } else {
      option.classList.remove("selected");
    }
  });
}

function toggleModelDropdown(event) {
  event.stopPropagation();
  const dropdown = document.getElementById("model-filter-options");
  const button = document.getElementById("model-filter-button");
  const isVisible = dropdown.style.display !== "none";

  if (isVisible) {
    dropdown.style.display = "none";
  } else {
    // Calculate position based on button location
    const buttonRect = button.getBoundingClientRect();
    dropdown.style.left = buttonRect.left + "px";
    dropdown.style.top = buttonRect.bottom + 4 + "px";
    dropdown.style.width = buttonRect.width + "px";
    dropdown.style.display = "block";
  }
}

function handleGameNameClick(event, gameName) {
  event.stopPropagation();
  setGameFilter(gameName);
}

function handleModelTagClick(event, modelName) {
  event.stopPropagation();
  toggleModelSelection(event, modelName);
}

function handleDateClick(event, dateText) {
  event.stopPropagation();
  // Extract just the YYYY-MM-DD part
  const date = dateText.trim().split(" ")[0];

  // Toggle date filter - if already selected, clear it
  if (selectedDate === date) {
    selectedDate = null;
  } else {
    selectedDate = date;
  }

  updateDateFilterDisplay();
  saveFilters();
  applyFilters();
}

function updateDateFilterDisplay() {
  // Find all date cells and update their styling
  const dateCells = document.querySelectorAll(".date-text");
  dateCells.forEach((cell) => {
    const cellDate = cell.textContent.trim().split(" ")[0];
    if (selectedDate && cellDate === selectedDate) {
      cell.classList.add("date-selected");
    } else {
      cell.classList.remove("date-selected");
    }
  });

  // Update the filter badge
  const badge = document.getElementById("date-filter-badge");
  const badgeText = document.getElementById("date-filter-text");
  const container = document.getElementById("active-filters-container");

  if (selectedDate) {
    if (badgeText) badgeText.textContent = selectedDate;
    if (badge) badge.style.display = "inline-flex";
    if (container) container.style.display = "flex";
  } else {
    if (badge) badge.style.display = "none";
    // Hide container if no filters are active
    if (container && !hasActiveFilters()) {
      container.style.display = "none";
    }
  }
}

function hasActiveFilters() {
  return (
    selectedDate !== null ||
    selectedModels.size > 0 ||
    (document.getElementById("game-filter")?.value || "") !== ""
  );
}

function clearDateFilter(event) {
  if (event) {
    event.preventDefault();
    event.stopPropagation();
  }
  selectedDate = null;
  updateDateFilterDisplay();
  saveFilters();
  applyFilters();
}

// Filter persistence
const FILTERS_KEY = "picker_filters";

function saveFilters() {
  const filters = {
    game: document.getElementById("game-filter")?.value || "",
    models: Array.from(selectedModels),
    date: selectedDate,
  };
  try {
    localStorage.setItem(FILTERS_KEY, JSON.stringify(filters));
  } catch (e) {
    console.error("Failed to save filters:", e);
  }
}

function loadFilters() {
  try {
    const stored = localStorage.getItem(FILTERS_KEY);
    if (stored) {
      const filters = JSON.parse(stored);

      // Restore game filter
      const gameFilter = document.getElementById("game-filter");
      if (gameFilter && filters.game) {
        gameFilter.value = filters.game;
      }

      // Restore model filter
      if (filters.models && Array.isArray(filters.models)) {
        filters.models.forEach((model) => selectedModels.add(model));
        updateModelFilterDisplay();
      }

      // Restore date filter
      if (filters.date) {
        selectedDate = filters.date;
        updateDateFilterDisplay();
      }

      return true;
    }
  } catch (e) {
    console.error("Failed to load filters:", e);
  }
  return false;
}

// Sorting functionality
let currentSort = { column: null, ascending: true };

function sortTable(column) {
  // Toggle sort order if clicking the same column
  if (currentSort.column === column) {
    currentSort.ascending = !currentSort.ascending;
  } else {
    currentSort.column = column;
    currentSort.ascending = true;
  }

  const rows = Array.from(document.querySelectorAll(".game-row"));

  // Build a tree structure to maintain hierarchy
  const rowsByPath = new Map();
  rows.forEach((row) => {
    rowsByPath.set(row.dataset.path, row);
  });

  // Group rows by their parent
  const childrenByParent = new Map();
  rows.forEach((row) => {
    const parent = row.dataset.parent || "";
    if (!childrenByParent.has(parent)) {
      childrenByParent.set(parent, []);
    }
    childrenByParent.get(parent).push(row);
  });

  // Comparison function based on selected column
  function compareRows(a, b) {
    let aValue, bValue;

    if (column === "name") {
      // For name sorting, use just the folder name (not full path)
      aValue = a.dataset.path.split("/").pop() || "";
      bValue = b.dataset.path.split("/").pop() || "";
      return currentSort.ascending
        ? aValue.localeCompare(bValue)
        : bValue.localeCompare(aValue);
    } else if (column === "date") {
      // Get timestamps, treat empty/missing as 0 (will sort to the end when ascending)
      aValue = parseInt(a.dataset.timestamp) || 0;
      bValue = parseInt(b.dataset.timestamp) || 0;

      // Put entries without timestamps at the end
      if (aValue === 0 && bValue === 0) return 0;
      if (aValue === 0) return 1;
      if (bValue === 0) return -1;

      return currentSort.ascending ? aValue - bValue : bValue - aValue;
    }

    return 0;
  }

  // Sort children at each level
  childrenByParent.forEach((children) => {
    children.sort(compareRows);
  });

  // Recursively build the sorted list maintaining hierarchy
  function buildSortedList(parent) {
    const result = [];
    const children = childrenByParent.get(parent) || [];

    for (const child of children) {
      result.push(child);
      // Add all descendants of this child
      result.push(...buildSortedList(child.dataset.path));
    }

    return result;
  }

  // Build the final sorted list starting from root (empty parent)
  const sortedRows = buildSortedList("");

  // Get the table header element
  const tableHeader = document.querySelector(".table-header");

  // Remove all existing rows
  rows.forEach((row) => row.remove());

  // Re-insert rows in sorted order
  let previousElement = tableHeader;
  sortedRows.forEach((row) => {
    previousElement.after(row);
    previousElement = row;
  });

  // Re-apply filters to maintain visibility state
  applyFilters();
}
