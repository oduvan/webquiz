# Question Explanations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** After a student answers a question that has an explanation, show the explanation (Markdown, with images) as its own step before the next question; the teacher writes it in the quiz editor with a live preview.

**Architecture:** A new pure module `webquiz/explanations.py` renders Markdown with mistune (raw HTML escaped, unsafe links dropped, `/imgs/` paths made relative) and finds/rewrites image references. The server renders every explanation once at quiz load and adds `explanation_html` to the answer reply. The student page shows it as a step between questions; the admin editor gets a text area, image insert and a live preview served by a new admin endpoint.

**Tech Stack:** Python 3.10+, aiohttp, mistune 3, vanilla JS, pytest + Selenium.

**Spec:** `docs/superpowers/specs/2026-11-07-question-explanations-design.md`

## Global Constraints

- Dependency: `mistune = "^3.1"` in `[tool.poetry.dependencies]`; regenerate `poetry.lock` with Poetry 2.3.2 (the version that made it), changing only mistune.
- Import mistune plugins as functions (`from mistune.plugins.table import table`, `from mistune.plugins.formatting import strikethrough`), never by name, so PyInstaller bundles them.
- Quiz text stays safe: raw HTML in Markdown is shown as text; links with harmful schemes are rendered as plain text.
- `show_explanation` default `false`; explanations only when the running quiz has `show_right_answer` **and** `show_explanation` on.
- Never put explanation text into the page before the answer (not in `QUESTIONS_DATA`).
- Whole-quiz timeout replies carry no `explanation_html`.
- Image paths: student page `imgs/…`, admin preview `../imgs/…`.
- No external JS; mobile ≤768px (`width: 100%; max-width: …`), images and tables never wider than the screen.
- uk/en translations for every student-facing string; admin page strings are Ukrainian like the rest of admin.html.
- black, line length 120. Tests first. Venv: `source venv/bin/activate`.

## Review Focus

1. A hand-edited quiz file with a non-string `explanation` (number, list) or a non-boolean `show_explanation` must still load and run; the question just has no explanation. → test in Task 2.
2. Random question order: the reply's explanation must belong to the answered question id, not the position. → test in Task 2.
3. Double-click on "Далі" must not skip a question. → test in Task 4.
4. Whole-quiz time running out while the explanation step is open must end on the results, with no step and no error. → test in Task 4.
5. A wide table or big image on a phone must not make the page scroll sideways. → test in Task 4.

---

### Task 1: Markdown module and dependency

**Files:**
- Create: `webquiz/explanations.py`
- Modify: `pyproject.toml`, `poetry.lock`
- Test: `tests/test_explanations_unit.py`

**Interfaces:**
- Produces:
  - `STUDENT_IMAGES_URL = "imgs/"`, `ADMIN_IMAGES_URL = "../imgs/"`
  - `has_explanation(question: dict) -> bool` — True only for a string with non-space text.
  - `render_explanation(markdown: str, images_url: str = STUDENT_IMAGES_URL) -> str`
  - `explanation_image_names(markdown: str) -> List[str]` — file names under `/imgs/` in `](/imgs/name)`, `](/imgs/name "title")` and `](</imgs/name with space>)`, no duplicates, in order.
  - `rewrite_explanation_images(markdown: str, renamed: Dict[str, str]) -> str` — replaces those names (old → new) keeping the reference form.
  - `validate_explanations(data: dict) -> List[str]` — `"'show_explanation' must be a boolean (true or false)"`; `"Question {n} 'explanation' must be text"` (None allowed).

