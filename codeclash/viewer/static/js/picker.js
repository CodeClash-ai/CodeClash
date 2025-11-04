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
    // Navigate to directory (index.html will be served automatically)
    const url = `/game/${pathSegments.join("/")}`;
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
    // Navigate to directory (index.html will be served automatically)
    const url = `/game/${pathSegments.join("/")}`;
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

  if (checkbox || checkboxCell) {
    // Click is on checkbox or in checkbox area - handle selection
    event.stopPropagation();

    if (!checkbox) {
      // Click in checkbox area but not on checkbox - toggle selection
      toggleGameSelection(gameName);
    }
  } else {
    // Click is anywhere else on the row - open game
    if (event.button === 1 || event.ctrlKey || event.metaKey) {
      // Middle click, Ctrl+click, or Cmd+click - open in new tab
      event.preventDefault();
      openGameInNewTab(gameName);
    } else if (event.button === 0) {
      // Left click - open in same tab
      openGame(gameName);
    }
  }
}

function toggleSelectAll(selectAllCheckbox) {
  // Toggle all game checkboxes
  const gameCheckboxes = document.querySelectorAll("input[data-path]");
  gameCheckboxes.forEach((checkbox) => {
    checkbox.checked = selectAllCheckbox.checked;
  });
  updateRunsStatus();
}

function updateSelectAllCheckbox() {
  const selectAllCheckbox = document.getElementById("select-all");
  if (!selectAllCheckbox) return;

  const allGameCheckboxes = document.querySelectorAll("input[data-path]");
  if (allGameCheckboxes.length === 0) {
    selectAllCheckbox.checked = false;
    selectAllCheckbox.indeterminate = false;
    return;
  }

  const checkedCount = document.querySelectorAll(
    "input[data-path]:checked",
  ).length;

  if (checkedCount === 0) {
    selectAllCheckbox.checked = false;
    selectAllCheckbox.indeterminate = false;
  } else if (checkedCount === allGameCheckboxes.length) {
    selectAllCheckbox.checked = true;
    selectAllCheckbox.indeterminate = false;
  } else {
    selectAllCheckbox.checked = false;
    selectAllCheckbox.indeterminate = true;
  }

  updateRunsStatus();
}

function updateRunsStatus() {
  const statusElement = document.getElementById("runs-status");
  if (!statusElement) return;

  // Count visible rows
  const allRows = document.querySelectorAll(".game-row");
  const visibleRows = Array.from(allRows).filter(
    (row) => row.style.display !== "none",
  );
  const listedCount = visibleRows.length;

  // Count checked rows among visible ones
  const markedCount = visibleRows.filter((row) => {
    const checkbox = row.querySelector("input[data-path]");
    return checkbox && checkbox.checked;
  }).length;

  // Update display
  statusElement.textContent = `${listedCount} runs listed (${markedCount} selected)`;
}

