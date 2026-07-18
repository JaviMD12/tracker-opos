// ---------- Autenticacion (JWT) ----------
const TOKEN_STORAGE_KEY = "token";
const authGateEl = document.getElementById("auth-gate");
const appShellEl = document.getElementById("app-shell");

function obtenerToken() {
  return localStorage.getItem(TOKEN_STORAGE_KEY);
}

function guardarToken(token) {
  localStorage.setItem(TOKEN_STORAGE_KEY, token);
}

function borrarToken() {
  localStorage.removeItem(TOKEN_STORAGE_KEY);
}

function obtenerUsuarioIdDesdeToken() {
  const token = obtenerToken();
  if (!token) return null;
  try {
    const payloadBase64 = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    return JSON.parse(atob(payloadBase64)).sub ?? null;
  } catch {
    return null;
  }
}

async function fetchAutenticado(url, options = {}) {
  const headers = { ...(options.headers || {}), Authorization: `Bearer ${obtenerToken()}` };
  const res = await fetch(url, { ...options, headers });
  if (res.status === 401) {
    borrarToken();
    mostrarAuthGate();
    mostrarToast("Tu sesion ha caducado. Inicia sesion de nuevo.", "error");
  }
  return res;
}

function mostrarAuthGate() {
  authGateEl.classList.remove("hidden");
  appShellEl.classList.add("hidden");
 }

function mostrarApp() {
  authGateEl.classList.add("hidden");
  appShellEl.classList.remove("hidden");
  mostrarEstadoPremium();
  cargarDashboardGlobal();
  cargarHeatmap();
  procesarRetornoDePago();
}

const authTabButtons = document.querySelectorAll(".auth-tab-btn");
const authTabsWrapper = document.getElementById("auth-tabs");
const authPanels = {
  login: document.getElementById("form-login"),
  registro: document.getElementById("form-registro"),
  olvido: document.getElementById("form-olvido"),
  reset: document.getElementById("form-reset"),
};

// Token de recuperacion capturado de la URL (?reset_token=...), usado por el
// formulario de "nueva contraseña" al enviarse.
let resetTokenActual = null;

function mostrarPanelAuth(nombre) {
  Object.entries(authPanels).forEach(([clave, panel]) => {
    panel.classList.toggle("hidden", clave !== nombre);
  });
  const esTab = nombre === "login" || nombre === "registro";
  authTabsWrapper.classList.toggle("hidden", !esTab);
  if (esTab) {
    authTabButtons.forEach((b) => b.classList.toggle("active", b.dataset.authTab === nombre));
  }
}

authTabButtons.forEach((btn) => {
  btn.addEventListener("click", () => mostrarPanelAuth(btn.dataset.authTab));
});

document.getElementById("link-olvido-password").addEventListener("click", () => {
  mostrarPanelAuth("olvido");
});

document.getElementById("link-volver-login").addEventListener("click", () => {
  mostrarPanelAuth("login");
});

const formLogin = document.getElementById("form-login");
const loginErrorEl = document.getElementById("login-error");

formLogin.addEventListener("submit", async (event) => {
  event.preventDefault();
  loginErrorEl.classList.add("hidden");

  const body = new URLSearchParams();
  body.set("username", document.getElementById("login-email").value);
  body.set("password", document.getElementById("login-password").value);

  try {
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body,
    });
    const data = await res.json();

    if (!res.ok) {
      loginErrorEl.textContent = data.detail ?? "No se pudo iniciar sesion.";
      loginErrorEl.classList.remove("hidden");
      return;
    }

    guardarToken(data.access_token);
    mostrarApp();
  } catch (err) {
    console.error("Error en login", err);
    loginErrorEl.textContent = "No se pudo conectar con el backend.";
    loginErrorEl.classList.remove("hidden");
  }
});

const formRegistro = document.getElementById("form-registro");
const registroErrorEl = document.getElementById("registro-error");

formRegistro.addEventListener("submit", async (event) => {
  event.preventDefault();
  registroErrorEl.classList.add("hidden");

  const email = document.getElementById("registro-email").value;
  const password = document.getElementById("registro-password").value;

  try {
    const res = await fetch("/api/auth/registro", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    const data = await res.json();

    if (!res.ok) {
      registroErrorEl.textContent =
        typeof data.detail === "string" ? data.detail : "No se pudo crear la cuenta.";
      registroErrorEl.classList.remove("hidden");
      return;
    }

    // Cuenta creada: iniciar sesion automaticamente con las mismas credenciales.
    const bodyLogin = new URLSearchParams();
    bodyLogin.set("username", email);
    bodyLogin.set("password", password);
    const resLogin = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: bodyLogin,
    });
    const dataLogin = await resLogin.json();

    if (!resLogin.ok) {
      registroErrorEl.textContent = "Cuenta creada. Inicia sesion manualmente.";
      registroErrorEl.classList.remove("hidden");
      return;
    }

    guardarToken(dataLogin.access_token);
    mostrarApp();
  } catch (err) {
    console.error("Error en registro", err);
    registroErrorEl.textContent = "No se pudo conectar con el backend.";
    registroErrorEl.classList.remove("hidden");
  }
});

document.getElementById("btn-logout").addEventListener("click", () => {
  borrarToken();
  window.location.reload();
});

// ---------- Recuperacion de contraseña: paso 1 (pedir email) ----------
const formOlvido = document.getElementById("form-olvido");
const olvidoMensajeEl = document.getElementById("olvido-mensaje");

formOlvido.addEventListener("submit", async (event) => {
  event.preventDefault();
  const email = document.getElementById("olvido-email").value;
  const boton = formOlvido.querySelector('button[type="submit"]');
  boton.disabled = true;
  olvidoMensajeEl.classList.add("hidden");

  try {
    const res = await fetch("/api/auth/olvido-password", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    });
    const data = await res.json();
    olvidoMensajeEl.textContent =
      data.mensaje ?? "Si el email existe en nuestro sistema, recibiras un enlace en breve.";
    olvidoMensajeEl.classList.remove("hidden");
  } catch (err) {
    console.error("Error en olvido-password", err);
    olvidoMensajeEl.textContent = "No se pudo conectar con el backend.";
    olvidoMensajeEl.classList.remove("hidden");
  } finally {
    boton.disabled = false;
  }
});

// ---------- Recuperacion de contraseña: paso 2 (nueva contraseña) ----------
const formReset = document.getElementById("form-reset");
const resetErrorEl = document.getElementById("reset-error");