- [ ] **Step 1: Add the dependency.** `pip install poetry==2.3.2` in a scratch venv, add `mistune = "^3.1"` to pyproject, run its `poetry lock` in the repo, then `poetry install` in the project venv. `git diff poetry.lock` shows only mistune added (plus the content hash).
- [ ] **Step 2: Write the failing tests** in `tests/test_explanations_unit.py`:
  - `test_renders_bold_and_list` → `<strong>b</strong>` and `<li>` present.
  - `test_renders_table` → `<table>` present for a pipe table.
  - `test_raw_html_is_shown_as_text` → `"<script>"` not in output, `"&lt;script&gt;"` in output; `<img src=x onerror=alert(1)>` also escaped.
  - `test_javascript_link_is_plain_text` → `[x](javascript:alert(1))` gives no `<a`, and `x` stays.
  - `test_links_open_in_new_tab` → `href="https://e.com"`, `target="_blank"`, `rel="noopener"`.
  - `test_image_path_for_student_page` → `![a](/imgs/a.png)` gives `src="imgs/a.png"`.
  - `test_image_path_for_admin_preview` → with `ADMIN_IMAGES_URL` gives `src="../imgs/a.png"`.
  - `test_image_name_with_space_in_angle_brackets` → `![a](</imgs/my pic.png>)` gives `src="imgs/my%20pic.png"`.
  - `test_external_image_url_unchanged` → `https://e.com/a.png` stays.
  - `test_has_explanation` → True for `"x"`; False for missing, `None`, `""`, `"  "`, `5`, `["x"]`.
  - `test_explanation_image_names` → for text with `/imgs/a.png`, `/imgs/b.png "t"`, `</imgs/my pic.png>`, `https://e.com/c.png` and `/imgs/a.png` again → `["a.png", "b.png", "my pic.png"]`.
  - `test_rewrite_explanation_images` → `{"a.png": "s_a.png", "my pic.png": "s_my pic.png"}` rewrites both forms; other text unchanged.
  - `test_validate_explanations` → errors for `show_explanation: "yes"` and `explanation: 5` / `["x"]`; none for a string, `None`, or `show_explanation: True`.
- [ ] **Step 3: Run** `python -m pytest tests/test_explanations_unit.py -q` → fails (module missing).
- [ ] **Step 4: Implement `webquiz/explanations.py`.** A `mistune.HTMLRenderer(escape=True)` subclass that overrides `link` (if `safe_url(url) == "#harmful-link"` return the text; else add `target="_blank" rel="noopener"`) and `image` (replace a leading `/imgs/` with `images_url` before calling the parent). Build one `mistune.Markdown` per `images_url` (cache in a dict) with plugins `[table, strikethrough]`. Image-name patterns: `\]\(\s*</imgs/([^>\n]+)>` and `\]\(\s*/imgs/([^)\s]+)`.
- [ ] **Step 5: Run** the tests → all pass.
- [ ] **Step 6: Commit** `pyproject.toml poetry.lock webquiz/explanations.py tests/test_explanations_unit.py` — "Add Markdown rendering for question explanations (mistune)".

### Task 2: Server — load, validate, reply, start settings, unite, preview endpoint

**Files:**
- Modify: `webquiz/server.py` (`__init__` defaults near `self.show_final_list = True`; `load_questions_from_file`; `START_SETTING_KEYS`; `_apply_start_settings`; `current_quiz_settings`; `_record_answer`; `_end_whole_quiz`; `_validate_quiz_data`; unite `optional_fields`; routes)
- Test: `tests/test_explanations.py`

**Interfaces:**
- Consumes: Task 1 functions.
- Produces:
  - `self.show_explanation: bool` (file value `data.get("show_explanation", False)`), `self.explanations_html: Dict[int, str]` (question id → HTML, only for `has_explanation`).
  - Answer reply key `explanation_html` (string), inside the `if self.show_right_answer:` block, when `with_explanation and self.show_explanation and question id in self.explanations_html`.
  - `_record_answer(..., timed_out=False, with_explanation=True)`; `_end_whole_quiz` passes `with_explanation=False`.
  - `"show_explanation"` in `START_SETTING_KEYS`, applied and reported like the other booleans.
  - `POST /api/admin/preview-explanation` (`@admin_auth_required`): body `{"markdown": str}` → `{"html": render_explanation(markdown, ADMIN_IMAGES_URL)}`; non-string or missing → 400 `{"error": ...}`.

