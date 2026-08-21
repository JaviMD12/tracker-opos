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
    mostrarToast("Tu sesión ha caducado. Inicia sesión de nuevo.", "error");
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
  cargarAcondicionamientoDashboard();
  cargarHeatmap();
  cargarMejoresMarcas();
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
      loginErrorEl.textContent = data.detail ?? "No se pudo iniciar sesión.";
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
      registroErrorEl.textContent = "Cuenta creada. Inicia sesión manualmente.";
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
      data.mensaje ?? "Si el email existe en nuestro sistema, recibirás un enlace en breve.";
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
    mostrarToast("Contraseña actualizada. Ya puedes iniciar sesión.", "success");
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

// ---------- Selector Hombre/Mujer: el baremo oficial (BOP Huelva 80/2026)
// fija marcas distintas por sexo, ver backend/baremos_fisicas.json y
// app/services/calculo.py. Cambiar el selector recalcula la puntuacion al
// instante contra /api/marcas/preview (sin guardar nada en BD) para que el
// usuario vea el efecto real antes de decidir registrar la marca. ----------
const sexoBotones = document.querySelectorAll(".sexo-btn");
const sexoInput = document.getElementById("sexo");

function leerCamposNumericosMarca() {
  const dominadas = Number(document.getElementById("dominadas").value);
  const sprint_100m = Number(document.getElementById("sprint").value);
  const carrera_1500m = minSegAsegundos("carrera_min", "carrera_seg");
  const natacion_100m = minSegAsegundos("natacion_min", "natacion_seg");

  // Los mismos limites que exige el backend (Field(gt=0)/(ge=0)): si algo
  // todavia esta vacio o en 0, no hay una marca real que recalcular.
  if (!(dominadas >= 0) || !(sprint_100m > 0) || !(carrera_1500m > 0) || !(natacion_100m > 0)) {
    return null;
  }
  return { dominadas, sprint_100m, carrera_1500m, natacion_100m };
}

let recalculoEnCurso = null;
async function recalcularVistaPrevia() {
  const campos = leerCamposNumericosMarca();
  if (!campos) return;

  // Evita pisar una respuesta mas vieja si el usuario teclea rapido y
  // dispara varias llamadas solapadas (ultima peticion lanzada = la que
  // manda, aunque no sea la ultima en responder).
  const idPeticion = Symbol();
  recalculoEnCurso = idPeticion;

  try {
    const res = await fetchAutenticado("/api/marcas/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sexo: sexoInput.value, ...campos }),
    });
    if (recalculoEnCurso !== idPeticion) return; // llego una respuesta obsoleta
    if (!res.ok) return;
    const data = await res.json();
    pintarResultado(data);
  } catch (err) {
    console.error("No se pudo recalcular la vista previa", err);
  }
}

sexoBotones.forEach((btn) => {
  btn.addEventListener("click", () => {
    sexoBotones.forEach((b) => b.classList.toggle("active", b === btn));
    sexoInput.value = btn.dataset.sexo;
    recalcularVistaPrevia();
  });
});

["dominadas", "sprint", "carrera_min", "carrera_seg", "natacion_min", "natacion_seg"].forEach((id) => {
  document.getElementById(id)?.addEventListener("input", recalcularVistaPrevia);
});

const formTeorica = document.getElementById("form-teorica");
const resultadoTeoricaBox = document.getElementById("resultado-teorica");
const notaTeoricaResultadoEl = document.getElementById("nota-teorica-resultado");

const dashboardNotaTotalEl = document.getElementById("dashboard-nota-total");
const dashboardNotaFisicaEl = document.getElementById("dashboard-nota-fisica");
const dashboardNotaTeoricaEl = document.getElementById("dashboard-nota-teorica");
const dashboardVeredictoEl = document.getElementById("dashboard-veredicto");
const gaugeFisicaProgressEl = document.getElementById("gauge-fisica-progress");
const gaugeFisicaValorEl = document.getElementById("gauge-fisica-valor");
const gaugeTeoricaProgressEl = document.getElementById("gauge-teorica-progress");
const gaugeTeoricaValorEl = document.getElementById("gauge-teorica-valor");

