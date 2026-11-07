# Question explanations — design

Date: 2026-11-07

## Why

After a student answers a question, the teacher wants to show a short
explanation of it, to reinforce the knowledge. The explanation is a step of
its own between two questions, not something hidden that the student may
open.

## What the student sees

```
Question 3  →  answer  →  ✓/✗ feedback  →  [Продовжити]
            →  📖 Explanation of question 3  →  [Далі]
            →  Question 4
```

- The explanation step shows the question text as a small heading and the
  explanation below it, then a "Далі" (Next) button.
- Only questions that have an explanation get this step. Other questions go
  straight to the next question, as today.
- After the last question, the explanation comes first, then the results.
- When correct answers are not shown (`show_right_answer: false`, the page
  moves on automatically), there is no explanation step at all. This is the
  only exception. Explanations are never shown on the results screen, also
  not when `show_answers_on_completion` reveals the answers later.
- A timed-out question (per-question limit) that has an explanation still
  gets the step: the feedback says "time is up" and shows the correct answer,
  then the explanation follows.

## Quiz file

```yaml
show_explanation: true        # quiz-wide, default false
questions:
  - question: "Яка планета найбільша?"
    options: ["Марс", "Юпітер", "Земля"]
    correct_answer: 1
    explanation: |
      **Юпітер** — найбільша планета Сонячної системи.

      ![Юпітер](/imgs/jupiter.png)
```

- `explanation` (per question, optional): Markdown text. Images use the same
  path form as question images, `/imgs/name.png` (files in `quizzes/imgs/`).
  An empty or missing value means the question has no explanation.
- `show_explanation` (quiz-wide, optional, default `false`): turns the
  explanation step on.
- Explanations work for every question type (single choice, multiple choice,
  text).

## The teacher's controls

- **Quiz editor** (admin panel wizard):
  - Every question card gets an "Пояснення (Markdown)" text area, with a
    button that opens the existing image picker and inserts
    `![](/imgs/name.png)` at the cursor.
  - The quiz settings get a "Показувати пояснення" checkbox. It is shown only
    while at least one question has explanation text (it appears and hides as
    the teacher types). Its value is saved to the file as `show_explanation`
    and is the default for the start pop-up.
- **Start pop-up**: a "Показувати пояснення" checkbox, filled from the file.
  It is shown only when the quiz file has at least one explanation. When "show
  correct answers" is unticked in the pop-up, this checkbox is greyed out
  with a short note that explanations need correct answers to be shown. Like
  the other start settings, the value applies to this run only and is never
  written to the file.
- **Live preview in the quiz editor**: under each explanation text area, a
  preview box shows the rendered explanation, styled like the student's
  explanation step (same CSS, light and dark), with images. It updates
  about 300 ms after the teacher stops typing, and is hidden while the text
  is empty. The preview comes from the server, so it is exactly what students
  will get: `POST /api/admin/preview-explanation` (`{"markdown": "..."}` →
  `{"html": "..."}`, admin session and local network required like the other
  admin endpoints) uses the same renderer. The renderer takes the image path
  prefix as a parameter: `imgs/...` for the student page (served at `/`) and
  `../imgs/...` for the admin page (served at `/admin/`), so both work also
  behind a reverse proxy with a path prefix.
- **File manager (YAML)**: nothing new; the fields are plain YAML.

## Decisions on how it is built

- **Markdown is rendered on the server with mistune 3** (new dependency,
  pure Python, BSD licence). Chosen over a hand-written renderer in the page
  (common Markdown only, our own parser to maintain) and over copying a
  JavaScript library and a sanitizer into the repo.
  - Raw HTML in the Markdown is shown as text, not run (`escape=True`), so
    the rule "quiz text is plain text, never HTML" still holds.
  - Links with unsafe schemes (`javascript:`, `vbscript:`, `data:` other than
    images) are not made into links.
  - Links open in a new tab (`target="_blank" rel="noopener"`), so a click
    does not take the student away from the quiz. (Builder's call: kept as a
    proposal; easy to drop.)
  - Image paths `/imgs/...` are rewritten to `imgs/...`, the way the page
    already treats question images (`makeRelativePath`), so explanations work
    behind a reverse proxy with a path prefix (`server.url_format`).
  - Plugins: tables and strikethrough. Import the plugin functions directly
    (not by name) so the PyInstaller binaries include them.
  - Rendered once when the quiz loads, kept in memory per question id.
- **The explanation comes with the answer reply**, like the correct answer.
  It is never part of the page before the student answers.
  `POST /api/submit-answer` adds `explanation_html` when the running quiz has
  `show_right_answer` and `show_explanation` on and the question has an
  explanation. It is stored with the reply in `answer_results`, so a repeated
  request gets the same reply.