formReset.addEventListener("submit", async (event) => {
  event.preventDefault();
  resetErrorEl.classList.add("hidden");
  const nuevaPassword = document.getElementById("reset-password").value;

  try {
    const res = await fetch("/api/auth/reset-password", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token: resetTokenActual, nueva_password: nuevaPassword }),
    });
    const data = await res.json();

    if (!res.ok) {
      resetErrorEl.textContent = data.detail ?? "No se pudo actualizar la contraseña.";
      resetErrorEl.classList.remove("hidden");
      return;
    }

    resetTokenActual = null;
    mostrarPanelAuth("login");
    mostrarToast("Contraseña actualizada. Ya puedes iniciar sesion.", "success");
  } catch (err) {
    console.error("Error en reset-password", err);
    resetErrorEl.textContent = "No se pudo conectar con el backend.";
    resetErrorEl.classList.remove("hidden");
  }
});

const form = document.getElementById("form-marca");
const resultadoBox = document.getElementById("resultado");
const tablaDetalle = document.getElementById("tabla-detalle");
const recomendacionBox = document.getElementById("recomendacion");
const notaGlobalEl = document.getElementById("nota-global");
const ultimaFechaEl = document.getElementById("ultima-fecha");

const formTeorica = document.getElementById("form-teorica");
const resultadoTeoricaBox = document.getElementById("resultado-teorica");
const notaTeoricaResultadoEl = document.getElementById("nota-teorica-resultado");

const dashboardNotaTotalEl = document.getElementById("dashboard-nota-total");
const dashboardNotaFisicaEl = document.getElementById("dashboard-nota-fisica");
const dashboardNotaTeoricaEl = document.getElementById("dashboard-nota-teorica");
const dashboardVeredictoEl = document.getElementById("dashboard-veredicto");
const barraFisicaEl = document.getElementById("barra-fisica");
const barraTeoricaEl = document.getElementById("barra-teorica");

const tabButtons = document.querySelectorAll(".tab-btn");
const tabPanels = {
  fisico: document.getElementById("panel-fisico"),
  teorico: document.getElementById("panel-teorico"),
};

tabButtons.forEach((btn) => {
  btn.addEventListener("click", () => {
    tabButtons.forEach((b) => b.classList.toggle("active", b === btn));
    Object.values(tabPanels).forEach((panel) => panel.classList.add("hidden"));
    tabPanels[btn.dataset.tab].classList.remove("hidden");
  });
});

// Navegacion principal (SPA basica): Dashboard Analitico <-> Guia del Opositor <-> Zona Premium
const navButtons = document.querySelectorAll(".nav-view-btn");
const views = {
  dashboard: document.getElementById("view-dashboard"),
  guia: document.getElementById("view-guia"),
  premium: document.getElementById("view-premium"),
};

function activarVista(nombre) {
  navButtons.forEach((btn) => {
    const activo = btn.dataset.view === nombre;
    btn.classList.toggle("active", activo);
  });
  Object.entries(views).forEach(([nombreVista, el]) => {
    el.classList.toggle("hidden", nombreVista !== nombre);
  });

  if (nombre === "premium" && proEstaDesbloqueado()) {
    cargarZonaPremium();
    verificarTourPremium();
  }
}

navButtons.forEach((btn) => {
  btn.addEventListener("click", () => activarVista(btn.dataset.view));
});

// ---------- Zona Premium: muro de pago (simulado) ----------
// La clave se namespacea por usuario_id (extraido del JWT) para que dos
// cuentas distintas en el mismo navegador no compartan el desbloqueo.
// Un unico muro de pago para toda la Zona Premium (Tablon, Tutor IA,
// Simulacros, grafica/entrenamiento): antes cada modulo llevaba su
// propio candado y podian desincronizarse entre si (ver Bug 1 del tablon).
const premiumLockedBox = document.getElementById("premium-locked");
const premiumUnlockedBox = document.getElementById("premium-unlocked");
const btnDesbloquear = document.getElementById("btn-desbloquear");

function clavePlanPro() {
  const usuarioId = obtenerUsuarioIdDesdeToken();
  return usuarioId ? `plan_pro_desbloqueado_${usuarioId}` : "plan_pro_desbloqueado";
}

function proEstaDesbloqueado() {
  return localStorage.getItem(clavePlanPro()) === "true";
}

function desbloquearPremium() {
  localStorage.setItem(clavePlanPro(), "true");
  premiumLockedBox.classList.add("hidden");
  premiumUnlockedBox.classList.remove("hidden");
  cargarZonaPremium();
}

function mostrarEstadoPremium() {
  const desbloqueado = proEstaDesbloqueado();
  premiumLockedBox.classList.toggle("hidden", desbloqueado);
  premiumUnlockedBox.classList.toggle("hidden", !desbloqueado);
}

async function iniciarCheckoutStripe(boton) {
  const textoOriginal = boton.textContent;
  boton.disabled = true;
  boton.textContent = "Redirigiendo a pago seguro...";

  try {
    const res = await fetchAutenticado("/api/pagos/checkout", { method: "POST" });
    const data = await res.json();

    if (!res.ok) {
      mostrarToast(data.detail ?? "No se pudo iniciar el pago.", "error");
      boton.disabled = false;
      boton.textContent = textoOriginal;
      return;
    }

    window.location.href = data.url;
  } catch (err) {
    console.error("No se pudo iniciar el checkout de Stripe", err);
    mostrarToast("No se pudo conectar con el backend de pagos.", "error");
    boton.disabled = false;
    boton.textContent = textoOriginal;
  }
}

btnDesbloquear.addEventListener("click", () => iniciarCheckoutStripe(btnDesbloquear));

// ---------- Plan Pro: Portal de Cliente de Stripe (gestion de suscripcion) ----------
const btnGestionarSuscripcion = document.getElementById("btn-gestionar-suscripcion");

async function iniciarPortalStripe(boton) {
  const textoOriginal = boton.textContent;
  boton.disabled = true;
  boton.textContent = "Abriendo portal...";

  try {
    const res = await fetchAutenticado("/api/pagos/portal", { method: "POST" });
    const data = await res.json();

    if (!res.ok) {
      mostrarToast(data.detail ?? "No se pudo abrir el portal de suscripcion.", "error");
      boton.disabled = false;
      boton.textContent = textoOriginal;
      return;
    }

    window.location.href = data.url;
  } catch (err) {
    console.error("No se pudo abrir el portal de Stripe", err);
    mostrarToast("No se pudo conectar con el backend de pagos.", "error");
    boton.disabled = false;
    boton.textContent = textoOriginal;
  }
}

