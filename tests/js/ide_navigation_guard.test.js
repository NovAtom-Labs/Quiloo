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

const submissions = globalThis.QuilooIDEState.createSubmissionTracker();
const firstAttempt = submissions.begin("conversation-b", "edit and test");
assertEqual(firstAttempt.messageId, null, "a new prompt should create a message");
submissions.recordMessage(firstAttempt, "message-1");
const retry = submissions.begin("conversation-b", "edit and test");
assertEqual(retry.messageId, "message-1", "a retry must reuse the persisted message");
submissions.recordRun(retry, "run-1");
assertEqual(submissions.current(), null, "a successful run should clear submission state");

const eventLedger = globalThis.QuilooIDEState.createEventLedger();
assertEqual(eventLedger.accept(17), true, "a new SSE event should render");
assertEqual(eventLedger.accept(17), false, "a replayed SSE event must not render twice");
assertEqual(eventLedger.accept(18), true, "the next SSE event should render");

const runningControls = globalThis.QuilooIDEState.controlsForState("running");
assertEqual(runningControls.pause, true, "running work can be paused");
assertEqual(runningControls.stop, true, "running work can be stopped");
assertEqual(runningControls.send, false, "another prompt cannot start while running");
const pausedControls = globalThis.QuilooIDEState.controlsForState("paused");
assertEqual(pausedControls.resume, true, "paused work can be resumed");
const finishedControls = globalThis.QuilooIDEState.controlsForState("completed");
assertEqual(finishedControls.send, true, "a terminal run re-enables prompting");

assertEqual(
  globalThis.QuilooIDEState.isActiveState("waiting_for_approval"),
  true,
  "approval waits should continue background synchronization",
);
assertEqual(
  globalThis.QuilooIDEState.isActiveState("completed"),
  false,
  "terminal runs should not trigger active-run polling",
);

let refreshCalls = 0;
let releaseRefresh;
const refreshCoordinator = globalThis.QuilooIDEState.createRefreshCoordinator(
  () => {
    refreshCalls += 1;
    return new Promise((resolve) => { releaseRefresh = resolve; });
  },
);
const firstRefresh = refreshCoordinator.request("conversation-b");
const duplicateRefresh = refreshCoordinator.request("conversation-b");
assertEqual(firstRefresh, duplicateRefresh, "overlapping refreshes should be coalesced");
assertEqual(refreshCalls, 1, "coalesced refreshes should issue one request");
releaseRefresh();
Promise.all([firstRefresh, duplicateRefresh]).then(async () => {
  const nextRefresh = refreshCoordinator.request("conversation-b");
  assertEqual(refreshCalls, 2, "a completed refresh should allow the next sync");
  releaseRefresh();
  await nextRefresh;
}).catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
