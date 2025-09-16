// Experiment management functionality for CodeClash Trajectory Viewer

// Delete experiment function
function deleteExperiment(folderPath) {
  const confirmed = confirm(
    "Are you sure you want to delete this experiment? This action cannot be undone.\n\nFolder: " +
      folderPath,
  );
  if (confirmed) {
    fetch("/delete-experiment", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        folder_path: folderPath,
      }),
    })
      .then((response) => response.json())
      .then((data) => {
        if (data.success) {
          alert("Experiment deleted successfully.");
          // Redirect to picker
          window.location.href = "/picker";
        } else {
          alert(
            "Error deleting experiment: " + (data.error || "Unknown error"),
          );
        }
      })
      .catch((error) => {
        console.error("Error:", error);
        alert("Error deleting experiment: " + error.message);
      });
  }
}
