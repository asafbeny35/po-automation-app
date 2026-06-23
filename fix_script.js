<script>
document.addEventListener("DOMContentLoaded", () => {

const fileInput = document.getElementById("file");
const dropZone = document.getElementById("dropZone");
const fileNameEl = document.getElementById("fileName");

if (!fileInput || !dropZone) return;

dropZone.addEventListener("click", () => fileInput.click());

dropZone.addEventListener("dragover", e => e.preventDefault());

dropZone.addEventListener("drop", e => {
  e.preventDefault();
  fileInput.files = e.dataTransfer.files;
  showFileName();
});

fileInput.addEventListener("change", showFileName);

function showFileName() {
  if (fileInput.files.length) {
    fileNameEl.innerText = "📄 " + fileInput.files[0].name;
  }
}

window.upload = async function(mode) {
  const file = fileInput.files[0];
  if (!file) return alert("בחר קובץ");

  const fd = new FormData();
  fd.append("file", file);
  fd.append("mode", mode);

  const res = await fetch("/process", {method:"POST", body:fd});
  const data = await res.json();

  window.currentData = data;
  renderFields(data);
};

window.send = async function(mode) {
  await fetch("/finalize", {
    method:"POST",
    headers:{"Content-Type":"application/json"},
    body:JSON.stringify({mode:mode, data:window.currentData})
  });
  alert("נוצר");
};

});
</script>
