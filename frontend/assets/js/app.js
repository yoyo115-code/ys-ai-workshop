const TABS = ["career", "resume", "copywrite", "translate", "pdf", "csv", "admin"];
const AUTH_TOKEN_KEY = "nova_auth_token";
const API_CONFIG = window.YS_AI_CONFIG;
let currentUser = null;
let registrationMode = false;
let currentCareerApplicationId = null;

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
  if (name === "career") refreshCareerHistory();
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
    message = typeof detail === "string"
      ? detail
      : (detail?.message || JSON.stringify(detail || payload));
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
    switchTab("career");
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
    refreshCareerHistory();
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
    renderCareerHistory([]);
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
  if (currentUser) refreshCareerHistory();
}

const CAREER_GROUPS = [
  ["covered_requirements", "已覆盖能力"],
  ["partially_covered_requirements", "部分覆盖"],
  ["missing_requirements", "缺失能力"],
  ["uncertain_requirements", "信息不足"],
  ["resume_expression_issues", "表达问题"],
  ["qualification_risks", "岗位风险"]
];

const ALIGNMENT_LABELS = {
  strong_alignment: "高度匹配",
  partial_alignment: "部分匹配",
  significant_gaps: "存在显著差距",
  insufficient_evidence: "证据不足"
};

const CAREER_STATUS_LABELS = {
  ready: "待分析",
  analyzing: "分析中",
  completed: "已完成",
  analysis_failed: "分析失败",
  parse_failed: "文件解析失败"
};

function careerApplicationUrl(applicationId = "", suffix = "") {
  const base = API_CONFIG.endpoints.career.applications;
  return `${base}${applicationId ? `/${applicationId}` : ""}${suffix}`;
}

function setCareerMessage(message, state = "placeholder") {
  const target = document.getElementById("career-message");
  target.className = `career-message ${state}`;
  target.textContent = message;
}

function clearCareerFile() {
  document.getElementById("career-resume-file").value = "";
  document.getElementById("career-file-name").textContent = "尚未选择文件";
  document.getElementById("career-clear-file").hidden = true;
}

function onCareerFileChosen() {
  const input = document.getElementById("career-resume-file");
  const file = input.files[0];
  if (!file) {
    clearCareerFile();
    return;
  }
  const fileName = file.name.toLowerCase();
  if (!fileName.endsWith(".pdf") && !fileName.endsWith(".docx")) {
    clearCareerFile();
    setCareerMessage("文件类型不正确，请上传 PDF 或 DOCX 简历。", "error");
    return;
  }
  document.getElementById("career-resume-text").value = "";
  document.getElementById("career-file-name").textContent = `已选择：${file.name}`;
  document.getElementById("career-clear-file").hidden = false;
  setCareerMessage("简历文件已就绪。文件只用于提取文字，不保存原文件。", "placeholder");
}

async function submitCareerMatch() {
  const button = document.getElementById("career-analyze-btn");
  const resumeText = document.getElementById("career-resume-text").value.trim();
  const resumeFile = document.getElementById("career-resume-file").files[0];
  const jobDescription = document.getElementById("career-jd").value.trim();
  if (!currentUser) {
    setCareerMessage("请先登录，再保存和分析申请。", "error");
    return;
  }
  if (!resumeText && !resumeFile) {
    setCareerMessage("请粘贴简历文本或上传 PDF / DOCX 简历。", "error");
    return;
  }
  if (resumeText && resumeFile) {
    setCareerMessage("简历文本和文件只能选择一种。", "error");
    return;
  }
  if (!jobDescription) {
    setCareerMessage("请粘贴目标岗位 JD。", "error");
    return;
  }

  const form = new FormData();
  form.append("resume_text", resumeText);
  form.append("job_description", jobDescription);
  form.append("company_name", document.getElementById("career-company").value.trim());
  form.append("job_title", document.getElementById("career-job-title").value.trim());
  form.append("location", document.getElementById("career-location").value.trim());
  form.append("language", document.getElementById("career-language").value);
  if (resumeFile) form.append("resume_file", resumeFile);

  setButtonLoading(button, true);
  document.getElementById("career-result").hidden = true;
  setCareerMessage("正在保存申请并解析简历…", "loading");
  try {
    const response = await fetch(apiUrl(careerApplicationUrl()), {
      method: "POST",
      headers: authHeaders(),
      body: form
    });
    const payload = await getResponsePayload(response);
    if (!response.ok) {
      if (payload?.detail?.application_id) currentCareerApplicationId = payload.detail.application_id;
      throw new Error(formatError(response, payload));
    }
    currentCareerApplicationId = payload.id;
    await refreshCareerHistory();
    await analyzeCareerApplication(payload.id, false);
  } catch (error) {
    setCareerMessage(error.message || "申请创建失败，请检查输入后重试。", "error");
    await refreshCareerHistory();
  } finally {
    setButtonLoading(button, false);
  }
}

