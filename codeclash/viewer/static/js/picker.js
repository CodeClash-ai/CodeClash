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
  // Handle different types of clicks
  if (event.button === 1 || event.ctrlKey || event.metaKey) {
    // Middle click, Ctrl+click, or Cmd+click - open in new tab
    event.preventDefault();
    openGameInNewTab(gameName);
  } else if (event.button === 0) {
    // Left click - open in same tab
    openGame(gameName);
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

// Initialize theme and other functionality on page load
document.addEventListener("DOMContentLoaded", function () {
  initializeTheme();

  console.log("Game Picker initialized");
  console.log("Available keyboard shortcuts:");
  console.log("  Ctrl/Cmd + D: Toggle dark mode");
});
