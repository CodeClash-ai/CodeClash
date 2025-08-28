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

// Folder selection
function changeFolder() {
  const select = document.getElementById("folder-select");
  const selectedFolder = select.value;

  if (selectedFolder) {
    // Reload page with new folder parameter
    const url = new URL(window.location);
    url.searchParams.set("folder", selectedFolder);
    window.location.href = url.toString();
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

// Code highlighting (basic syntax highlighting)
function initializeCodeHighlighting() {
  const codeBlocks = document.querySelectorAll(
    ".code-block code, .message-text pre",
  );

  codeBlocks.forEach((block) => {
    const text = block.textContent;

    // Simple bash highlighting
    if (text.includes("#!/bin/bash") || text.includes("```bash")) {
      block.classList.add("language-bash");
      highlightBash(block);
    }

    // Simple Python highlighting
    if (
      text.includes("def ") ||
      text.includes("import ") ||
      text.includes("python")
    ) {
      block.classList.add("language-python");
      highlightPython(block);
    }
  });
}

function highlightBash(block) {
  let html = block.innerHTML;

  // Commands
  html = html.replace(
    /\b(ls|cd|cat|grep|sed|awk|find|mkdir|rm|cp|mv|chmod|echo|export)\b/g,
    '<span style="color: var(--accent-color); font-weight: 600;">$1</span>',
  );

  // Flags
  html = html.replace(
    /\s(-[a-zA-Z]+)/g,
    ' <span style="color: var(--warning-color);">$1</span>',
  );

  block.innerHTML = html;
}

function highlightPython(block) {
  let html = block.innerHTML;

  // Keywords
  html = html.replace(
    /\b(def|class|import|from|if|else|elif|for|while|try|except|finally|return|yield|with|as|pass|break|continue|lambda|global|nonlocal)\b/g,
    '<span style="color: var(--accent-color); font-weight: 600;">$1</span>',
  );

  // Strings
  html = html.replace(
    /(["'])((?:\\.|(?!\1)[^\\])*?)\1/g,
    '<span style="color: var(--success-color);">$1$2$1</span>',
  );

  block.innerHTML = html;
}

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

// Initialize everything when DOM is loaded
document.addEventListener("DOMContentLoaded", function () {
  initializeTheme();
  initializeFoldouts();
  initializeKeyboardShortcuts();
  initializeCodeHighlighting();
  initializePerformanceMonitoring();

  console.log("CodeClash Trajectory Viewer initialized");
  console.log("Keyboard shortcuts:");
  console.log("  Ctrl/Cmd + D: Toggle dark mode");
  console.log("  Ctrl/Cmd + E: Expand all sections");
  console.log("  Ctrl/Cmd + Shift + E: Collapse all sections");
  console.log("  Escape: Close all sections");
});
