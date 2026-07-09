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
  mostrarEstadoPro();
  cargarDashboardGlobal();
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

// Navegacion principal (SPA basica): Dashboard Analitico <-> Guia del Opositor <-> Plan Pro
const navButtons = document.querySelectorAll(".nav-view-btn");
const views = {
  dashboard: document.getElementById("view-dashboard"),
  guia: document.getElementById("view-guia"),
  pro: document.getElementById("view-pro"),
};

function activarVista(nombre) {
  navButtons.forEach((btn) => {
    const activo = btn.dataset.view === nombre;
    btn.classList.toggle("active", activo);
  });
  Object.entries(views).forEach(([nombreVista, el]) => {
    el.classList.toggle("hidden", nombreVista !== nombre);
  });

  if (nombre === "pro" && proEstaDesbloqueado()) {
    cargarPlanPro();
  }
}

navButtons.forEach((btn) => {
  btn.addEventListener("click", () => activarVista(btn.dataset.view));
});

// ---------- Plan Pro: muro de pago (simulado) ----------
// La clave se namespacea por usuario_id (extraido del JWT) para que dos
// cuentas distintas en el mismo navegador no compartan el desbloqueo.
const proLockedBox = document.getElementById("pro-locked");
const proUnlockedBox = document.getElementById("pro-unlocked");
const btnDesbloquear = document.getElementById("btn-desbloquear");
const btnSimularPago = document.getElementById("btn-simular-pago");

function clavePlanPro() {
  const usuarioId = obtenerUsuarioIdDesdeToken();
  return usuarioId ? `plan_pro_desbloqueado_${usuarioId}` : "plan_pro_desbloqueado";
}

function proEstaDesbloqueado() {
  return localStorage.getItem(clavePlanPro()) === "true";
}

function desbloquearPro() {
  localStorage.setItem(clavePlanPro(), "true");
  proLockedBox.classList.add("hidden");
  proUnlockedBox.classList.remove("hidden");
  cargarPlanPro();
}

function mostrarEstadoPro() {
  const desbloqueado = proEstaDesbloqueado();
  proLockedBox.classList.toggle("hidden", desbloqueado);
  proUnlockedBox.classList.toggle("hidden", !desbloqueado);
}

btnDesbloquear.addEventListener("click", async () => {
  const textoOriginal = btnDesbloquear.textContent;
  btnDesbloquear.disabled = true;
  btnDesbloquear.textContent = "Redirigiendo a pago seguro...";

  try {
    const res = await fetchAutenticado("/api/pagos/checkout", { method: "POST" });
    const data = await res.json();

    if (!res.ok) {
      mostrarToast(data.detail ?? "No se pudo iniciar el pago.", "error");
      btnDesbloquear.disabled = false;
      btnDesbloquear.textContent = textoOriginal;
      return;
    }

    window.location.href = data.url;
  } catch (err) {
    console.error("No se pudo iniciar el checkout de Stripe", err);
    mostrarToast("No se pudo conectar con el backend de pagos.", "error");
    btnDesbloquear.disabled = false;
    btnDesbloquear.textContent = textoOriginal;
  }
});
btnSimularPago.addEventListener("click", desbloquearPro);

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
    desbloquearPro();
    activarVista("pro");
    mostrarToast("¡Bienvenido al Plan Pro! Ya tienes acceso a tus graficas y rutinas.", "success");
  } else if (pago === "cancelado") {
    mostrarToast("El pago no se ha completado. Puedes intentarlo de nuevo cuando quieras.", "error");
  }

  params.delete("pago");
  const queryLimpia = params.toString();
  const urlLimpia = window.location.pathname + (queryLimpia ? `?${queryLimpia}` : "") + window.location.hash;
  window.history.replaceState({}, document.title, urlLimpia);
}

let graficaEvolucion = null;

async function cargarGraficaEvolucion() {
  const canvas = document.getElementById("grafica-evolucion");
  const vaciaMsg = document.getElementById("grafica-vacia");
  try {
    const res = await fetchAutenticado("/api/dashboard/evolucion");
    if (!res.ok) return;
    const data = await res.json();
    const puntos = data.puntos || [];

    if (puntos.length === 0) {
      canvas.classList.add("hidden");
      vaciaMsg.classList.remove("hidden");
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

function cargarPlanPro() {
  cargarGraficaEvolucion();
  cargarEntrenamientoEspecifico();
  cargarTecnicasEstudio();
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
