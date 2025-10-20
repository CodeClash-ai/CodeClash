// CodeClash Trajectory Viewer - JavaScript Controls

// Game picker
function openGamePicker() {
  const isStatic = document.body.hasAttribute("data-static-mode");
  const url = isStatic ? "/picker.html" : "/picker";
  window.location.href = url;
}

function openGamePickerInNewTab() {
  const isStatic = document.body.hasAttribute("data-static-mode");
  const url = isStatic ? "/picker.html" : "/picker";
  window.open(url, "_blank");
}

// Game navigation
function navigateToGame(gameName) {
  if (!gameName) return;

  const isStatic = document.body.hasAttribute("data-static-mode");
  const url = isStatic
    ? `/game/${gameName}.html`
    : `/?folder=${encodeURIComponent(gameName)}`;
  window.location.href = url;
}

function navigateToPreviousGame() {
  const prevBtn = document.getElementById("prev-game-btn");
  if (prevBtn && !prevBtn.disabled) {
    prevBtn.click();
  }
}

function navigateToNextGame() {
  const nextBtn = document.getElementById("next-game-btn");
  if (nextBtn && !nextBtn.disabled) {
    nextBtn.click();
  }
}

// Help modal functionality
function showHelpModal() {
  const helpModal = new bootstrap.Modal(document.getElementById("help-modal"));
  helpModal.show();
}

function handlePickerClick(event) {
  // Handle different types of clicks for picker button
  if (event.button === 1 || event.ctrlKey || event.metaKey) {
    // Middle click, Ctrl+click, or Cmd+click - open in new tab
    event.preventDefault();
    openGamePickerInNewTab();
  } else if (event.button === 0) {
    // Left click - open in same tab
    openGamePicker();
  }
}

// Enhanced foldout behavior
function initializeFoldouts() {
  // Add smooth animations to details elements
  const detailsElements = document.querySelectorAll("details");

  detailsElements.forEach((details) => {
    const summary = details.querySelector("summary");

    // Add click analytics/feedback
    summary.addEventListener("click", function (e) {
      // Small delay to allow default behavior
      setTimeout(() => {
        // Scroll into view if needed
        if (details.open) {
          const rect = details.getBoundingClientRect();
          const isInViewport =
            rect.top >= 0 && rect.bottom <= window.innerHeight;

          if (!isInViewport) {
            details.scrollIntoView({
              behavior: "smooth",
              block: "nearest",
            });
          }
        }
      }, 100);
    });
  });
}

// Keyboard shortcuts
function initializeKeyboardShortcuts() {
  document.addEventListener("keydown", function (e) {
    // Don't trigger shortcuts if user is typing in an input field
    if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") {
      return;
    }

    // h or Left Arrow: Navigate to previous game
    if (e.key === "h" || e.key === "ArrowLeft") {
      e.preventDefault();
      navigateToPreviousGame();
      return;
    }

    // l or Right Arrow: Navigate to next game
    if (e.key === "l" || e.key === "ArrowRight") {
      e.preventDefault();
      navigateToNextGame();
      return;
    }

    // p: Open game picker in same tab, P: Open game picker in new tab
    if (e.key === "p") {
      e.preventDefault();
      openGamePicker();
      return;
    }

    if (e.key === "P") {
      e.preventDefault();
      openGamePickerInNewTab();
      return;
    }

    // t/T: Toggle TOC menu visibility
    if (e.key === "t" || e.key === "T") {
      e.preventDefault();
      toggleTocMenu();
      return;
    }

    // ?: Show help modal
    if (e.key === "?") {
      e.preventDefault();
      showHelpModal();
      return;
    }

    // Escape: Close all open details
    if (e.key === "Escape") {
      const openDetails = document.querySelectorAll("details[open]");
      openDetails.forEach((details) => {
        details.removeAttribute("open");
      });
      return;
    }

    // Ctrl/Cmd + E: Expand all details
    if ((e.ctrlKey || e.metaKey) && e.key === "e") {
      e.preventDefault();
      const allDetails = document.querySelectorAll("details");
      allDetails.forEach((details) => {
        details.setAttribute("open", "");
      });
      return;
    }

    // Ctrl/Cmd + Shift + E: Collapse all details
    if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === "E") {
      e.preventDefault();
      const allDetails = document.querySelectorAll("details");
      allDetails.forEach((details) => {
        details.removeAttribute("open");
      });
      return;
    }
  });
}