// Circunferencia de un circulo r=52 (ver .gauge-progress en style.css):
// 2 * PI * 52 ~= 326.73. offset = circunferencia entero es 0% de trazo
// visible; restarle el porcentaje real revela el arco correspondiente.
const GAUGE_CIRCUNFERENCIA = 326.73;
function actualizarGaugeCircular(circuloEl, porcentaje) {
  if (!circuloEl) return;
  const clamped = Math.max(0, Math.min(1, porcentaje || 0));
  circuloEl.style.strokeDashoffset = String(GAUGE_CIRCUNFERENCIA * (1 - clamped));
}

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

  if (nombre === "premium") {
    // Siempre se entra por "Inicio": evita que alguien reabra la Zona
    // Premium y se encuentre a media conversacion del chat o a mitad de un
    // simulacro de una visita anterior sin contexto.
    activarVistaPremium("inicio");
    if (proEstaDesbloqueado()) {
      cargarZonaPremium();
      verificarTourPremium();
    }
  }
}

navButtons.forEach((btn) => {
  btn.addEventListener("click", () => activarVista(btn.dataset.view));
});

// ---------- Menu movil (hamburguesa) ----------
// Por debajo de lg, #sidebar-nav esta oculto por defecto (ver #sidebar-nav
// en style.css) porque los 4 botones del sidebar no caben como fila
// horizontal. Este boton lo despliega como un desplegable a pantalla
// completa bajo la cabecera anadiendo "menu-movil-abierto"; en lg+ el CSS
// lo mantiene siempre visible pase lo que pase con esta clase, y el propio
// boton esta oculto ahi con "lg:hidden".
const btnMenuMovil = document.getElementById("btn-menu-movil");
const sidebarNav = document.getElementById("sidebar-nav");

function cerrarMenuMovil() {
  sidebarNav.classList.remove("menu-movil-abierto");
  btnMenuMovil?.setAttribute("aria-expanded", "false");
}

btnMenuMovil?.addEventListener("click", () => {
  const seVaAAbrir = !sidebarNav.classList.contains("menu-movil-abierto");
  sidebarNav.classList.toggle("menu-movil-abierto");
  btnMenuMovil.setAttribute("aria-expanded", String(seVaAAbrir));
});

// Elegir cualquier opcion (incluido "Cerrar sesion") cierra el menu: sin
// esto, en movil el desplegable se quedaria abierto tapando la vista nueva.
sidebarNav?.addEventListener("click", (event) => {
  if (event.target.closest("button")) cerrarMenuMovil();
});

// ---------- Zona Premium: sub-navegacion (Inicio / Tutor IA / Simulacros) ----------
// Un segundo nivel de pestañas, solo dentro de la Zona Premium: antes las tres
// herramientas (grafica+entrenamiento+tecnicas+tablon, chat del Tutor IA,
// Simulacros) vivian apiladas en una unica pagina larga. Cada una es ahora su
// propia sub-vista con scroll independiente (ver #premium-view-* en
// index.html); el Tutor IA en particular necesita ser la unica vista visible
// para poder ocupar toda la altura disponible estilo chat real.
const premiumTabButtons = document.querySelectorAll(".premium-tab-btn");
const premiumSubviews = {
  inicio: document.getElementById("premium-view-inicio"),
  tutor: document.getElementById("premium-view-tutor"),
  simulacros: document.getElementById("premium-view-simulacros"),
  flashcards: document.getElementById("premium-view-flashcards"),
  enfoque: document.getElementById("premium-view-enfoque"),
};

function activarVistaPremium(nombre) {
  premiumTabButtons.forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.premiumView === nombre);
  });
  Object.entries(premiumSubviews).forEach(([nombreVista, el]) => {
    el.classList.toggle("hidden", nombreVista !== nombre);
  });
  if (nombre === "tutor") {
    chatInput?.focus();
  }
}

