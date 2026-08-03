const TABS = ["career", "optimizer", "resume", "copywrite", "translate", "pdf", "csv", "admin"];
const API_CONFIG = window.YS_AI_CONFIG;
let currentUser = null;
let registrationMode = false;
let publicConfiguration = {
  registration_mode: "open",
  export_retention_days: 7,
  private_beta: false,
  ai_labs_enabled: false,
  session_active: false
};
let currentCareerApplicationId = null;
let optimizerWorkspace = null;
let optimizerVersions = [];
let optimizerFilter = "all";
let optimizerDirty = false;
let lastOptimizerSuggestionId = null;
let resumeExportVersionId = null;
let resumeExportData = null;
let resumeExportHistory = [];
let resumeExportDirty = false;

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
  const optimizerIsActive = document.getElementById("panel-optimizer")?.classList.contains("active");
  if (optimizerIsActive && name !== "optimizer" && (optimizerDirty || resumeExportDirty)) {
    const confirmed = window.confirm("有尚未生成文件的编辑，确定离开 Resume Optimizer？");
    if (!confirmed) return;
    optimizerDirty = false;
    resumeExportDirty = false;
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
  if (name === "optimizer") loadOptimizerApplications();
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
  if (!loggedIn) {
    document.getElementById("daily-usage-summary").textContent = "今日剩余：登录后查看";
  }
}

function applyAiLabsAvailability(enabled) {
  document.getElementById("ai-labs-nav-label").hidden = !enabled;
  document.querySelectorAll("[data-ai-lab-nav], [data-ai-lab-panel]").forEach(element => {
    element.hidden = !enabled;
  });
  const activeLab = ["resume", "copywrite", "translate", "pdf", "csv"]
    .some(name => document.getElementById(`panel-${name}`)?.classList.contains("active"));
  if (!enabled && activeLab) switchTab("career");
}

async function refreshDailyUsage() {
  const target = document.getElementById("daily-usage-summary");
  if (!currentUser) {
    target.textContent = "今日剩余：登录后查看";
    return;
  }
  try {
    const response = await fetch(apiUrl(API_CONFIG.endpoints.dailyUsage));
    if (!response.ok) throw new Error("usage unavailable");
    const quotas = (await response.json()).quotas || {};
    const analysis = quotas.career_analysis;
    const suggestions = quotas.suggestion_generation;
    const display = value => value?.unlimited ? "不限" : (value?.remaining ?? "-");
    target.textContent = `今日剩余：分析 ${display(analysis)} · 建议生成 ${display(suggestions)}`;
  } catch {
    target.textContent = "今日剩余：暂时无法读取";
  }
}

function setRegistrationMode(enabled) {
  if (enabled && publicConfiguration.registration_mode === "disabled") return;
  registrationMode = enabled;
  document.getElementById("display-name").hidden = !enabled;
  document.getElementById("confirm-password").hidden = !enabled;
  document.getElementById("invite-code").hidden = !enabled || publicConfiguration.registration_mode !== "invite_only";
  document.getElementById("login-btn").textContent = enabled ? "创建账号" : "登录";
  document.getElementById("auth-switch-btn").textContent = enabled ? "返回登录" : "注册新账号";
  document.getElementById("password").autocomplete = enabled ? "new-password" : "current-password";
  document.getElementById("auth-message").textContent = enabled
    ? (publicConfiguration.registration_mode === "invite_only"
      ? "Private Beta 仅限受邀用户；请输入管理员单独发送的邀请码。"
      : "账号仅支持小写字母、数字和下划线；密码至少 8 位并包含字母和数字。")
    : "请输入账号密码，或注册新账号。";
}

async function loadPublicConfiguration() {
  try {
    const response = await fetch(apiUrl(API_CONFIG.endpoints.publicConfig));
    if (!response.ok) throw new Error("configuration unavailable");
    publicConfiguration = await response.json();
    applyAiLabsAvailability(publicConfiguration.ai_labs_enabled !== false);
    const retentionDays = publicConfiguration.export_retention_days || 7;
    document.getElementById("retention-summary").textContent =
      `导出文件默认保留 ${retentionDays} 天；可随时删除申请、简历、导出或账号。`;
    const switchButton = document.getElementById("auth-switch-btn");
    switchButton.hidden = publicConfiguration.registration_mode === "disabled";
    if (publicConfiguration.registration_mode === "invite_only") {
      switchButton.textContent = "使用邀请码注册";
    }
  } catch {
    document.getElementById("auth-message").textContent = API_CONFIG.isFilePreview
      ? "当前为界面预览；请通过 http://127.0.0.1:8000 使用登录和完整功能。"
      : "公开配置暂未加载，请稍后重试。";
  }
}

async function submitAuth() {
  const button = document.getElementById("login-btn");
  const message = document.getElementById("auth-message");
  const username = document.getElementById("username").value.trim();
  const password = document.getElementById("password").value;
  const displayName = document.getElementById("display-name").value.trim();
  const confirmPassword = document.getElementById("confirm-password").value;
  const inviteCode = document.getElementById("invite-code").value.trim();

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
        ? { username, password, display_name: displayName, invite_code: inviteCode }
        : { username, password })
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || (registrationMode ? "注册失败" : "登录失败"));
    currentUser = data.user;
    setRegistrationMode(false);
    updateAuthUI();
    await refreshDailyUsage();
    refreshCareerHistory();
  } catch (error) {
    message.textContent = error.message;
  } finally {
    button.disabled = false;
  }
}

async function deleteAccount() {
  if (!currentUser) return;
  const confirmed = window.confirm(
    "这会删除账号、申请、简历版本、建议和导出文件，且无法撤销。确定继续？"
  );
  if (!confirmed) return;
  const password = window.prompt("请输入当前密码以确认删除账号：");
  if (!password) return;
  try {
    const response = await fetch(apiUrl(API_CONFIG.endpoints.auth.account), {
      method: "DELETE",
      headers: authHeaders(true),
      body: JSON.stringify({ password })
    });
    const payload = await getResponsePayload(response);
    if (!response.ok) throw new Error(formatError(response, payload));
    currentUser = null;
    updateAuthUI();
    renderCareerHistory([]);
    resetOptimizerUI();
    window.alert("账号及关联数据已删除。");
  } catch (error) {
    window.alert(error.message || "数据删除未完成，请稍后重试。");
  }
}

