// Game Picker JavaScript

function openGame(gameName) {
  // Navigate to the viewer with the selected game
  const url = `/?folder=${encodeURIComponent(gameName)}`;
  window.location.href = url;
}

function openGameInNewTab(gameName) {
  // Open the viewer in a new tab with the selected game
  const url = `/?folder=${encodeURIComponent(gameName)}`;
  window.open(url, "_blank");
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

    if (checkbox) {
      // Direct checkbox click - handle shift-click range selection
      handleCheckboxClick(event, gameName);
    } else {
      // Click in checkbox area but not on checkbox - toggle selection
      toggleGameSelection(gameName);
    }
  } else {
    // Click is elsewhere - open game (original behavior)
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

  const isCollapsed = folderRow.classList.contains("collapsed");
  const collapseIcon = folderRow.querySelector(".collapse-icon");

  if (isCollapsed) {
    // Expand folder - show all children
    folderRow.classList.remove("collapsed");
    if (collapseIcon) collapseIcon.textContent = "📁";

    // Show all descendant rows
    const allRows = document.querySelectorAll(".game-row");
    allRows.forEach((row) => {
      const rowPath = row.getAttribute("data-path");
      if (rowPath && rowPath.startsWith(folderPath + "/")) {
        row.style.display = "";
        // If this child row is also a collapsed folder, don't show its children
        const childFolderPath = rowPath;
        const childRow = document.querySelector(
          `[data-path="${childFolderPath}"]`,
        );
        if (childRow && childRow.classList.contains("collapsed")) {
          // Hide this collapsed folder's children
          hideChildrenOfFolder(childFolderPath);
        }
      }
    });
  } else {
    // Collapse folder - hide all children
    folderRow.classList.add("collapsed");
    if (collapseIcon) collapseIcon.textContent = "📂";

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

function toggleSelectAll(selectAllCheckbox) {
  // Toggle all game checkboxes
  const gameCheckboxes = document.querySelectorAll("input[data-path]");
  gameCheckboxes.forEach((checkbox) => {
    checkbox.checked = selectAllCheckbox.checked;
  });
}

function handleAction(action) {
  if (!action) return;

  if (action === "copy-paths") {
    copySelectedPaths();
  }

  // Reset dropdown
  document.getElementById("action-dropdown").value = "";
}

function copySelectedPaths() {
  const selectedCheckboxes = document.querySelectorAll(
    "input[data-path]:checked",
  );

  if (selectedCheckboxes.length === 0) {
    alert("Please select at least one game to copy paths.");
    return;
  }

  const paths = Array.from(selectedCheckboxes).map((checkbox) =>
    checkbox.getAttribute("data-path"),
  );

  const pathsString = paths.join(" ");

  // Copy to clipboard
  navigator.clipboard
    .writeText(pathsString)
    .then(() => {
      // Show temporary success message
      showCopyMessage(
        `Copied ${paths.length} path${paths.length > 1 ? "s" : ""} to clipboard`,
      );
    })
    .catch((err) => {
      console.error("Failed to copy paths: ", err);
      // Fallback: show paths in alert
      alert("Failed to copy to clipboard. Paths:\n" + pathsString);
    });
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

// Initialize theme and other functionality on page load
document.addEventListener("DOMContentLoaded", function () {
  initializeTheme();

  console.log("Game Picker initialized");
  console.log("Available keyboard shortcuts:");
  console.log("  Ctrl/Cmd + D: Toggle dark mode");
  console.log("  Shift + Click: Range select checkboxes");
});
