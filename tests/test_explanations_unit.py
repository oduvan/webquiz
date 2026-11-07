"""Unit tests for question explanations: Markdown rendering, image references and checks."""

from webquiz.explanations import (
    ADMIN_IMAGES_URL,
    explanation_image_names,
    has_explanation,
    render_explanation,
    rewrite_explanation_images,
    validate_explanations,
)


def test_renders_bold_and_list():
    html = render_explanation("**b** text\n\n- one\n- two")
    assert "<strong>b</strong>" in html
    assert "<li>one</li>" in html


def test_renders_table():
    html = render_explanation("| a | b |\n|---|---|\n| 1 | 2 |")
    assert "<table>" in html
    assert "<td>1</td>" in html


def test_raw_html_is_shown_as_text():
    html = render_explanation("<script>alert(1)</script>\n\n<img src=x onerror=alert(1)>")
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "<img src=x" not in html
    assert "&lt;img src=x onerror=alert(1)&gt;" in html


def test_javascript_link_is_plain_text():
    html = render_explanation("see [x](javascript:alert) now")
    assert "<a" not in html
    assert "see x now" in html


def test_links_open_in_new_tab():
    html = render_explanation("[site](https://e.com)")
    assert 'href="https://e.com"' in html
    assert 'target="_blank"' in html
    assert 'rel="noopener"' in html


def test_image_path_for_student_page():
    assert 'src="imgs/a.png"' in render_explanation("![a](/imgs/a.png)")


def test_image_path_for_admin_preview():
    assert 'src="../imgs/a.png"' in render_explanation("![a](/imgs/a.png)", ADMIN_IMAGES_URL)


def test_image_name_with_space_in_angle_brackets():
    assert 'src="imgs/my%20pic.png"' in render_explanation("![a](</imgs/my pic.png>)")


def test_external_image_url_unchanged():
    assert 'src="https://e.com/a.png"' in render_explanation("![a](https://e.com/a.png)")


def test_has_explanation():
    assert has_explanation({"explanation": "x"})
    assert not has_explanation({})
    assert not has_explanation({"explanation": None})
    assert not has_explanation({"explanation": ""})
    assert not has_explanation({"explanation": "  \n "})
    assert not has_explanation({"explanation": 5})
    assert not has_explanation({"explanation": ["x"]})


def test_explanation_image_names():
    text = (
        '![a](/imgs/a.png) and ![b](/imgs/b.png "title")\n'
        "![c](</imgs/my pic.png>) ![d](https://e.com/c.png) ![e](/imgs/a.png)"
    )
    assert explanation_image_names(text) == ["a.png", "b.png", "my pic.png"]


def test_rewrite_explanation_images():
    text = "Look: ![a](/imgs/a.png) and ![c](</imgs/my pic.png>) and ![k](/imgs/keep.png)."
    result = rewrite_explanation_images(text, {"a.png": "s_a.png", "my pic.png": "s_my pic.png"})
    assert result == "Look: ![a](/imgs/s_a.png) and ![c](</imgs/s_my pic.png>) and ![k](/imgs/keep.png)."


def test_validate_explanations():
    assert validate_explanations({"show_explanation": "yes", "questions": []}) == [
        "'show_explanation' must be a boolean (true or false)"
    ]
    errors = validate_explanations({"questions": [{"explanation": 5}, {"explanation": ["x"]}]})
    assert errors == ["Question 1 'explanation' must be text", "Question 2 'explanation' must be text"]
    assert (
        validate_explanations({"show_explanation": True, "questions": [{"explanation": "t"}, {"explanation": None}]})
        == []
    )
