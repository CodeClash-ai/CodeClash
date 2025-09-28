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

    // Handle move dialog shortcuts first
    const dialog = document.getElementById("move-dialog");
    if (dialog && dialog.style.display === "flex") {
      if (e.key === "Escape") {
        window.cancelMove();
        return;
      }
      if (e.key === "Enter") {
        window.confirmMove();
        return;
      }
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

// Move/Rename Dialog Variables (for main viewer page)
window.currentMovePath = "";

window.showMoveDialog = function (folderPath) {
  window.currentMovePath = folderPath;
  const dialog = document.getElementById("move-dialog");
  const input = document.getElementById("move-path-input");

  if (dialog && input) {
    input.value = folderPath;
    dialog.style.display = "flex";

    // Focus and select the input text
    setTimeout(() => {
      input.focus();
      input.select();
    }, 100);
  }
};

window.cancelMove = function () {
  const dialog = document.getElementById("move-dialog");
  if (dialog) {
    dialog.style.display = "none";
  }
  window.currentMovePath = "";
};

window.confirmMove = function () {
  const input = document.getElementById("move-path-input");
  if (!input) return;

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
        alert(`Moved folder to: ${newPath}`);
        // Redirect to the new path
        window.location.href = `/?folder=${encodeURIComponent(newPath)}`;
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

// Move dialog keyboard shortcuts are now handled in the main keyboard handler
