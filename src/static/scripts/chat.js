// src/static/scripts/chat.js
document.addEventListener("DOMContentLoaded", () => {
  const chatBox = document.getElementById("chat-box");
  const perguntaInput = document.getElementById("pergunta");
  const apiKeyInput = document.getElementById("apiKey");
  const enviarBtn = document.getElementById("enviar");

  function addMessage(text, sender) {
    const msg = document.createElement("div");
    msg.classList.add("chat-message", sender);
    msg.textContent = text;
    chatBox.appendChild(msg);
    chatBox.scrollTop = chatBox.scrollHeight;
    return msg;  // Retorna pra manipular loading
  }

  enviarBtn.addEventListener("click", async () => {
    const pergunta = perguntaInput.value.trim();
    const apiKey = apiKeyInput.value.trim();

    if (!apiKey) return addMessage("⚠️ Informe sua chave da API Gemini ou Grok.", "bot");
    if (!pergunta) return addMessage("⚠️ Escreva uma pergunta antes de enviar.", "bot");

    addMessage(pergunta, "user");
    perguntaInput.value = "";

    const loadingMsg = addMessage("⏳ Pensando... (usando suas notas fiscais)", "bot");
    enviarBtn.disabled = true;
    enviarBtn.textContent = "Enviando...";

    try {
      const resposta = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pergunta, apiKey })
      });

      const data = await resposta.json();
      chatBox.removeChild(loadingMsg);  // Remove loading

      if (resposta.ok && data.resposta) {
        addMessage("🤖 " + data.resposta, "bot");
      } else {
        addMessage("⚠️ Erro: " + (data.erro || "Sem resposta da IA."), "bot");
      }
    } catch (err) {
      chatBox.removeChild(loadingMsg);
      addMessage("❌ Erro na comunicação com o servidor.", "bot");
      console.error("Erro:", err);
    } finally {
      enviarBtn.disabled = false;
      enviarBtn.textContent = "Enviar";
    }
  });

  // Enter envia
  perguntaInput.addEventListener("keypress", (e) => {
    if (e.key === "Enter") enviarBtn.click();
  });
});