// Modal functions
function openBulkActionsModal() {
  const selectedCheckboxes = getVisibleCheckedCheckboxes();
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

function getVisibleCheckedCheckboxes() {
  // Get all checked checkboxes and filter out those in hidden rows
  const allChecked = document.querySelectorAll("input[data-path]:checked");
  return Array.from(allChecked).filter((checkbox) => {
    const row = checkbox.closest(".game-row");
    return row && row.style.display !== "none";
  });
}

function fillTextareaWithPaths() {
  const selectedCheckboxes = getVisibleCheckedCheckboxes();

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
  const selectedCheckboxes = getVisibleCheckedCheckboxes();

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
  const selectedCheckboxes = getVisibleCheckedCheckboxes();

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
  const selectedCheckboxes = getVisibleCheckedCheckboxes();

  if (selectedCheckboxes.length === 0) {
    showModalWarning(
      "No folders selected. Please select folders from the table first.",
    );
    document.getElementById("bulk-actions-textarea").value = "";
    return;
  }

  // Get the row for each checkbox and extract AWS command from metadata
  const commandsWithInfo = Array.from(selectedCheckboxes).map((checkbox) => {
    const row = checkbox.closest(".game-row");
    const awsCommand = row ? row.getAttribute("data-aws-command") : "";
    const fullPath = checkbox.getAttribute("data-path");

    return {
      path: fullPath,
      awsCommand: awsCommand,
      hasCommand: awsCommand && awsCommand.trim() !== "",
    };
  });

  // Separate folders with and without AWS commands
  const foldersWithCommands = commandsWithInfo.filter(
    (info) => info.hasCommand,
  );
  const foldersWithoutCommands = commandsWithInfo.filter(
    (info) => !info.hasCommand,
  );

  if (foldersWithCommands.length === 0) {
    showModalWarning(
      "None of the selected folders have AWS command information in their metadata.",
    );
    document.getElementById("bulk-actions-textarea").value = "";
    return;
  }

  // Generate commands for folders that have AWS command info
  const commands = foldersWithCommands.map((info) => {
    return `aws/run_job.py -- ${info.awsCommand}`;
  });

  document.getElementById("bulk-actions-textarea").value = commands.join("\n");

  // Show warning if some folders are missing AWS commands
  if (foldersWithoutCommands.length > 0) {
    const folderNames = foldersWithoutCommands
      .map((info) => info.path.split("/").pop())
      .join(", ");
    showModalWarning(
      `Warning: ${foldersWithoutCommands.length} folder(s) skipped due to missing AWS command in metadata: ${folderNames}`,
    );
  } else {
    hideModalWarning();
  }
}

async function fillTextareaWithGuessedConfigNames() {
  const selectedCheckboxes = getVisibleCheckedCheckboxes();

  if (selectedCheckboxes.length === 0) {
    showModalWarning(
      "No folders selected. Please select folders from the table first.",
    );
    document.getElementById("bulk-actions-textarea").value = "";
    return;
  }

  // Show loading message
  const textarea = document.getElementById("bulk-actions-textarea");
  textarea.value = "Loading...";
  hideModalWarning();

  // Extract folder paths
  const folderPaths = Array.from(selectedCheckboxes).map((checkbox) =>
    checkbox.getAttribute("data-path"),
  );

  try {
    // Call backend API
    const response = await fetch("/picker/api/guess-config-names", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ folder_paths: folderPaths }),
    });

    const data = await response.json();

    if (!data.success) {
      showModalWarning(`Error: ${data.error}`);
      textarea.value = "";
      return;
    }

    // Process results
    const successfulResults = data.results.filter(
      (result) => result.config_name,
    );
    const failedResults = data.results.filter((result) => !result.config_name);

    if (successfulResults.length === 0) {
      showModalWarning("No config names could be guessed from the metadata.");
      textarea.value = "";
      return;
    }

    // Format output
    const configNames = successfulResults.map((result) => result.config_name);
    textarea.value = configNames.join("\n");

    // Show warning if some folders failed
    if (failedResults.length > 0) {
      const errorMessages = failedResults.map((result) => {
        const folderName = result.folder.split("/").pop();
        return `${folderName}: ${result.error}`;
      });
      showModalWarning(
        `Warning: ${failedResults.length} folder(s) failed:\n${errorMessages.join("\n")}`,
      );
    } else {
      hideModalWarning();
    }
  } catch (error) {
    console.error("Error guessing config names:", error);
    showModalWarning(`Error: ${error.message}`);
    textarea.value = "";
  }
}

