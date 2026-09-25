"use strict";

(() => {
  function createNavigationGuard() {
    let routeGeneration = 0;

    return {
      beginRoute() {
        routeGeneration += 1;
        return routeGeneration;
      },
      currentRoute() {
        return routeGeneration;
      },
      isCurrent(routeToken) {
        return routeToken === routeGeneration;
      },
      captureMessage(routeToken, conversationId, draft) {
        return {routeToken, conversationId, draft};
      },
      canApplyMessage(pending, activeConversationId) {
        return pending.routeToken === routeGeneration
          && pending.conversationId === activeConversationId;
      },
      canClearDraft(pending, activeConversationId, currentDraft) {
        return this.canApplyMessage(pending, activeConversationId)
          && pending.draft === currentDraft;
      },
    };
  }

  function createSubmissionTracker() {
    let pending = null;

    return {
      begin(conversationId, draft) {
        if (!pending || pending.conversationId !== conversationId || pending.draft !== draft) {
          pending = {conversationId, draft, messageId: null};
        }
        return pending;
      },
      recordMessage(submission, messageId) {
        if (pending === submission) pending.messageId = messageId;
      },
      recordRun(submission, runId) {
        if (pending === submission) pending = null;
        return runId;
      },
      current() {
        return pending;
      },
      reset() {
        pending = null;
      },
    };
  }

  function createEventLedger() {
    const rendered = new Set();
    return {
      accept(eventId) {
        const key = String(eventId);
        if (rendered.has(key)) return false;
        rendered.add(key);
        return true;
      },
      reset() {
        rendered.clear();
      },
    };
  }

  function createRunResourceCache() {
    const resources = new Map();
    let selectedRunId = null;
    return {
      select(runId) {
        selectedRunId = runId ? String(runId) : null;
        return this.current();
      },
      put(runId, value) {
        if (runId) resources.set(String(runId), value);
        return this.current();
      },
      current() {
        return selectedRunId ? resources.get(selectedRunId) || null : null;
      },
      clear() {
        resources.clear();
        selectedRunId = null;
      },
    };
  }

  function createRepositoryRequestCoordinator(initialPath = ".") {
    let generation = 0;
    let desiredPath = initialPath;
    let refreshPending = false;
    const pendingNavigation = new Set();

    function createToken(path, kind) {
      generation += 1;
      return {generation, kind, path};
    }

    return {
      beginNavigation(path) {
        desiredPath = path;
        const token = createToken(path, "navigation");
        pendingNavigation.add(token);
        return token;
      },
      beginRefresh() {
        if (pendingNavigation.size) {
          refreshPending = true;
          return null;
        }
        return createToken(desiredPath, "refresh");
      },
      currentPath() {
        return desiredPath;
      },
      finish(token) {
        if (token?.kind !== "navigation" || !pendingNavigation.delete(token)) return false;
        if (pendingNavigation.size || !refreshPending) return false;
        refreshPending = false;
        return true;
      },
      hasNavigationPending() {
        return pendingNavigation.size > 0;
      },
      isCurrent(token) {
        return Boolean(token)
          && token.generation === generation
          && token.path === desiredPath;
      },
    };
  }

  function shouldAutoFollowChat(previousLastId, nextLastId, wasNearBottom, forceScroll) {
    if (forceScroll) return true;
    return Boolean(nextLastId && nextLastId !== previousLastId && wasNearBottom);
  }

  function shouldRefreshRepository(eventKind) {
    return [
      "tool_call_completed",
      "run_completed",
      "run_failed",
      "run_blocked",
      "run_cancelled",
    ].includes(eventKind);
  }

  function controlsForState(state) {
    const running = state === "queued" || state === "running";
    const waiting = state === "waiting_for_approval" || state === "waiting_for_user";
    const paused = state === "paused";
    const active = isActiveState(state);
    return {
      pause: running,
      resume: paused,
      stop: active,
      send: !active,
    };
  }

  function isActiveState(state) {
    return ["queued", "running", "waiting_for_approval", "waiting_for_user", "paused"].includes(state);
  }

  function createRefreshCoordinator(refresh) {
    let inFlight = null;
    let activeConversationId = null;

    return {
      request(conversationId) {
        if (inFlight && activeConversationId === conversationId) return inFlight;
        activeConversationId = conversationId;
        try {
          inFlight = Promise.resolve(refresh(conversationId)).finally(() => {
            inFlight = null;
            activeConversationId = null;
          });
        } catch (error) {
          inFlight = null;
          activeConversationId = null;
          throw error;
        }
        return inFlight;
      },
    };
  }

  globalThis.QuilooIDEState = {
    controlsForState,
    createRefreshCoordinator,
    createRepositoryRequestCoordinator,
    createRunResourceCache,
    createEventLedger,
    createNavigationGuard,
    createSubmissionTracker,
    isActiveState,
    shouldAutoFollowChat,
    shouldRefreshRepository,
  };
})();