btnGestionarSuscripcion.addEventListener("click", () => iniciarPortalStripe(btnGestionarSuscripcion));

// ---------- Toasts ----------
function mostrarToast(mensaje, tipo = "info") {
  let contenedor = document.getElementById("toast-container");
  if (!contenedor) {
    contenedor = document.createElement("div");
    contenedor.id = "toast-container";
    document.body.appendChild(contenedor);
  }

  const toast = document.createElement("div");
  toast.className = `toast toast-${tipo}`;
  toast.textContent = mensaje;
  contenedor.appendChild(toast);

  requestAnimationFrame(() => toast.classList.add("show"));
  setTimeout(() => {
    toast.classList.remove("show");
    setTimeout(() => toast.remove(), 300);
  }, 4500);
}

// ---------- Retorno desde Stripe Checkout (?pago=exito|cancelado) ----------
function procesarRetornoDePago() {
  const params = new URLSearchParams(window.location.search);
  const pago = params.get("pago");
  if (!pago) return;

  if (pago === "exito") {
    desbloquearPremium();
    activarVista("premium");
    mostrarToast("¡Bienvenido a la Zona Premium! Ya tienes acceso a todos los modulos.", "success");
  } else if (pago === "cancelado") {
    mostrarToast("El pago no se ha completado. Puedes intentarlo de nuevo cuando quieras.", "error");
  }

  params.delete("pago");
  const queryLimpia = params.toString();
  const urlLimpia = window.location.pathname + (queryLimpia ? `?${queryLimpia}` : "") + window.location.hash;
  window.history.replaceState({}, document.title, urlLimpia);
}

let graficaEvolucion = null;

// Estado Vacio: se usa tanto cuando el usuario aun no tiene registros como
// cuando la peticion falla, para que la grafica nunca se quede rota o en
// blanco sin explicacion (ver Bug 2 del refactor de UI).
function mostrarEstadoVacioGrafica(mensaje) {
  const canvas = document.getElementById("grafica-evolucion");
  const vaciaMsg = document.getElementById("grafica-vacia");
  canvas.classList.add("hidden");
  vaciaMsg.textContent = mensaje;
  vaciaMsg.classList.remove("hidden");
}