async function analyzeCareerApplication(applicationId, retry = false) {
  currentCareerApplicationId = applicationId;
  setCareerMessage(retry ? "正在重新分析，请稍候…" : "申请已保存，正在生成证据化匹配分析…", "loading");
  try {
    const response = await fetch(apiUrl(careerApplicationUrl(applicationId, "/analyze")), {
      method: "POST",
      headers: authHeaders(true),
      body: JSON.stringify({ retry })
    });
    const payload = await getResponsePayload(response);
    if (!response.ok) throw new Error(formatError(response, payload));
    renderCareerAnalysis(payload);
    setCareerMessage("分析已完成并保存。刷新或重新登录后仍可从右侧历史记录打开。", "success");
    await refreshCareerHistory();
  } catch (error) {
    document.getElementById("career-result").hidden = true;
    setCareerMessage(`${error.message || "模型调用失败。"}\n可以点击“重新分析”再次尝试。`, "error");
    document.getElementById("career-result").hidden = false;
    document.getElementById("career-overall").textContent = "分析未完成";
    document.getElementById("career-summary").textContent = "原始简历和 JD 已保存，失败不会丢失输入。";
    document.getElementById("career-result-groups").innerHTML = "";
    document.getElementById("career-limitations").textContent = "模型调用或结构校验失败，请重试。";
    await refreshCareerHistory();
  }
}

function renderCareerAnalysis(analysis) {
  document.getElementById("career-result").hidden = false;
  document.getElementById("career-overall").textContent = ALIGNMENT_LABELS[analysis.overall_alignment] || analysis.overall_alignment;
  document.getElementById("career-summary").textContent = analysis.summary;
  document.getElementById("career-result-meta").textContent = `${analysis.model} · ${analysis.prompt_version} · ${formatTime(analysis.created_at)}`;
  document.getElementById("career-result-groups").innerHTML = CAREER_GROUPS.map(([key, title]) => {
    const items = Array.isArray(analysis[key]) ? analysis[key] : [];
    const content = items.length
      ? items.map(item => `
        <article class="match-item confidence-${escapeHtml(item.confidence_level)}">
          <div><span class="match-label">JD 原始要求</span><p>${escapeHtml(item.jd_requirement)}</p></div>
          <div><span class="match-label">简历证据</span><p>${escapeHtml(item.resume_evidence || "无简历证据")}</p></div>
          <div><span class="match-label">解释</span><p>${escapeHtml(item.explanation)}</p></div>
          <span class="confidence-badge">证据：${escapeHtml(item.confidence_level)}</span>
        </article>`).join("")
      : '<div class="empty-state">本次分析未发现此类项目。</div>';
    return `<section class="result-group"><h3>${title}<span>${items.length}</span></h3><div class="match-items">${content}</div></section>`;
  }).join("");
  const limitations = analysis.analysis_limitations || [];
  document.getElementById("career-limitations").innerHTML = limitations.length
    ? `<ul>${limitations.map(item => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`
    : "暂无额外限制。";
}

function renderCareerHistory(applications) {
  const container = document.getElementById("career-history");
  if (!currentUser) {
    container.innerHTML = '<div class="empty-state">登录后可查看保存的申请。</div>';
    return;
  }
  if (!applications.length) {
    container.innerHTML = '<div class="empty-state">还没有申请记录。完成左侧输入后，第一份记录会显示在这里。</div>';
    return;
  }
  container.innerHTML = applications.map(application => `
    <article class="history-item ${application.id === currentCareerApplicationId ? "active" : ""}">
      <button class="history-open" type="button" onclick="openCareerApplication(${application.id})">
        <strong>${escapeHtml(application.company_name || "未填写公司")}</strong>
        <span>${escapeHtml(application.job_title || "未填写岗位")}</span>
        <small>${escapeHtml(formatTime(application.created_at))}</small>
        <em class="history-status status-${escapeHtml(application.status)}">${escapeHtml(CAREER_STATUS_LABELS[application.status] || application.status)}</em>
      </button>
      <button class="history-delete" type="button" aria-label="删除申请" onclick="deleteCareerApplication(${application.id})">删除</button>
    </article>`).join("");
}

