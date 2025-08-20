<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>PDF Splitter</title>
  <link rel="stylesheet" href="assets/css/style.css">
</head>
<body>
  <div class="container">
      <h2>Split PDF File</h2>
      <p>Upload a PDF and split pages as needed.</p>

      <form id="pdfForm">
          <label class="file-label">
              <span>📂 Choose PDF File</span>
              <input type="file" id="pdfFile" name="pdfFile" accept="application/pdf" required>
          </label>
          <br><br>

          <label>Enter Page Range (e.g. 1-5, 8, 10-12):</label>
          <input type="text" id="pageRange" name="pageRange" placeholder="Leave blank for full PDF">
          <br><br>

          <button id="proceedBtn" type="submit" class="btn" style="display:none;">
              Proceed
          </button>
      </form>

      <div id="responseBox" class="response-box"></div>
  </div>

  <script>
    const pdfInput = document.getElementById("pdfFile");
    const proceedBtn = document.getElementById("proceedBtn");
    const pdfForm = document.getElementById("pdfForm");
    const responseBox = document.getElementById("responseBox");

    pdfInput.addEventListener("change", function() {
        proceedBtn.style.display = this.files.length > 0 ? "inline-block" : "none";
    });

    pdfForm.addEventListener("submit", async function(event) {
        event.preventDefault();

        const file = pdfInput.files[0];
        console.log(file);
        const pageRange = document.getElementById("pageRange").value;

        if (!file) {
            showMessage("Please select a PDF file.", "error");
            return;
        }

        if (file.type !== "application/pdf") {
            showMessage("Only PDF files are allowed.", "error");
            return;
        }

        const formData = new FormData();
        formData.append("file", file);
        // formData.append("pageRange", pageRange);

        try {
            showMessage("⏳ Processing PDF, please wait...", "info");

            const response = await fetch("http://localhost:8000/process", {
                method: "POST",
                body: formData
            });

            if (!response.ok) {
                throw new Error(`Server error: ${response.status}`);
            }

            const result = await response.json();
            showMessage("Success! PDF processed.<br><pre>" + JSON.stringify(result, null, 2) + "</pre>", "success");
        } catch (error) {
            showMessage("Error: " + error.message, "error");
        }
    });

    function showMessage(msg, type) {
        responseBox.innerHTML = msg;
        responseBox.className = "response-box " + type;
    }
  </script>
</body>
</html>