// Code highlighting removed to prevent CSS code from appearing in text

// Performance monitoring
function initializePerformanceMonitoring() {
  // Log page load time
  window.addEventListener("load", function () {
    const loadTime = performance.now();
    console.log(`Page loaded in ${loadTime.toFixed(2)}ms`);

    // Count elements for performance insight
    const messageCount = document.querySelectorAll(".message-block").length;
    const foldoutCount = document.querySelectorAll("details").length;

    console.log(
      `Rendered ${messageCount} messages and ${foldoutCount} foldouts`,
    );
  });
}

// Message expand/collapse functionality
function expandMessage(clickedElement) {
  const messageContent = clickedElement.closest(".message-content");
  const previewShort = messageContent.querySelector(".message-preview-short");
  const contentFull = messageContent.querySelector(".message-content-full");
  const contentExpanded = messageContent.querySelector(
    ".message-content-expanded",
  );

  // Expanding - hide preview, show full content
  if (previewShort) previewShort.style.display = "none";
  if (contentFull) contentFull.style.display = "block";
  if (contentExpanded) contentExpanded.style.display = "block";

  // Smooth scroll to keep the content in view
  setTimeout(() => {
    messageContent.scrollIntoView({
      behavior: "smooth",
      block: "nearest",
    });
  }, 100);
}

function collapseMessage(clickedElement) {
  const messageContent = clickedElement.closest(".message-content");
  const previewShort = messageContent.querySelector(".message-preview-short");
  const contentFull = messageContent.querySelector(".message-content-full");
  const contentExpanded = messageContent.querySelector(
    ".message-content-expanded",
  );

  // Collapsing - show preview, hide full content
  if (contentFull) contentFull.style.display = "none";
  if (contentExpanded) contentExpanded.style.display = "none";
  if (previewShort) previewShort.style.display = "block";

  // Smooth scroll to keep the content in view
  setTimeout(() => {
    messageContent.scrollIntoView({
      behavior: "smooth",
      block: "nearest",
    });
  }, 100);
}

function collapseTrajectoryMessages(clickedElement) {
  // Find the parent trajectory messages foldout
  const trajectoryFoldout = clickedElement.closest(
    ".trajectory-messages-foldout",
  );

  if (trajectoryFoldout) {
    // Close the details element
    trajectoryFoldout.removeAttribute("open");

    // Smooth scroll to the trajectory header
    setTimeout(() => {
      const trajectoryHeader = trajectoryFoldout.closest(".trajectory-header");
      if (trajectoryHeader) {
        trajectoryHeader.scrollIntoView({
          behavior: "smooth",
          block: "nearest",
        });
      }
    }, 100);
  }
}

// Round navigation functionality
function scrollToRound(roundNum) {
  const roundAnchor = document.getElementById(`round-${roundNum}`);
  if (roundAnchor) {
    // Smooth scroll to the round section
    roundAnchor.scrollIntoView({
      behavior: "smooth",
      block: "start",
    });

    // Close TOC menu after navigation (optional - user can keep it open)
    // closeTocMenu();
  } else {
    console.warn(`Round ${roundNum} anchor not found`);
  }
}

// Scroll to top functionality
function scrollToTop() {
  window.scrollTo({
    top: 0,
    behavior: "smooth",
  });
  // closeTocMenu(); // Keep TOC open after scrolling to top
}

// Scroll to element functionality
function scrollToElement(selector) {
  const element = document.querySelector(selector);
  if (element) {
    element.scrollIntoView({
      behavior: "smooth",
      block: "start",
    });
    // closeTocMenu(); // Keep TOC open after navigation
  }
}

// Floating Table of Contents functionality
function initializeFloatingToc() {
  const tocMenu = document.getElementById("toc-menu");
  const tocClose = document.getElementById("toc-close");

  if (!tocMenu || !tocClose) {
    return;
  }

  // Close TOC menu
  tocClose.addEventListener("click", function (e) {
    e.stopPropagation();
    closeTocMenu();
  });

  // Prevent menu from closing when clicking inside
  tocMenu.addEventListener("click", function (e) {
    e.stopPropagation();
  });

  // TOC keyboard shortcuts are now handled in the main keyboard handler
}

