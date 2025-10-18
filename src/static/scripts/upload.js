// upload.js - integração com /api/process-documents
const uploadBtn = document.getElementById("upload-btn");
const fileInput = document.getElementById("file-input");
const resultDiv = document.getElementById("result");
const uploadBox = document.getElementById("upload-box");

// Estilo drag and drop
function handleDragOver(event) {
    event.preventDefault();
    uploadBox.classList.add("dragging");
}
function handleDrop(event) {
    event.preventDefault();
    uploadBox.classList.remove("dragging");
    const files = event.dataTransfer.files;
    fileInput.files = files;
}

// Enviar os arquivos para a API
uploadBtn.addEventListener("click", async () => {
    const files = fileInput.files;
    if (!files.length) {
        alert("Selecione ao menos um arquivo!");
        return;
    }

    const formData = new FormData();
    for (const file of files) formData.append("files", file);

    resultDiv.innerHTML = "⏳ Enviando...";

    try {
        const response = await fetch("/api/process-documents", {
            method: "POST",
            body: formData
        });

        const data = await response.json();

        if (!response.ok) {
            resultDiv.innerHTML = `❌ Erro: ${data.error || "Falha no envio"}`;
            return;
        }

        // Exibe resultados formatados
        resultDiv.innerHTML = data.map(item =>
            `<div class="resultado-item">
                <b>${item.arquivo}</b>: ${item.status}
             </div>`
        ).join("");
    } catch (error) {
        console.error("Erro:", error);
        resultDiv.innerHTML = "❌ Erro ao enviar os arquivos.";
    }
});