- **Start settings**: `show_explanation` joins `START_SETTING_KEYS`,
  `_apply_start_settings()` and `current_quiz_settings()`.
- **Validation on save** (`_validate_quiz_data`): `show_explanation` must be a
  boolean; `explanation` must be a string. Loading a quiz does not validate,
  as today.
- **Unite quizzes**: `show_explanation` is copied from the first quiz with
  the other quiz-wide settings; explanations travel with their questions.
- **File transfer between servers**: `quiz_media_files()` also finds images
  referenced inside explanations (`](/imgs/name)` in the Markdown), and
  `rewrite_quiz_media()` rewrites them inside the text when an image is
  saved under a new name.

## Timing

- The question clock stops when the answer arrives, and the next question's
  clock starts at its question-start, which the page sends when the next
  question is shown (after "Далі"). So with a per-question limit, reading the
  explanation does not count. The per-question countdown is hidden on the
  explanation step.
- With a whole-quiz limit the clock keeps running and its countdown stays
  visible while the student reads. If it runs out during the explanation
  step, the existing time-up handling applies: the page keeps
  `currentQuestionIndex` on the answered question during the step, so
  `onQuizTimeUp()` sends the empty answer for the next question (as it
  already does on the "Продовжити" screen) and shows the results.

- When the whole-quiz time runs out (including while a question with an
  explanation is on screen), the page goes straight to the results, as it
  does today; there is no explanation step. Whole-quiz timeout replies do
  not carry `explanation_html` (otherwise a time-up during the step would
  bring the explanation of a question the student never saw).

## Page details

- After "Продовжити", if the last answer reply had `explanation_html`, the
  page shows the explanation step instead of the next question; "Далі" then
  calls the existing `continueToNextQuestion()`.
- A reload during the explanation step opens the next question (the step is
  not restored). Acceptable: the student already saw the answer feedback.
- Translations (uk/en): the step title ("📖 Пояснення" / "📖 Explanation") and
  the button ("Далі" / "Next").
- Styling: headings, lists, code, tables and images inside the explanation
  use the theme variables (light and dark); images and tables never get
  wider than the screen (`max-width: 100%`, tables scroll inside their own
  box on phones).
- Copy prevention applies to question text only; explanation text may be
  selected. The copy blocker covers `#current-question-container`, so the
  explanation step is shown outside it (or the blocker skips it).
- `explanation:` with no value (null), or only spaces, means no explanation.
- The image picker writes `![](/imgs/name.png)`; for a file name with a
  space it writes `![](</imgs/my picture.png>)` (CommonMark angle brackets),
  and the transfer pattern reads both forms.

## Non-goals

- No explanation per answer option ("why option B is wrong"); one
  explanation per question.
- No preview in the file manager's YAML editor (only in the quiz editor).
- No explanations on the results screen or in live stats.
- No change to CSV files.

## Anti-goals

- An explanation must never reach the page before the student answers.
- Markdown must never let HTML or scripts from a quiz file run in a
  student's browser.

## Tests (written first)

- Rendering: Markdown basics, tables, raw HTML shown as text,
  `javascript:` links not made, `/imgs/` paths made relative, links get
  `target="_blank"`.
- Validation: non-boolean `show_explanation`, non-string `explanation`.
- Submit reply: `explanation_html` present only when `show_right_answer` and
  `show_explanation` are on and the question has one; absent when correct
  answers are hidden; same reply on a repeated request; present on a
  per-question timeout.
- Start settings: `show_explanation` accepted, applied, not written to the
  file; invalid value gives 400.
- Unite copies `show_explanation`. Transfer finds and rewrites images inside
  explanations.
- Preview endpoint: renders Markdown with the admin image prefix, needs the
  admin session, refuses a non-string `markdown`, shows raw HTML as text.
- Browser: step between questions, "Далі" opens the next question, last
  question → explanation → results, no step without an explanation, no step
  with `show_right_answer: false`, whole-quiz time-up during the step shows
  the results; editor saves the explanation and shows/hides the checkbox; the
  start pop-up shows, fills and greys out the checkbox; the editor preview
  shows the rendered Markdown and an image, and updates after typing; phone
  width.

## Docs

`docs/en` and `docs/uk` (`050_quiz_format.md`, `030_admin.md`), README
(feature, `show_explanation` option, test counts), CLAUDE.md (technical
decision, config option, the new dependency, the preview endpoint).

## Left to the builder

Exact CSS, element ids, the image-insert button's look, where in the
question card the text area goes, and the mistune renderer details within
the rules above.