- [ ] **Step 1: Write the failing tests** in `tests/test_explanations.py` (helpers like `tests/test_quiz_start_settings.py`: `custom_webquiz_server`, `get_admin_session`, `register_student`). Quiz: Q1 with `explanation: "**Why** it is A"`, Q2 without; `show_right_answer: true`, `show_explanation: true` unless a test says otherwise.
  - `test_answer_reply_has_explanation_html` → `"<strong>Why</strong>" in reply["explanation_html"]`.
  - `test_question_without_explanation_has_none` → Q2 reply has no `explanation_html`.
  - `test_no_explanation_when_option_off` (`show_explanation` missing) and `test_no_explanation_when_right_answer_hidden` (`show_right_answer: false`).
  - `test_explanation_is_not_in_page_before_answer` → `"Why it is A"` and `"Why"` not in `GET /`.
  - `test_repeated_answer_returns_same_explanation` → second identical submit returns equal `explanation_html`.
  - `test_per_question_timeout_reply_has_explanation` → `time_limit: {per_question: 30}`, question-start, submit `selected_answer: None` → `timed_out` and `explanation_html` present.
  - `test_whole_quiz_timeout_reply_has_no_explanation` → `time_limit: {whole_quiz: 30}`, question-start, submit `None` for Q1 → `timed_out`, no `explanation_html`.
  - `test_random_order_explanation_follows_question_id` → `randomize_questions: true`, three questions each with explanation `"E{n}"`; answer the first id in `question_order`; reply HTML contains that question's `E{n}`.
  - `test_hand_edited_bad_values_still_load` → file with `explanation: 5` and `show_explanation: "yes"`; page loads, answering Q1 returns 200 with no `explanation_html`.
  - `test_create_quiz_rejects_bad_explanation_values` → `POST /api/admin/create-quiz` with `show_explanation: "yes"` → 400; with `explanation: ["x"]` → 400; valid → 200.
  - `test_start_setting_turns_explanations_off` → switch-quiz with `{"show_explanation": False}` → reply has no `explanation_html`; response `settings["show_explanation"] is False`; quiz file still has `show_explanation: true`.
  - `test_start_setting_rejects_non_boolean` → `{"show_explanation": "no"}` → 400.
  - `test_unite_copies_show_explanation` → united file has `show_explanation: true` and Q1's explanation.
  - `test_preview_needs_admin_session` → no cookies → 401 (match what `@admin_auth_required` returns in other tests).
  - `test_preview_renders_with_admin_image_path` → `![a](/imgs/a.png) <b>x</b>` → html has `src="../imgs/a.png"` and `&lt;b&gt;`.
  - `test_preview_rejects_non_string` → `{"markdown": 5}` → 400.
- [ ] **Step 2: Run** `python -m pytest tests/test_explanations.py -q -n 4` → fail.
- [ ] **Step 3: Implement** the Produces list above. In `load_questions_from_file`, build `explanations_html` after ids are assigned. `_validate_quiz_data` extends `errors` with `validate_explanations(data)`. Add `"show_explanation"` to the unite `optional_fields`. Register the route next to the other `/api/admin/` routes. Log `show_explanation` in the "Loaded … questions" line.
- [ ] **Step 4: Run** the new tests plus `tests/test_quiz_start_settings.py tests/test_admin_unite_quizzes.py tests/test_time_limits_submit.py` → pass.
- [ ] **Step 5: Commit** — "Send question explanations with the answer reply; preview endpoint".

### Task 3: File transfer — images inside explanations

**Files:**
- Modify: `webquiz/transfer.py` (`quiz_media_files`, `rewrite_quiz_media`)
- Test: `tests/test_transfer.py`

**Interfaces:**
- Consumes: `explanation_image_names`, `rewrite_explanation_images`.
- Produces: `quiz_media_files()` also returns `("images", name)` for each explanation image (via `is_allowed_file`); `rewrite_quiz_media()` rewrites `question["explanation"]` text with `{name: new}` built from `renamed` entries of type `"images"`.