async function refreshCareerHistory() {
  if (!currentUser) {
    renderCareerHistory([]);
    return;
  }
  const container = document.getElementById("career-history");
  container.innerHTML = '<div class="empty-state">正在加载历史记录…</div>';
  try {
    const response = await fetch(apiUrl(careerApplicationUrl()), { headers: authHeaders() });
    const payload = await getResponsePayload(response);
    if (!response.ok) throw new Error(formatError(response, payload));
    renderCareerHistory(payload);
  } catch (error) {
    container.innerHTML = `<div class="empty-state error-state">${escapeHtml(error.message || "历史记录加载失败")}</div>`;
  }
}

async function openCareerApplication(applicationId) {
  try {
    const response = await fetch(apiUrl(careerApplicationUrl(applicationId)), { headers: authHeaders() });
    const payload = await getResponsePayload(response);
    if (!response.ok) throw new Error(formatError(response, payload));
    currentCareerApplicationId = payload.id;
    document.getElementById("career-company").value = payload.company_name;
    document.getElementById("career-job-title").value = payload.job_title;
    document.getElementById("career-location").value = payload.location;
    document.getElementById("career-language").value = payload.language;
    document.getElementById("career-jd").value = payload.job_description;
    document.getElementById("career-resume-text").value = payload.resume_source.source_type === "text" ? payload.resume_source.extracted_text : "";
    clearCareerFile();
    if (payload.resume_source.original_filename) {
      document.getElementById("career-file-name").textContent = `已保存文本来源：${payload.resume_source.original_filename}`;
    }
    if (payload.latest_analysis) {
      renderCareerAnalysis(payload.latest_analysis);
      setCareerMessage(
        payload.latest_analysis_error_code
          ? `最近一次重试未完成（${payload.latest_analysis_error_code}），当前展示上一次成功分析。`
          : "已打开保存的匹配分析。",
        payload.latest_analysis_error_code ? "error" : "success"
      );
    } else {
      const reason = payload.resume_source.parse_error || payload.latest_analysis_error_code;
      const canAnalyze = payload.resume_source.parse_status === "parsed";
      document.getElementById("career-result").hidden = !canAnalyze;
      if (canAnalyze) {
        document.getElementById("career-overall").textContent = payload.status === "analysis_failed" ? "分析未完成" : "等待分析";
        document.getElementById("career-summary").textContent = "申请输入已保存，可以重新发起匹配分析。";
        document.getElementById("career-result-meta").textContent = "";
        document.getElementById("career-result-groups").innerHTML = "";
        document.getElementById("career-limitations").textContent = reason || "尚未生成分析结果。";
      }
      setCareerMessage(reason ? `此记录未完成：${reason}` : "申请已保存，尚未完成分析。", reason ? "error" : "placeholder");
    }
    renderCareerHistory(await fetchCareerHistory());
  } catch (error) {
    setCareerMessage(error.message || "申请详情加载失败。", "error");
  }
}

async function fetchCareerHistory() {
  const response = await fetch(apiUrl(careerApplicationUrl()), { headers: authHeaders() });
  if (!response.ok) return [];
  return response.json();
}

async function deleteCareerApplication(applicationId) {
  if (!window.confirm("确认删除这条申请及其分析结果？")) return;
  try {
    const response = await fetch(apiUrl(careerApplicationUrl(applicationId)), {
      method: "DELETE",
      headers: authHeaders()
    });
    if (!response.ok) throw new Error("删除失败，请稍后重试。");
    if (currentCareerApplicationId === applicationId) {
      currentCareerApplicationId = null;
      document.getElementById("career-result").hidden = true;
      setCareerMessage("申请已删除。", "success");
    }
    await refreshCareerHistory();
  } catch (error) {
    setCareerMessage(error.message, "error");
  }
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
document.getElementById("career-analyze-btn").addEventListener("click", submitCareerMatch);
document.getElementById("career-resume-file").addEventListener("change", onCareerFileChosen);
document.getElementById("career-clear-file").addEventListener("click", clearCareerFile);
document.getElementById("career-refresh-btn").addEventListener("click", refreshCareerHistory);
document.getElementById("career-retry-btn").addEventListener("click", () => {
  if (currentCareerApplicationId) analyzeCareerApplication(currentCareerApplicationId, true);
});
document.getElementById("career-resume-text").addEventListener("input", (event) => {
  if (event.target.value.trim()) clearCareerFile();
});
document.getElementById("password").addEventListener("keydown", (event) => {
  if (event.key === "Enter") submitAuth();
});
document.getElementById("confirm-password").addEventListener("keydown", (event) => {
  if (event.key === "Enter") submitAuth();
});
loadCurrentUser();
