"use strict";

function assertEqual(actual, expected, message) {
  if (actual !== expected) throw new Error(message);
}

const guard = globalThis.QuilooIDEState.createNavigationGuard();
const firstRoute = guard.beginRoute();
const pendingMessage = guard.captureMessage(firstRoute, "conversation-a", "inspect the deck");

assertEqual(
  guard.canApplyMessage(pendingMessage, "conversation-a"),
  true,
  "the current conversation response should be accepted",
);

guard.beginRoute();
assertEqual(
  guard.canApplyMessage(pendingMessage, "conversation-a"),
  false,
  "a response from the previous route must be ignored",
);

const currentRoute = guard.currentRoute();
const currentMessage = guard.captureMessage(currentRoute, "conversation-b", "run validation");
assertEqual(
  guard.canApplyMessage(currentMessage, "conversation-c"),
  false,
  "a response must not render in another conversation",
);
assertEqual(
  guard.canClearDraft(currentMessage, "conversation-b", "new draft"),
  false,
  "a response must not clear a draft typed while it was pending",
);
