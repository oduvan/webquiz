"""Server tests for question explanations: the answer reply, settings, checks, unite and preview."""

import os

import requests
import yaml
from conftest import custom_webquiz_server, get_admin_session, register_student

EXPLANATION = "**Why** it is A"


def question(text, explanation=None, **extra):
    data = {"question": text, "options": ["A", "B"], "correct_answer": 0, **extra}
    if explanation is not None:
        data["explanation"] = explanation
    return data


def quiz(questions=None, **settings):
    data = {
        "title": "Explanations",
        "show_right_answer": True,
        "show_explanation": True,
        "questions": questions or [question("Q1?", EXPLANATION), question("Q2?")],
    }
    data.update(settings)
    return {"default.yaml": data}


def answer(port, user_id, question_id, selected=0):
    response = requests.post(
        f"http://localhost:{port}/api/submit-answer",
        json={"user_id": user_id, "question_id": question_id, "selected_answer": selected},
    )
    assert response.status_code == 200, response.text
    return response.json()


def question_start(port, user_id, question_id):
    response = requests.post(
        f"http://localhost:{port}/api/question-start", json={"user_id": user_id, "question_id": question_id}
    )
    assert response.status_code == 200, response.text


def preview(port, cookies, body):
    return requests.post(f"http://localhost:{port}/api/admin/preview-explanation", cookies=cookies, json=body)


def test_answer_reply_has_explanation_html(temp_dir):
    with custom_webquiz_server(quizzes=quiz()) as (proc, port):
        user_id = register_student(port)
        reply = answer(port, user_id, 1)
        assert "<strong>Why</strong>" in reply["explanation_html"]


def test_question_without_explanation_has_none(temp_dir):
    with custom_webquiz_server(quizzes=quiz()) as (proc, port):
        user_id = register_student(port)
        answer(port, user_id, 1)
        assert "explanation_html" not in answer(port, user_id, 2)


def test_no_explanation_when_option_off(temp_dir):
    quizzes = quiz()
    del quizzes["default.yaml"]["show_explanation"]
    with custom_webquiz_server(quizzes=quizzes) as (proc, port):
        user_id = register_student(port)
        assert "explanation_html" not in answer(port, user_id, 1)


def test_no_explanation_when_right_answer_hidden(temp_dir):
    with custom_webquiz_server(quizzes=quiz(show_right_answer=False)) as (proc, port):
        user_id = register_student(port)
        assert "explanation_html" not in answer(port, user_id, 1)


def test_explanation_is_not_in_page_before_answer(temp_dir):
    with custom_webquiz_server(quizzes=quiz()) as (proc, port):
        page = requests.get(f"http://localhost:{port}/").text
        assert "it is A" not in page
        assert "Why" not in page


def test_repeated_answer_returns_same_explanation(temp_dir):
    with custom_webquiz_server(quizzes=quiz()) as (proc, port):
        user_id = register_student(port)
        first = answer(port, user_id, 1)
        second = answer(port, user_id, 1)
        assert second["explanation_html"] == first["explanation_html"]


def test_per_question_timeout_reply_has_explanation(temp_dir):
    with custom_webquiz_server(quizzes=quiz(time_limit={"per_question": 30})) as (proc, port):
        user_id = register_student(port)
        question_start(port, user_id, 1)
        reply = answer(port, user_id, 1, selected=None)
        assert reply["timed_out"] is True
        assert "<strong>Why</strong>" in reply["explanation_html"]


def test_whole_quiz_timeout_reply_has_no_explanation(temp_dir):
    with custom_webquiz_server(quizzes=quiz(time_limit={"whole_quiz": 30})) as (proc, port):
        user_id = register_student(port)
        question_start(port, user_id, 1)
        reply = answer(port, user_id, 1, selected=None)
        assert reply["timed_out"] is True
        assert "explanation_html" not in reply


def test_random_order_explanation_follows_question_id(temp_dir):
    questions = [question(f"Q{n}?", f"E{n}") for n in (1, 2, 3)]
    with custom_webquiz_server(quizzes=quiz(questions, randomize_questions=True)) as (proc, port):
        response = requests.post(f"http://localhost:{port}/api/register", json={"username": "Student"})
        data = response.json()
        first_id = data["question_order"][0]
        reply = answer(port, data["user_id"], first_id)
        assert f"E{first_id}" in reply["explanation_html"]