function toggleTocMenu() {
  const tocMenu = document.getElementById("toc-menu");
  if (tocMenu) {
    tocMenu.classList.toggle("hidden");
  }
}

function closeTocMenu() {
  const tocMenu = document.getElementById("toc-menu");
  if (tocMenu) {
    tocMenu.classList.add("hidden");
  }
}

// Log loading functionality
function loadLogContent(logPath, container) {
  const placeholder = container.querySelector(".log-load-placeholder");
  const spinner = container.querySelector(".log-loading-spinner");
  const contentPre = container.querySelector(".log-content-scrollable");
  const contentCode = container.querySelector(".log-content");

  // Hide placeholder, show spinner
  placeholder.style.display = "none";
  spinner.style.display = "block";

  // Fetch log content from server
  fetch(`/load-log?path=${encodeURIComponent(logPath)}`)
    .then((response) => response.json())
    .then((data) => {
      spinner.style.display = "none";

      if (data.success) {
        // Display the content
        contentCode.textContent = data.content;
        contentPre.style.display = "block";
      } else {
        // Show error message
        contentCode.textContent = `Error loading log: ${data.error}`;
        contentPre.style.display = "block";
      }
    })
    .catch((error) => {
      spinner.style.display = "none";
      contentCode.textContent = `Error loading log: ${error}`;
      contentPre.style.display = "block";
    });
}

// Trajectory diffs loading functionality
function loadTrajectoryDiffs(playerName, roundNum, button) {
  const container = button.closest(".trajectory-content");

  // Find the specific placeholder that contains this button
  const placeholder = button.closest(
    ".diff-load-placeholder, .incremental-diff-load-placeholder, .modified-files-load-placeholder",
  );

  // Try to find trajectory header
  let trajectoryHeader = button.closest(".trajectory-header");

  // If not found, try looking up from container
  if (!trajectoryHeader && container) {
    trajectoryHeader = container.closest(".trajectory-header");
  }

  // If still not found, look for parent details element and then its parent
  if (!trajectoryHeader) {
    const detailsElement = button.closest("details");
    if (detailsElement) {
      trajectoryHeader = detailsElement.parentElement;
    }
  }

  // Get selected folder from page
  const selectedFolder =
    document.body.getAttribute("data-folder") ||
    new URLSearchParams(window.location.search).get("folder");

  if (!selectedFolder) {
    alert("Error: Could not determine selected folder");
    return;
  }

  // Hide placeholder and show loading
  if (placeholder) {
    placeholder.style.display = "none";
  }

  if (container) {
    container.innerHTML =
      '<div style="padding: 2rem; text-align: center;">Loading...</div>';
  }

  // Store trajectoryHeader in the outer scope to use in the fetch handler
  const finalTrajectoryHeader = trajectoryHeader;

  // Fetch diff data from server
  fetch(
    `/load-trajectory-diffs?folder=${encodeURIComponent(selectedFolder)}&player=${encodeURIComponent(playerName)}&round=${roundNum}`,
  )
    .then((response) => response.json())
    .then((data) => {
      if (data.success) {
        if (finalTrajectoryHeader) {
          // 1. Populate main diff section
          const diffContainer = finalTrajectoryHeader.querySelector(
            ".trajectory-diffs-foldout .trajectory-content",
          );
          if (diffContainer) {
            let html = "";
            if (
              data.diff_by_files &&
              Object.keys(data.diff_by_files).length > 0
            ) {
              html += `<div class="log-content">`;
              for (const [filePath, fileDiff] of Object.entries(
                data.diff_by_files,
              )) {
                html += `
                  <details class="foldout">
                    <summary>${escapeHtml(filePath)}</summary>
                    <div class="log-content">
                      <pre><code>${escapeHtml(fileDiff)}</code></pre>
                    </div>
                  </details>
                `;
              }
              html += `</div>`;
            } else if (data.diff && data.diff.trim()) {
              html += `<div class="log-content"><pre><code>${escapeHtml(data.diff)}</code></pre></div>`;
            } else {
              html += `<p>No diff data available</p>`;
            }
            diffContainer.innerHTML = html;
          }

          // 2. Populate incremental diff section
          const incrementalDiffContainer = finalTrajectoryHeader.querySelector(
            ".trajectory-incremental-diffs-foldout .trajectory-content",
          );
          if (incrementalDiffContainer) {
            let html = "";
            if (
              data.incremental_diff_by_files &&
              Object.keys(data.incremental_diff_by_files).length > 0
            ) {
              html += `<div class="log-content">`;
              for (const [filePath, fileDiff] of Object.entries(
                data.incremental_diff_by_files,
              )) {
                html += `
                  <details class="foldout">
                    <summary>${escapeHtml(filePath)}</summary>
                    <div class="log-content">
                      <pre><code>${escapeHtml(fileDiff)}</code></pre>
                    </div>
                  </details>
                `;
              }
              html += `</div>`;
            } else if (data.incremental_diff && data.incremental_diff.trim()) {
              html += `<div class="log-content"><pre><code>${escapeHtml(data.incremental_diff)}</code></pre></div>`;
            } else {
              html += `<p>No incremental diff data available</p>`;
            }
            incrementalDiffContainer.innerHTML = html;
          }

          // 3. Populate modified files section
          const modifiedFilesContainer = finalTrajectoryHeader.querySelector(
            ".trajectory-modified-files-foldout .trajectory-content",
          );
          if (modifiedFilesContainer) {
            let html = "";
            if (
              data.modified_files &&
              Object.keys(data.modified_files).length > 0
            ) {
              html += `<div class="log-content">`;
              for (const [filePath, fileContent] of Object.entries(
                data.modified_files,
              )) {
                html += `
                  <details class="foldout">
                    <summary>${escapeHtml(filePath)}</summary>
                    <div class="log-content">
                      <pre><code>${escapeHtml(fileContent)}</code></pre>
                    </div>
                  </details>
                `;
              }
              html += `</div>`;
            } else {
              html += `<p>No modified files data available</p>`;
            }
            modifiedFilesContainer.innerHTML = html;
          }
        } else {
          container.innerHTML = `<p>Error: Could not find trajectory header</p>`;
        }
      } else {
        container.innerHTML = `<p>Error loading diffs: ${data.error}</p>`;
      }
    })
    .catch((error) => {
      if (container) {
        container.innerHTML = `<p>Error loading diffs: ${error}</p>`;
      }
    });
}

