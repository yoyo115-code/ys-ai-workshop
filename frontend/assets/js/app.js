const TABS = ["resume", "copywrite", "translate", "pdf", "csv", "admin"];
const AUTH_TOKEN_KEY = "nova_auth_token";
const API_CONFIG = window.YS_AI_CONFIG;
let currentUser = null;
let registrationMode = false;

function apiUrl(path) {
  return `${API_CONFIG.apiBaseUrl}${path}`;
}

const FIELD = {
  resume: "text",
  copywrite: "scene",
  translate: "text"
};

const FILE_RULES = {
  pdf: {
    label: "PDF",
    extensions: [".pdf"],
    mimeTypes: ["application/pdf"]
  },
  csv: {
    label: "CSV",
    extensions: [".csv"],
    mimeTypes: ["text/csv", "application/csv", "application/vnd.ms-excel"]
  }
};

function switchTab(name) {
  const targetButton = document.querySelector(`[data-tab="${name}"]`);
  if (!TABS.includes(name) || !targetButton || targetButton.hidden) {
    return;
  }

  document.querySelectorAll(".tab-btn").forEach((button) => {
    const isActive = button.dataset.tab === name;
    button.classList.toggle("active", isActive);
    button.setAttribute("aria-selected", String(isActive));
  });

  TABS.forEach((tabName) => {
    const panel = document.getElementById(`panel-${tabName}`);

    if (panel) {
      panel.classList.toggle("active", tabName === name);
    }
  });

  if (name === "admin") refreshAdminDashboard();
}

function onFileChosen(type) {
  const input = document.getElementById(`${type}-file`);
  const fileName = document.getElementById(`${type}-file-name`);
  const file = input.files[0];

  if (!currentUser) {
    setOutput(type, "请先登录后使用。", "error");
    return;
  }

  if (!file) {
    fileName.textContent = "尚未选择文件";
    return;
  }

  const error = validateFile(type, file);

  if (error) {
    input.value = "";
    fileName.textContent = "尚未选择文件";
    setOutput(type, error, "error");
    return;
  }

  fileName.textContent = `已选择：${file.name}`;
  setOutput(type, `${FILE_RULES[type].label} 文件已就绪，点击按钮开始处理。`, "placeholder");
}

function setOutput(id, text, state = "") {
  const output = document.getElementById(`${id}-output`);
  const outputCard = document.getElementById(`${id}-output-card`);
  const className = ["output-area"];

  if (state) {
    className.push(state);
  }

  output.className = className.join(" ");
  output.textContent = text;

  if (outputCard) {
    outputCard.classList.toggle("has-error", state === "error");
  }
}

function setButtonLoading(button, isLoading) {
  if (!button.dataset.defaultText) {
    button.dataset.defaultText = button.textContent.trim();
  }

  button.disabled = isLoading;
  button.textContent = isLoading ? "处理中…" : button.dataset.defaultText;
}

function validateFile(type, file) {
  const rule = FILE_RULES[type];
  const fileName = file.name.toLowerCase();
  const hasValidExtension = rule.extensions.some((extension) => fileName.endsWith(extension));
  const hasValidMime = !file.type || rule.mimeTypes.includes(file.type);

  if (!hasValidExtension || !hasValidMime) {
    return `文件类型不正确，请上传 ${rule.label} 文件。`;
  }

  return "";
}

async function getResponsePayload(response) {
  const contentType = response.headers.get("content-type") || "";

  if (contentType.includes("application/json")) {
    return response.json();
  }

  return response.text();
}

function formatError(response, payload) {
  let message = "";

  if (payload && typeof payload === "object") {
    const detail = payload.detail || payload.message || payload.error;
    message = typeof detail === "string" ? detail : JSON.stringify(detail || payload);
  } else if (typeof payload === "string") {
    message = payload;
  }

  return `请求失败，HTTP 状态码：${response.status}${message ? `\n${message}` : ""}`;
}