async function cargarGraficaEvolucion() {
  const canvas = document.getElementById("grafica-evolucion");
  const vaciaMsg = document.getElementById("grafica-vacia");

  try {
    const res = await fetchAutenticado("/api/dashboard/evolucion");
    if (!res.ok) {
      mostrarEstadoVacioGrafica("No se pudo cargar tu evolucion ahora mismo. Intentalo de nuevo en unos minutos.");
      return;
    }

    const data = await res.json();
    const puntos = data.puntos || [];

    if (puntos.length === 0) {
      mostrarEstadoVacioGrafica("Registra tus primeras marcas fisicas para visualizar tu evolucion.");
      return;
    }

    canvas.classList.remove("hidden");
    vaciaMsg.classList.add("hidden");

    const etiquetas = puntos.map((p) => p.fecha);
    const valores = puntos.map((p) => p.nota_global_combinada);

    if (graficaEvolucion) {
      graficaEvolucion.data.labels = etiquetas;
      graficaEvolucion.data.datasets[0].data = valores;
      graficaEvolucion.update();
      return;
    }

    graficaEvolucion = new Chart(canvas, {
      type: "line",
      data: {
        labels: etiquetas,
        datasets: [
          {
            label: "Nota Global Oposicion",
            data: valores,
            borderColor: "#f59e0b",
            backgroundColor: "rgba(245, 158, 11, 0.15)",
            borderWidth: 2,
            tension: 0.3,
            fill: true,
            pointBackgroundColor: "#ea580c",
            pointRadius: 4,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          y: {
            min: 0,
            max: 10,
            grid: { color: "rgba(255,255,255,0.08)" },
            ticks: { color: "#9ca3af" },
          },
          x: {
            grid: { color: "rgba(255,255,255,0.05)" },
            ticks: { color: "#9ca3af" },
          },
        },
        plugins: {
          legend: { labels: { color: "#e5e7eb" } },
        },
      },
    });
  } catch (err) {
    console.error("No se pudo cargar la evolucion", err);
    mostrarEstadoVacioGrafica("No se pudo cargar tu evolucion ahora mismo. Intentalo de nuevo en unos minutos.");
  }
}

async function cargarEntrenamientoEspecifico() {
  const contenedor = document.getElementById("entrenamiento-contenido");
  try {
    const res = await fetchAutenticado("/api/pro/entrenamiento");
    if (!res.ok) {
      const error = await res.json();
      contenedor.innerHTML = `<p class="text-gray-500">${error.detail ?? "No se pudo generar el entrenamiento."}</p>`;
      return;
    }
    const data = await res.json();
    const rutina = data.rutina;
    const fases = rutina.entrenamiento_semanal;

    const timeline = fases
      .map((paso, indice) => {
        const esUltima = indice === fases.length - 1;
        return `
        <div class="fase-item">
          <div class="fase-node">
            <span class="fase-numero">${indice + 1}</span>
            ${esUltima ? "" : '<span class="fase-linea"></span>'}
          </div>
          <div class="fase-contenido">
            <p class="fase-titulo">${paso.fase}</p>
            <div class="fase-badges">
              <span class="badge-stat badge-intensidad">
                <svg xmlns="http://www.w3.org/2000/svg" class="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M13 2 3 14h7l-1 8 11-14h-7l1-6z"/></svg>
                ${paso.intensidad}
              </span>
              <span class="badge-stat badge-volumen">
                <svg xmlns="http://www.w3.org/2000/svg" class="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 12h16M4 18h10"/></svg>
                ${paso.volumen}
              </span>
            </div>
            <p class="fase-detalle">${paso.detalle}</p>
            <div class="fundamento-box">
              <span>&#128161;</span>
              <span><strong>Por que funciona:</strong> ${paso.fundamento}</span>
            </div>
          </div>
        </div>`;
      })
      .join("");

    const referencias = rutina.bibliografia
      .split(/;\s*/)
      .map((ref) => ref.trim())
      .filter(Boolean);
    const bibliografia = referencias
      .map(
        (ref) => `
        <div class="biblio-item">
          <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5 flex-shrink-0 mt-0.5 text-amber-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path stroke-linecap="round" stroke-linejoin="round" d="M12 6.25C10.5 5 8.4 4.5 6 4.5c-.83 0-1.63.08-2.4.24A1 1 0 0 0 3 5.72v12.06a1 1 0 0 0 1.2.98c.7-.15 1.44-.22 2.2-.22 2.1 0 4.02.55 5.6 1.7m0-14.01c1.5-1.25 3.6-1.75 6-1.75.83 0 1.63.08 2.4.24a1 1 0 0 1 .6.98v12.06a1 1 0 0 1-1.2.98 11 11 0 0 0-2.2-.22c-2.1 0-4.02.55-5.6 1.7m0-14.01v14.01"/></svg>
          <span>${ref}</span>
        </div>`
      )
      .join("");

    contenedor.innerHTML = `
      <div class="mb-5 inline-flex items-center gap-2 bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs rounded-full px-3 py-1.5">
        <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m9-.75a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-8.99 3.75h.008v.008h-.008v-.008Z"/></svg>
        Punto debil detectado: ${data.nombre} (${data.puntos_actuales.toFixed(2)} / 10)
      </div>

      <h4 class="text-white font-bold text-xl mb-3 leading-snug">${rutina.titulo}</h4>

      <div class="cientifica-callout">
        <p class="text-xs font-semibold uppercase tracking-wide text-amber-400 mb-1.5">Base cientifica</p>
        ${rutina.descripcion_cientifica}
      </div>

      <p class="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-4">Programa semanal</p>
      <div class="fase-timeline mb-6">${timeline}</div>

      <p class="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-2">Bibliografia</p>
      <div class="space-y-2">${bibliografia}</div>
    `;
  } catch (err) {
    console.error("No se pudo cargar el entrenamiento especifico", err);
    contenedor.innerHTML = `<p class="text-gray-500">No se pudo conectar con el backend.</p>`;
  }
}

async function cargarTecnicasEstudio() {
  const contenedor = document.getElementById("tecnicas-estudio-contenido");
  try {
    const res = await fetchAutenticado("/api/pro/teorica");
    if (!res.ok) {
      contenedor.innerHTML = `<p class="text-gray-500">No se pudieron cargar las tecnicas de estudio.</p>`;
      return;
    }
    const data = await res.json();

    contenedor.innerHTML = data.tecnicas
      .map((tecnica) => {
        const pasos = tecnica.paso_a_paso
          .map(
            (paso) => `
            <li class="flex items-start gap-2.5">
              <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 text-amber-400 flex-shrink-0 mt-0.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="m4.5 12.75 6 6 9-13.5"/></svg>
              <span>${paso}</span>
            </li>`
          )
          .join("");

        return `
        <article class="tecnica-card">
          <h4 class="text-white font-bold text-lg mb-2">${tecnica.nombre}</h4>
          <p class="text-sm text-gray-400 leading-relaxed mb-4">${tecnica.concepto_cientifico}</p>
          <p class="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-2">Como aplicarla</p>
          <ul class="space-y-2 text-sm text-gray-300 mb-4">${pasos}</ul>
          <div class="ejemplo-destacado">
            <p class="text-xs font-semibold uppercase tracking-wide text-amber-300 mb-1.5">Ejemplo aplicado al temario</p>
            <p class="text-sm text-gray-100 leading-relaxed">${tecnica.ejemplo_aplicado}</p>
          </div>
        </article>`;
      })
      .join("");
  } catch (err) {
    console.error("No se pudieron cargar las tecnicas de estudio", err);
    contenedor.innerHTML = `<p class="text-gray-500">No se pudo conectar con el backend.</p>`;
  }
}

// ---------- Zona Premium: Tablon de Plazas en Tiempo Real ----------
const tablonContenido = document.getElementById("tablon-convocatorias-contenido");

function pintarConvocatorias(convocatorias) {
  tablonContenido.innerHTML = convocatorias
    .map(
      (c) => `
      <article class="convocatoria-card">
        <p class="convocatoria-titulo">${c.titulo_plaza}</p>
        <p class="convocatoria-meta">${c.organismo_localidad}</p>
        <span class="convocatoria-plazo">${
          c.plazo_dias != null ? `Quedan ${c.plazo_dias} dias` : "Plazo no especificado"
        }</span>
        <p class="convocatoria-requisitos">${c.requisitos_minimos ?? "Sin requisitos detallados"}</p>
        <button type="button" class="btn-plan-ia" data-convocatoria-id="${c.id}">
          &#9889; Generar Plan de Estudio IA
        </button>
        <div class="plan-ia-contenido hidden"></div>
      </article>`
    )
    .join("");
}

// Delegacion de eventos: las tarjetas se regeneran en cada carga del tablon,
// asi que un listener fijo en el contenedor evita tener que re-engancharlo
// cada vez que pintarConvocatorias() reescribe el innerHTML.
tablonContenido.addEventListener("click", async (event) => {
  const boton = event.target.closest(".btn-plan-ia");
  if (!boton) return;

  const convocatoriaId = boton.dataset.convocatoriaId;
  const tarjeta = boton.closest(".convocatoria-card");
  const contenedorPlan = tarjeta.querySelector(".plan-ia-contenido");
  const textoOriginal = boton.textContent;

  boton.disabled = true;
  boton.textContent = "Analizando convocatoria...";

  try {
    const res = await fetchAutenticado(`/api/tutor/analizar-plaza/${convocatoriaId}`, {
      method: "POST",
    });
    const data = await res.json();

    if (!res.ok) {
      mostrarToast(data.detail ?? "No se pudo generar el plan de estudio.", "error");
      return;
    }

    // El plan viene en Markdown: se convierte a HTML con marked.js y se
    // sanitiza con DOMPurify antes de insertarlo (mismo patron que el chat
    // del Tutor IA, ver pintarBurbujaChat()).
    contenedorPlan.innerHTML = DOMPurify.sanitize(marked.parse(data.plan_estudio_md));
    contenedorPlan.classList.remove("hidden");
  } catch (err) {
    console.error("No se pudo generar el plan de estudio IA", err);
    mostrarToast("No se pudo conectar con el backend.", "error");
  } finally {
    boton.disabled = false;
    boton.textContent = textoOriginal;
  }
});

async function cargarTablonConvocatorias() {
  try {
    const res = await fetchAutenticado("/api/convocatorias");

    if (res.status === 403) {
      // La Zona Premium ya se muestra desbloqueada en local (proEstaDesbloqueado
      // dio true), pero el backend -la fuente real de verdad para is_pro- dice
      // lo contrario. No se pinta ninguna capa/CTA de bloqueo sobre las plazas
      // (ver Bug 1 del refactor de UI): solo un aviso de texto, sin duplicar el
      // muro de pago que ya vive en la Zona Premium.
      tablonContenido.innerHTML = `<p class="text-gray-500">No se pudo verificar tu Plan Pro para el Tablon. Si acabas de pagar, recarga la pagina en unos segundos.</p>`;
      return;
    }

    if (!res.ok) {
      tablonContenido.innerHTML = `<p class="text-gray-500">No se pudo cargar el tablon de convocatorias.</p>`;
      return;
    }

    const data = await res.json();
    pintarConvocatorias(data);
  } catch (err) {
    console.error("No se pudo cargar el tablon de convocatorias", err);
    tablonContenido.innerHTML = `<p class="text-gray-500">No se pudo conectar con el backend.</p>`;
  }
}

function cargarZonaPremium() {
  cargarGraficaEvolucion();
  cargarEntrenamientoEspecifico();
  cargarTecnicasEstudio();
  cargarTablonConvocatorias();
}

// ---------- Tour Guiado: onboarding de la Zona Premium ----------
// Se muestra una unica vez por usuario (is_pro real + tour_premium_completado
// en false, ver GET /api/usuarios/me), la primera vez que entra en la Zona
// Premium. Al terminar se registra en el backend para no volver a mostrarlo.
const PASOS_TOUR_PREMIUM = [
  {
    selector: "#tour-tablon",
    texto: "El radar activado. Filtramos el ruido y te mostramos solo plazas reales de emergencias. Usa la IA para analizar los requisitos en segundos.",
  },
  {
    selector: "#tour-tutor",
    texto: "Tu sargento 24/7. Pregúntale dudas técnicas sobre el CTE, hidráulica o legislación. Nunca duerme.",
  },
  {
    selector: "#tour-simulacros",
    texto: "Fuego real. Genera exámenes tipo test a medida basados en el temario oficial para blindar tus conocimientos.",
  },
];

let pasoTourActual = 0;
let elementoResaltadoTour = null;
let overlayTourEl = null;
let tooltipTourEl = null;

function limpiarResaltadoTour() {
  if (elementoResaltadoTour) {
    elementoResaltadoTour.classList.remove("tour-highlight");
    elementoResaltadoTour = null;
  }
}

function posicionarTooltipTour(elementoResaltado) {
  const margen = 12;
  const rect = elementoResaltado.getBoundingClientRect();

  tooltipTourEl.style.top = `${rect.bottom + window.scrollY + margen}px`;
  tooltipTourEl.style.left = `${rect.left + window.scrollX}px`;

  // Si se sale por la derecha de la ventana, lo pegamos al borde (con
  // margen), una vez que el navegador ya calculo su ancho real.
  requestAnimationFrame(() => {
    const maximoLeft = window.innerWidth - tooltipTourEl.offsetWidth - 20;
    if (rect.left + window.scrollX > maximoLeft) {
      tooltipTourEl.style.left = `${Math.max(20, maximoLeft)}px`;
    }
  });
}

function pintarPasoTour(indice) {
  limpiarResaltadoTour();

  const paso = PASOS_TOUR_PREMIUM[indice];
  const elemento = document.querySelector(paso.selector);
  if (!elemento) {
    avanzarTour();
    return;
  }

  elemento.scrollIntoView({ behavior: "smooth", block: "center" });
  elemento.classList.add("tour-highlight");
  elementoResaltadoTour = elemento;

  const esUltimoPaso = indice === PASOS_TOUR_PREMIUM.length - 1;
  tooltipTourEl.innerHTML = `
    <p class="tour-tooltip-paso">Paso ${indice + 1} de ${PASOS_TOUR_PREMIUM.length}</p>
    <p class="tour-tooltip-texto">${paso.texto}</p>
    <div class="tour-tooltip-acciones">
      <button type="button" id="btn-tour-siguiente" class="btn-primary px-5">
        ${esUltimoPaso ? "Finalizar" : "Siguiente"}
      </button>
    </div>
  `;
  document.getElementById("btn-tour-siguiente").addEventListener("click", avanzarTour);

  posicionarTooltipTour(elemento);
}

function avanzarTour() {
  pasoTourActual++;
  if (pasoTourActual >= PASOS_TOUR_PREMIUM.length) {
    finalizarTourPremium();
    return;
  }
  pintarPasoTour(pasoTourActual);
}

function iniciarTourPremium() {
  pasoTourActual = 0;

  overlayTourEl = document.createElement("div");
  overlayTourEl.className = "tour-overlay";
  document.body.appendChild(overlayTourEl);

  tooltipTourEl = document.createElement("div");
  tooltipTourEl.className = "tour-tooltip";
  document.body.appendChild(tooltipTourEl);

  pintarPasoTour(pasoTourActual);
}

async function finalizarTourPremium() {
  limpiarResaltadoTour();
  overlayTourEl?.remove();
  tooltipTourEl?.remove();
  overlayTourEl = null;
  tooltipTourEl = null;

  // Fetch silencioso: el usuario ya vio el tour completo delante suyo, no le
  // bloqueamos ni avisamos si esto falla (en la proxima visita se volveria a
  // verificar contra el backend y, como mucho, se le mostraria otra vez).
  try {
    await fetchAutenticado("/api/usuarios/tour-completado", { method: "POST" });
  } catch (err) {
    console.error("No se pudo registrar el tour premium como completado", err);
  }
}

async function verificarTourPremium() {
  try {
    const res = await fetchAutenticado("/api/usuarios/me");
    if (!res.ok) return;
    const perfil = await res.json();
    if (perfil.is_pro && !perfil.tour_premium_completado) {
      iniciarTourPremium();
    }
  } catch (err) {
    console.error("No se pudo verificar el estado del tour premium", err);
  }
}

// ---------- Tutor Inteligente 24/7 (chat RAG) ----------
const formChat = document.getElementById("form-chat");
const chatInput = document.getElementById("chat-input");
const chatMensajesEl = document.getElementById("chat-mensajes");

function pintarBurbujaChat(texto, autor) {
  const burbuja = document.createElement("div");
  burbuja.className = `chat-bubble chat-bubble-${autor}`;
  burbuja.innerHTML = `
    <span class="chat-avatar">${autor === "ia" ? "&#128657;" : "&#128100;"}</span>
    <div class="chat-texto"></div>
  `;

  const textoEl = burbuja.querySelector(".chat-texto");
  if (autor === "ia") {
    // El tutor responde en Markdown: se convierte a HTML con marked.js y se
    // sanitiza con DOMPurify antes de insertarlo. marked.js NO sanitiza por
    // si solo — sin DOMPurify, una respuesta con HTML/JS incrustado (via
    // prompt injection desde un PDF cargado, por ejemplo) se ejecutaria tal
    // cual en la pagina.
    textoEl.innerHTML = DOMPurify.sanitize(marked.parse(texto));
  } else {
    // El texto del propio usuario nunca se interpreta como HTML.
    textoEl.textContent = texto;
  }

  chatMensajesEl.appendChild(burbuja);
  chatMensajesEl.scrollTop = chatMensajesEl.scrollHeight;
  return burbuja;
}

function pintarEscribiendo() {
  const burbuja = document.createElement("div");
  burbuja.className = "chat-bubble chat-bubble-ia";
  burbuja.id = "chat-escribiendo";
  burbuja.innerHTML = `
    <span class="chat-avatar">&#128657;</span>
    <div class="chat-texto">
      <span class="chat-escribiendo-dots"><span></span><span></span><span></span></span>
    </div>
  `;
  chatMensajesEl.appendChild(burbuja);
  chatMensajesEl.scrollTop = chatMensajesEl.scrollHeight;
}

function quitarEscribiendo() {
  document.getElementById("chat-escribiendo")?.remove();
}

if (formChat) {
  formChat.addEventListener("submit", async (event) => {
    event.preventDefault();
    const texto = chatInput.value.trim();
    if (!texto) return;

    pintarBurbujaChat(texto, "usuario");
    chatInput.value = "";
    chatInput.disabled = true;
    pintarEscribiendo();

    try {
      const res = await fetchAutenticado("/api/pro/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mensaje: texto }),
      });
      const data = await res.json();
      quitarEscribiendo();

      if (!res.ok) {
        pintarBurbujaChat(data.detail ?? "El tutor no esta disponible ahora mismo.", "ia");
      } else {
        pintarBurbujaChat(data.respuesta, "ia");
      }
    } catch (err) {
      console.error("No se pudo contactar al tutor IA", err);
      quitarEscribiendo();
      pintarBurbujaChat("No se pudo conectar con el tutor. Intentalo de nuevo.", "ia");
    } finally {
      chatInput.disabled = false;
      chatInput.focus();
    }
  });
}

