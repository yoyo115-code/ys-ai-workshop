(function configureWorkshop(global) {
  const metaValue = document
    .querySelector('meta[name="api-base-url"]')
    ?.getAttribute("content")
    ?.trim();
  const injectedValue =
    typeof global.YS_AI_API_BASE_URL === "string"
      ? global.YS_AI_API_BASE_URL.trim()
      : "";

  global.YS_AI_CONFIG = Object.freeze({
    apiBaseUrl: (injectedValue || metaValue || "").replace(/\/+$/, ""),
    endpoints: Object.freeze({
      auth: Object.freeze({
        login: "/auth/login",
        register: "/auth/register",
        logout: "/auth/logout",
        me: "/auth/me"
      }),
      tools: Object.freeze({
        resume: "/resume",
        copywrite: "/copywrite",
        translate: "/translate",
        pdf: "/pdf-summary",
        csv: "/csv-preview"
      }),
      career: Object.freeze({
        applications: "/career/applications"
      }),
      optimizer: Object.freeze({
        suggestions: "/career/resume-suggestions",
        resumes: "/career/resumes",
        versions: "/career/resume-versions"
      }),
      admin: Object.freeze({
        users: "/admin/users",
        logs: "/admin/logs"
      }),
      health: "/health"
    })
  });
})(window);
