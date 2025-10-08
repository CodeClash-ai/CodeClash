/**
 * Analysis functionality for the CodeClash trajectory viewer
 */

let lineCountChart = null;
let analysisData = null;

/**
 * Initialize the analysis functionality
 */
function initializeAnalysis() {
  const analysisDataElement = document.getElementById("analysis-data");
  if (!analysisDataElement) {
    return; // No analysis data available
  }

  // Check if the element has any content before parsing
  const textContent = analysisDataElement.textContent.trim();
  if (!textContent) {
    return; // No data loaded yet (will be loaded on demand)
  }

  try {
    analysisData = JSON.parse(textContent);

    if (
      analysisData &&
      analysisData.all_files &&
      analysisData.all_files.length > 0
    ) {
      setupFileDropdown();
      createLineCountChart(analysisData.all_files[0]); // Start with first file
    }
  } catch (error) {
    console.error("Error parsing analysis data:", error);
  }
}

/**
 * Setup the file dropdown change handler
 */
function setupFileDropdown() {
  const dropdown = document.getElementById("file-dropdown");
  if (!dropdown) return;

  dropdown.addEventListener("change", function () {
    const selectedFile = this.value;
    if (selectedFile && lineCountChart) {
      updateLineCountChart(selectedFile);
    }
  });
}

/**
 * Create the line count chart for a specific file
 */
function createLineCountChart(fileName) {
  const canvas = document.getElementById("line-count-chart");
  if (!canvas || !analysisData) return;

  const ctx = canvas.getContext("2d");

  // Destroy existing chart if it exists
  if (lineCountChart) {
    lineCountChart.destroy();
  }

  const chartData = prepareChartData(fileName);

  lineCountChart = new Chart(ctx, {
    type: "line",
    data: chartData,
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        title: {
          display: true,
          text: `Line Count Over Rounds: ${fileName}`,
        },
        legend: {
          display: true,
          position: "top",
        },
      },
      scales: {
        x: {
          title: {
            display: true,
            text: "Round",
          },
          type: "linear",
          position: "bottom",
        },
        y: {
          title: {
            display: true,
            text: "Line Count",
          },
          beginAtZero: true,
        },
      },
      interaction: {
        intersect: false,
        mode: "index",
      },
    },
  });
}

/**
 * Update the existing chart with data for a new file
 */
function updateLineCountChart(fileName) {
  if (!lineCountChart || !analysisData) return;

  const chartData = prepareChartData(fileName);
  lineCountChart.data = chartData;
  lineCountChart.options.plugins.title.text = `Line Count Over Rounds: ${fileName}`;
  lineCountChart.update();
}

/**
 * Prepare chart data for a specific file
 */
function prepareChartData(fileName) {
  const datasets = [];
  const colors = [
    "#FF6384",
    "#36A2EB",
    "#FFCE56",
    "#4BC0C0",
    "#9966FF",
    "#FF9F40",
    "#FF6384",
    "#C9CBCF",
    "#4BC0C0",
    "#FF6384",
  ];

  let colorIndex = 0;

  // Get all rounds across all players
  const allRounds = new Set();
  Object.values(analysisData.line_counts_by_round).forEach((playerData) => {
    Object.keys(playerData).forEach((round) => {
      allRounds.add(parseInt(round));
    });
  });

  const sortedRounds = Array.from(allRounds).sort((a, b) => a - b);

  // Create dataset for each player
  Object.entries(analysisData.line_counts_by_round).forEach(
    ([playerName, playerData]) => {
      const data = [];

      sortedRounds.forEach((round) => {
        const roundData = playerData[round];
        if (roundData && roundData[fileName] !== undefined) {
          data.push({
            x: round,
            y: roundData[fileName],
          });
        } else {
          // If file doesn't exist in this round, use 0 or previous value
          const prevValue = data.length > 0 ? data[data.length - 1].y : 0;
          data.push({
            x: round,
            y: prevValue,
          });
        }
      });

      datasets.push({
        label: playerName,
        data: data,
        borderColor: colors[colorIndex % colors.length],
        backgroundColor: colors[colorIndex % colors.length] + "20", // Add transparency
        borderWidth: 2,
        fill: false,
        tension: 0.1,
      });

      colorIndex++;
    },
  );

  return { datasets };
}

// Initialize when DOM is loaded

// --- Overview Scores Chart ---
let overviewScoresChart = null;
let overviewScoresData = null;

function initializeOverviewScoresChart() {
  const overviewScoresDataElement = document.getElementById(
    "overview-scores-data",
  );
  if (!overviewScoresDataElement) return;
  try {
    overviewScoresData = JSON.parse(overviewScoresDataElement.textContent);
    if (
      overviewScoresData &&
      overviewScoresData.players &&
      overviewScoresData.players.length > 0 &&
      overviewScoresData.rounds &&
      overviewScoresData.rounds.length > 0
    ) {
      createOverviewScoresChart();
    }
  } catch (error) {
    console.error("Error parsing overview scores data:", error);
  }
}

function createOverviewScoresChart() {
  const canvas = document.getElementById("overview-scores-chart");
  if (!canvas || !overviewScoresData) return;
  const ctx = canvas.getContext("2d");
  if (overviewScoresChart) overviewScoresChart.destroy();

  // Prepare datasets
  const colors = [
    "#FF6384",
    "#36A2EB",
    "#FFCE56",
    "#4BC0C0",
    "#9966FF",
    "#FF9F40",
    "#C9CBCF",
    "#4BC0C0",
    "#FF6384",
  ];
  let colorIndex = 0;
  const datasets = overviewScoresData.players.map((player) => {
    const data = overviewScoresData.rounds.map((round, i) => ({
      x: round,
      y: overviewScoresData.scores_by_player[player][i],
    }));
    const color = colors[colorIndex % colors.length];
    colorIndex++;
    return {
      label: player,
      data: data,
      borderColor: color,
      backgroundColor: color + "20",
      borderWidth: 2,
      fill: false,
      tension: 0.1,
    };
  });

  overviewScoresChart = new Chart(ctx, {
    type: "line",
    data: { datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        title: {
          display: true,
          text: `Scores Per Round`,
        },
        legend: {
          display: true,
          position: "top",
        },
      },
      scales: {
        x: {
          title: { display: true, text: "Round" },
          type: "linear",
          position: "bottom",
        },
        y: {
          title: { display: true, text: "Score %" },
          beginAtZero: true,
          max: 100,
        },
      },
      interaction: { intersect: false, mode: "index" },
    },
  });
}

/**
 * Render line count chart with dynamically loaded data
 * This is called by app.js after loading analysis data
 */
window.renderLineCountChart = function (data) {
  analysisData = data;
  if (
    analysisData &&
    analysisData.all_files &&
    analysisData.all_files.length > 0
  ) {
    setupFileDropdown();
    createLineCountChart(analysisData.all_files[0]); // Start with first file
  }
};

// Listen for dynamically loaded analysis data
document.addEventListener("analysisDataLoaded", function (event) {
  if (event.detail) {
    window.renderLineCountChart(event.detail);
  }
});

// Initialize all analyses when DOM is loaded
document.addEventListener("DOMContentLoaded", function () {
  initializeAnalysis();
  initializeOverviewScoresChart();
});