async function logout() {
  try {
    await fetch(apiUrl(API_CONFIG.endpoints.auth.logout), {
      method: "POST",
      headers: authHeaders()
    });
  } finally {
    currentUser = null;
    updateAuthUI();
    renderCareerHistory([]);
    resetOptimizerUI();
  }
}

async function loadCurrentUser() {
  try {
    const response = await fetch(apiUrl(API_CONFIG.endpoints.auth.me), {
      headers: authHeaders()
    });
    if (!response.ok) throw new Error("session expired");
    currentUser = (await response.json()).user;
  } catch {
    currentUser = null;
  }
  updateAuthUI();
  if (currentUser) {
    await refreshDailyUsage();
    refreshCareerHistory();
  }
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
  await refreshDailyUsage();
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
      ${application.status === "completed" ? `<button class="history-optimize" type="button" onclick="openOptimizerForApplication(${application.id})">优化简历</button>` : ""}
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

const OPTIMIZER_STATUS_LABELS = {
  pending: "Pending",
  accepted: "Accepted",
  rejected: "Rejected",
  edited: "Edited",
  superseded: "Superseded"
};

const VERSION_SOURCE_LABELS = {
  uploaded: "Uploaded",
  parsed: "Parsed source",
  optimized: "Accepted suggestions",
  manual_edit: "Manual edit",
  restored: "Restored snapshot"
};

function optimizerApplicationPath(applicationId, suffix = "") {
  return `/career/applications/${applicationId}${suffix}`;
}

function optimizerSuggestionPath(suggestionId, suffix = "") {
  return `${API_CONFIG.endpoints.optimizer.suggestions}/${suggestionId}${suffix}`;
}

function optimizerVersionPath(versionId, suffix = "") {
  return `${API_CONFIG.endpoints.optimizer.versions}/${versionId}${suffix}`;
}

function setOptimizerMessage(message, state = "placeholder", retry = false) {
  const target = document.getElementById("optimizer-message");
  target.className = `career-message ${state}`;
  target.textContent = message;
  document.getElementById("optimizer-retry-btn").hidden = !retry;
}

function markOptimizerDirty() {
  optimizerDirty = true;
  setOptimizerMessage("建议文本有未保存编辑，请点击对应卡片的“保存编辑”。", "loading");
}

async function loadOptimizerApplications(selectedApplicationId = null) {
  const select = document.getElementById("optimizer-application-select");
  if (!currentUser) {
    select.innerHTML = '<option value="">请先登录</option>';
    setOptimizerMessage("请先登录，再打开 Resume Optimizer。", "error");
    return;
  }
  const previous = selectedApplicationId || select.value || optimizerWorkspace?.application_id;
  try {
    const response = await fetch(apiUrl(API_CONFIG.endpoints.career.applications), { headers: authHeaders() });
    const payload = await getResponsePayload(response);
    if (!response.ok) throw new Error(formatError(response, payload));
    const eligibleApplications = payload.filter(application => application.status === "completed");
    select.innerHTML = '<option value="">请选择已完成分析的申请</option>' + eligibleApplications.map(application => `
      <option value="${application.id}">${escapeHtml(application.company_name || "未填写公司")} · ${escapeHtml(application.job_title || "未填写岗位")} · ${escapeHtml(CAREER_STATUS_LABELS[application.status] || application.status)}</option>
    `).join("");
    if (previous && eligibleApplications.some(item => item.id === Number(previous))) {
      select.value = String(previous);
    }
    if (!eligibleApplications.length) {
      setOptimizerMessage("还没有已完成分析的申请。请先完成 Career Match。", "placeholder");
    }
  } catch (error) {
    setOptimizerMessage(error.message || "申请记录加载失败。", "error", true);
  }
}

async function openOptimizerForApplication(applicationId) {
  optimizerDirty = false;
  switchTab("optimizer");
  await loadOptimizerApplications(applicationId);
  document.getElementById("optimizer-application-select").value = String(applicationId);
  await loadOptimizerWorkspace(applicationId);
}

async function loadSelectedOptimizerWorkspace() {
  const applicationId = Number(document.getElementById("optimizer-application-select").value);
  if (!applicationId) {
    setOptimizerMessage("请选择一条申请记录。", "error");
    return;
  }
  await loadOptimizerWorkspace(applicationId);
}

async function loadOptimizerWorkspace(applicationId) {
  setOptimizerMessage("正在加载简历版本和建议状态…", "loading");
  document.getElementById("optimizer-suggestions").innerHTML = '<div class="empty-state">Loading suggestions…</div>';
  try {
    const response = await fetch(
      apiUrl(optimizerApplicationPath(applicationId, "/resume-suggestions")),
      { headers: authHeaders() }
    );
    const payload = await getResponsePayload(response);
    if (!response.ok) throw new Error(formatError(response, payload));
    optimizerWorkspace = payload;
    optimizerDirty = false;
    renderOptimizerWorkspace();
    await loadOptimizerVersions();
    setOptimizerMessage("工作区已加载。所有建议状态和版本都会保存到当前账号。", "success");
  } catch (error) {
    setOptimizerMessage(error.message || "工作区加载失败。", "error", true);
    document.getElementById("optimizer-suggestions").innerHTML = '<div class="empty-state error-state">加载失败，请点击 Retry。</div>';
  }
}

function renderOptimizerWorkspace() {
  if (!optimizerWorkspace) return;
  document.getElementById("optimizer-job").textContent = `${optimizerWorkspace.company_name || "未填写公司"} / ${optimizerWorkspace.job_title || "未填写岗位"}`;
  document.getElementById("optimizer-version-number").textContent = `v${optimizerWorkspace.current_version.version_number}`;
  document.getElementById("optimizer-accepted-count").textContent = optimizerWorkspace.accepted_count;
  document.getElementById("optimizer-pending-count").textContent = optimizerWorkspace.pending_count;
  document.getElementById("optimizer-resume-content").className = "resume-content";
  document.getElementById("optimizer-resume-content").textContent = optimizerWorkspace.current_version.content;
  renderOptimizerSuggestions();
}

function visibleOptimizerSuggestions() {
  if (!optimizerWorkspace) return [];
  return optimizerWorkspace.suggestions.filter(suggestion => {
    if (optimizerFilter === "all") return true;
    if (optimizerFilter === "accepted") return ["accepted", "edited"].includes(suggestion.status);
    if (optimizerFilter === "risk") return suggestion.risk_level === "high" || suggestion.clarification_required;
    return suggestion.status === optimizerFilter;
  });
}

function renderOptimizerSuggestions() {
  const container = document.getElementById("optimizer-suggestions");
  const suggestions = visibleOptimizerSuggestions();
  if (!optimizerWorkspace?.suggestions.length) {
    container.innerHTML = '<div class="empty-state">Empty：尚未生成逐条建议。点击顶部“生成逐条建议”。</div>';
    return;
  }
  if (!suggestions.length) {
    container.innerHTML = '<div class="empty-state">当前筛选条件下没有建议。</div>';
    return;
  }
  container.innerHTML = suggestions.map(suggestion => {
    const blocked = suggestion.risk_level === "high" || suggestion.clarification_required;
    const canDecide = suggestion.status === "pending";
    const canEdit = ["pending", "edited"].includes(suggestion.status);
    const canRegenerate = suggestion.status !== "superseded";
    return `
      <article class="suggestion-card status-${escapeHtml(suggestion.status)}" data-suggestion-id="${suggestion.id}">
        <div class="suggestion-card-top">
          <div class="suggestion-tags">
            <span class="suggestion-status">${escapeHtml(OPTIMIZER_STATUS_LABELS[suggestion.status] || suggestion.status)}</span>
            <span class="risk-badge risk-${escapeHtml(suggestion.risk_level)}">Risk: ${escapeHtml(suggestion.risk_level)}</span>
            ${suggestion.clarification_required ? '<span class="clarification-badge">需要事实确认</span>' : ""}
          </div>
          <small>${escapeHtml(suggestion.section_key)} · generation ${suggestion.generation_number}</small>
        </div>
        <div class="suggestion-field"><span>原句</span><p>${escapeHtml(suggestion.source_text)}</p></div>
        <label class="suggestion-field">建议句
          <textarea id="optimizer-edit-${suggestion.id}" class="suggestion-edit" oninput="markOptimizerDirty()" ${canEdit ? "" : "disabled"}>${escapeHtml(suggestion.suggested_text)}</textarea>
        </label>
        <div class="suggestion-field"><span>修改原因</span><p>${escapeHtml(suggestion.reason)}</p></div>
        <div class="suggestion-evidence-grid">
          <div class="suggestion-field"><span>JD 依据</span><p>${escapeHtml(suggestion.jd_evidence || "无可验证 JD 证据")}</p></div>
          <div class="suggestion-field"><span>简历依据</span><p>${escapeHtml(suggestion.resume_evidence || "无可验证简历证据")}</p></div>
        </div>
        <div class="suggestion-actions">
          ${canDecide ? `<button class="secondary-btn suggestion-accept" type="button" onclick="updateOptimizerSuggestion(${suggestion.id}, 'accept')" ${blocked ? 'disabled title="高风险或待确认建议必须先编辑"' : ""}>接受</button>` : ""}
          ${canDecide ? `<button class="secondary-btn" type="button" onclick="updateOptimizerSuggestion(${suggestion.id}, 'reject')">拒绝</button>` : ""}
          ${canEdit ? `<button class="secondary-btn" type="button" onclick="saveOptimizerSuggestionEdit(${suggestion.id}, ${blocked})">保存编辑</button>` : ""}
          ${canRegenerate ? `<button class="secondary-btn" type="button" onclick="regenerateOptimizerSuggestion(${suggestion.id})">重新生成此条</button>` : ""}
        </div>
      </article>`;
  }).join("");
}

async function generateOptimizerSuggestions(retry = false) {
  const applicationId = Number(document.getElementById("optimizer-application-select").value || optimizerWorkspace?.application_id);
  if (!applicationId) {
    setOptimizerMessage("请先选择申请。", "error");
    return;
  }
  const button = document.getElementById("optimizer-generate-btn");
  setButtonLoading(button, true);
  setOptimizerMessage(retry ? "正在重试生成建议…" : "正在生成有证据的逐条建议…", "loading");
  try {
    const response = await fetch(
      apiUrl(optimizerApplicationPath(applicationId, "/resume-suggestions/generate")),
      {
        method: "POST",
        headers: authHeaders(true),
        body: JSON.stringify({ retry })
      }
    );
    const payload = await getResponsePayload(response);
    if (!response.ok) throw new Error(formatError(response, payload));
    optimizerWorkspace = payload;
    optimizerDirty = false;
    renderOptimizerWorkspace();
    await loadOptimizerVersions();
    setOptimizerMessage("建议已生成并保存。请逐条核查事实后再创建版本。", "success");
  } catch (error) {
    setOptimizerMessage(error.message || "建议生成失败。", "error", true);
  } finally {
    setButtonLoading(button, false);
    await refreshDailyUsage();
  }
}

async function updateOptimizerSuggestion(suggestionId, action) {
  if (optimizerDirty && !window.confirm("此操作会放弃尚未保存的建议文本编辑，是否继续？")) return;
  optimizerDirty = false;
  setOptimizerMessage("正在保存建议状态…", "loading");
  try {
    const response = await fetch(apiUrl(optimizerSuggestionPath(suggestionId)), {
      method: "PATCH",
      headers: authHeaders(true),
      body: JSON.stringify({ action })
    });
    const payload = await getResponsePayload(response);
    if (!response.ok) throw new Error(formatError(response, payload));
    lastOptimizerSuggestionId = suggestionId;
    document.getElementById("optimizer-undo-btn").disabled = false;
    optimizerDirty = false;
    await loadOptimizerWorkspace(optimizerWorkspace.application_id);
    setOptimizerMessage(`建议已${action === "accept" ? "接受" : "拒绝"}并保存。`, "success");
  } catch (error) {
    setOptimizerMessage(error.message || "建议状态保存失败。", "error", true);
  }
}

async function saveOptimizerSuggestionEdit(suggestionId, requiresConfirmation) {
  const suggestedText = document.getElementById(`optimizer-edit-${suggestionId}`).value.trim();
  if (!suggestedText) {
    setOptimizerMessage("编辑后的建议不能为空。", "error");
    return;
  }
  let confirmRisk = false;
  if (requiresConfirmation) {
    confirmRisk = window.confirm("该建议包含事实风险或证据不足。请确认你已核实并手工修正内容。是否继续保存？");
    if (!confirmRisk) return;
  }
  setOptimizerMessage("正在保存手工编辑…", "loading");
  try {
    const response = await fetch(apiUrl(optimizerSuggestionPath(suggestionId)), {
      method: "PATCH",
      headers: authHeaders(true),
      body: JSON.stringify({ action: "edit", suggested_text: suggestedText, confirm_risk: confirmRisk })
    });
    const payload = await getResponsePayload(response);
    if (!response.ok) throw new Error(formatError(response, payload));
    lastOptimizerSuggestionId = suggestionId;
    document.getElementById("optimizer-undo-btn").disabled = false;
    optimizerDirty = false;
    await loadOptimizerWorkspace(optimizerWorkspace.application_id);
    setOptimizerMessage("手工编辑已保存，并记录到建议事件历史。", "success");
  } catch (error) {
    setOptimizerMessage(error.message || "编辑保存失败。", "error", true);
  }
}

async function regenerateOptimizerSuggestion(suggestionId) {
  if (optimizerDirty && !window.confirm("重新生成会放弃当前未保存编辑，是否继续？")) return;
  optimizerDirty = false;
  setOptimizerMessage("正在重新生成这一条建议，旧记录会保留…", "loading");
  try {
    const response = await fetch(apiUrl(optimizerSuggestionPath(suggestionId, "/regenerate")), {
      method: "POST",
      headers: authHeaders()
    });
    const payload = await getResponsePayload(response);
    if (!response.ok) throw new Error(formatError(response, payload));
    await loadOptimizerWorkspace(optimizerWorkspace.application_id);
    setOptimizerMessage("新建议已生成；旧建议标记为 Superseded 并继续保留。", "success");
  } catch (error) {
    setOptimizerMessage(error.message || "单条建议重新生成失败。", "error", true);
  } finally {
    await refreshDailyUsage();
  }
}

async function undoOptimizerSuggestion() {
  if (!lastOptimizerSuggestionId) return;
  setOptimizerMessage("正在撤销最近一次建议操作…", "loading");
  try {
    const response = await fetch(
      apiUrl(optimizerSuggestionPath(lastOptimizerSuggestionId, "/undo")),
      { method: "POST", headers: authHeaders() }
    );
    const payload = await getResponsePayload(response);
    if (!response.ok) throw new Error(formatError(response, payload));
    lastOptimizerSuggestionId = null;
    document.getElementById("optimizer-undo-btn").disabled = true;
    optimizerDirty = false;
    await loadOptimizerWorkspace(optimizerWorkspace.application_id);
    setOptimizerMessage(`已撤销最近的 ${payload.undone_event_type} 操作。`, "success");
  } catch (error) {
    setOptimizerMessage(error.message || "Undo 失败。", "error", true);
  }
}

async function createOptimizerVersion() {
  if (!optimizerWorkspace) {
    setOptimizerMessage("请先打开工作区。", "error");
    return;
  }
  if (optimizerDirty) {
    setOptimizerMessage("请先保存或放弃卡片中的手工编辑。", "error");
    return;
  }
  const button = document.getElementById("optimizer-create-version-btn");
  setButtonLoading(button, true);
  setOptimizerMessage("正在事务化生成新版本…", "loading");
  try {
    const response = await fetch(
      apiUrl(optimizerApplicationPath(optimizerWorkspace.application_id, "/resume-versions")),
      { method: "POST", headers: authHeaders() }
    );
    const payload = await getResponsePayload(response);
    if (!response.ok) throw new Error(formatError(response, payload));
    await loadOptimizerWorkspace(optimizerWorkspace.application_id);
    setOptimizerMessage(`版本 v${payload.version_number} 已保存，旧版本保持不变。`, "success");
  } catch (error) {
    setOptimizerMessage(error.message || "版本生成失败，没有保存半成品。", "error", true);
  } finally {
    setButtonLoading(button, false);
  }
}

async function loadOptimizerVersions() {
  if (!optimizerWorkspace) return;
  try {
    const response = await fetch(
      apiUrl(`${API_CONFIG.endpoints.optimizer.resumes}/${optimizerWorkspace.resume.id}/versions`),
      { headers: authHeaders() }
    );
    const payload = await getResponsePayload(response);
    if (!response.ok) throw new Error(formatError(response, payload));
    optimizerVersions = payload;
    renderOptimizerVersions();
  } catch (error) {
    document.getElementById("optimizer-version-history").innerHTML = `<div class="empty-state error-state">${escapeHtml(error.message || "版本历史加载失败")}</div>`;
  }
}

function renderOptimizerVersions() {
  const options = optimizerVersions.map(version => `
    <option value="${version.id}">v${version.version_number} · ${escapeHtml(VERSION_SOURCE_LABELS[version.source_type] || version.source_type)}</option>
  `).join("");
  document.getElementById("optimizer-version-select").innerHTML = options;
  document.getElementById("optimizer-compare-from").innerHTML = options;
  document.getElementById("optimizer-compare-to").innerHTML = options;
  if (optimizerWorkspace) {
    document.getElementById("optimizer-version-select").value = String(optimizerWorkspace.current_version.id);
    document.getElementById("optimizer-compare-from").value = String(optimizerWorkspace.current_version.id);
    const previous = optimizerVersions.find(version => version.id !== optimizerWorkspace.current_version.id);
    if (previous) document.getElementById("optimizer-compare-to").value = String(previous.id);
  }
  document.getElementById("optimizer-version-history").innerHTML = optimizerVersions.map(version => `
    <article class="version-item ${version.id === optimizerWorkspace?.current_version.id ? "active" : ""}">
      <button type="button" onclick="viewOptimizerVersion(${version.id})">
        <strong>v${version.version_number}</strong>
        <span>${escapeHtml(VERSION_SOURCE_LABELS[version.source_type] || version.source_type)}</span>
        <small>${escapeHtml(formatTime(version.created_at))} · parent ${version.parent_version_id || "none"}</small>
      </button>
      ${version.id !== optimizerWorkspace?.current_version.id ? `<button class="secondary-btn" type="button" onclick="restoreOptimizerVersion(${version.id})">恢复</button>` : '<span class="current-version-badge">Current</span>'}
    </article>
  `).join("") || '<div class="empty-state">暂无版本。</div>';
}

async function viewOptimizerVersion(versionId) {
  try {
    const response = await fetch(apiUrl(optimizerVersionPath(versionId)), { headers: authHeaders() });
    const payload = await getResponsePayload(response);
    if (!response.ok) throw new Error(formatError(response, payload));
    document.getElementById("optimizer-version-select").value = String(versionId);
    document.getElementById("optimizer-resume-content").textContent = payload.content;
    setOptimizerMessage(`正在查看历史版本 v${payload.version_number}；当前版本没有被改变。`, "placeholder");
  } catch (error) {
    setOptimizerMessage(error.message || "版本加载失败。", "error", true);
  }
}

async function compareOptimizerVersions() {
  const fromId = Number(document.getElementById("optimizer-compare-from").value);
  const toId = Number(document.getElementById("optimizer-compare-to").value);
  if (!fromId || !toId) {
    setOptimizerMessage("请选择两个版本进行比较。", "error");
    return;
  }
  try {
    const response = await fetch(
      apiUrl(optimizerVersionPath(fromId, `/compare/${toId}`)),
      { headers: authHeaders() }
    );
    const payload = await getResponsePayload(response);
    if (!response.ok) throw new Error(formatError(response, payload));
    renderOptimizerDiff(payload);
    setOptimizerMessage(`已比较 v${payload.from_version.version_number} 与 v${payload.to_version.version_number}。`, "success");
  } catch (error) {
    setOptimizerMessage(error.message || "版本比较失败。", "error", true);
  }
}

function renderOptimizerDiff(diff) {
  const container = document.getElementById("optimizer-diff");
  container.hidden = false;
  const changes = diff.changes || [];
  container.innerHTML = `
    <div class="diff-heading"><strong>v${diff.from_version.version_number} → v${diff.to_version.version_number}</strong><span>${escapeHtml(VERSION_SOURCE_LABELS[diff.to_version.source_type] || diff.to_version.source_type)} · ${escapeHtml(formatTime(diff.to_version.created_at))} · parent ${diff.to_version.parent_version_id || "none"}</span></div>
    ${changes.length ? changes.map(change => `
      <div class="diff-change diff-${escapeHtml(change.change_type)}">
        <span>${escapeHtml(change.change_type)}</span>
        ${change.before.map(line => `<del>${escapeHtml(line)}</del>`).join("")}
        ${change.after.map(line => `<ins>${escapeHtml(line)}</ins>`).join("")}
      </div>`).join("") : '<div class="empty-state">两个版本内容相同。</div>'}
  `;
}

async function restoreOptimizerVersion(versionId) {
  if (!window.confirm("恢复会创建一个新的版本快照，不会删除现有历史。是否继续？")) return;
  try {
    const response = await fetch(apiUrl(optimizerVersionPath(versionId, "/restore")), {
      method: "POST",
      headers: authHeaders()
    });
    const payload = await getResponsePayload(response);
    if (!response.ok) throw new Error(formatError(response, payload));
    await loadOptimizerWorkspace(optimizerWorkspace.application_id);
    setOptimizerMessage(`已创建 restored 版本 v${payload.version_number}。`, "success");
  } catch (error) {
    setOptimizerMessage(error.message || "版本恢复失败。", "error", true);
  }
}

function resumeExportPath(exportId = "", suffix = "") {
  return `${API_CONFIG.endpoints.optimizer.exports}${exportId ? `/${exportId}` : ""}${suffix}`;
}

function setResumeExportMessage(message, state = "placeholder", retry = false) {
  const target = document.getElementById("export-message");
  target.className = `career-message ${state}`;
  target.textContent = message;
  document.getElementById("export-retry-btn").hidden = !retry;
}

async function openResumeExport() {
  if (!currentUser || !optimizerWorkspace) {
    setOptimizerMessage("请先登录并打开 Resume Optimizer 工作区。", "error");
    return;
  }
  const versionId = Number(
    document.getElementById("optimizer-version-select").value
      || optimizerWorkspace.current_version.id
  );
  if (!versionId) {
    setOptimizerMessage("请选择需要导出的 ResumeVersion。", "error");
    return;
  }
  const workspace = document.getElementById("resume-export-workspace");
  workspace.hidden = false;
  workspace.scrollIntoView({ behavior: "smooth", block: "start" });
  resumeExportVersionId = versionId;
  resumeExportData = null;
  resumeExportDirty = false;
  setResumeExportMessage("正在结构化 ResumeVersion…", "loading");
  document.getElementById("export-preview").innerHTML = '<div class="empty-state">Loading preview…</div>';
  try {
    const response = await fetch(
      apiUrl(optimizerVersionPath(versionId, "/preview")),
      { headers: authHeaders() }
    );
    const payload = await getResponsePayload(response);
    if (!response.ok) throw new Error(formatError(response, payload));
    resumeExportData = payload.resume;
    document.getElementById("export-version-label").textContent = `v${payload.version_number}`;
    document.getElementById("export-job-label").textContent = `${payload.company_name || "未填写公司"} / ${payload.job_title || "未填写岗位"}`;
    document.getElementById("export-parse-label").textContent = payload.parse_status === "structured" ? "Structured" : "Needs review";
    renderResumeExportEditor();
    renderResumeExportPreview();
    await loadResumeExportHistory();
    const warning = (payload.parse_warnings || []).join(" ");
    setResumeExportMessage(
      warning || "结构化预览已就绪。请核对内容后生成文件。",
      warning ? "error" : "success"
    );
  } catch (error) {
    setResumeExportMessage(error.message || "结构化预览失败。", "error", true);
    document.getElementById("export-preview").innerHTML = '<div class="empty-state error-state">Preview unavailable，请检查 ResumeVersion 文本。</div>';
  }
}

function renderResumeExportEditor() {
  if (!resumeExportData) return;
  const basics = resumeExportData.basics || {};
  document.getElementById("export-name").value = basics.name || "";
  document.getElementById("export-email").value = basics.email || "";
  document.getElementById("export-phone").value = basics.phone || "";
  document.getElementById("export-location").value = basics.location || "";
  document.getElementById("export-links").value = (basics.links || []).join("\n");
  document.getElementById("export-summary").value = basics.summary || "";
  ["experience", "projects", "education"].forEach(key => renderResumeExportEntries(key));
  document.getElementById("export-skills").value = (resumeExportData.skills || []).join("\n");
  document.getElementById("export-certifications").value = (resumeExportData.certifications || []).join("\n");
  document.getElementById("export-awards").value = (resumeExportData.awards || []).join("\n");
  document.getElementById("export-additional").value = (resumeExportData.additional_information || []).join("\n");
}

function renderResumeExportEntries(key) {
  const container = document.getElementById(`export-${key}-editor`);
  const entries = resumeExportData?.[key] || [];
  container.innerHTML = entries.map((entry, index) => `
    <article class="export-entry-card" data-export-entry="${escapeHtml(key)}" data-entry-index="${index}">
      <div class="export-entry-card-heading"><strong>${escapeHtml(key)} ${index + 1}</strong><button type="button" class="secondary-btn" onclick="removeResumeExportEntry('${escapeHtml(key)}', ${index})">删除</button></div>
      <div class="export-entry-grid">
        <label>Title<input data-entry-field="title" value="${escapeHtml(entry.title || "")}"></label>
        <label>Organization<input data-entry-field="organization" value="${escapeHtml(entry.organization || "")}"></label>
        <label>Location<input data-entry-field="location" value="${escapeHtml(entry.location || "")}"></label>
        <label>Start date<input data-entry-field="start_date" value="${escapeHtml(entry.start_date || "")}"></label>
        <label>End date<input data-entry-field="end_date" value="${escapeHtml(entry.end_date || "")}"></label>
      </div>
      <label class="export-field">Bullet points（每行一个）<textarea data-entry-field="bullet_points">${escapeHtml((entry.bullet_points || []).join("\n"))}</textarea></label>
    </article>
  `).join("") || '<div class="empty-state compact">Empty：此章节不会渲染。</div>';
}

function addResumeExportEntry(key) {
  if (!resumeExportData || !["experience", "projects", "education"].includes(key)) return;
  syncResumeExportDataFromEditor();
  resumeExportData[key].push({ organization: "", title: "", location: "", start_date: "", end_date: "", bullet_points: [] });
  renderResumeExportEntries(key);
  resumeExportDirty = true;
  renderResumeExportPreview();
}

function removeResumeExportEntry(key, index) {
  if (!resumeExportData || !Array.isArray(resumeExportData[key])) return;
  syncResumeExportDataFromEditor();
  resumeExportData[key].splice(index, 1);
  renderResumeExportEntries(key);
  resumeExportDirty = true;
  renderResumeExportPreview();
}

function exportLines(id) {
  return document.getElementById(id).value.split(/\r?\n/).map(value => value.trim()).filter(Boolean);
}

function readResumeExportEntries(key) {
  return Array.from(document.querySelectorAll(`#export-${key}-editor .export-entry-card`)).map(card => ({
    organization: card.querySelector('[data-entry-field="organization"]').value.trim(),
    title: card.querySelector('[data-entry-field="title"]').value.trim(),
    location: card.querySelector('[data-entry-field="location"]').value.trim(),
    start_date: card.querySelector('[data-entry-field="start_date"]').value.trim(),
    end_date: card.querySelector('[data-entry-field="end_date"]').value.trim(),
    bullet_points: card.querySelector('[data-entry-field="bullet_points"]').value.split(/\r?\n/).map(value => value.trim()).filter(Boolean)
  }));
}

function syncResumeExportDataFromEditor() {
  if (!resumeExportData) return;
  resumeExportData.basics = {
    name: document.getElementById("export-name").value.trim(),
    email: document.getElementById("export-email").value.trim(),
    phone: document.getElementById("export-phone").value.trim(),
    location: document.getElementById("export-location").value.trim(),
    links: exportLines("export-links"),
    summary: document.getElementById("export-summary").value.trim()
  };
  resumeExportData.experience = readResumeExportEntries("experience");
  resumeExportData.projects = readResumeExportEntries("projects");
  resumeExportData.education = readResumeExportEntries("education");
  resumeExportData.skills = exportLines("export-skills");
  resumeExportData.certifications = exportLines("export-certifications");
  resumeExportData.awards = exportLines("export-awards");
  resumeExportData.additional_information = exportLines("export-additional");
}

function resumeExportSectionLabel(key, language) {
  const labels = {
    summary: ["个人简介", "SUMMARY"], experience: ["工作经历", "EXPERIENCE"],
    projects: ["项目经历", "PROJECTS"], education: ["教育经历", "EDUCATION"],
    skills: ["技能", "SKILLS"], certifications: ["证书", "CERTIFICATIONS"],
    awards: ["荣誉奖项", "AWARDS"], additional_information: ["补充信息", "ADDITIONAL INFORMATION"]
  };
  const [zh, en] = labels[key];
  return language === "zh" ? zh : (language === "en" ? en : `${zh} / ${en}`);
}

function renderResumeExportPreview() {
  if (!resumeExportData) return;
  const template = document.getElementById("export-template-select").value;
  const language = document.getElementById("export-language-select").value;
  const paper = document.getElementById("export-paper-select").value.toUpperCase();
  const preview = document.getElementById("export-preview");
  preview.className = `resume-document-preview ${template}`;
  document.getElementById("export-page-hint").textContent = `${paper} · 实际分页以下载文件为准`;
  const basics = resumeExportData.basics || {};
  const contacts = [basics.email, basics.phone, basics.location, ...(basics.links || [])].filter(Boolean);
  const section = (key, content) => content ? `<section><h5>${escapeHtml(resumeExportSectionLabel(key, language))}</h5>${content}</section>` : "";
  const entries = key => (resumeExportData[key] || []).filter(item => item.title || item.organization || item.location || item.start_date || item.end_date || item.bullet_points?.length).map(item => {
    const title = [item.title, item.organization].filter(Boolean).join(" — ");
    const dates = [item.start_date, item.end_date].filter(Boolean).join(" - ");
    const meta = [item.location, dates].filter(Boolean).join(" | ");
    return `<article class="document-entry"><div><strong>${escapeHtml(title)}</strong>${meta ? `<span>${escapeHtml(meta)}</span>` : ""}</div>${item.bullet_points?.length ? `<ul>${item.bullet_points.map(point => `<li>${escapeHtml(point)}</li>`).join("")}</ul>` : ""}</article>`;
  }).join("");
  const list = values => values?.length ? `<ul>${values.map(value => `<li>${escapeHtml(value)}</li>`).join("")}</ul>` : "";
  preview.innerHTML = `
    <header><h4>${escapeHtml(basics.name || "Name required")}</h4>${contacts.length ? `<p>${contacts.map(escapeHtml).join(" | ")}</p>` : ""}</header>
    ${section("summary", basics.summary ? `<p>${escapeHtml(basics.summary).replaceAll("\n", "<br>")}</p>` : "")}
    ${section("experience", entries("experience"))}
    ${section("projects", entries("projects"))}
    ${section("education", entries("education"))}
    ${section("skills", resumeExportData.skills?.length ? `<p>${resumeExportData.skills.map(escapeHtml).join(" • ")}</p>` : "")}
    ${section("certifications", list(resumeExportData.certifications))}
    ${section("awards", list(resumeExportData.awards))}
    ${section("additional_information", list(resumeExportData.additional_information))}
  `;
}

async function createResumeExport() {
  if (!resumeExportVersionId || !resumeExportData) {
    setResumeExportMessage("请先打开结构化预览。", "error", true);
    return;
  }
  syncResumeExportDataFromEditor();
  const button = document.getElementById("export-generate-btn");
  setButtonLoading(button, true);
  setResumeExportMessage("Generating：正在安全生成文件…", "loading");
  try {
    const response = await fetch(
      apiUrl(optimizerVersionPath(resumeExportVersionId, "/exports")),
      {
        method: "POST",
        headers: authHeaders(true),
        body: JSON.stringify({
          template_key: document.getElementById("export-template-select").value,
          format: document.getElementById("export-format-select").value,
          paper_size: document.getElementById("export-paper-select").value,
          language: document.getElementById("export-language-select").value,
          resume: resumeExportData
        })
      }
    );
    const payload = await getResponsePayload(response);
    if (!response.ok) throw new Error(formatError(response, payload));
    resumeExportDirty = false;
    await loadResumeExportHistory();
    setResumeExportMessage(`Ready：${payload.filename} 已生成，可从历史记录下载。`, "success");
  } catch (error) {
    await loadResumeExportHistory();
    setResumeExportMessage(error.message || "导出失败，未保留不完整文件。", "error", true);
  } finally {
    setButtonLoading(button, false);
    await refreshDailyUsage();
  }
}

async function loadResumeExportHistory() {
  const container = document.getElementById("export-history");
  if (!resumeExportVersionId || !currentUser) {
    container.innerHTML = '<div class="empty-state">Empty：尚无导出记录。</div>';
    return;
  }
  container.innerHTML = '<div class="empty-state">Loading export history…</div>';
  try {
    const response = await fetch(
      `${apiUrl(resumeExportPath())}?version_id=${resumeExportVersionId}`,
      { headers: authHeaders() }
    );
    const payload = await getResponsePayload(response);
    if (!response.ok) throw new Error(formatError(response, payload));
    resumeExportHistory = payload;
    container.innerHTML = payload.map(item => `
      <article class="export-history-item status-${escapeHtml(item.status)}">
        <div><strong>${escapeHtml(item.filename)}</strong><span>${escapeHtml(item.template_key)} · ${escapeHtml(item.format.toUpperCase())} · v${item.version_number}</span><small>${escapeHtml(formatTime(item.created_at))}${item.error_code ? ` · ${escapeHtml(item.error_code)}` : ""}</small></div>
        <div class="export-history-actions">
          <span class="export-status">${escapeHtml(item.status)}</span>
          ${item.status === "ready" ? `<button class="secondary-btn" type="button" onclick="downloadResumeExport(${item.id})">下载</button>` : ""}
          <button class="secondary-btn" type="button" onclick="deleteResumeExport(${item.id})">删除</button>
        </div>
      </article>
    `).join("") || '<div class="empty-state">Empty：尚无导出记录。</div>';
  } catch (error) {
    container.innerHTML = `<div class="empty-state error-state">${escapeHtml(error.message || "导出记录加载失败")}</div>`;
  }
}

async function downloadResumeExport(exportId) {
  const record = resumeExportHistory.find(item => item.id === exportId);
  try {
    const response = await fetch(
      apiUrl(resumeExportPath(exportId, "/download")),
      { headers: authHeaders() }
    );
    if (!response.ok) {
      const payload = await getResponsePayload(response);
      throw new Error(formatError(response, payload));
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = record?.filename || `resume-export-${exportId}`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    setResumeExportMessage(`已下载 ${record?.filename || "简历文件"}。`, "success");
  } catch (error) {
    setResumeExportMessage(error.message || "下载失败。", "error", true);
  }
}

async function deleteResumeExport(exportId) {
  if (!window.confirm("删除会同时移除本地导出文件，是否继续？")) return;
  try {
    const response = await fetch(apiUrl(resumeExportPath(exportId)), {
      method: "DELETE",
      headers: authHeaders()
    });
    if (!response.ok) {
      const payload = await getResponsePayload(response);
      throw new Error(formatError(response, payload));
    }
    await loadResumeExportHistory();
    setResumeExportMessage("导出记录和对应文件已删除。", "success");
  } catch (error) {
    setResumeExportMessage(error.message || "删除导出失败。", "error");
  }
}

function closeResumeExport() {
  if (resumeExportDirty && !window.confirm("当前结构化编辑尚未生成文件，确定关闭？")) return;
  resumeExportDirty = false;
  document.getElementById("resume-export-workspace").hidden = true;
}

function resetOptimizerUI() {
  optimizerWorkspace = null;
  optimizerVersions = [];
  optimizerDirty = false;
  resumeExportVersionId = null;
  resumeExportData = null;
  resumeExportHistory = [];
  resumeExportDirty = false;
  lastOptimizerSuggestionId = null;
  document.getElementById("optimizer-job").textContent = "-";
  document.getElementById("optimizer-version-number").textContent = "-";
  document.getElementById("optimizer-accepted-count").textContent = "0";
  document.getElementById("optimizer-pending-count").textContent = "0";
  document.getElementById("optimizer-resume-content").textContent = "打开申请后显示结构化文本版本。";
  document.getElementById("optimizer-suggestions").innerHTML = '<div class="empty-state">登录并打开申请后显示建议。</div>';
  document.getElementById("optimizer-version-history").innerHTML = '<div class="empty-state">暂无版本记录。</div>';
  document.getElementById("optimizer-diff").hidden = true;
  document.getElementById("optimizer-undo-btn").disabled = true;
  document.getElementById("resume-export-workspace").hidden = true;
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
document.getElementById("delete-account-btn").addEventListener("click", deleteAccount);
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
document.getElementById("optimizer-load-btn").addEventListener("click", loadSelectedOptimizerWorkspace);
document.getElementById("optimizer-generate-btn").addEventListener("click", () => generateOptimizerSuggestions(false));
document.getElementById("optimizer-retry-btn").addEventListener("click", () => {
  if (optimizerWorkspace) loadOptimizerWorkspace(optimizerWorkspace.application_id);
  else loadOptimizerApplications();
});
document.getElementById("optimizer-undo-btn").addEventListener("click", undoOptimizerSuggestion);
document.getElementById("optimizer-create-version-btn").addEventListener("click", createOptimizerVersion);
document.getElementById("optimizer-export-btn").addEventListener("click", openResumeExport);
document.getElementById("optimizer-refresh-versions-btn").addEventListener("click", loadOptimizerVersions);
document.getElementById("optimizer-compare-btn").addEventListener("click", compareOptimizerVersions);
document.getElementById("optimizer-version-select").addEventListener("change", (event) => {
  if (event.target.value) viewOptimizerVersion(Number(event.target.value));
});
document.getElementById("export-close-btn").addEventListener("click", closeResumeExport);
document.getElementById("export-generate-btn").addEventListener("click", createResumeExport);
document.getElementById("export-retry-btn").addEventListener("click", createResumeExport);
document.getElementById("export-refresh-btn").addEventListener("click", loadResumeExportHistory);
document.getElementById("resume-export-editor").addEventListener("input", () => {
  if (!resumeExportData) return;
  syncResumeExportDataFromEditor();
  resumeExportDirty = true;
  renderResumeExportPreview();
  setResumeExportMessage("结构化内容有未导出的编辑。", "loading");
});
["export-template-select", "export-paper-select", "export-language-select"].forEach(id => {
  document.getElementById(id).addEventListener("change", () => {
    if (!resumeExportData) return;
    resumeExportDirty = true;
    renderResumeExportPreview();
  });
});
document.getElementById("export-format-select").addEventListener("change", () => {
  if (resumeExportData) resumeExportDirty = true;
});
document.querySelectorAll("[data-optimizer-filter]").forEach(button => {
  button.addEventListener("click", () => {
    optimizerFilter = button.dataset.optimizerFilter;
    document.querySelectorAll("[data-optimizer-filter]").forEach(item => item.classList.toggle("active", item === button));
    renderOptimizerSuggestions();
  });
});
window.addEventListener("beforeunload", (event) => {
  if (!optimizerDirty && !resumeExportDirty) return;
  event.preventDefault();
  event.returnValue = "";
});
document.getElementById("password").addEventListener("keydown", (event) => {
  if (event.key === "Enter") submitAuth();
});
document.getElementById("confirm-password").addEventListener("keydown", (event) => {
  if (event.key === "Enter") submitAuth();
});
loadPublicConfiguration().then(() => {
  if (publicConfiguration.session_active) loadCurrentUser();
  else updateAuthUI();
});