async function submitText(feature) {
  const input = document.getElementById(`${feature}-input`);
  const button = document.getElementById(`${feature}-btn`);
  const text = input.value.trim();

  if (!currentUser) {
    setOutput(feature, "请先登录后使用。", "error");
    return;
  }

  if (!text) {
    setOutput(feature, "请输入需要处理的内容。", "error");
    input.focus();
    return;
  }

  setButtonLoading(button, true);
  setOutput(feature, "处理中，请稍候…", "placeholder");

  try {
    const response = await fetch(apiUrl(API_CONFIG.endpoints.tools[feature]), {
      method: "POST",
      headers: authHeaders(true),
      body: JSON.stringify({
        [FIELD[feature]]: text
      })
    });

    const payload = await getResponsePayload(response);

    if (!response.ok) {
      throw new Error(formatError(response, payload));
    }

    const reply = payload && typeof payload === "object" ? payload.reply : payload;
    setOutput(feature, reply || "后端未返回有效内容。");
  } catch (error) {
    setOutput(feature, error.message || "请求失败，请检查后端是否已启动。", "error");
  } finally {
    setButtonLoading(button, false);
  }
}

async function submitFile(type) {
  const input = document.getElementById(`${type}-file`);
  const button = document.getElementById(`${type}-btn`);
  const file = input.files[0];

  if (!file) {
    setOutput(type, "请先选择需要上传的文件。", "error");
    input.focus();
    return;
  }

  const validationError = validateFile(type, file);

  if (validationError) {
    input.value = "";
    document.getElementById(`${type}-file-name`).textContent = "尚未选择文件";
    setOutput(type, validationError, "error");
    return;
  }

  setButtonLoading(button, true);
  setOutput(type, "处理中，请稍候…", "placeholder");

  const formData = new FormData();
  formData.append("file", file);

  try {
    const response = await fetch(apiUrl(API_CONFIG.endpoints.tools[type]), {
      method: "POST",
      headers: authHeaders(),
      body: formData
    });

    const payload = await getResponsePayload(response);

    if (!response.ok) {
      throw new Error(formatError(response, payload));
    }

    const reply = payload && typeof payload === "object" ? payload.reply : payload;
    setOutput(type, reply || "后端未返回有效内容。");
  } catch (error) {
    setOutput(type, error.message || "请求失败，请检查后端是否已启动。", "error");
  } finally {
    setButtonLoading(button, false);
  }
}


function authHeaders(json = false) {
  const headers = {};
  const token = localStorage.getItem(AUTH_TOKEN_KEY);
  if (token) headers["X-Session-Token"] = token;
  if (json) headers["Content-Type"] = "application/json";
  return headers;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;").replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
}

function formatTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("zh-CN", { hour12: false });
}

function updateAuthUI() {
  const loggedIn = Boolean(currentUser);
  document.getElementById("login-panel").hidden = loggedIn;
  document.getElementById("user-panel").hidden = !loggedIn;
  document.getElementById("status-text").textContent = loggedIn ? "账户已登录" : "请登录后使用";
  document.getElementById("admin-tab").hidden = currentUser?.role !== "admin";
  if (loggedIn) {
    document.getElementById("current-user").textContent = `${currentUser.display_name} (${currentUser.username})`;
    document.getElementById("current-role").textContent = currentUser.role === "admin" ? "管理员" : "普通用户";
  } else if (document.getElementById("panel-admin").classList.contains("active")) {
    switchTab("resume");
  }
}

function setRegistrationMode(enabled) {
  registrationMode = enabled;
  document.getElementById("display-name").hidden = !enabled;
  document.getElementById("confirm-password").hidden = !enabled;
  document.getElementById("login-btn").textContent = enabled ? "创建账号" : "登录";
  document.getElementById("auth-switch-btn").textContent = enabled ? "返回登录" : "注册新账号";
  document.getElementById("password").autocomplete = enabled ? "new-password" : "current-password";
  document.getElementById("auth-message").textContent = enabled
    ? "账号仅支持小写字母、数字和下划线；密码至少 8 位并包含字母和数字。"
    : "请输入账号密码，或注册新账号。";
}

