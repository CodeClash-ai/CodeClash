// Clipboard functionality for CodeClash Trajectory Viewer

// Copy to clipboard function
function copyToClipboard(text, button) {
  function showSuccessMessage() {
    if (button) {
      const originalText = button.textContent;
      const originalColor = button.style.color;
      button.textContent = "✓ Copied";
      button.style.color = "green";
      setTimeout(() => {
        button.textContent = originalText;
        button.style.color = originalColor;
      }, 1500);
    }
  }

  // Check if modern clipboard API is available
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard
      .writeText(text)
      .then(function () {
        showSuccessMessage();
        console.log("Copied to clipboard:", text);
      })
      .catch(function (err) {
        console.error("Failed to copy text with clipboard API: ", err);
        // Fall back to legacy method
        fallbackCopy();
      });
  } else {
    // Use fallback method directly
    fallbackCopy();
  }

  function fallbackCopy() {
    try {
      const textArea = document.createElement("textarea");
      textArea.value = text;
      textArea.style.position = "fixed";
      textArea.style.left = "-9999px";
      textArea.style.top = "-9999px";
      document.body.appendChild(textArea);
      textArea.focus();
      textArea.select();

      const successful = document.execCommand("copy");
      document.body.removeChild(textArea);

      if (successful) {
        showSuccessMessage();
        console.log("Copied to clipboard (fallback):", text);
      } else {
        console.error("Failed to copy text with fallback method");
        if (button) {
          button.textContent = "✗ Failed";
          button.style.color = "red";
          setTimeout(() => {
            button.textContent = button.getAttribute("title") || "Copy";
            button.style.color = "";
          }, 1500);
        }
      }
    } catch (err) {
      console.error("Fallback copy failed:", err);
      if (button) {
        button.textContent = "✗ Failed";
        button.style.color = "red";
        setTimeout(() => {
          button.textContent = button.getAttribute("title") || "Copy";
          button.style.color = "";
        }, 1500);
      }
    }
  }
}

// Download file function
function downloadFile(filePath, button) {
  function showSuccessMessage() {
    if (button) {
      const originalText = button.textContent;
      const originalColor = button.style.color;
      button.textContent = "✓ Downloading";
      button.style.color = "green";
      setTimeout(() => {
        button.textContent = originalText;
        button.style.color = originalColor;
      }, 1500);
    }
  }

  function showErrorMessage() {
    if (button) {
      const originalText = button.textContent;
      const originalColor = button.style.color;
      button.textContent = "✗ Failed";
      button.style.color = "red";
      setTimeout(() => {
        button.textContent = originalText;
        button.style.color = originalColor;
      }, 1500);
    }
  }

  try {
    // Create a temporary link element to trigger download
    const downloadUrl = `/download-file?path=${encodeURIComponent(filePath)}`;
    const link = document.createElement("a");
    link.href = downloadUrl;
    link.style.display = "none";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    showSuccessMessage();
    console.log("Downloading file:", filePath);
  } catch (err) {
    console.error("Failed to download file:", err);
    showErrorMessage();
  }
}

// Setup copy and download button event listeners
function setupCopyButtons() {
  // Add event listeners to all copy path buttons
  document
    .querySelectorAll(".copy-path-btn, .copy-path-btn-small")
    .forEach((button) => {
      button.addEventListener("click", function (e) {
        e.preventDefault();
        e.stopPropagation();

        const path = this.getAttribute("data-path");
        if (path) {
          copyToClipboard(path, this);
        } else {
          console.error("No path found on button:", this);
        }
      });
    });
}

// Setup download button event listeners
function setupDownloadButtons() {
  // Add event listeners to all download buttons
  document
    .querySelectorAll(".download-btn, .download-btn-small")
    .forEach((button) => {
      button.addEventListener("click", function (e) {
        e.preventDefault();
        e.stopPropagation();

        const path = this.getAttribute("data-path");
        if (path) {
          downloadFile(path, this);
        } else {
          console.error("No path found on download button:", this);
        }
      });
    });
}