premiumTabButtons.forEach((btn) => {
  btn.addEventListener("click", () => activarVistaPremium(btn.dataset.premiumView));
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
  // Los ganchos de upsell del Dashboard gratuito (teaser + banner) no tienen
  // sentido para quien ya es Pro -- se ocultan aqui, en el mismo sitio que
  // decide el resto del estado premium, para no tener dos fuentes de verdad.
  teaserTablonBox?.classList.toggle("hidden", desbloqueado);
  bannerUpsellEntrenamiento?.classList.toggle("hidden", desbloqueado);
}

async function iniciarCheckoutStripe(boton) {
  // innerHTML, no textContent: varios de estos botones llevan spans anidados
  // para destacar el precio (9,99 grande + /mes sutil) y textContent los
  // aplanaria a texto plano al restaurar tras un error.
  const htmlOriginal = boton.innerHTML;
  boton.disabled = true;
  boton.textContent = "Redirigiendo a pago seguro...";

  try {
    const res = await fetchAutenticado("/api/pagos/checkout", { method: "POST" });
    const data = await res.json();

    if (!res.ok) {
      mostrarToast(data.detail ?? "No se pudo iniciar el pago.", "error");
      boton.disabled = false;
      boton.innerHTML = htmlOriginal;
      return;
    }

    boton.disabled = false;
    boton.innerHTML = htmlOriginal;

    // ENABLE_STRIPE=false en el backend (ver routers/pagos.py): el checkout
    // real esta pausado, se abre la lista de espera en su lugar en vez de
    // redirigir a Stripe.
    if (data.stripe_habilitado === false) {
      abrirModalWaitlist();
      return;
    }

    window.location.href = data.url;
  } catch (err) {
    console.error("No se pudo iniciar el checkout de Stripe", err);
    mostrarToast("No se pudo conectar con el backend de pagos.", "error");
    boton.disabled = false;
    boton.innerHTML = htmlOriginal;
  }
}

btnDesbloquear.addEventListener("click", () => iniciarCheckoutStripe(btnDesbloquear));

// ---------- Upsell Free -> Premium (Dashboard gratuito) ----------
// Tres ganchos de conversion sobre el Dashboard free: el teaser "cristal
// empañado" del tablon (abre el modal), el modal en si (CTA con checkout
// directo, reutilizando iniciarCheckoutStripe) y el banner contextual tras
// el resultado del entreno fisico (navega a la Zona Premium real). Los tres
// se ocultan para quien ya es Pro, ver mostrarEstadoPremium().
const teaserTablonBox = document.getElementById("teaser-tablon");
const btnTeaserTablon = document.getElementById("btn-teaser-tablon");
const modalPaywall = document.getElementById("modal-paywall");
const btnCerrarModalPaywall = document.getElementById("btn-cerrar-modal-paywall");
const btnModalActualizarPremium = document.getElementById("btn-modal-actualizar-premium");
const bannerUpsellEntrenamiento = document.getElementById("banner-upsell-entrenamiento");
const btnBannerUpsellEntrenamiento = document.getElementById("btn-banner-upsell-entrenamiento");

function abrirModalPaywall() {
  modalPaywall.classList.remove("hidden");
  // La clase que dispara la transicion se añade un frame despues de quitar
  // "hidden" (mismo patron que los toasts, ver mostrarToast()): si se
  // añadiera en el mismo tick, el navegador podria fusionar ambos cambios
  // de estilo en un unico frame y la transicion no se veria, apareceria de
  // golpe.
  requestAnimationFrame(() => modalPaywall.classList.add("show"));
}

function cerrarModalPaywall() {
  modalPaywall.classList.remove("show");
  setTimeout(() => modalPaywall.classList.add("hidden"), 200);
}

btnTeaserTablon?.addEventListener("click", abrirModalPaywall);
btnCerrarModalPaywall?.addEventListener("click", cerrarModalPaywall);
document.getElementById("modal-paywall-backdrop")?.addEventListener("click", cerrarModalPaywall);
document.addEventListener("keydown", (evento) => {
  if (evento.key === "Escape" && !modalPaywall.classList.contains("hidden")) {
    cerrarModalPaywall();
  }
});
btnModalActualizarPremium?.addEventListener("click", () =>
  iniciarCheckoutStripe(btnModalActualizarPremium)
);

// ---------- Lista de espera (checkout de Stripe pausado, ENABLE_STRIPE=false) ----------
// Se abre desde iniciarCheckoutStripe() de arriba cuando el backend responde
// {"stripe_habilitado": false} -- ningun boton llama a esto directamente.
const modalWaitlist = document.getElementById("modal-waitlist");
const btnCerrarModalWaitlist = document.getElementById("btn-cerrar-modal-waitlist");
const formWaitlist = document.getElementById("form-waitlist");
const waitlistEmailEl = document.getElementById("waitlist-email");
const waitlistErrorEl = document.getElementById("waitlist-error");

function abrirModalWaitlist() {
  modalWaitlist.classList.remove("hidden");
  requestAnimationFrame(() => modalWaitlist.classList.add("show"));
}

function cerrarModalWaitlist() {
  modalWaitlist.classList.remove("show");
  setTimeout(() => modalWaitlist.classList.add("hidden"), 200);
}

btnCerrarModalWaitlist?.addEventListener("click", cerrarModalWaitlist);
document.getElementById("modal-waitlist-backdrop")?.addEventListener("click", cerrarModalWaitlist);
document.addEventListener("keydown", (evento) => {
  if (evento.key === "Escape" && !modalWaitlist.classList.contains("hidden")) {
    cerrarModalWaitlist();
  }
});

formWaitlist?.addEventListener("submit", async (event) => {
  event.preventDefault();
  waitlistErrorEl.classList.add("hidden");

  const boton = formWaitlist.querySelector('button[type="submit"]');
  const textoOriginal = boton.textContent;
  boton.disabled = true;
  boton.textContent = "Enviando...";

  try {
    // Sin fetchAutenticado a proposito: apuntarse a la lista de espera no
    // exige sesion iniciada (ver POST /api/waitlist en el backend).
    const res = await fetch("/api/waitlist", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: waitlistEmailEl.value.trim() }),
    });
    const data = await res.json();

    if (!res.ok) {
      const detalle = Array.isArray(data.detail)
        ? data.detail.map((d) => d.msg).join(", ")
        : data.detail ?? "No se pudo completar el registro.";
      waitlistErrorEl.textContent = detalle;
      waitlistErrorEl.classList.remove("hidden");
      return;
    }

    formWaitlist.reset();
    cerrarModalWaitlist();
    mostrarToast("¡Apuntado! Revisa tu email para la confirmación.", "success");
  } catch (err) {
    console.error("No se pudo unir a la lista de espera", err);
    waitlistErrorEl.textContent = "No se pudo conectar con el backend.";
    waitlistErrorEl.classList.remove("hidden");
  } finally {
    boton.disabled = false;
    boton.textContent = textoOriginal;
  }
});

