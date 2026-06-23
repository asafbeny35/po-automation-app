<script>
const dropZone = document.getElementById("dropZone");
const fileInput = document.getElementById("file");

if (dropZone && fileInput) {

  dropZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropZone.style.background = "#fff7ed";
    dropZone.style.borderColor = "#ff7d12";
  });

  dropZone.addEventListener("dragleave", () => {
    dropZone.style.background = "";
    dropZone.style.borderColor = "";
  });

  dropZone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropZone.style.background = "";
    dropZone.style.borderColor = "";

    const files = e.dataTransfer.files;
    if (files.length > 0) {
      fileInput.files = files;
      fileInput.dispatchEvent(new Event("change"));
      
    }
  });

  dropZone.addEventListener("click", () => {
    fileInput.click();
  });

  fileInput.addEventListener("change", () => {
    if (fileInput.files.length > 0) {
      const nameEl = document.getElementById("fileName");
      if (nameEl) {
        nameEl.innerText = "✔ " + fileInput.files[0].name;
      }
    }
  });

}
</script>
<script>
async function send(mode) {
  try {
    const fileInput = document.getElementById("file");
    if (!fileInput.files.length) {
      alert("בחר קובץ קודם");
      return;
    }

    const formData = new FormData();
    formData.append("file", fileInput.files[0]);
    formData.append("mode", mode);

    const res = await fetch("/process", {
      method: "POST",
      body: formData
    });

    const data = await res.json();

    if (!data || data.error) {
      alert("שגיאה בעיבוד הקובץ");
      return;
    }

    const finalizeRes = await fetch("/finalize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode: mode, data: data })
    });

    const result = await finalizeRes.json();
    console.log(result);

    alert("הפעולה הושלמה");

  } catch (e) {
    console.error(e);
    alert("שגיאה בתהליך");
  }
}
</script>
