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

  globalThis.QuilooIDEState = {createNavigationGuard};
})();
