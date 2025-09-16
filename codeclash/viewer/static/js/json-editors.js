// JSON Editor initialization for CodeClash Trajectory Viewer

// Initialize JSON editors when page loads
function initializeJSONEditors(metadata) {
  // Initialize metadata JSON editor
  const metadataContainer = document.getElementById("metadata-jsoneditor");
  if (metadataContainer) {
    const metadataEditor = new JSONEditor(metadataContainer, {
      mode: "view",
      modes: ["view", "tree"],
      name: "metadata",
    });
    metadataEditor.set(metadata.results);
  }

  // Initialize round results JSON editors
  metadata.rounds.forEach((roundData) => {
    if (roundData.results) {
      const roundContainer = document.getElementById(
        `round-${roundData.round_num}-results-jsoneditor`,
      );
      if (roundContainer) {
        const roundEditor = new JSONEditor(roundContainer, {
          mode: "view",
          modes: ["view", "tree"],
          name: `round_${roundData.round_num}_results`,
        });
        roundEditor.set(roundData.results);
      }
    }
  });
}
