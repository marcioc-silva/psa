(async function () {
  const video = document.getElementById("video");
  const canvas = document.getElementById("canvas");
  const btn = document.getElementById("btnSnap");
  const status = document.getElementById("status");

  if (!video || !btn) return;

  function setStatus(msg, isErr = false) {
    if (!status) return;
    status.textContent = msg;
    status.className = isErr ? "text-danger" : "text-success";
  }

  function openDB() {
    return new Promise((resolve, reject) => {
      const req = indexedDB.open("mydot", 1);
      req.onupgradeneeded = () => {
        const db = req.result;
        if (!db.objectStoreNames.contains("photos")) {
          db.createObjectStore("photos", { keyPath: "id" });
        }
      };
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
  }

  async function savePhoto(id, dataUrl) {
    const db = await openDB();
    return new Promise((resolve, reject) => {
      const tx = db.transaction("photos", "readwrite");
      const store = tx.objectStore("photos");
      store.put({ id: Number(id), dataUrl, savedAt: Date.now() });
      tx.oncomplete = () => resolve(true);
      tx.onerror = () => reject(tx.error);
    });
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
      setStatus("Capturando foto...");

      const w = video.videoWidth || 720;
      const h = video.videoHeight || 1280;
      canvas.width = w;
      canvas.height = h;

      const ctx = canvas.getContext("2d");
      ctx.drawImage(video, 0, 0, w, h);

      const dataUrl = canvas.toDataURL("image/jpeg", 0.85);

      setStatus("Registrando no servidor...");

      const dtEl = document.getElementById("dtLocal");
      const dtLocal = dtEl?.value?.trim() || null;

      console.log("dtLocal enviado:", dtLocal);
      console.log("Timezone do navegador:", Intl.DateTimeFormat().resolvedOptions().timeZone);
      console.log("Agora local navegador:", new Date().toString());
      console.log("Agora ISO UTC navegador:", new Date().toISOString());

      const resp = await fetch("/mydot/registrar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ dt_local: dtLocal })
      });

      const json = await resp.json().catch(() => ({}));
      console.log("Resposta backend:", json);

      if (!resp.ok || !json.ok) {
        setStatus("Erro ao registrar: " + (json.error || resp.status), true);
        return;
      }

      await savePhoto(json.id, dataUrl);

      setStatus(`OK! ${String(json.kind).toUpperCase()} em ${json.data} ${json.hora}`);

      setTimeout(() => {
        window.location.href = "/mydot/history";
      }, 1500);
    } catch (e) {
      console.error(e);
      setStatus("Falha ao registrar (erro inesperado).", true);
    } finally {
      btn.disabled = false;
    }
  });
})();