async function fillTextareaWithAWSSubmitCommands() {
  const selectedCheckboxes = getVisibleCheckedCheckboxes();

  if (selectedCheckboxes.length === 0) {
    showModalWarning(
      "No folders selected. Please select folders from the table first.",
    );
    document.getElementById("bulk-actions-textarea").value = "";
    return;
  }

  // Show loading message
  const textarea = document.getElementById("bulk-actions-textarea");
  textarea.value = "Loading...";
  hideModalWarning();

  // Extract folder paths
  const folderPaths = Array.from(selectedCheckboxes).map((checkbox) =>
    checkbox.getAttribute("data-path"),
  );

  try {
    // Call backend API
    const response = await fetch("/picker/api/guess-config-names", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ folder_paths: folderPaths }),
    });

    const data = await response.json();

    if (!data.success) {
      showModalWarning(`Error: ${data.error}`);
      textarea.value = "";
      return;
    }

    // Process results
    const successfulResults = data.results.filter(
      (result) => result.config_name,
    );
    const failedResults = data.results.filter((result) => !result.config_name);

    if (successfulResults.length === 0) {
      showModalWarning("No config names could be guessed from the metadata.");
      textarea.value = "";
      return;
    }

    // Format output as AWS submit commands
    const commands = successfulResults.map(
      (result) =>
        `aws/run_job.py -- aws/docker_and_sync.sh python main.py configs/main/${result.config_name}`,
    );
    textarea.value = commands.join("\n");

    // Show warning if some folders failed
    if (failedResults.length > 0) {
      const errorMessages = failedResults.map((result) => {
        const folderName = result.folder.split("/").pop();
        return `${folderName}: ${result.error}`;
      });
      showModalWarning(
        `Warning: ${failedResults.length} folder(s) skipped:\n${errorMessages.join("\n")}`,
      );
    } else {
      hideModalWarning();
    }
  } catch (error) {
    console.error("Error generating AWS submit commands:", error);
    showModalWarning(`Error: ${error.message}`);
    textarea.value = "";
  }
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
  console.log("  Escape: Close move dialog");
  console.log("  Arrow keys / hjkl: Navigate");
  console.log("  Enter: Open selected game");

  // Initialize keyboard navigation
  initializeKeyboardNavigation();

  // Initialize filters
  initializeFilters();

  // Set default folder to first option if not already set
  const folderFilter = document.getElementById("folder-filter");
  if (folderFilter && folderFilter.options.length > 0 && !folderFilter.value) {
    folderFilter.selectedIndex = 0;
    selectedFolder = folderFilter.value;
  }

  // Add change event listeners to all game checkboxes to update select-all state
  document.querySelectorAll("input[data-path]").forEach((checkbox) => {
    checkbox.addEventListener("change", updateSelectAllCheckbox);
  });

  // Initialize select-all checkbox state
  updateSelectAllCheckbox();

  // Initialize runs status
  updateRunsStatus();

  // Add listener to filters to save changes
  if (folderFilter) {
    folderFilter.addEventListener("change", saveFilters);
  }

  const nameFilter = document.getElementById("name-filter");
  if (nameFilter) {
    nameFilter.addEventListener("input", saveFilters);
  }

  const gameFilter = document.getElementById("game-filter");
  if (gameFilter) {
    gameFilter.addEventListener("change", saveFilters);
  }

  const roundsFilter = document.getElementById("rounds-filter");
  if (roundsFilter) {
    roundsFilter.addEventListener("change", saveFilters);
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

function activateSelectedRow() {
  if (
    currentSelectedIndex >= 0 &&
    currentSelectedIndex < allNavigableRows.length
  ) {
    const selectedRow = allNavigableRows[currentSelectedIndex];
    const folderPath = selectedRow.getAttribute("data-path");

    // Open game
    openGame(folderPath);
  }
}

// Filtering functionality
let allGameRows = [];
let uniqueGames = new Set();
let uniqueModels = new Set();
let selectedModels = new Set();
let selectedDate = null;
let selectedFolder = "";

function shouldRowBeVisible(row) {
  // Check folder filter (mandatory)
  const folderFilter = document.getElementById("folder-filter")?.value;
  if (folderFilter !== undefined) {
    const rowParentFolder = row.getAttribute("data-parent-folder") || "";
    if (rowParentFolder !== folderFilter) {
      return false;
    }
  }

  // Check name filter
  const nameFilter =
    document.getElementById("name-filter")?.value.toLowerCase() || "";
  if (nameFilter) {
    const sessionNameElement = row.querySelector(".game-name");
    const sessionName = sessionNameElement
      ? sessionNameElement.textContent.toLowerCase()
      : "";
    if (!sessionName.includes(nameFilter)) {
      return false;
    }
  }

  // Check game name filter
  const gameFilter =
    document.getElementById("game-filter")?.value.toLowerCase() || "";
  if (gameFilter) {
    const gameNameElement = row.querySelector(".game-name-text");
    const gameName = gameNameElement
      ? gameNameElement.textContent.toLowerCase()
      : "";
    if (!gameName.includes(gameFilter)) {
      return false;
    }
  }

  // Check rounds filter
  const roundsFilter = document.getElementById("rounds-filter")?.value || "";
  if (roundsFilter) {
    const roundsElement = row.querySelector(".rounds-count");
    if (roundsFilter === "complete") {
      // Only show rows with complete rounds (no warning class)
      if (
        !roundsElement ||
        roundsElement.classList.contains("rounds-count-warning")
      ) {
        return false;
      }
    } else if (roundsFilter === "incomplete") {
      // Only show rows with incomplete rounds (has warning class) or unknown
      if (
        roundsElement &&
        !roundsElement.classList.contains("rounds-count-warning")
      ) {
        return false;
      }
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
      // Extract just the MM/DD part
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

  // Initialize clear filters button visibility
  updateClearFiltersButton();
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
  // Get all game rows
  const allRows = document.querySelectorAll(".game-row");

  allRows.forEach((row) => {
    if (shouldRowBeVisible(row)) {
      row.style.display = "";
    } else {
      row.style.display = "none";
    }
  });

  // Update keyboard navigation after filtering
  updateNavigableRows();

  // Update select-all checkbox state after filtering
  updateSelectAllCheckbox();

  // Update clear filters button visibility
  updateClearFiltersButton();

  // Update runs status
  updateRunsStatus();
}

function clearFilters() {
  // Reset folder filter to first option (folder filter is mandatory)
  const folderFilter = document.getElementById("folder-filter");
  if (folderFilter && folderFilter.options.length > 0) {
    folderFilter.selectedIndex = 0;
    selectedFolder = folderFilter.value;
  }

  const nameFilter = document.getElementById("name-filter");
  if (nameFilter) nameFilter.value = "";

  const gameFilter = document.getElementById("game-filter");
  if (gameFilter) gameFilter.value = "";

  const roundsFilter = document.getElementById("rounds-filter");
  if (roundsFilter) roundsFilter.value = "";

  selectedModels.clear();
  selectedDate = null;
  updateModelFilterDisplay();
  updateDateFilterDisplay();
  updateClearFiltersButton();
  saveFilters();

  // Reapply filters
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

  // Update clear filters button visibility
  updateClearFiltersButton();
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

  // Update clear filters button visibility
  updateClearFiltersButton();
}

function hasActiveFilters() {
  return (
    selectedDate !== null ||
    selectedModels.size > 0 ||
    (document.getElementById("name-filter")?.value || "") !== "" ||
    (document.getElementById("game-filter")?.value || "") !== "" ||
    (document.getElementById("rounds-filter")?.value || "") !== ""
  );
}

function updateClearFiltersButton() {
  const clearButton = document.getElementById("clear-filters");
  if (clearButton) {
    if (hasActiveFilters()) {
      clearButton.classList.add("show");
    } else {
      clearButton.classList.remove("show");
    }
  }
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
    folder: document.getElementById("folder-filter")?.value || "",
    name: document.getElementById("name-filter")?.value || "",
    game: document.getElementById("game-filter")?.value || "",
    rounds: document.getElementById("rounds-filter")?.value || "",
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

      // Restore folder filter
      const folderFilter = document.getElementById("folder-filter");
      if (folderFilter && filters.folder !== undefined) {
        // Check if the saved folder still exists in options
        const optionExists = Array.from(folderFilter.options).some(
          (opt) => opt.value === filters.folder,
        );
        if (optionExists) {
          folderFilter.value = filters.folder;
          selectedFolder = filters.folder;
        } else if (folderFilter.options.length > 0) {
          // Saved folder doesn't exist, default to first option
          folderFilter.selectedIndex = 0;
          selectedFolder = folderFilter.value;
        }
      } else if (folderFilter && folderFilter.options.length > 0) {
        // No saved folder, default to first option
        folderFilter.selectedIndex = 0;
        selectedFolder = folderFilter.value;
      }

      // Restore name filter
      const nameFilter = document.getElementById("name-filter");
      if (nameFilter && filters.name) {
        nameFilter.value = filters.name;
      }

      // Restore game filter
      const gameFilter = document.getElementById("game-filter");
      if (gameFilter && filters.game) {
        gameFilter.value = filters.game;
      }

      // Restore rounds filter
      const roundsFilter = document.getElementById("rounds-filter");
      if (roundsFilter && filters.rounds) {
        roundsFilter.value = filters.rounds;
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

  // Sort all rows
  rows.sort(compareRows);

  // Get the table header element
  const tableHeader = document.querySelector(".table-header");

  // Remove all existing rows
  rows.forEach((row) => row.remove());

  // Re-insert rows in sorted order
  let previousElement = tableHeader;
  rows.forEach((row) => {
    previousElement.after(row);
    previousElement = row;
  });

  // Re-apply filters to maintain visibility state
  applyFilters();
}
