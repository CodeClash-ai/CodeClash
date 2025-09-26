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

// Setup copy button event listeners
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

  // Add event listeners to AWS command copy buttons
  document.querySelectorAll(".copy-aws-command-btn").forEach((button) => {
    button.addEventListener("click", function (e) {
      e.preventDefault();
      e.stopPropagation();

      // Get the AWS command from the code element next to this button
      const codeElement = this.parentElement.querySelector(".folder-path");
      if (codeElement) {
        const command = codeElement.textContent.trim();
        copyToClipboard(command, this);
      } else {
        console.error("No AWS command found near button:", this);
      }
    });
  });
}