function minSegAsegundos(minInputId, segInputId) {
  const min = Number(document.getElementById(minInputId).value || 0);
  const seg = Number(document.getElementById(segInputId).value || 0);
  return min * 60 + seg;
}

function pintarResultado(data) {
  tablaDetalle.innerHTML = "";
  for (const clave in data.detalle) {
    const prueba = data.detalle[clave];
    const fila = document.createElement("tr");
    fila.className = "border-b border-slate-100";
    fila.innerHTML = `
      <td class="py-1">${prueba.nombre}</td>
      <td class="py-1">${prueba.valor} ${prueba.unidad}</td>
      <td class="py-1 font-semibold">${prueba.puntos.toFixed(2)}</td>
    `;
    tablaDetalle.appendChild(fila);
  }

  if (data.recomendacion) {
    recomendacionBox.textContent = data.recomendacion.mensaje;
    recomendacionBox.classList.remove("hidden");
  } else {
    recomendacionBox.textContent = "Ya tienes 10 puntos en todas las pruebas.";
  }

  resultadoBox.classList.remove("hidden");
  notaGlobalEl.textContent = `${data.nota_global.toFixed(2)} / 10`;
  ultimaFechaEl.textContent = `Registrado el ${data.marca.fecha}`;
}

function pintarResultadoTeorica(data) {
  notaTeoricaResultadoEl.textContent = data.nota_calculada.toFixed(2);
  resultadoTeoricaBox.classList.remove("hidden");
}

