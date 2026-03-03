async function loadPSAs() {
  const res = await fetch("/dash/api/psas");
  const psas = await res.json();
  const sel = document.getElementById("psaSelect");
  psas.forEach(p => {
    const opt = document.createElement("option");
    opt.value = p;
    opt.textContent = p;
    sel.appendChild(opt);
  });
}
loadPSAs();
