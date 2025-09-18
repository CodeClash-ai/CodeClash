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
    if (collapseIcon) collapseIcon.innerHTML = '<i class="bi bi-folder"></i>';

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
    if (collapseIcon)
      collapseIcon.innerHTML = '<i class="bi bi-folder-open"></i>';

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
  } else if (action === "add-suffix") {
    addSuffixToSelected();
  } else if (action === "copy-foldernames") {
    copySelectedFoldernames();
  } else if (action === "move-to-subfolder") {
    moveToSubfolder();
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

  // Copy to clipboard with fallback
  copyToClipboard(pathsString)
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

function addSuffixToSelected() {
  const selectedCheckboxes = document.querySelectorAll(
    "input[data-path]:checked",
  );

  if (selectedCheckboxes.length === 0) {
    alert("Please select at least one game to add suffix.");
    return;
  }

  // Create a minimally styled input prompt
  const suffix = prompt("Enter suffix to add to selected folders:");

  if (suffix === null || suffix.trim() === "") {
    return; // User cancelled or entered empty string
  }

  const trimmedSuffix = suffix.trim();
  const paths = Array.from(selectedCheckboxes).map((checkbox) =>
    checkbox.getAttribute("data-path"),
  );

  // Send rename request to server
  fetch("/rename-folders", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      action: "add-suffix",
      paths: paths,
      suffix: trimmedSuffix,
    }),
  })
    .then((response) => response.json())
    .then((data) => {
      if (data.success) {
        showCopyMessage(
          `Added suffix "${trimmedSuffix}" to ${paths.length} folder${paths.length > 1 ? "s" : ""}`,
        );
        // Refresh the page to show updated folder names
        setTimeout(() => window.location.reload(), 1500);
      } else {
        alert("Failed to add suffix: " + data.error);
      }
    })
    .catch((err) => {
      console.error("Failed to add suffix: ", err);
      alert("Failed to add suffix. Please try again.");
    });
}

function copySelectedFoldernames() {
  const selectedCheckboxes = document.querySelectorAll(
    "input[data-path]:checked",
  );

  if (selectedCheckboxes.length === 0) {
    alert("Please select at least one game to copy folder names.");
    return;
  }

  const folderNames = Array.from(selectedCheckboxes).map((checkbox) => {
    const fullPath = checkbox.getAttribute("data-path");
    // Extract just the folder name (last part of the path)
    return fullPath.split("/").pop();
  });

  const folderNamesString = folderNames.join(" ");

  // Copy to clipboard with fallback
  copyToClipboard(folderNamesString)
    .then(() => {
      // Show temporary success message
      showCopyMessage(
        `Copied ${folderNames.length} folder name${folderNames.length > 1 ? "s" : ""} to clipboard`,
      );
    })
    .catch((err) => {
      console.error("Failed to copy folder names: ", err);
      // Fallback: show folder names in alert
      alert("Failed to copy to clipboard. Folder names:\n" + folderNamesString);
    });
}

function moveToSubfolder() {
  const selectedCheckboxes = document.querySelectorAll(
    "input[data-path]:checked",
  );

  if (selectedCheckboxes.length === 0) {
    alert("Please select at least one game to move to subfolder.");
    return;
  }

  // Create a minimally styled input prompt
  const subfolderName = prompt(
    "Enter subfolder name to move selected folders to:",
  );

  if (subfolderName === null || subfolderName.trim() === "") {
    return; // User cancelled or entered empty string
  }

  const trimmedSubfolderName = subfolderName.trim();
  const paths = Array.from(selectedCheckboxes).map((checkbox) =>
    checkbox.getAttribute("data-path"),
  );

  // Send move request to server
  fetch("/move-to-subfolder", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      paths: paths,
      subfolder: trimmedSubfolderName,
    }),
  })
    .then((response) => response.json())
    .then((data) => {
      if (data.success) {
        showCopyMessage(
          `Moved ${paths.length} folder${paths.length > 1 ? "s" : ""} to subfolder "${trimmedSubfolderName}"`,
        );
        // Refresh the page to show updated folder structure
        setTimeout(() => window.location.reload(), 1500);
      } else {
        alert("Failed to move folders: " + data.error);
      }
    })
    .catch((err) => {
      console.error("Failed to move folders: ", err);
      alert("Failed to move folders. Please try again.");
    });
}

// Move/Rename Dialog Variables (for picker page)
// Only define these if they don't already exist (app.js might have defined them)
if (typeof window.currentMovePath === "undefined") {
  window.currentMovePath = "";
}

if (typeof window.showMoveDialog === "undefined") {
  window.showMoveDialog = function (gamePath) {
    window.currentMovePath = gamePath;
    const dialog = document.getElementById("move-dialog");
    const input = document.getElementById("move-path-input");

    input.value = gamePath;
    dialog.style.display = "flex";

    // Focus and select the input text
    setTimeout(() => {
      input.focus();
      input.select();
    }, 100);
  };
}

if (typeof window.cancelMove === "undefined") {
  window.cancelMove = function () {
    const dialog = document.getElementById("move-dialog");
    dialog.style.display = "none";
    window.currentMovePath = "";
  };
}

if (typeof window.confirmMove === "undefined") {
  window.confirmMove = function () {
    const input = document.getElementById("move-path-input");
    const newPath = input.value.trim();

    if (!newPath) {
      alert("Please enter a valid path");
      return;
    }

    if (newPath === window.currentMovePath) {
      window.cancelMove();
      return;
    }

    // Send move request to server
    fetch("/move-folder", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        old_path: window.currentMovePath,
        new_path: newPath,
      }),
    })
      .then((response) => response.json())
      .then((data) => {
        if (data.success) {
          showCopyMessage(`Moved folder to: ${newPath}`);
          // Refresh the page to show updated folder structure
          setTimeout(() => window.location.reload(), 1500);
        } else {
          alert("Failed to move folder: " + data.error);
        }
      })
      .catch((err) => {
        console.error("Failed to move folder: ", err);
        alert("Failed to move folder. Please try again.");
      });

    window.cancelMove();
  };
}

// Close dialog on Escape key
document.addEventListener("keydown", function (event) {
  if (event.key === "Escape") {
    const dialog = document.getElementById("move-dialog");
    if (dialog.style.display === "flex") {
      cancelMove();
    }
  }
});

// Close dialog when clicking outside the dialog content
document
  .getElementById("move-dialog")
  .addEventListener("click", function (event) {
    if (event.target === this) {
      cancelMove();
    }
  });

// Initialize functionality on page load
document.addEventListener("DOMContentLoaded", function () {
  console.log("Game Picker initialized");
  console.log("Available keyboard shortcuts:");
  console.log("  Shift + Click: Range select checkboxes");
  console.log("  Escape: Close move dialog");
});
