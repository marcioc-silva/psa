(async function () {
  const video = document.getElementById("video");
  const canvas = document.getElementById("canvas");
  const btn = document.getElementById("btnSnap");
  const status = document.getElementById("status");

  if (!video || !btn) return;

  function setStatus(msg, isErr=false) {
    if (!status) return;
    status.textContent = msg;
    status.className = isErr ? "text-danger" : "text-success";
  }

  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: { ideal: "environment" } },
      audio: false
    });
    video.srcObject = stream;
  } catch (e) {
    setStatus("Não foi possível acessar a câmera. Verifique permissões.", true);
    return;
  }

  btn.addEventListener("click", async () => {
    try {
      btn.disabled = true;
      setStatus("Registrando...");

      const w = video.videoWidth || 720;
      const h = video.videoHeight || 1280;
      canvas.width = w;
      canvas.height = h;

      const ctx = canvas.getContext("2d");
      ctx.drawImage(video, 0, 0, w, h);

      // JPEG base64
      const dataUrl = canvas.toDataURL("image/jpeg", 0.85);
      const base64 = dataUrl.split(",")[1];

      const resp = await fetch("/mydot/registrar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ image_base64: base64 })
      });

      const json = await resp.json().catch(() => ({}));

      if (!resp.ok || !json.ok) {
        setStatus("Erro ao registrar: " + (json.error || resp.status), true);
        return;
      }

      setStatus(`OK! ${json.kind.toUpperCase()} registrada às ${json.ts_utc}`);
    } catch (e) {
      setStatus("Falha ao registrar (erro inesperado).", true);
    } finally {
      btn.disabled = false;
    }
  });
})();