(function (global) {
  "use strict";

  async function selectDirectory(fetchImpl, desktopApi) {
    if (desktopApi && typeof desktopApi.selectDirectory === "function") {
      const selection = await desktopApi.selectDirectory();
      if (!selection || selection.cancelled) return null;
      return typeof selection.path === "string" && selection.path ? selection.path : null;
    }

    const response = await fetchImpl("/api/system/directories/select", {method: "POST"});
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || "Could not open the folder selector.");
    }
    return typeof payload.path === "string" && payload.path ? payload.path : null;
  }

  global.AgentKronigDesktopBridge = Object.freeze({selectDirectory});
})(globalThis);
