// CodeClash Trajectory Viewer - JavaScript Controls

// Theme management
function initializeTheme() {
  // Check for saved theme preference or default to 'light'
  const savedTheme = localStorage.getItem("theme") || "light";
  setTheme(savedTheme);
}

function setTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  localStorage.setItem("theme", theme);

  // Update theme toggle button
  const themeToggle = document.getElementById("theme-toggle");
  const themeIcon = themeToggle.querySelector(".theme-icon");

  if (theme === "dark") {
    themeIcon.textContent = "☀️";
    themeToggle.setAttribute("aria-label", "Switch to light mode");
  } else {
    themeIcon.textContent = "🌙";
    themeToggle.setAttribute("aria-label", "Switch to dark mode");
  }
}

function toggleTheme() {
  const currentTheme = document.documentElement.getAttribute("data-theme");
  const newTheme = currentTheme === "dark" ? "light" : "dark";
  setTheme(newTheme);
}

// Game picker
function openGamePicker() {
  window.location.href = "/picker";
}

function openGamePickerInNewTab() {
  window.open("/picker", "_blank");
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
    // p: Open game picker in same tab, P: Open game picker in new tab
    if (e.key === "p") {
      // Don't trigger if user is typing in an input field
      if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") {
        return;
      }
      e.preventDefault();
      openGamePicker();
    }

    if (e.key === "P") {
      // Don't trigger if user is typing in an input field
      if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") {
        return;
      }
      e.preventDefault();
      openGamePickerInNewTab();
    }

    // Ctrl/Cmd + D: Toggle dark mode
    if ((e.ctrlKey || e.metaKey) && e.key === "d") {
      e.preventDefault();
      toggleTheme();
    }

    // Escape: Close all open details
    if (e.key === "Escape") {
      const openDetails = document.querySelectorAll("details[open]");
      openDetails.forEach((details) => {
        details.removeAttribute("open");
      });
    }

    // Ctrl/Cmd + E: Expand all details
    if ((e.ctrlKey || e.metaKey) && e.key === "e") {
      e.preventDefault();
      const allDetails = document.querySelectorAll("details");
      allDetails.forEach((details) => {
        details.setAttribute("open", "");
      });
    }

    // Ctrl/Cmd + Shift + E: Collapse all details
    if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === "E") {
      e.preventDefault();
      const allDetails = document.querySelectorAll("details");
      allDetails.forEach((details) => {
        details.removeAttribute("open");
      });
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

    // Add a brief highlight effect
    const roundSection = roundAnchor.nextElementSibling;
    if (roundSection) {
      roundSection.classList.add("highlight-round");
      setTimeout(() => {
        roundSection.classList.remove("highlight-round");
      }, 2000);
    }
  } else {
    console.warn(`Round ${roundNum} anchor not found`);
  }
}

// Initialize everything when DOM is loaded
document.addEventListener("DOMContentLoaded", function () {
  initializeTheme();
  initializeFoldouts();
  initializeKeyboardShortcuts();
  initializePerformanceMonitoring();

  console.log("CodeClash Trajectory Viewer initialized");
  console.log("Keyboard shortcuts:");
  console.log("  p: Open game picker (same tab)");
  console.log("  P: Open game picker (new tab)");
  console.log("  Ctrl/Cmd + D: Toggle dark mode");
  console.log("  Ctrl/Cmd + E: Expand all sections");
  console.log("  Ctrl/Cmd + Shift + E: Collapse all sections");
  console.log("  Escape: Close all sections");
  console.log("Mouse shortcuts:");
  console.log("  Middle-click or Ctrl+click: Open in new tab");
});