// Line counting analysis loading functionality
function loadLineCountingAnalysis(button) {
  const container = button.closest(".log-content-container");

  if (!container) {
    alert("Error: Could not find container");
    return;
  }

  const placeholder = container.querySelector(".analysis-load-placeholder");
  const spinner = container.querySelector(".analysis-loading-spinner");
  const analysisContent = container.querySelector(".analysis-content");

  // Get selected folder from page
  const selectedFolder =
    document.body.getAttribute("data-folder") ||
    new URLSearchParams(window.location.search).get("folder");

  if (!selectedFolder) {
    alert("Error: Could not determine selected folder");
    return;
  }

  if (!placeholder || !spinner || !analysisContent) {
    alert("Error: Missing UI elements for analysis loading");
    return;
  }

  // Hide placeholder, show spinner
  placeholder.style.display = "none";
  spinner.style.display = "block";

  // Fetch analysis data from server
  fetch(`/analysis/line-counts?folder=${encodeURIComponent(selectedFolder)}`)
    .then((response) => response.json())
    .then((result) => {
      spinner.style.display = "none";

      if (result.success && result.data) {
        const data = result.data;

        // Populate file dropdown
        const fileDropdown = analysisContent.querySelector("#file-dropdown");
        if (fileDropdown && data.all_files) {
          fileDropdown.innerHTML = "";
          data.all_files.forEach((filePath) => {
            const option = document.createElement("option");
            option.value = filePath;
            option.textContent = filePath;
            fileDropdown.appendChild(option);
          });
        }

        // Store data in the script tag for the analysis.js to use
        const analysisDataScript =
          analysisContent.querySelector("#analysis-data");
        if (analysisDataScript) {
          analysisDataScript.textContent = JSON.stringify(data);
        }

        // Show the analysis content
        analysisContent.style.display = "block";

        // Trigger the chart rendering (analysis.js should listen for this)
        if (typeof window.renderLineCountChart === "function") {
          window.renderLineCountChart(data);
        } else {
          // If analysis.js hasn't loaded the function yet, dispatch an event
          const event = new CustomEvent("analysisDataLoaded", {
            detail: data,
          });
          document.dispatchEvent(event);
        }
      } else {
        analysisContent.innerHTML = `<p>Error loading analysis: ${result.error || "Unknown error"}</p>`;
        analysisContent.style.display = "block";
      }
    })
    .catch((error) => {
      spinner.style.display = "none";
      analysisContent.innerHTML = `<p>Error loading analysis: ${error}</p>`;
      analysisContent.style.display = "block";
    });
}

