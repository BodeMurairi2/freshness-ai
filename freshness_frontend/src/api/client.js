// Talks to the Freshness-ai API. The address comes from VITE_API_URL (see .env.example).
export const API_URL = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/$/, "");
export const DECISION_THRESHOLD = Number(import.meta.env.VITE_DECISION_THRESHOLD || 0.75);
export const RETRAIN_MIN_IMAGES = Number(import.meta.env.VITE_RETRAIN_MIN_IMAGES || 4);
export const RETRAIN_MAX_EPOCHS = Number(import.meta.env.VITE_RETRAIN_MAX_EPOCHS || 10);

const TOKEN_KEY = "freshness_token";

export function readToken() {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function saveToken(token) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    // private browsing: the session simply lasts until the page is closed
  }
}

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

// FastAPI errors are {"detail": "text"} or {"detail": [{msg: "..."}]} for validation errors
function errorMessage(body, status) {
  const detail = body?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length) {
    return detail.map((item) => String(item.msg || "").replace(/^Value error, /, "")).join(" · ");
  }
  if (status === 0) return "The server can't be reached. Check your connection and try again.";
  return `Something went wrong (error ${status}).`;
}

// listeners told when a token is rejected, so the app can log the user out
const sessionExpiredListeners = new Set();
export function onSessionExpired(listener) {
  sessionExpiredListeners.add(listener);
  return () => sessionExpiredListeners.delete(listener);
}

export async function request(path, { method = "GET", json, form, auth = false } = {}) {
  const headers = {};
  let body;
  if (json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(json);
  } else if (form) {
    body = form; // the browser sets the multipart boundary
  }
  if (auth) {
    const token = readToken();
    if (token) headers.Authorization = `Bearer ${token}`;
  }

  let response;
  try {
    response = await fetch(`${API_URL}${path}`, { method, headers, body });
  } catch {
    throw new ApiError(errorMessage(null, 0), 0);
  }

  const contentType = response.headers.get("content-type") || "";
  const data = contentType.includes("application/json") ? await response.json() : null;
  if (!response.ok) {
    if (response.status === 401 && auth) sessionExpiredListeners.forEach((listener) => listener());
    throw new ApiError(errorMessage(data, response.status), response.status);
  }
  return data;
}

// ------------------------------------------------------------ endpoints
export const api = {
  predictWithGradcam(file) {
    const form = new FormData();
    form.append("image", file);
    return request("/predict/gradcam", { method: "POST", form });
  },
  insights: () => request("/insights/"),

  register: (newUser) => request("/auth/register", { method: "POST", json: newUser }),
  login: (username, password) => request("/auth/login", { method: "POST", json: { username, password } }),
  usernameAvailable: (username) => request(`/auth/username-available?username=${encodeURIComponent(username)}`),
  requestPasswordCode: (emailAddress) => request("/auth/password/code", { method: "POST", json: { email_address: emailAddress } }),
  changePassword: (payload) => request("/auth/password", { method: "PUT", json: payload }),

  uploadTrainingImages(images) {
    // images: [{file, label}], all classes in one request (one label per image)
    const form = new FormData();
    images.forEach(({ file, label }) => {
      form.append("images", file);
      form.append("labels", label);
    });
    return request("/retrain/model", { method: "POST", form, auth: true });
  },
  // epochs is optional: without it, the server uses RETRAIN_EPOCHS from its .env
  startRetraining: (epochs) => request("/retrain/start", { method: "POST", auth: true, json: epochs ? { epochs } : {} }),
  retrainingStatus: () => request("/retrain/status", { auth: true }),
  models: () => request("/retrain/models/all"),
  modelPerformance: () => request("/retrain/models/performance"),
  selectModel(modelName) {
    const form = new FormData();
    form.append("model_name", modelName);
    return request("/retrain/models/select", { method: "POST", form, auth: true });
  },
};
