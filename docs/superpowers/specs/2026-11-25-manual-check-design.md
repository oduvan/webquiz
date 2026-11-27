# Manual check of text answers — design

## Why

Some answers cannot be checked by code: a short explanation, an opinion, an
answer with many correct spellings. For these the teacher decides by hand.
The teacher cannot decide at once, so the student learns the result later, on
the results screen.

Both servers (Python 1.x and Go 2.x) get the same feature with the same quiz
format, HTTP API and WebSocket messages.

## Goals

- A text question can say `manual_check: true`. Its answers are not checked by
  code; a teacher marks each one right or wrong.
- A separate page for teachers, `/review/`, made for a phone. It stays
  connected over a WebSocket and shows one waiting answer at a time: the
  question, the student's answer and the sample answer (`correct_value`), but
  never the student's name. Two big buttons: right / wrong. After a tap it shows
  the next answer or a waiting screen.
- Several teachers can review at once. Each gets a different answer while there
  are enough; when there are not, two teachers may see the same answer and the
  first verdict counts.
- The teacher is told about it when the quiz starts (start pop-up) and while it
  runs (admin panel), with the address of the review page.
- The student sees "the teacher will check this answer" after answering. On the
  results screen such answers are highlighted as waiting, and the screen
  updates by itself when the teacher decides.

## Non-goals

- Partial points. A verdict is right (full points) or wrong (0).
- Changing a verdict after it is given.
- A "skip" button on the review page.
- Keeping waiting answers over a server restart (all quiz state is in memory,
  as before).

## Quiz format

```yaml
- question: "Why is the sky blue?"
  manual_check: true
  correct_value: "Because of Rayleigh scattering"   # optional, shown to the teacher as a sample
  default_value: ""                                  # optional
  points: 2
```

- `manual_check: true` makes the question a text question by itself; no
  `checker` is needed. Text question detection everywhere becomes
  "has `checker`, or `manual_check` is true".
- Validation (on save): `manual_check` must be a boolean; with
  `manual_check: true` the question must not have a non-empty `checker`, and
  must not have `options` or `correct_answer`.

## Server state

- Each answer to a manual question (not a timeout) is stored with
  `is_correct: null`, `earned_points: 0` and `pending_review: true` in the
  student's answers, and gets a review item: `review_id` (a counter, as text),
  user, question, the answer text.
- The review queue keeps the items in answer order. It is cleared on quiz
  switch or restart, like the rest of the state.
- A verdict sets `is_correct`, `earned_points` (points if right, else 0),
  removes `pending_review`, recalculates the stored final stats of a student who
  has finished (keeping `completed_at`), and updates live stats.

## Student

- Submit reply for a manual question: `pending_review: true`; with
  `show_right_answer` also `is_text_question: true`, but no `is_correct`, no
  `correct_value` and no `checker_error`. The page shows "Your answer is saved.
  The teacher will check it; you will see the result at the end." and the
  Continue button. The explanation step works as for other questions. Without
  `show_right_answer` the page moves on as usual.
- Final results (`verify-user` → `final_results`): `pending_count` (answers still
  waiting) and `pending_review: true` on each waiting row. Waiting rows have
  `is_correct: null`. `correct_count` and `earned_points` count only decided
  answers. When correct answers are hidden, `is_correct` and `correct_answer`
  are removed as before; `pending_review` stays.
- The results screen shows a highlighted notice "The teacher has not checked N
  of your answers yet. This page updates by itself." Waiting rows are
  highlighted and marked "⏳ Waiting for the teacher". While `pending_count > 0`
  the page asks `verify-user` every 5 seconds and redraws the results.

## Review page and WebSocket

- `GET /review/` — page, local network only. It asks
  `GET /api/admin/check-session`; without a session it shows the master key form
  (`POST /api/admin/auth`), then connects.
- `WS /ws/review` — local network only and the admin session (trusted IPs need
  no session), refused before the upgrade otherwise (same answers as
  `admin_auth_required`).
- Server → page: `{"type": "review_state", "item": {...} | null,
  "pending_count": N, "has_manual": bool, "already_decided": bool}`.
  `item` is `{"review_id", "question", "image", "answer", "correct_value",
  "points"}`. It is sent on connect, after each verdict of this page, and
  whenever the count or this page's item changes. `already_decided` is true
  once, after a verdict for an answer that another teacher had already decided.
- Page → server: `{"type": "verdict", "review_id": "7", "is_correct": true}`;
  `{"type": "take_shared"}`; `{"type": "ping"}` → `{"type": "pong"}`. A verdict
  with an `is_correct` that is not a boolean is ignored (the page gets its state
  again).
- Handing out answers: a page without an answer gets the oldest answer that no
  page shows. If every waiting answer is open on another page, the page waits
  and offers "🤝 Help check"; that sends `take_shared`, and the page gets the
  answer open on the fewest pages (oldest first). Then two teachers see the same
  answer and the first verdict counts. A page keeps its answer until it gives a
  verdict, the answer is decided elsewhere, or it disconnects; an answer is never
  swapped under the teacher's finger. When a page disconnects, its answer goes
  to a waiting page. The WebSocket has a 30 s heartbeat, so a phone that went to
  sleep is dropped and its answer moves on.
- First version shared automatically (a free page took an answer already open
  elsewhere). That made two teachers who opened the page before the first
  answer share every answer one by one, so the work was never split. Sharing is
  now on request only.
- The buttons are disabled after a tap until the next state arrives.

## Admin panel

- Start pop-up: when the quiz file has manual questions, a highlighted note:
  "N questions in this quiz are checked by you. Open the review page on your
  phone (same network, log in with the master key):" with the review address
  for each network address (`{quiz_url}review/`).
- While the running quiz has manual questions, a block "✍️ Manual check:
  waiting N, reviewers M" with a link to `/review/`. Data from `WS /ws/admin`:
  `review` in `initial_state` and `review_status` messages
  (`{"has_manual", "pending_count", "reviewers"}`).
- Navigation gets a "✍️ Review" link.
- Quiz editor: a text question has a checkbox "Checked by the teacher by hand"
  (`manual_check`); while it is on, the checker code and templates are hidden
  and `correct_value` is labelled as a sample answer for the teacher.

## Live stats

New state `"pending"` (✍️): the question is answered, not yet right or wrong.
It counts as answered. A verdict sends a normal `state_update` with `ok` or
`fail`, so the existing incremental counting replaces the pending state.

## CSV

- Answers CSV (and `answers_with_users`): a waiting answer is written at once
  with an empty `is_correct`. After a verdict the whole file is written again
  from memory at the next flush (temporary file, fsync, rename), so the row
  keeps its place and gets `True` / `False`.
- Users CSV is written in full every flush, so it picks up verdicts; only
  `True` counts as a correct answer.

## Approaches considered

- **Hold the CSV row until the verdict** — simple, but a waiting answer is
  missing from the file for minutes and is lost if nobody decides; rows end up
  out of order. Rejected.
- **Append a second row with the verdict** — breaks every reader that expects
  one row per answer. Rejected.
- **Rewrite the file after a verdict** (chosen) — the file always has every
  answer in order; the cost (a few hundred rows per class) is small.
- **Teachers pick answers from a list** instead of the server handing them out
  — more taps on a phone and two teachers would often pick the same answer.
  Rejected in favour of one answer per page.
- **Student page gets a WebSocket** for verdicts — more moving parts through the
  tunnel; polling `verify-user` every 5 s while something waits is enough.
