/**
 * Matrix Analysis Functionality
 *
 * Handles the interactive matrix visualization including dropdown switching
 * and cell hover effects for detailed information display.
 */

// Initialize matrix functionality when DOM is loaded
document.addEventListener("DOMContentLoaded", function () {
  initializeMatrixAnalysis();
});

// Utility function to decode HTML entities
function decodeHtmlEntities(text) {
  const textarea = document.createElement("textarea");
  textarea.innerHTML = text;
  return textarea.value;
}

function initializeMatrixAnalysis() {
  const matrixDropdown = document.getElementById("matrix-dropdown");
  const matrixData = getMatrixData();

  if (!matrixDropdown || !matrixData) {
    return;
  }

  // Show the first matrix by default
  const firstMatrixName = Object.keys(matrixData.matrices)[0];
  if (firstMatrixName) {
    showMatrix(firstMatrixName);
    matrixDropdown.value = firstMatrixName;
  }

  // Handle dropdown changes
  matrixDropdown.addEventListener("change", function () {
    const selectedMatrix = this.value;
    showMatrix(selectedMatrix);
  });

  // Add enhanced tooltips for matrix cells
  setupMatrixTooltips();
}

function getMatrixData() {
  const matrixDataElement = document.getElementById("matrix-data");
  if (!matrixDataElement) {
    return null;
  }

  try {
    return JSON.parse(matrixDataElement.textContent);
  } catch (error) {
    console.error("Error parsing matrix data:", error);
    return null;
  }
}

function showMatrix(matrixName) {
  // Hide all matrix tables
  const allMatrixContainers = document.querySelectorAll(
    ".matrix-table-container",
  );
  allMatrixContainers.forEach((container) => {
    container.style.display = "none";
  });

  // Show the selected matrix
  const selectedContainer = document.getElementById(`matrix-${matrixName}`);
  if (selectedContainer) {
    selectedContainer.style.display = "block";
  }
}

function setupMatrixTooltips() {
  // No JavaScript tooltips needed - using HTML title attributes
}

// Utility function to format matrix cell information
function formatMatrixCellInfo(cellData) {
  if (!cellData || !cellData.scores) {
    return "No data available";
  }

  const { win_percentage, scores, total_games } = cellData;
  const scoresText = Object.entries(scores)
    .map(([player, score]) => `${player}: ${score}`)
    .join(", ");

  return `Win Rate: ${win_percentage}%\nScores: ${scoresText}\nTotal Games: ${total_games}`;
}

// Export functions for potential use by other modules
window.MatrixAnalysis = {
  initialize: initializeMatrixAnalysis,
  showMatrix: showMatrix,
  getMatrixData: getMatrixData,
};
