// Trajectory on-demand loading functionality for CodeClash Trajectory Viewer

function setupTrajectoryLoading() {
  // Handle load trajectory button clicks
  document.addEventListener("click", function (e) {
    if (e.target.closest(".load-trajectory-btn")) {
      const button = e.target.closest(".load-trajectory-btn");
      const playerName = button.dataset.player;
      const roundNum = button.dataset.round;

      loadTrajectoryDetails(playerName, roundNum);
    }
  });
}

function loadTrajectoryDetails(playerName, roundNum) {
  // Get the folder from URL params
  const urlParams = new URLSearchParams(window.location.search);
  const folder = urlParams.get("folder");

  if (!folder) {
    console.error("No folder parameter in URL");
    return;
  }

  // Find the trajectory foldout container
  const foldout = document.querySelector(
    `.trajectory-details-foldout[data-player="${playerName}"][data-round="${roundNum}"]`,
  );

  if (!foldout) {
    console.error("Trajectory foldout not found");
    return;
  }

  // Show loading spinner, hide placeholder
  const placeholder = foldout.querySelector(".trajectory-load-placeholder");
  const spinner = foldout.querySelector(".trajectory-loading-spinner");
  const content = foldout.querySelector(".trajectory-details-content");

  placeholder.style.display = "none";
  spinner.style.display = "flex";

  // Fetch trajectory details
  fetch(
    `/load-trajectory-details?folder=${encodeURIComponent(
      folder,
    )}&player=${encodeURIComponent(playerName)}&round=${encodeURIComponent(
      roundNum,
    )}`,
  )
    .then((response) => response.json())
    .then((data) => {
      if (data.success) {
        // Populate the messages
        renderMessages(
          foldout,
          data.messages,
          playerName,
          roundNum,
          data.trajectory_file_path,
        );

        // Hide spinner, show content
        spinner.style.display = "none";
        content.style.display = "block";
      } else {
        console.error("Error loading trajectory:", data.error);
        spinner.innerHTML = `<div class="alert alert-danger">Error: ${data.error}</div>`;
      }
    })
    .catch((error) => {
      console.error("Error loading trajectory:", error);
      spinner.innerHTML = `<div class="alert alert-danger">Error loading trajectory data</div>`;
    });
}

function renderMessages(
  foldout,
  messages,
  playerName,
  roundNum,
  trajectoryFilePath,
) {
  const messagesContainer = foldout.querySelector(".messages-container");
  const headerInfo = foldout.querySelector(".trajectory-header-info");

  // Clear existing content
  messagesContainer.innerHTML = "";

  // Add header info with file path and buttons
  if (trajectoryFilePath) {
    headerInfo.innerHTML = `
      <div style="display: flex; gap: 0.5rem; align-items: center;">
        <span style="color: var(--muted-text);">${messages.length} messages</span>
        <button class="copy-path-btn-small" data-path="${trajectoryFilePath}" title="Copy trajectory file path">
          <i class="bi bi-clipboard"></i> Copy path
        </button>
        <button class="download-btn-small" data-path="${trajectoryFilePath}" title="Download trajectory file">
          <i class="bi bi-download"></i> Download
        </button>
      </div>
    `;

    // Re-setup copy and download buttons for these new buttons
    setupCopyButtons();
    setupDownloadButtons();
  } else {
    headerInfo.innerHTML = `<span style="color: var(--muted-text);">${messages.length} messages</span>`;
  }

  // Render each message
  messages.forEach((message, index) => {
    const messageBlock = createMessageElement(message, index + 1);
    messagesContainer.appendChild(messageBlock);
  });
}

function createMessageElement(message, index) {
  const messageBlock = document.createElement("div");
  messageBlock.className = `message-block ${message.role}`;

  const roleBadge = document.createElement("span");
  roleBadge.className = "message-role-badge";
  roleBadge.textContent =
    message.role.charAt(0).toUpperCase() + message.role.slice(1) + " #" + index;

  const messageContent = document.createElement("div");
  messageContent.className = "message-content";

  // Handle different content types.
  // mini-swe-agent v2 (tool-call) assistant messages keep the command in
  // extra.actions / tool_calls instead of in a ```bash block in the text, so they need
  // their own renderer. v1 messages have neither and fall through to the text paths below.
  const toolActions =
    message.extra && Array.isArray(message.extra.actions)
      ? message.extra.actions
      : [];
  const hasToolCalls =
    Array.isArray(message.tool_calls) && message.tool_calls.length > 0;
  if (toolActions.length > 0 || hasToolCalls) {
    messageContent.innerHTML = createToolCallContentHTML(message);
  } else if (typeof message.content === "string") {
    const lines = message.content.split("\n");
    if (lines.length <= 5) {
      // Show full content
      messageContent.innerHTML = createFullContentHTML(
        message.content,
        message.role,
      );
    } else {
      // Show preview with expand
      messageContent.innerHTML = createPreviewContentHTML(
        message.content,
        lines,
        message.role,
      );
    }
  } else if (Array.isArray(message.content)) {
    // Handle complex content (e.g., user messages with multiple parts)
    messageContent.innerHTML = createComplexContentHTML(message.content);
  } else {
    // Fallback
    messageContent.innerHTML = `<div class="message-content-full"><div class="message-text"><pre>${JSON.stringify(
      message.content,
      null,
      2,
    )}</pre></div></div>`;
  }

  messageBlock.appendChild(roleBadge);
  messageBlock.appendChild(messageContent);

  return messageBlock;
}

