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
    createEventLedger,
    createNavigationGuard,
    createSubmissionTracker,
    isActiveState,
  };
})();
