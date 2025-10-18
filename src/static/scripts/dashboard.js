document.addEventListener("DOMContentLoaded", () => {
    const uploadBtn = document.getElementById("upload-btn");
    const fileInput = document.getElementById("file-input");
    const statusDiv = document.getElementById("upload-status");
    const abrirChat = document.getElementById("abrir-chat");
    const logoutBtn = document.getElementById("logout-btn");

    // Enviar arquivo
    uploadBtn.addEventListener("click", async () => {
        const file = fileInput.files[0];
        if (!file) {
            statusDiv.textContent = "Selecione um arquivo primeiro!";
            statusDiv.style.color = "red";
            return;
        }

        const formData = new FormData();
        formData.append("file", file);

        statusDiv.textContent = "⏳ Enviando nota...";
        statusDiv.style.color = "#00bcd4";

        try {
            const response = await fetch("/api/process-documents", {
                method: "POST",
                body: formData
            });
            const result = await response.json();
            if (response.ok) {
                statusDiv.textContent = `✅ ${result.mensagem || "Nota processada com sucesso!"}`;
                statusDiv.style.color = "#00e676";
            } else {
                statusDiv.textContent = `❌ Erro: ${result.erro || "Falha no envio"}`;
                statusDiv.style.color = "red";
            }
        } catch (error) {
            statusDiv.textContent = "❌ Erro de conexão com o servidor.";
            statusDiv.style.color = "red";
        }
    });

    // Abrir chat fiscal
    abrirChat.addEventListener("click", () => {
        window.location.href = "/chat";
    });

    // Logout
    logoutBtn.addEventListener("click", async () => {
        await fetch("/logout", { method: "POST" });
        window.location.href = "/";
    });
});