def test_hand_edited_bad_values_still_load(temp_dir):
    quizzes = quiz([question("Q1?", 5), question("Q2?")], show_explanation="yes")
    with custom_webquiz_server(quizzes=quizzes) as (proc, port):
        user_id = register_student(port)
        assert "explanation_html" not in answer(port, user_id, 1)


def test_create_quiz_rejects_bad_explanation_values(temp_dir):
    with custom_webquiz_server(quizzes=quiz()) as (proc, port):
        cookies = get_admin_session(port)

        def create(name, data):
            return requests.post(
                f"http://localhost:{port}/api/admin/create-quiz",
                cookies=cookies,
                json={"filename": name, "mode": "wizard", "quiz_data": data},
            )

        bad_option = {"show_explanation": "yes", "questions": [question("Q1?")]}
        bad_text = {"questions": [question("Q1?", ["x"])]}
        good = {"show_explanation": True, "questions": [question("Q1?", "Text")]}
        assert create("bad1.yaml", bad_option).status_code == 400
        assert create("bad2.yaml", bad_text).status_code == 400
        assert create("good.yaml", good).status_code == 200


def test_start_setting_turns_explanations_off(temp_dir):
    with custom_webquiz_server(quizzes=quiz()) as (proc, port):
        cookies = get_admin_session(port)
        response = requests.post(
            f"http://localhost:{port}/api/admin/switch-quiz",
            cookies=cookies,
            json={"quiz_filename": "default.yaml", "settings": {"show_explanation": False}},
        )
        assert response.status_code == 200, response.text
        assert response.json()["settings"]["show_explanation"] is False
        user_id = register_student(port)
        assert "explanation_html" not in answer(port, user_id, 1)
        with open(os.path.join(temp_dir, f"quizzes_{port}", "default.yaml"), encoding="utf-8") as f:
            assert yaml.safe_load(f)["show_explanation"] is True


def test_start_setting_rejects_non_boolean(temp_dir):
    with custom_webquiz_server(quizzes=quiz()) as (proc, port):
        cookies = get_admin_session(port)
        response = requests.post(
            f"http://localhost:{port}/api/admin/switch-quiz",
            cookies=cookies,
            json={"quiz_filename": "default.yaml", "settings": {"show_explanation": "no"}},
        )
        assert response.status_code == 400


def test_unite_copies_show_explanation(temp_dir):
    quizzes = quiz()
    quizzes["other.yaml"] = {"title": "Other", "questions": [question("Q3?")]}
    with custom_webquiz_server(quizzes=quizzes) as (proc, port):
        cookies = get_admin_session(port)
        response = requests.post(
            f"http://localhost:{port}/api/admin/unite-quizzes",
            cookies=cookies,
            json={"quiz_filenames": ["default.yaml", "other.yaml"], "new_name": "united"},
        )
        assert response.status_code == 200, response.text
        with open(os.path.join(temp_dir, f"quizzes_{port}", "united.yaml"), encoding="utf-8") as f:
            united = yaml.safe_load(f)
        assert united["show_explanation"] is True
        assert united["questions"][0]["explanation"] == EXPLANATION


def test_preview_needs_admin_session(temp_dir):
    with custom_webquiz_server(quizzes=quiz()) as (proc, port):
        assert preview(port, None, {"markdown": "x"}).status_code == 401


def test_preview_renders_with_admin_image_path(temp_dir):
    with custom_webquiz_server(quizzes=quiz()) as (proc, port):
        response = preview(port, get_admin_session(port), {"markdown": "![a](/imgs/a.png) <b>x</b>"})
        assert response.status_code == 200
        html = response.json()["html"]
        assert 'src="../imgs/a.png"' in html
        assert "&lt;b&gt;" in html


def test_preview_rejects_non_string(temp_dir):
    with custom_webquiz_server(quizzes=quiz()) as (proc, port):
        assert preview(port, get_admin_session(port), {"markdown": 5}).status_code == 400
