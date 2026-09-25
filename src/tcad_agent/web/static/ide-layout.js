"use strict";

(() => {
  const DEFAULTS = {explorer: 218, agent: 420};
  const LIMITS = {
    explorerMin: 196,
    explorerMax: 360,
    agentMin: 320,
    agentMax: 520,
    centerMin: 480,
    desktopMin: 996,
    narrowMax: 799,
    keyboardStep: 12,
  };

  function finite(value, fallback) {
    const numeric = Number(value);
    return Number.isFinite(numeric) ? numeric : fallback;
  }

  function between(value, minimum, maximum) {
    return Math.max(minimum, Math.min(maximum, value));
  }

  function clampLayout(input) {
    const viewport = Math.max(0, finite(input.viewport, 0));
    let explorer = between(
      finite(input.explorer, DEFAULTS.explorer),
      LIMITS.explorerMin,
      LIMITS.explorerMax,
    );
    let agent = between(
      finite(input.agent, DEFAULTS.agent),
      LIMITS.agentMin,
      LIMITS.agentMax,
    );
    if (viewport <= LIMITS.narrowMax) {
      return {mode: "narrow", explorer: 0, agent, center: viewport};
    }
    if (viewport < LIMITS.desktopMin) {
      const maximumAgent = Math.max(LIMITS.agentMin, viewport - LIMITS.centerMin);
      agent = between(agent, LIMITS.agentMin, maximumAgent);
      return {mode: "tablet", explorer: 0, agent, center: viewport - agent};
    }
    if (explorer + agent + LIMITS.centerMin > viewport) {
      agent = LIMITS.agentMin;
      if (explorer + agent + LIMITS.centerMin > viewport) {
        explorer = between(
          viewport - agent - LIMITS.centerMin,
          LIMITS.explorerMin,
          LIMITS.explorerMax,
        );
      }
    }
    return {mode: "desktop", explorer, agent, center: viewport - explorer - agent};
  }

  function resizeByKey(input, side, key) {
    const current = clampLayout(input);
    if (current.mode !== "desktop") return current;
    let explorer = current.explorer;
    let agent = current.agent;
    if (side === "explorer" && key === "ArrowLeft") explorer -= LIMITS.keyboardStep;
    if (side === "explorer" && key === "ArrowRight") explorer += LIMITS.keyboardStep;
    if (side === "agent" && key === "ArrowLeft") agent += LIMITS.keyboardStep;
    if (side === "agent" && key === "ArrowRight") agent -= LIMITS.keyboardStep;
    return clampLayout({viewport: input.viewport, explorer, agent});
  }

  function resetSide(input, side) {
    return clampLayout({
      viewport: input.viewport,
      explorer: side === "explorer" ? DEFAULTS.explorer : input.explorer,
      agent: side === "agent" ? DEFAULTS.agent : input.agent,
    });
  }

  function parseStoredLayout(serialized) {
    try {
      const parsed = JSON.parse(serialized || "{}");
      return {
        explorer: Number.isFinite(Number(parsed.explorer))
          ? Number(parsed.explorer)
          : DEFAULTS.explorer,
        agent: Number.isFinite(Number(parsed.agent))
          ? Number(parsed.agent)
          : DEFAULTS.agent,
      };
    } catch (_error) {
      return {...DEFAULTS};
    }
  }

  function createController(options) {
    const shell = options.shell;
    const explorerHandle = options.explorerHandle;
    const agentHandle = options.agentHandle;
    const windowRef = options.windowRef || window;
    const storage = options.storage || windowRef.localStorage;
    const storageKey = `agent-kronig.layout.${options.workspaceId || "default"}`;
    let preferred = parseStoredLayout(storage.getItem(storageKey));
    let current = null;
    let dragging = null;

    function viewportWidth() {
      return shell.getBoundingClientRect().width || windowRef.innerWidth;
    }

    function apply(next = preferred, {persist = false} = {}) {
      current = clampLayout({viewport: viewportWidth(), ...next});
      shell.dataset.layoutMode = current.mode;
      shell.style.setProperty("--explorer-width", `${current.explorer || DEFAULTS.explorer}px`);
      shell.style.setProperty("--agent-width", `${current.agent}px`);
      explorerHandle.setAttribute("aria-valuenow", String(current.explorer));
      agentHandle.setAttribute("aria-valuenow", String(current.agent));
      if (current.mode === "desktop") preferred = {
        explorer: current.explorer,
        agent: current.agent,
      };
      if (persist && current.mode === "desktop") {
        storage.setItem(storageKey, JSON.stringify(preferred));
      }
      options.onModeChange?.(current.mode);
      return current;
    }

    function beginDrag(side, event) {
      if (current.mode !== "desktop") return;
      dragging = side;
      shell.classList.add("is-resizing");
      event.currentTarget.setPointerCapture?.(event.pointerId);
      event.preventDefault();
    }

    function moveDrag(event) {
      if (!dragging) return;
      const rect = shell.getBoundingClientRect();
      const next = {
        explorer: dragging === "explorer" ? event.clientX - rect.left : current.explorer,
        agent: dragging === "agent" ? rect.right - event.clientX : current.agent,
      };
      apply(next);
    }

    function endDrag() {
      if (!dragging) return;
      dragging = null;
      shell.classList.remove("is-resizing");
      apply(preferred, {persist: true});
    }

    function bind(handle, side) {
      handle.addEventListener("pointerdown", (event) => beginDrag(side, event));
      handle.addEventListener("keydown", (event) => {
        if (!["ArrowLeft", "ArrowRight"].includes(event.key)) return;
        current = resizeByKey({...current, viewport: viewportWidth()}, side, event.key);
        apply(current, {persist: true});
        event.preventDefault();
      });
      handle.addEventListener("dblclick", () => {
        current = resetSide({...current, viewport: viewportWidth()}, side);
        apply(current, {persist: true});
      });
    }

    bind(explorerHandle, "explorer");
    bind(agentHandle, "agent");
    const onResize = () => apply(preferred);
    windowRef.addEventListener("pointermove", moveDrag);
    windowRef.addEventListener("pointerup", endDrag);
    windowRef.addEventListener("pointercancel", endDrag);
    windowRef.addEventListener("resize", onResize);
    apply(preferred);
    return {
      apply,
      destroy() {
        windowRef.removeEventListener("pointermove", moveDrag);
        windowRef.removeEventListener("pointerup", endDrag);
        windowRef.removeEventListener("pointercancel", endDrag);
        windowRef.removeEventListener("resize", onResize);
      },
      getState: () => ({...current}),
    };
  }

  function mount(documentRef = document, windowRef = window) {
    const shell = documentRef.querySelector(".ide-shell");
    const explorerHandle = documentRef.querySelector("#explorer-resizer");
    const agentHandle = documentRef.querySelector("#agent-resizer");
    if (!shell || !explorerHandle || !agentHandle) return null;
    const explorer = documentRef.querySelector("#workspace-browser");
    const agent = documentRef.querySelector("#agent-panel");
    const toggleExplorer = documentRef.querySelector("#toggle-explorer-panel");
    const closeExplorer = documentRef.querySelector("#close-workspace-browser");
    const toggleAgent = documentRef.querySelector("#toggle-agent-panel");
    const workspaceId = windowRef.location.pathname.match(/\/workspaces\/([0-9a-f-]{36})/i)?.[1]
      || "default";

    function setExplorerOpen(open) {
      explorer?.classList.toggle("is-open", open);
      toggleExplorer?.setAttribute("aria-expanded", String(open));
    }

    toggleExplorer?.addEventListener("click", () => {
      const open = !explorer.classList.contains("is-open");
      setExplorerOpen(open);
      if (open) {
        agent?.classList.remove("is-open");
        toggleAgent?.setAttribute("aria-expanded", "false");
      }
    });
    closeExplorer?.addEventListener("click", () => setExplorerOpen(false));
    toggleAgent?.addEventListener("click", () => setExplorerOpen(false));

    return createController({
      shell,
      explorerHandle,
      agentHandle,
      workspaceId,
      windowRef,
      onModeChange(mode) {
        if (mode === "desktop") setExplorerOpen(false);
      },
    });
  }

  globalThis.AgentKronigLayout = {
    DEFAULTS,
    LIMITS,
    clampLayout,
    createController,
    mount,
    parseStoredLayout,
    resetSide,
    resizeByKey,
  };
  if (typeof document !== "undefined" && typeof window !== "undefined") {
    window.addEventListener("DOMContentLoaded", () => mount(document, window), {once: true});
  }
})();