- [ ] **Step 1: Write failing tests:** `test_quiz_media_files_finds_explanation_images` (plain and angle-bracket forms, external URL ignored) and `test_rewrite_quiz_media_rewrites_explanation_images` (file text after rewrite has the new names, other text and YAML comments kept).
- [ ] **Step 2: Run** them → fail.
- [ ] **Step 3: Implement** inside the existing loops; only string explanations are touched.
- [ ] **Step 4: Run** `python -m pytest tests/test_transfer.py tests/test_transfer_api.py -q` → pass.
- [ ] **Step 5: Commit** — "Transfer images used inside question explanations".

### Task 4: Student page — the explanation step

**Files:**
- Modify: `webquiz/templates/index.html`, `webquiz/translations.py` (keys `explanation_title`: "📖 Пояснення" / "📖 Explanation", `next_button`: "Далі" / "Next")
- Test: `tests/test_selenium_explanations.py`

**Interfaces:**
- Consumes: reply key `explanation_html`.
- Produces (page): `#explanation-step` (inside `#test-section`, after `#current-question-container`, outside it so the copy blocker does not apply) containing `.explanation-title`, `.explanation-question` (question text via `escapeHtml`), `.explanation-content` (server HTML), button `#explanation-next-btn`. JS: `pendingExplanation` (`{question, html}` or null), `showExplanationStep()`, `leaveExplanationStep()`.

- [ ] **Step 1: Write failing tests** (pattern of `tests/test_selenium_time_limits.py`):
  - `test_explanation_step_between_questions` → answer Q1, Продовжити → `#explanation-step` visible with `<strong>` text and Q1 text; `#current-question-container` hidden; click Далі → "Питання 2 з 3".
  - `test_question_without_explanation_goes_straight_on` → Q2 has none: Продовжити → Q3 directly.
  - `test_last_question_explanation_then_results` → last question has one: step, then Далі → "Результат".
  - `test_no_step_when_right_answer_hidden` → `show_right_answer: false` → auto-advance to Q2, step never shown.
  - `test_double_click_next_does_not_skip` → double-click `#explanation-next-btn` (ActionChains) → "Питання 2 з 3".
  - `test_whole_quiz_time_up_during_step_shows_results` → `time_limit: {whole_quiz: 5}`, server env `WEBQUIZ_TIME_LIMIT_GRACE_SECONDS=0`; answer Q1 quickly, open the step, wait → "Результат" within 15 s, `#explanation-step` hidden.
  - `test_explanation_fits_phone_width` → 375×800 window, explanation with a 6-column table and an image → `document.documentElement.scrollWidth <= window.innerWidth`.
  - `test_explanation_image_is_loaded` → image under `quizzes/imgs/` (write a tiny PNG in the test) → `naturalWidth > 0`.
- [ ] **Step 2: Run** → fail.
- [ ] **Step 3: Implement.** On the answer reply (where `testResults.push` happens) set `pendingExplanation` when `data.explanation_html` is a non-empty string, else null. `continueToNextQuestion()`: if `pendingExplanation` → `showExplanationStep()` and return (index unchanged). The step hides `#current-question-container`, the question countdown box and both buttons; the whole-quiz box stays. `#explanation-next-btn` disables itself, calls `leaveExplanationStep()` (hide step, show container, clear `pendingExplanation`) then `continueToNextQuestion()`. `finishQuizAfterTimeUp()` and the results branch of `showCurrentQuestion` hide the step. CSS `.explanation-content`: theme vars, `img {max-width: 100%; height: auto}`, `table` wrapped by `display: block; overflow-x: auto; max-width: 100%`, `pre {overflow-x: auto}`; `@media (max-width: 768px)` padding.
- [ ] **Step 4: Run** the new file plus `tests/test_selenium_time_limits.py tests/test_auto_advance.py tests/test_user_journey_selenium.py` → pass.
- [ ] **Step 5: Commit** — "Show the explanation as a step after the answer".

### Task 5: Admin editor and start pop-up