// Helper function to escape HTML
function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

// Setup button event listeners
function setupButtonEventListeners() {
  // Pick game button
  const pickGameBtn = document.getElementById("pick-game-btn");
  if (pickGameBtn) {
    pickGameBtn.addEventListener("mousedown", handlePickerClick);
  }

  // Pick game new tab button
  const pickGameNewTabBtn = document.getElementById("pick-game-new-tab-btn");
  if (pickGameNewTabBtn) {
    pickGameNewTabBtn.addEventListener("click", openGamePickerInNewTab);
  }

  // Help button
  const helpBtn = document.getElementById("help-btn");
  if (helpBtn) {
    helpBtn.addEventListener("click", showHelpModal);
  }

  // Delete experiment button
  const deleteBtn = document.querySelector(".delete-experiment-btn");
  if (deleteBtn) {
    deleteBtn.addEventListener("click", function () {
      const folderPath = this.getAttribute("data-folder-path");
      if (folderPath) {
        deleteExperiment(folderPath);
      }
    });
  }

  // Round navigation buttons
  document.querySelectorAll(".nav-to-round-btn").forEach((button) => {
    button.addEventListener("click", function () {
      const roundNum = this.getAttribute("data-round");
      if (roundNum) {
        scrollToRound(parseInt(roundNum));
      }
    });
  });

  // Message expand/collapse buttons
  document.querySelectorAll(".clickable-message").forEach((element) => {
    element.addEventListener("click", function () {
      if (this.classList.contains("message-preview-short")) {
        expandMessage(this);
      } else if (this.classList.contains("collapse-indicator")) {
        collapseMessage(this);
      }
    });
  });

  // Collapse trajectory messages buttons
  document.querySelectorAll(".btn-collapse-messages").forEach((button) => {
    button.addEventListener("click", function () {
      collapseTrajectoryMessages(this);
    });
  });

  // Log loading buttons
  document.querySelectorAll(".load-log-btn").forEach((button) => {
    button.addEventListener("click", function () {
      const logPath = this.getAttribute("data-log-path");
      const container = this.closest(".log-content-container");
      if (logPath && container) {
        loadLogContent(logPath, container);
      }
    });
  });

  // Trajectory diff loading buttons
  document.querySelectorAll(".load-diffs-btn").forEach((button) => {
    button.addEventListener("click", function () {
      const playerName = this.getAttribute("data-player");
      const roundNum = this.getAttribute("data-round");
      if (playerName && roundNum) {
        loadTrajectoryDiffs(playerName, roundNum, this);
      }
    });
  });

  // Analysis loading button
  document.querySelectorAll(".load-analysis-btn").forEach((button) => {
    button.addEventListener("click", function () {
      loadLineCountingAnalysis(this);
    });
  });
}

// Initialize everything when DOM is loaded
document.addEventListener("DOMContentLoaded", function () {
  initializeFoldouts();
  initializeKeyboardShortcuts();
  initializePerformanceMonitoring();
  initializeFloatingToc();
  setupButtonEventListeners();

  console.log("CodeClash Trajectory Viewer initialized");
  console.log("Keyboard shortcuts:");
  console.log("  h or ←: Navigate to previous game");
  console.log("  l or →: Navigate to next game");
  console.log("  p: Open game picker (same tab)");
  console.log("  P: Open game picker (new tab)");
  console.log("  t: Toggle floating table of contents");
  console.log("  Ctrl/Cmd + E: Expand all sections");
  console.log("  Ctrl/Cmd + Shift + E: Collapse all sections");
  console.log("  Escape: Close all sections");
  console.log("Mouse shortcuts:");
  console.log("  Middle-click or Ctrl+click: Open in new tab");
});