async function cargarDashboardGlobal() {
  try {
    const res = await fetchAutenticado("/api/dashboard/global");
    if (!res.ok) return;
    const data = await res.json();

    dashboardNotaTotalEl.textContent =
      data.nota_global_combinada !== null ? data.nota_global_combinada.toFixed(2) : "--";
    dashboardNotaFisicaEl.textContent = data.nota_fisica
      ? `${data.nota_fisica.valor.toFixed(2)} / ${data.nota_fisica.sobre}`
      : "Sin datos";
    dashboardNotaTeoricaEl.textContent = data.nota_teorica
      ? `${data.nota_teorica.valor.toFixed(2)} / ${data.nota_teorica.sobre}`
      : "Sin datos";
    dashboardVeredictoEl.textContent = data.veredicto;

    barraFisicaEl.style.width = data.nota_fisica ? `${data.nota_fisica.porcentaje * 100}%` : "0%";
    barraTeoricaEl.style.width = data.nota_teorica ? `${data.nota_teorica.porcentaje * 100}%` : "0%";
  } catch (err) {
    console.error("No se pudo cargar el dashboard global", err);
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const payload = {
    fecha: document.getElementById("fecha").value || null,
    dominadas: Number(document.getElementById("dominadas").value),
    sprint_100m: Number(document.getElementById("sprint").value),
    carrera_1500m: minSegAsegundos("carrera_min", "carrera_seg"),
    natacion_100m: minSegAsegundos("natacion_min", "natacion_seg"),
  };

  try {
    const res = await fetchAutenticado("/api/marcas", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const error = await res.json();
      alert(`Error al guardar: ${JSON.stringify(error.detail ?? error)}`);
      return;
    }

    const data = await res.json();
    pintarResultado(data);
    cargarDashboardGlobal();
  } catch (err) {
    console.error(err);
    alert("No se pudo conectar con el backend.");
  }
});

// ---------- Racha de Actividad (Heatmap estilo GitHub) ----------
const heatmapContainer = document.getElementById("heatmap-container");