**Files:**
- Modify: `webquiz/templates/admin.html` (`addQuestion`, `loadQuizDataToWizard`, the wizard collect function before `saveQuiz`, `selectImage`, start pop-up HTML and `openStartQuizModal`/`getStartSettings`, CSS)
- Test: `tests/test_selenium_admin_explanations.py`

**Interfaces:**
- Consumes: `POST /api/admin/preview-explanation`; `show_explanation` start setting.
- Produces (page): per question `textarea.question-explanation`, button calling `openImagePicker('explanation', questionId)`, `.explanation-preview.explanation-content`; helper `explanationFieldHtml(questionId, value)` used by both card builders; `scheduleExplanationPreview(textarea)` (300 ms debounce per textarea); `updateShowExplanationVisibility()`; quiz setting `#show-explanation-group` / `#show-explanation`; pop-up `#start-show-explanation-group`, `#start-show-explanation`, `#start-show-explanation-note`.

- [ ] **Step 1: Write failing tests** (helpers from `tests/test_selenium_quiz_editor.py` and `tests/test_selenium_admin_start_settings.py`):
  - `test_editor_preview_renders_markdown` → type `**Bold** text` into the first question's explanation → within 3 s the preview contains `<strong>Bold</strong>`; empty text → preview hidden.
  - `test_editor_show_explanation_appears_with_text` → `#show-explanation-group` hidden with no explanation, shown after typing, hidden again after clearing.
  - `test_editor_saves_explanation_and_option` → save → quiz file has the question's `explanation` and `show_explanation: true` (ticked).
  - `test_editor_loads_existing_explanation` → quiz with explanation and `show_explanation: true` opens with the textarea filled, preview shown, box ticked.
  - `test_editor_inserts_image_markdown` → `quizzes/imgs/pic.png` exists; picker → `![](/imgs/pic.png)` in the textarea; preview `img` has `naturalWidth > 0`.
  - `test_start_popup_explanation_checkbox` → quiz with an explanation: group shown, ticked from file; untick `start-show-right-answer` → `#start-show-explanation` disabled and note shown; quiz without explanations → group hidden.
  - `test_start_popup_sends_show_explanation` → untick it, start → `GET /` then answer Q1 via API → reply has no `explanation_html`.
- [ ] **Step 2: Run** → fail.
- [ ] **Step 3: Implement.** Collect: `questionData.explanation` when the textarea has non-space text; `quizData.show_explanation` only while the group is shown. `selectImage` for `'explanation'` inserts at the cursor `![](/imgs/name)` or `![](</imgs/name>)` when the name has a space, then dispatches `input`. Preview fetch uses `credentials: 'same-origin'`; the reply HTML is put in with `innerHTML` (it is server-sanitized). Pop-up: group shown when any question in the fetched quiz has non-space string `explanation`; `getStartSettings()` adds `show_explanation` only then. Mobile: textarea `width: 100%`.
- [ ] **Step 4: Run** the new file plus `tests/test_selenium_quiz_editor.py tests/test_selenium_admin_start_settings.py tests/test_selenium_admin_time_limits.py` → pass.
- [ ] **Step 5: Commit** — "Explanation field, image insert and live preview in the quiz editor".

### Task 6: Docs and full run

**Files:**
- Modify: `README.md` (feature section, `show_explanation`, `explanation`, test counts and total), `docs/en/050_quiz_format.md`, `docs/uk/050_quiz_format.md`, `docs/en/030_admin.md`, `docs/uk/030_admin.md`, `CLAUDE.md` (Key Files: `explanations.py`; API: preview endpoint and `explanation_html` in submit-answer; Technical Decisions line; config option; START_SETTING_KEYS list)

- [ ] **Step 1: Write the docs** (uk and en in sync).
- [ ] **Step 2: Count tests** with `python -m pytest tests/ --collect-only -q` and update README numbers.
- [ ] **Step 3: Run the full suite** `python -m pytest tests/ -q -n 4` → 0 failures (count the dots; the repo runs `-q` already).
- [ ] **Step 4: Commit and push** — "Docs: question explanations".
