"""Question explanations: Markdown text shown to a student after answering a question.

Explanations are written in Markdown and rendered on the server with mistune.
The rendered HTML is safe to put into a page:

- raw HTML in the Markdown is shown as text, never run;
- links with harmful schemes (javascript: and similar) are shown as plain text;
- other links open in a new tab, so a click does not leave the quiz.

Images use the same path form as question images, "/imgs/name.png". The
renderer turns that into a relative path for the page that shows it.
"""

import re
from typing import Dict, List

import mistune
from mistune.util import safe_entity
from mistune.plugins.formatting import strikethrough
from mistune.plugins.table import table

IMAGES_PATH = "/imgs/"
STUDENT_IMAGES_URL = "imgs/"  # The quiz page is served at "/"
ADMIN_IMAGES_URL = "../imgs/"  # The admin page is served at "/admin/"

# "](/imgs/name)" with an optional title, and "](</imgs/name with spaces>)"
_ANGLE_IMAGE = re.compile(r"(\]\(\s*<" + re.escape(IMAGES_PATH) + r")([^>\n]+)(>)")
# A plain name may hold balanced brackets, as in "pic(1).png"
_PLAIN_IMAGE = re.compile(r"(\]\(\s*" + re.escape(IMAGES_PATH) + r")((?:[^()\s>]|\([^()\s>]*\))+)()")
# Names with these characters must be written in angle brackets: "](</imgs/my map.png>)"
_NEEDS_ANGLE_BRACKETS = re.compile(r"[\s()<>]")


class _ExplanationRenderer(mistune.HTMLRenderer):
    def __init__(self, images_url: str):
        super().__init__(escape=True)
        self.images_url = images_url

    def link(self, text, url, title=None):
        href = self.safe_url(url)
        if href == "#harmful-link":
            return text
        html = f'<a href="{href}" target="_blank" rel="noopener"'
        if title:
            html += f' title="{safe_entity(title)}"'
        return html + f">{text}</a>"

    def image(self, text, url, title=None):
        if url.startswith(IMAGES_PATH):
            url = self.images_url + url[len(IMAGES_PATH) :]
        return super().image(text, url, title)


_renderers: Dict[str, mistune.Markdown] = {}


def _markdown(images_url: str) -> mistune.Markdown:
    if images_url not in _renderers:
        _renderers[images_url] = mistune.Markdown(
            renderer=_ExplanationRenderer(images_url), plugins=[table, strikethrough]
        )
    return _renderers[images_url]


def has_explanation(question: dict) -> bool:
    """True when the question has explanation text (not empty, not only spaces)."""
    value = question.get("explanation")
    return isinstance(value, str) and value.strip() != ""


def render_explanation(markdown: str, images_url: str = STUDENT_IMAGES_URL) -> str:
    """Render explanation Markdown to safe HTML; "/imgs/" image paths start with images_url."""
    return _markdown(images_url)(markdown)


def explanation_image_names(markdown: str) -> List[str]:
    """File names of the quiz images ("/imgs/...") that the explanation shows, without duplicates."""
    matches = sorted(
        (match.start(), match.group(2).strip())
        for pattern in (_ANGLE_IMAGE, _PLAIN_IMAGE)
        for match in pattern.finditer(markdown)
    )
    found = []
    for _, name in matches:
        if name and name not in found:
            found.append(name)
    return found


def rewrite_explanation_images(markdown: str, renamed: Dict[str, str]) -> str:
    """Point image references to new file names ({old name: new name}), keeping their form."""

    def replace(match):
        name = match.group(2).strip()
        if name not in renamed:
            return match.group(0)
        new_name = renamed[name]
        is_plain = match.group(3) == ""
        if is_plain and _NEEDS_ANGLE_BRACKETS.search(new_name):
            start = match.group(1)[: -len(IMAGES_PATH)]
            return f"{start}<{IMAGES_PATH}{new_name}>"
        return match.group(1) + new_name + match.group(3)

    for pattern in (_ANGLE_IMAGE, _PLAIN_IMAGE):
        markdown = pattern.sub(replace, markdown)
    return markdown


def validate_explanations(data: dict) -> List[str]:
    """Check show_explanation and every question's explanation before a quiz is saved."""
    errors = []
    if "show_explanation" in data and not isinstance(data["show_explanation"], bool):
        errors.append("'show_explanation' must be a boolean (true or false)")
    questions = data.get("questions")
    if isinstance(questions, list):
        for index, question in enumerate(questions):
            if not isinstance(question, dict) or "explanation" not in question:
                continue
            value = question["explanation"]
            if value is not None and not isinstance(value, str):
                errors.append(f"Question {index + 1} 'explanation' must be text")
    return errors
