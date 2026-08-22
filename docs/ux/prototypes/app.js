(function () {
  "use strict";
  const titles = {portfolio:"Portafolio",import:"Importación",reconcile:"Conciliación",close:"Cierre",signals:"Señales",reports:"Informes",mobile:"Solicitud móvil"};
  const stateCopy = {
    ready:null,
    empty:["empty","Estado vacío: todavía no hay fuentes para este periodo. Configura la expectativa o carga un archivo."],
    error:["error","Error verificable: falló el último procesamiento. El original permanece intacto y puedes reintentar."],
    degraded:["degraded","Modo degradado: el feed no está disponible. El canal por archivo continúa habilitado."],
    partial:["partial","Cobertura parcial: faltan registros del periodo y el cierre certificado permanece bloqueado."],
    ambiguous:["ambiguous","Interpretación ambigua: hay más de una lectura plausible. Confirma o conserva el estado unknown."]
  };
  function route() {
    const name = location.hash.slice(1) || "portfolio";
    const active = titles[name] ? name : "portfolio";
    document.querySelectorAll("[data-page]").forEach(page => { page.hidden = page.dataset.page !== active; });
    document.querySelectorAll("[data-route]").forEach(link => { link.classList.toggle("active", link.dataset.route === active); if(link.dataset.route === active){link.setAttribute("aria-current","page");}else{link.removeAttribute("aria-current");} });
    document.getElementById("page-title").textContent = titles[active];
  }
  function setState(value) {
    const banner = document.getElementById("state-banner");
    banner.className = "state-banner";
    const copy = stateCopy[value];
    if (!copy) { banner.hidden = true; banner.textContent = ""; return; }
    banner.classList.add(copy[0]); banner.textContent = copy[1]; banner.hidden = false;
  }
  window.addEventListener("hashchange", route);
  document.querySelectorAll("[data-go]").forEach(button => button.addEventListener("click", () => { location.hash = button.dataset.go; }));
  document.getElementById("ui-state").addEventListener("change", event => setState(event.target.value));
  document.querySelectorAll("[data-stage]").forEach(button => button.addEventListener("click", () => {
    document.querySelectorAll("[data-stage]").forEach(item => item.setAttribute("aria-selected", String(item === button)));
    const labels = {original:["Original inmutable","Bytes/render fiel, hash y versión"],extraction:["Extracción fiel","Celdas y tokens preservados, incluido ruido"],clean:["Dataset limpio","Receta reversible y diff versionado"],canonical:["Esquema canónico","Campos tipados; publicación todavía bloqueada"]};
    document.getElementById("stage-title").textContent = labels[button.dataset.stage][0];
    document.getElementById("stage-description").textContent = labels[button.dataset.stage][1];
  }));
  document.querySelectorAll("[data-locator]").forEach(button => button.addEventListener("click", () => {
    document.getElementById("locator").textContent = button.dataset.locator;
    document.getElementById("raw-value").textContent = button.dataset.value;
  }));
  route();
}());