function nivelIntensidad(intensity) {
  if (intensity >= 2) return "intensity-2";
  if (intensity === 1) return "intensity-1";
  return null;
}

function renderHeatmap(data) {
  const intensidadPorFecha = new Map(data.map((d) => [d.date, d.intensity]));
  heatmapContainer.innerHTML = "";

  const hoy = new Date();
  for (let i = data.length - 1; i >= 0; i--) {
    const fecha = new Date(hoy);
    fecha.setDate(hoy.getDate() - i);
    const clave = fecha.toISOString().slice(0, 10);

    const celda = document.createElement("div");
    celda.className = "heatmap-cell";
    const intensidad = intensidadPorFecha.get(clave) ?? 0;
    const clase = nivelIntensidad(intensidad);
    if (clase) celda.classList.add(clase);
    celda.title = `${clave}: ${intensidad} actividad${intensidad === 1 ? "" : "es"}`;

    heatmapContainer.appendChild(celda);
  }
}

async function cargarHeatmap() {
  try {
    const res = await fetchAutenticado("/api/actividad/heatmap");
    if (!res.ok) return;
    const data = await res.json();
    renderHeatmap(data);
  } catch (err) {
    console.error("No se pudo cargar el heatmap de actividad", err);
  }
}

formTeorica.addEventListener("submit", async (event) => {
  event.preventDefault();

  const payload = {
    fecha: document.getElementById("teorica-fecha").value || null,
    aciertos: Number(document.getElementById("aciertos").value),
    fallos: Number(document.getElementById("fallos").value),
    blancos: Number(document.getElementById("blancos").value),
  };

  try {
    const res = await fetchAutenticado("/api/teorica", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const error = await res.json();
      alert(`Error al guardar: ${JSON.stringify(error.detail ?? error)}`);
      return;
    }

    const data = await res.json();
    pintarResultadoTeorica(data);
    cargarDashboardGlobal();
  } catch (err) {
    console.error(err);
    alert("No se pudo conectar con el backend.");
  }
});

// ---------- Simulacros (examen tipo test generado por IA) ----------
const simulacroTemaSelect = document.getElementById("simulacro-tema");
const simulacroNumPreguntasSelect = document.getElementById("simulacro-num-preguntas");
const btnGenerarSimulacro = document.getElementById("btn-generar-simulacro");
const simulacroConfigBox = document.getElementById("simulacro-config");
const simulacroTestBox = document.getElementById("simulacro-test");
const simulacroPreguntasEl = document.getElementById("simulacro-preguntas");
const btnCorregirSimulacro = document.getElementById("btn-corregir-simulacro");
const simulacroResultadoBox = document.getElementById("simulacro-resultado");
const simulacroNotaEl = document.getElementById("simulacro-nota");
const btnNuevoSimulacro = document.getElementById("btn-nuevo-simulacro");

// Preguntas del simulacro en curso, guardadas en memoria para poder
// corregirlas contra el indice "correcta" sin volver a llamar al backend.
let preguntasSimulacroActual = [];
let temaSimulacroActual = "";

function pintarPreguntasSimulacro(preguntas) {
  simulacroPreguntasEl.innerHTML = preguntas
    .map(
      (p, indice) => `
      <div class="simulacro-pregunta" data-indice="${indice}">
        <p class="simulacro-enunciado">${indice + 1}. ${p.pregunta}</p>
        <div class="simulacro-opciones">
          ${p.opciones
            .map(
              (opcion, opcionIndice) => `
            <label class="simulacro-opcion">
              <input type="radio" name="simulacro-pregunta-${indice}" value="${opcionIndice}" />
              <span>${opcion}</span>
            </label>`
            )
            .join("")}
        </div>
        <div class="simulacro-explicacion hidden"></div>
      </div>`
    )
    .join("");
}

btnGenerarSimulacro.addEventListener("click", async () => {
  const tema = simulacroTemaSelect.value;
  const numPreguntas = Number(simulacroNumPreguntasSelect.value);
  const textoOriginal = btnGenerarSimulacro.textContent;

  btnGenerarSimulacro.disabled = true;
  btnGenerarSimulacro.textContent = "Generando simulacro...";

  try {
    const res = await fetchAutenticado("/api/simulacros/generar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tema, num_preguntas: numPreguntas }),
    });
    const data = await res.json();

    if (!res.ok) {
      mostrarToast(data.detail ?? "No se pudo generar el simulacro.", "error");
      return;
    }

    preguntasSimulacroActual = data.preguntas;
    temaSimulacroActual = tema;

    pintarPreguntasSimulacro(preguntasSimulacroActual);
    simulacroResultadoBox.classList.add("hidden");
    simulacroConfigBox.classList.add("hidden");
    simulacroTestBox.classList.remove("hidden");
  } catch (err) {
    console.error("No se pudo generar el simulacro", err);
    mostrarToast("No se pudo conectar con el backend.", "error");
  } finally {
    btnGenerarSimulacro.disabled = false;
    btnGenerarSimulacro.textContent = textoOriginal;
  }
});

btnCorregirSimulacro.addEventListener("click", async () => {
  let aciertos = 0;

  document.querySelectorAll(".simulacro-pregunta").forEach((preguntaEl) => {
    const indice = Number(preguntaEl.dataset.indice);
    const correcta = preguntasSimulacroActual[indice].correcta;
    const opcionesEls = preguntaEl.querySelectorAll(".simulacro-opcion");
    const seleccionada = preguntaEl.querySelector(
      `input[name="simulacro-pregunta-${indice}"]:checked`
    );
    const valorSeleccionado = seleccionada ? Number(seleccionada.value) : null;

    if (valorSeleccionado === correcta) aciertos++;

    opcionesEls.forEach((opcionEl, opcionIndice) => {
      const input = opcionEl.querySelector("input");
      input.disabled = true;
      if (opcionIndice === correcta) {
        opcionEl.classList.add("opcion-correcta");
      } else if (opcionIndice === valorSeleccionado) {
        opcionEl.classList.add("opcion-incorrecta");
      }
    });

    const explicacionEl = preguntaEl.querySelector(".simulacro-explicacion");
    explicacionEl.textContent = preguntasSimulacroActual[indice].explicacion;
    explicacionEl.classList.remove("hidden");
  });

  const total = preguntasSimulacroActual.length;
  const nota = (aciertos / total) * 10;
  simulacroNotaEl.textContent = `${nota.toFixed(2)} / 10`;
  simulacroResultadoBox.classList.remove("hidden");
  btnCorregirSimulacro.classList.add("hidden");

  // Guardado silencioso: no bloqueamos ni avisamos al usuario si esto falla,
  // ya tiene su correccion delante y no queremos interrumpirle por un fallo
  // de persistencia que no afecta a lo que esta viendo.
  try {
    await fetchAutenticado("/api/simulacros/guardar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        tema: temaSimulacroActual,
        aciertos,
        total_preguntas: total,
      }),
    });
  } catch (err) {
    console.error("No se pudo guardar el resultado del simulacro", err);
  }
});