function createFullContentHTML(content, role) {
  if (role === "assistant" && content.includes("```")) {
    // Special handling for code blocks
    const parts = content.split("```");
    let html = '<div class="message-content-full">';
    parts.forEach((part, i) => {
      if (i % 2 === 0) {
        html += `<div class="message-text"><pre>${escapeHtml(
          part,
        )}</pre></div>`;
      } else {
        html += `<div class="code-block"><pre><code>${escapeHtml(
          part,
        )}</code></pre></div>`;
      }
    });
    html += "</div>";
    return html;
  } else {
    return `<div class="message-content-full"><div class="message-text"><pre>${escapeHtml(
      content,
    )}</pre></div></div>`;
  }
}

function createPreviewContentHTML(content, lines, role) {
  const preview = lines.slice(0, 5).join("\n");
  const moreLines = lines.length - 5;

  let html = `
    <div class="message-preview-short clickable-message" title="Click to expand (${moreLines} more lines)">
      <div class="message-text"><pre>${escapeHtml(preview)}</pre></div>
      <div class="expand-indicator">▼ ${moreLines} more lines</div>
    </div>
    <div class="message-content-full" style="display: none;" title="Content expanded - click collapse button below to hide">
  `;

  if (role === "assistant" && content.includes("```")) {
    const parts = content.split("```");
    parts.forEach((part, i) => {
      if (i % 2 === 0) {
        html += `<div class="message-text"><pre>${escapeHtml(
          part,
        )}</pre></div>`;
      } else {
        html += `<div class="code-block"><pre><code>${escapeHtml(
          part,
        )}</code></pre></div>`;
      }
    });
  } else {
    html += `<div class="message-text"><pre>${escapeHtml(content)}</pre></div>`;
  }

  html += `
      <div class="collapse-indicator clickable-message" title="Click to collapse">▲ Click to collapse</div>
    </div>
  `;

  return html;
}

function createComplexContentHTML(contentParts) {
  let html = '<div class="message-content-full">';

  contentParts.forEach((part) => {
    if (part.type === "text") {
      const lines = part.text.split("\n");
      if (lines.length <= 5) {
        html += `<div class="message-text"><pre>${escapeHtml(
          part.text,
        )}</pre></div>`;
      } else {
        const preview = lines.slice(0, 5).join("\n");
        const moreLines = lines.length - 5;
        html += `
          <div class="message-preview-short clickable-message" title="Click to expand (${moreLines} more lines)">
            <div class="message-text"><pre>${escapeHtml(preview)}</pre></div>
            <div class="expand-indicator">▼ ${moreLines} more lines</div>
          </div>
          <div class="message-content-expanded" style="display: none;" title="Content expanded - click collapse button below to hide">
            <div class="message-text"><pre>${escapeHtml(part.text)}</pre></div>
            <div class="collapse-indicator clickable-message" title="Click to collapse">▲ Click to collapse</div>
          </div>
        `;
      }
    } else {
      html += `<div class="message-part"><strong>${
        part.type.charAt(0).toUpperCase() + part.type.slice(1)
      }:</strong><pre>${JSON.stringify(part, null, 2)}</pre></div>`;
    }
  });

  html += "</div>";
  return html;
}

function createToolCallContentHTML(message) {
  // Render a mini-swe-agent v2 tool-call assistant message: the reasoning text (if any)
  // followed by each issued command as a code block (matching the v1 ```bash styling).

  // Thought text: content may be a string, an array of content blocks, or null.
  let thought = "";
  if (typeof message.content === "string") {
    thought = message.content;
  } else if (Array.isArray(message.content)) {
    thought = message.content
      .filter((p) => p && p.type === "text" && typeof p.text === "string")
      .map((p) => p.text)
      .join("\n");
  }

  // Commands: prefer the parsed actions, fall back to the raw tool_calls.
  let commands = [];
  if (message.extra && Array.isArray(message.extra.actions)) {
    commands = message.extra.actions.map((a) => a.command).filter(Boolean);
  }
  if (!commands.length && Array.isArray(message.tool_calls)) {
    commands = message.tool_calls
      .map((tc) => {
        try {
          return JSON.parse(tc.function.arguments).command;
        } catch (e) {
          return tc.function && tc.function.arguments;
        }
      })
      .filter(Boolean);
  }

  let html = '<div class="message-content-full">';
  if (thought.trim()) {
    html += `<div class="message-text"><pre>${escapeHtml(thought)}</pre></div>`;
  }
  commands.forEach((cmd) => {
    html += `<div class="code-block"><pre><code>${escapeHtml(cmd)}</code></pre></div>`;
  });
  if (!thought.trim() && !commands.length) {
    html += `<div class="message-text"><pre>${escapeHtml(
      JSON.stringify(message.content, null, 2),
    )}</pre></div>`;
  }
  html += "</div>";
  return html;
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}