async function submitAuth() {
  const button = document.getElementById("login-btn");
  const message = document.getElementById("auth-message");
  const username = document.getElementById("username").value.trim();
  const password = document.getElementById("password").value;
  const displayName = document.getElementById("display-name").value.trim();
  const confirmPassword = document.getElementById("confirm-password").value;

  if (registrationMode && password !== confirmPassword) {
    message.textContent = "两次输入的密码不一致";
    return;
  }
  if (registrationMode && !displayName) {
    message.textContent = "请输入姓名";
    return;
  }

  button.disabled = true;
  message.textContent = registrationMode ? "正在创建账号..." : "正在登录...";
  try {
    const endpoint = registrationMode
      ? API_CONFIG.endpoints.auth.register
      : API_CONFIG.endpoints.auth.login;
    const response = await fetch(apiUrl(endpoint), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(registrationMode
        ? { username, password, display_name: displayName }
        : { username, password })
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || (registrationMode ? "注册失败" : "登录失败"));
    localStorage.setItem(AUTH_TOKEN_KEY, data.token);
    currentUser = data.user;
    setRegistrationMode(false);
    updateAuthUI();
  } catch (error) {
    message.textContent = error.message;
  } finally {
    button.disabled = false;
  }
}

async function logout() {
  try {
    await fetch(apiUrl(API_CONFIG.endpoints.auth.logout), {
      method: "POST",
      headers: authHeaders()
    });
  } finally {
    localStorage.removeItem(AUTH_TOKEN_KEY);
    currentUser = null;
    updateAuthUI();
  }
}

async function loadCurrentUser() {
  if (!localStorage.getItem(AUTH_TOKEN_KEY)) {
    updateAuthUI();
    return;
  }
  try {
    const response = await fetch(apiUrl(API_CONFIG.endpoints.auth.me), {
      headers: authHeaders()
    });
    if (!response.ok) throw new Error("session expired");
    currentUser = (await response.json()).user;
  } catch {
    localStorage.removeItem(AUTH_TOKEN_KEY);
    currentUser = null;
  }
  updateAuthUI();
}

async function refreshAdminDashboard() {
  if (currentUser?.role !== "admin") return;
  const [usersResponse, logsResponse] = await Promise.all([
    fetch(apiUrl(API_CONFIG.endpoints.admin.users), { headers: authHeaders() }),
    fetch(`${apiUrl(API_CONFIG.endpoints.admin.logs)}?limit=100`, {
      headers: authHeaders()
    })
  ]);
  if (!usersResponse.ok || !logsResponse.ok) return;
  const usersData = await usersResponse.json();
  const logsData = await logsResponse.json();
  document.getElementById("total-users").textContent = usersData.summary.total_users;
  document.getElementById("total-requests").textContent = usersData.summary.total_requests;
  document.getElementById("total-errors").textContent = usersData.summary.total_errors;
  document.getElementById("user-stats-body").innerHTML = usersData.users.map(user => `
    <tr><td>${escapeHtml(user.username)}</td><td>${escapeHtml(user.display_name)}</td>
    <td>${user.role === "admin" ? "管理员" : "用户"}</td><td>${user.request_count}</td>
    <td>${user.success_count || 0}</td><td>${user.error_count || 0}</td><td>${escapeHtml(formatTime(user.last_active_at))}</td></tr>
  `).join("") || '<tr><td colspan="7">暂无数据</td></tr>';
  document.getElementById("activity-logs-body").innerHTML = logsData.logs.map(log => `
    <tr><td>${escapeHtml(formatTime(log.created_at))}</td><td>${escapeHtml(log.display_name)} (${escapeHtml(log.username)})</td>
    <td>${escapeHtml(log.feature)}</td><td class="status-${escapeHtml(log.status)}">${log.status === "success" ? "成功" : "失败"}</td>
    <td>${log.duration_ms} ms</td><td>${escapeHtml(log.error || log.input_preview || "-")}</td></tr>
  `).join("") || '<tr><td colspan="6">暂无数据</td></tr>';
}

document.getElementById("login-btn").addEventListener("click", submitAuth);
document.getElementById("auth-switch-btn").addEventListener("click", () => setRegistrationMode(!registrationMode));
document.getElementById("logout-btn").addEventListener("click", logout);
document.getElementById("refresh-admin-btn").addEventListener("click", refreshAdminDashboard);
document.getElementById("password").addEventListener("keydown", (event) => {
  if (event.key === "Enter") submitAuth();
});
document.getElementById("confirm-password").addEventListener("keydown", (event) => {
  if (event.key === "Enter") submitAuth();
});
loadCurrentUser();