btnNuevoSimulacro.addEventListener("click", () => {
  preguntasSimulacroActual = [];
  simulacroPreguntasEl.innerHTML = "";
  simulacroResultadoBox.classList.add("hidden");
  simulacroTestBox.classList.add("hidden");
  btnCorregirSimulacro.classList.remove("hidden");
  simulacroConfigBox.classList.remove("hidden");
});

// ---------- Modo Enfoque (Pomodoro a pantalla completa) ----------
let timerInterval;
let tiempoRestante = 25 * 60; // 25 minutos en segundos
let timerCorriendo = false;
// Solo se guarda una SesionEstudio cuando termina un ciclo de TRABAJO, nunca
// un descanso; estas dos variables llevan la cuenta de cual de los dos esta
// corriendo ahora mismo.
let duracionCicloActualMinutos = 25;
let cicloActualEsTrabajo = true;

// Sonido de alarma al terminar la sesion de enfoque, cargado en memoria de antemano.
const sonidoAlarma = new Audio("https://cdn.pixabay.com/audio/2021/08/04/audio_0625c1539c.mp3");

const pantallaEnfoque = document.getElementById("pantalla-enfoque");
const timerDisplay = document.getElementById("timer-display");

// Interruptores de pantalla
document.getElementById("btn-activar-enfoque").addEventListener("click", () => {
  document.body.classList.add("modo-enfoque-activo");
  pantallaEnfoque.classList.remove("hidden");
});

document.getElementById("btn-desactivar-enfoque").addEventListener("click", () => {
  document.body.classList.remove("modo-enfoque-activo");
  pantallaEnfoque.classList.add("hidden");
  pausarTimer();
});

// Logica del temporizador
function actualizarDisplayTimer() {
  const minutos = Math.floor(tiempoRestante / 60);
  const segundos = tiempoRestante % 60;
  timerDisplay.textContent = `${minutos.toString().padStart(2, "0")}:${segundos.toString().padStart(2, "0")}`;
}

function iniciarTimer() {
  if (timerCorriendo) return;
  timerCorriendo = true;
  timerInterval = setInterval(() => {
    if (tiempoRestante > 0) {
      tiempoRestante--;
      actualizarDisplayTimer();
    } else {
      // EL TIEMPO SE HA ACABADO
      clearInterval(timerInterval);
      timerCorriendo = false;

      sonidoAlarma.play().catch((err) => {
        // Los navegadores pueden bloquear el audio si no detectan gesto
        // reciente del usuario; no rompemos el flujo si esto pasa.
        console.warn("No se pudo reproducir el sonido de alarma", err);
      });

      // A diferencia de alert() (que bloquea el hilo y podria cortar el
      // audio), mostrarToast() no bloquea nada, asi que no hace falta
      // ningun setTimeout para dar margen a que el audio empiece a sonar.
      mostrarToast("¡Sesion de enfoque terminada! Tomate un descanso.", "success");

      if (cicloActualEsTrabajo) {
        guardarSesionEstudio(duracionCicloActualMinutos);
      }
    }
  }, 1000);
}

async function guardarSesionEstudio(duracionMinutos) {
  try {
    const res = await fetchAutenticado("/api/actividad/sesion-estudio", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ duracion_minutos: duracionMinutos }),
    });
    if (res.ok) cargarHeatmap();
  } catch (err) {
    // No interrumpimos la celebracion del Pomodoro por esto: se registra
    // en consola y ya esta, la sesion en si ya se completo igualmente.
    console.error("No se pudo guardar la sesion de estudio", err);
  }
}

function pausarTimer() {
  clearInterval(timerInterval);
  timerCorriendo = false;
}

function reiniciarTimer() {
  pausarTimer();
  tiempoRestante = 25 * 60;
  duracionCicloActualMinutos = 25;
  cicloActualEsTrabajo = true;
  actualizarDisplayTimer();
}

document.getElementById("btn-timer-start").addEventListener("click", iniciarTimer);
document.getElementById("btn-timer-pause").addEventListener("click", pausarTimer);
document.getElementById("btn-timer-reset").addEventListener("click", reiniciarTimer);

document.getElementById("btn-timer-descanso").addEventListener("click", () => {
  pausarTimer();
  tiempoRestante = 5 * 60; // Lo ponemos en 5 minutos
  duracionCicloActualMinutos = 5;
  cicloActualEsTrabajo = false;
  actualizarDisplayTimer();
});

// ---------- Arranque: parametros de la URL (?token=, ?reset_token=) o token guardado ----------
// "token" lo pone /api/auth/google/callback al redirigir (login ya resuelto).
// "reset_token" lo pone el enlace del email de recuperacion (aun falta que el
// usuario escriba la contraseña nueva). Se usan claves distintas a proposito
// para no confundir un JWT de sesion con un token de un solo uso de 15 min.
function procesarParametrosDeAcceso() {
  const params = new URLSearchParams(window.location.search);
  const tokenGoogle = params.get("token");
  const tokenReset = params.get("reset_token");

  if (!tokenGoogle && !tokenReset) return false;

  params.delete("token");
  params.delete("reset_token");
  const queryLimpia = params.toString();
  const urlLimpia = window.location.pathname + (queryLimpia ? `?${queryLimpia}` : "");
  window.history.replaceState({}, document.title, urlLimpia);

  if (tokenGoogle) {
    guardarToken(tokenGoogle);
    mostrarApp();
    mostrarToast("Sesion iniciada con Google.", "success");
    return true;
  }

  resetTokenActual = tokenReset;
  mostrarAuthGate();
  mostrarPanelAuth("reset");
  return true;
}

if (!procesarParametrosDeAcceso()) {
  if (obtenerToken()) {
    mostrarApp();
  } else {
    mostrarAuthGate();
  }
}