btnBannerUpsellEntrenamiento?.addEventListener("click", () => activarVista("premium"));

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
      mostrarToast(data.detail ?? "No se pudo abrir el portal de suscripción.", "error");
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
    mostrarToast("¡Bienvenido a la Zona Premium! Ya tienes acceso a todos los módulos.", "success");
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
      mostrarEstadoVacioGrafica("No se pudo cargar tu evolución ahora mismo. Inténtalo de nuevo en unos minutos.");
      return;
    }

    const data = await res.json();
    const puntos = data.puntos || [];

    if (puntos.length === 0) {
      mostrarEstadoVacioGrafica("Registra tus primeras marcas físicas para visualizar tu evolución.");
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
            label: "Nota Global Oposición",
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
    mostrarEstadoVacioGrafica("No se pudo cargar tu evolución ahora mismo. Inténtalo de nuevo en unos minutos.");
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
        Punto débil detectado: ${data.nombre} (${data.puntos_actuales.toFixed(2)} / 10)
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
    .map((c) => {
      // El backend ya excluye convocatorias con el plazo vencido (ver
      // GET /api/convocatorias), pero dejamos este estado como red de
      // seguridad por si alguna llega justo al filo del plazo.
      const cerrado = c.dias_restantes != null && c.dias_restantes < 0;
      const textoPlazo = cerrado
        ? "Plazo cerrado"
        : c.dias_restantes != null
        ? `Quedan ${c.dias_restantes} días`
        : "Plazo no especificado";

      return `
      <article class="convocatoria-card">
        <p class="convocatoria-titulo">${c.titulo_plaza}</p>
        <p class="convocatoria-meta">${c.organismo_localidad}</p>
        <span class="convocatoria-plazo${cerrado ? " convocatoria-plazo-cerrado" : ""}">${textoPlazo}</span>
        <p class="convocatoria-requisitos">${c.requisitos_minimos ?? "Sin requisitos detallados"}</p>
        <button type="button" class="btn-plan-ia" data-convocatoria-id="${c.id}" ${cerrado ? "disabled" : ""}>
          &#9889; Generar Plan de Estudio IA
        </button>
        <div class="plan-ia-contenido hidden"></div>
      </article>`;
    })
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
      tablonContenido.innerHTML = `<p class="text-gray-500">No se pudo verificar tu Plan Pro para el Tablón. Si acabas de pagar, recarga la página en unos segundos.</p>`;
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

// Acondicionamiento Fisico Estrategico (grafica + Entrenamiento Especifico)
// y Alto Rendimiento Teorico viven en el Dashboard gratuito: sus endpoints
// (/api/dashboard/evolucion, /api/pro/entrenamiento, /api/pro/teorica) solo
// exigen sesion iniciada, no is_pro, asi que se cargan para cualquier
// usuario logueado en cuanto arranca la app (ver mostrarApp()).
function cargarAcondicionamientoDashboard() {
  cargarGraficaEvolucion();
  cargarEntrenamientoEspecifico();
  cargarTecnicasEstudio();
}

// Acondicionamiento Fisico Estrategico y Alto Rendimiento Teorico viven en
// el Dashboard gratuito (ver cargarAcondicionamientoDashboard); la Zona
// Premium real, protegida por is_pro en el backend, es solo el Tablon.
function cargarZonaPremium() {
  cargarTablonConvocatorias();
}

// ---------- Tour Guiado: onboarding de la Zona Premium ----------
// Se muestra una unica vez por usuario (is_pro real + tour_premium_completado
// en false, ver GET /api/usuarios/me), la primera vez que entra en la Zona
// Premium. Al terminar se registra en el backend para no volver a mostrarlo.
const PASOS_TOUR_PREMIUM = [
  {
    selector: "#tour-tablon",
    vista: "inicio",
    texto: "El radar activado. Filtramos el ruido y te mostramos solo plazas reales de emergencias. Usa la IA para analizar los requisitos en segundos.",
  },
  {
    selector: "#tour-tutor",
    vista: "tutor",
    texto: "Tu sargento 24/7. Pregúntale dudas técnicas sobre el CTE, hidráulica o legislación. Nunca duerme.",
  },
  {
    selector: "#tour-simulacros",
    vista: "simulacros",
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
  // Cada paso vive en su propia sub-vista de la Zona Premium (Inicio / Tutor
  // IA / Simulacros), ocultas entre si -- hay que activar la que corresponda
  // antes de buscar/resaltar el elemento, o querySelector encontraria un nodo
  // con display:none (getBoundingClientRect devolveria un rectangulo vacio).
  activarVistaPremium(paso.vista);

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
      pintarBurbujaChat("No se pudo conectar con el tutor. Inténtalo de nuevo.", "ia");
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
      <td class="py-1 font-semibold">${prueba.puntos}</td>
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

  bannerUpsellEntrenamiento?.classList.toggle("hidden", proEstaDesbloqueado());
}

// ---------- Tus Mejores Marcas (records personales) ----------
// GET /api/marcas/historial ya existia en el backend (devuelve todo el
// historial de marcas del usuario) pero el frontend nunca lo llamaba --
// el resto del Dashboard solo muestra el ultimo registro, nunca el mejor
// historico. dominadas: mas alto mejor; el resto (segundos): mas bajo mejor
// (mismo criterio que PRUEBAS en backend/app/services/calculo.py).
const mejoresMarcasContenidoEl = document.getElementById("mejores-marcas-contenido");

function formatearSegundos(totalSegundos) {
  const min = Math.floor(totalSegundos / 60);
  const seg = totalSegundos % 60;
  return min > 0 ? `${min}m ${seg}s` : `${seg}s`;
}

async function cargarMejoresMarcas() {
  if (!mejoresMarcasContenidoEl) return;
  try {
    const res = await fetchAutenticado("/api/marcas/historial");
    if (!res.ok) return;
    const historial = await res.json();

    if (historial.length === 0) {
      mejoresMarcasContenidoEl.innerHTML = `<p class="text-sm text-gray-500">Registra tu primera marca para ver aquí tus récords.</p>`;
      return;
    }

    const filas = [
      { etiqueta: "Dominadas", valor: `${Math.max(...historial.map((m) => m.dominadas))} reps` },
      { etiqueta: "Sprint 100m", valor: `${Math.min(...historial.map((m) => m.sprint_100m)).toFixed(2)} s` },
      { etiqueta: "Carrera 1500m", valor: formatearSegundos(Math.min(...historial.map((m) => m.carrera_1500m))) },
      { etiqueta: "Natación 100m", valor: formatearSegundos(Math.min(...historial.map((m) => m.natacion_100m))) },
    ];

    mejoresMarcasContenidoEl.innerHTML = filas
      .map(
        (fila) => `
        <div class="flex items-center justify-between gap-3 py-2.5 border-b border-white/5 last:border-0">
          <span class="text-sm text-gray-300">${fila.etiqueta}</span>
          <span class="text-sm font-bold text-amber-400">${fila.valor}</span>
        </div>`
      )
      .join("");
  } catch (err) {
    console.error("No se pudieron cargar las mejores marcas", err);
  }
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

    gaugeFisicaValorEl.textContent = data.nota_fisica ? data.nota_fisica.valor.toFixed(2) : "--";
    gaugeTeoricaValorEl.textContent = data.nota_teorica ? data.nota_teorica.valor.toFixed(2) : "--";
    actualizarGaugeCircular(gaugeFisicaProgressEl, data.nota_fisica?.porcentaje);
    actualizarGaugeCircular(gaugeTeoricaProgressEl, data.nota_teorica?.porcentaje);
  } catch (err) {
    console.error("No se pudo cargar el dashboard global", err);
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const payload = {
    fecha: document.getElementById("fecha").value || null,
    sexo: sexoInput.value,
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
    // Refresca la rutina y la grafica con el nuevo punto debil / registro,
    // en vez de esperar a la proxima carga de la app (ver
    // cargarAcondicionamientoDashboard()).
    cargarEntrenamientoEspecifico();
    cargarGraficaEvolucion();
    cargarMejoresMarcas();
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

// ---------- Sugerencias / Contacto ----------
// Mismo formulario sirve de canal de soporte: el backend decide el trato
// segun is_pro (reenvio prioritario al admin si es Premium, autorespuesta
// automatica si es gratuito) -- el frontend no necesita saber cual de los
// dos es, solo manda asunto+mensaje.
const formSugerencia = document.getElementById("form-sugerencia");
const sugerenciaAsuntoEl = document.getElementById("sugerencia-asunto");
const sugerenciaTextoEl = document.getElementById("sugerencia-texto");

formSugerencia.addEventListener("submit", async (event) => {
  event.preventDefault();
  const asunto = sugerenciaAsuntoEl.value.trim();
  const mensaje = sugerenciaTextoEl.value.trim();
  if (!asunto || !mensaje) return;

  const boton = formSugerencia.querySelector('button[type="submit"]');
  const textoOriginal = boton.textContent;
  boton.disabled = true;
  boton.textContent = "Enviando...";

  try {
    const res = await fetchAutenticado("/api/contacto/enviar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ asunto, mensaje }),
    });
    const data = await res.json();

    if (!res.ok) {
      mostrarToast(data.detail ?? "No se pudo enviar la sugerencia.", "error");
      return;
    }

    sugerenciaAsuntoEl.value = "";
    sugerenciaTextoEl.value = "";
    mostrarToast("¡Gracias! Tu sugerencia se ha enviado correctamente.", "success");
  } catch (err) {
    console.error("No se pudo enviar la sugerencia", err);
    mostrarToast("No se pudo conectar con el backend.", "error");
  } finally {
    boton.disabled = false;
    boton.textContent = textoOriginal;
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

// ---------- Flashcards (repeticion espaciada estilo Anki, Zona Premium) ----------
const flashcardTemaSelect = document.getElementById("flashcard-tema");
const btnEmpezarFlashcards = document.getElementById("btn-empezar-flashcards");
const flashcardConfigBox = document.getElementById("flashcard-config");
const flashcardSesionBox = document.getElementById("flashcard-sesion");
const flashcardVacioBox = document.getElementById("flashcard-vacio");
const flashcardProgresoEl = document.getElementById("flashcard-progreso");
const flashcardEl = document.getElementById("flashcard");
const flashcardPreguntaEl = document.getElementById("flashcard-pregunta");
const flashcardRespuestaEl = document.getElementById("flashcard-respuesta");
const flashcardBotonesRespuesta = document.getElementById("flashcard-botones-respuesta");
const btnNuevaSesionFlashcards = document.getElementById("btn-nueva-sesion-flashcards");

// Cola de tarjetas pendientes de la sesion en curso, guardada en memoria:
// avanzar de tarjeta no necesita otra llamada al backend hasta que se acaba.
let colaFlashcards = [];
let indiceFlashcardActual = 0;

function pintarFlashcardActual() {
  const tarjeta = colaFlashcards[indiceFlashcardActual];
  flashcardEl.classList.remove("volteada");
  flashcardBotonesRespuesta.classList.add("hidden");
  flashcardPreguntaEl.textContent = tarjeta.pregunta;
  flashcardRespuestaEl.textContent = tarjeta.respuesta;
  flashcardProgresoEl.textContent = `${indiceFlashcardActual + 1} / ${colaFlashcards.length}`;
}

function mostrarPasoFlashcards(paso) {
  flashcardConfigBox.classList.toggle("hidden", paso !== "config");
  flashcardSesionBox.classList.toggle("hidden", paso !== "sesion");
  flashcardVacioBox.classList.toggle("hidden", paso !== "vacio");
}

btnEmpezarFlashcards.addEventListener("click", async () => {
  const tema = flashcardTemaSelect.value;
  const textoOriginal = btnEmpezarFlashcards.textContent;

  btnEmpezarFlashcards.disabled = true;
  btnEmpezarFlashcards.textContent = "Cargando...";

  try {
    const res = await fetchAutenticado(`/api/flashcards/due?tema=${encodeURIComponent(tema)}`);
    const data = await res.json();

    if (!res.ok) {
      mostrarToast(data.detail ?? "No se pudieron cargar las flashcards.", "error");
      return;
    }

    if (!data.flashcards.length) {
      mostrarPasoFlashcards("vacio");
      return;
    }

    colaFlashcards = data.flashcards;
    indiceFlashcardActual = 0;
    pintarFlashcardActual();
    mostrarPasoFlashcards("sesion");
  } catch (err) {
    console.error("No se pudieron cargar las flashcards", err);
    mostrarToast("No se pudo conectar con el backend.", "error");
  } finally {
    btnEmpezarFlashcards.disabled = false;
    btnEmpezarFlashcards.textContent = textoOriginal;
  }
});

flashcardEl.addEventListener("click", () => {
  if (flashcardEl.classList.contains("volteada")) return;
  flashcardEl.classList.add("volteada");
  flashcardBotonesRespuesta.classList.remove("hidden");
});

async function responderFlashcard(resultado) {
  const tarjeta = colaFlashcards[indiceFlashcardActual];

  // Guardado silencioso: el usuario ya esta viendo la siguiente tarjeta, un
  // fallo de red aqui no debe interrumpirle la sesion de repaso.
  try {
    await fetchAutenticado("/api/flashcards/review", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ flashcard_id: tarjeta.id, resultado }),
    });
  } catch (err) {
    console.error("No se pudo guardar el repaso de la flashcard", err);
  }

  indiceFlashcardActual++;
  if (indiceFlashcardActual >= colaFlashcards.length) {
    mostrarPasoFlashcards("vacio");
    return;
  }
  pintarFlashcardActual();
}

document.getElementById("btn-flashcard-facil").addEventListener("click", () => responderFlashcard(1));
document.getElementById("btn-flashcard-medio").addEventListener("click", () => responderFlashcard(2));
document.getElementById("btn-flashcard-dificil").addEventListener("click", () => responderFlashcard(3));

btnNuevaSesionFlashcards.addEventListener("click", () => mostrarPasoFlashcards("config"));

// ---------- Modo Enfoque (Pomodoro, apartado de la Zona Premium) ----------
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

const timerDisplay = document.getElementById("timer-display");

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
      mostrarToast("¡Sesión de enfoque terminada! Tómate un descanso.", "success");

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
    mostrarToast("Sesión iniciada con Google.", "success");
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
