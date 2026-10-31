# Optional commute and consistent listing cards

The user authorised improving intake and rental card layout. A known suburb such
as Burwood must remain usable without mandatory commute questions. Unrestricted
area intake should offer a single optional include/skip choice before asking for
commute details. Explicit commute constraints stay intact until explicitly
changed; skipping removes them through the normal confirmed-save workflow.

Keep English product copy, active Jev, source facts, consent and version guards.
Do not rewrite existing user records or silently infer a commute time.

- [x] Backend: reproduce the unrestricted-area intake path; add optional commute
  choice and persist include/skip decisions. Test known-suburb bypass, explicit
  skip, missing mode/time after include, reopening and confirmed updates.
- [x] Frontend: display the optional choice using ordinary user-authored chat
  replies; prevent obsolete choice controls from changing the current task.
- [x] Frontend: replace nested Space/fragment actions in listing cards with two
  aligned secondary actions (details/save) and a full-width primary follow-up
  action. Preserve comparison, favorites and selected-state behaviour.
- [x] Verify card geometry at mobile/tablet/desktop widths, consent and selection
  journeys, short follow-up answers, optional-commute branches, frontend build
  and appropriate unit tests. Inspect rendered cards.
- [x] Update presentation examples to include a Burwood/no-commute path and an
  unrestricted-area optional-commute path. Reload the backend only after source
  and tests are ready, preserving live data and active routing.
