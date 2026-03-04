(async function () {
  const video = document.getElementById("video");
  const canvas = document.getElementById("canvas");
  const preview = document.getElementById("preview");
  const statusEl = document.getElementById("status");

  function setStatus(msg) {
    if (statusEl) statusEl.textContent = msg;
  }

  async function getGeo() {
    // Geo opcional (depende de permissão do navegador)
    return await new Promise((resolve) => {
      if (!navigator.geolocation) return resolve(null);
      navigator.geolocation.getCurrentPosition(
        (pos) => resolve({
          lat: pos.coords.latitude,
          lon: pos.coords.longitude,
          acc_m: pos.coords.accuracy
        }),
        () => resolve(null),
        { enableHighAccuracy: true, timeout: 4000, maximumAge: 0 }
      );
    });
  }

  async function startCamera() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "environment" },
        audio: false
      });
      video.srcObject = stream;
      await video.play();
      setStatus("Câmera pronta. Escolha o tipo de ponto.");
    } catch (e) {
      console.error(e);
      setStatus("Falha ao abrir a câmera. Verifique HTTPS e permissões.");
    }
  }

  function captureJpegBase64() {
    const w = video.videoWidth || 1280;
    const h = video.videoHeight || 720;
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext("2d");
    ctx.drawImage(video, 0, 0, w, h);
    const dataUrl = canvas.toDataURL("image/jpeg", 0.85);
    preview.src = dataUrl;
    return dataUrl;
  }

  async function sendPunch(kind) {
    try {
      setStatus("Capturando foto…");
      const dataUrl = captureJpegBase64();

      setStatus("Obtendo localização (opcional)…");
      const geo = await getGeo();

      setStatus("Enviando registro…");
      const resp = await fetch("/mydot/punch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          kind,
          image_base64: dataUrl,
          geo
        })
      });

      const out = await resp.json().catch(() => ({}));
      if (!resp.ok || !out.ok) {
        const err = out.error || ("HTTP_" + resp.status);
        setStatus("Erro: " + err);
        return;
      }
      setStatus("Registrado! ID " + out.id + " — " + out.ts_utc);
      // opcional: vibrar
      if (navigator.vibrate) navigator.vibrate([80, 40, 80]);
    } catch (e) {
      console.error(e);
      setStatus("Erro inesperado ao registrar.");
    }
  }

  document.querySelectorAll("button[data-kind]").forEach((btn) => {
    btn.addEventListener("click", () => sendPunch(btn.dataset.kind));
  });

  await startCamera();
})();
