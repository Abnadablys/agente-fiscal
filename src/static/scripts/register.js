document.getElementById("registerForm").addEventListener("submit", async (e) => {
    e.preventDefault();

    const cnpj = document.getElementById("cnpj").value.trim();
    const senha = document.getElementById("senha").value.trim();

    const response = await fetch("/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cnpj, senha }),
    });

    const data = await response.json();
    const msg = document.getElementById("mensagem");

    if (response.ok) {
        msg.textContent = "✅ Cadastro realizado! Redirecionando...";
        msg.style.color = "lime";
        setTimeout(() => (window.location.href = "/"), 1500);
    } else {
        msg.textContent = "❌ " + (data.erro || "Erro ao cadastrar");
        msg.style.color = "red";
    }
});
