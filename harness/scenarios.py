"""The pilot scenarios.

Each scenario has a quiz file, the settings the teacher picks in the start
pop-up, scripted students with exact plans, and AI agent personas.

Scripted plans map a question number (1 = the first question the student
sees) to an action. Questions without an entry get the scenario's correct
answer after 3 seconds. Actions:

    ("answer", label_or_labels, delay)            click the option(s), submit at `delay` s
    ("text", value, delay)                        type into the answer box, submit at `delay` s
    ("pick", label, delay)                        click an option at `delay` s, never submit
    ("idle",)                                     do nothing, let the time run out
    ("leave", delay)                              close the tab at `delay` s and stop
    ("reload", reload_at, label, delay)           reload at `reload_at` s, then answer at `delay` s
    ("offline_answer", label, off_at, off_for, delay)
                                                  Wi-Fi off at `off_at` s for `off_for` s,
                                                  click and submit at `delay` s (while offline)
    ("offline_at_quiz_time", at, off_for)         Wi-Fi off when the whole quiz has run `at` s,
                                                  then do nothing

Times are seconds since the question appeared on that student's screen
(for offline_at_quiz_time: since the first question appeared).
"""

FRACTIONS = {
    "name": "normal-lesson",
    "description": (
        "A normal lesson. The quiz file says 60 s per question; the teacher starts it with 45 s in the "
        "pop-up. Mixed question types, students of different speeds, one reload, one student who leaves."
    ),
    "quiz_file": "fractions.yaml",
    "quiz": {
        "title": "Урок: дроби",
        "show_right_answer": True,
        "time_limit": {"per_question": 60},
        "questions": [
            {"question": "1/2 + 1/4 = ?", "options": ["3/4", "2/6", "1/6", "2/4"], "correct_answer": 0},
            {
                "question": "Які дроби дорівнюють 1/2? (усі правильні)",
                "options": ["2/4", "3/6", "2/3", "4/8"],
                "correct_answer": [0, 1, 3],
            },
            {
                "question": "Скільки буде 3/4 від 8? Введіть число.",
                "checker": "assert to_int(user_answer) == 6, 'Ні, це не 6'",
                "correct_value": "6",
                "points": 2,
            },
            {"question": "0,5 — це ...", "options": ["1/5", "1/2", "5/1", "1/50"], "correct_answer": 1},
            {"question": "Що більше: 2/3 чи 3/5?", "options": ["2/3", "3/5", "Вони рівні"], "correct_answer": 0},
        ],
    },
    "start_settings": {"time_limit": {"per_question": 45}},
    "answers": {1: "3/4", 2: ["2/4", "3/6", "4/8"], 3: ("text", "6"), 4: "1/2", 5: "2/3"},
    "scripted": {
        "s01-fast": {q: ("answer", None, 2) for q in (1, 2, 4, 5)} | {3: ("text", "6", 3)},
        "s02-slow": {1: ("answer", "3/4", 20), 2: ("answer", ["2/4", "3/6", "4/8"], 25), 3: ("text", "6", 30)},
        "s03-wrong": {1: ("answer", "2/6", 4), 4: ("answer", "1/5", 4)},
        "s04-text-wrong": {3: ("text", "5", 6)},
        "s05-reload": {3: ("reload", 5, ("text", "6"), 12)},
        "s06-leaves": {3: ("leave", 4)},
        "s07-partial": {2: ("answer", ["2/4"], 6)},
        "s08-near-limit": {1: ("answer", "3/4", 42), 4: ("answer", "1/2", 43)},
    },
    "agents": {
        "agent-careful": {
            "device": "desktop",
            "persona": "You are a careful student. Read each question, think, then answer. Try to get them right.",
        },
        "agent-phone": {
            "device": "phone",
            "persona": "You are a student on a phone who answers quickly and does not always read everything.",
        },
    },
    "finish_after": 60,
    "max_seconds": 600,
}

TIME_EDGES = {
    "name": "time-edges",
    "description": (
        "Time limit edges: 20 s per question, question 3 has its own 8 s, question 4 has no limit. "
        "Answers just before the limit, inside and after the 5 s grace (sent while the Wi-Fi is off), "
        "a picked but unsent option, no answer, a reload, and a student who closes the tab."
    ),
    "quiz_file": "time-edges.yaml",
    "quiz": {
        "title": "Перевірка часу",
        "show_right_answer": True,
        "time_limit": {"per_question": 20},
        "questions": [
            {"question": "Скільки буде 6 × 7?", "options": ["42", "36", "48", "49"], "correct_answer": 0},
            {"question": "Столиця України?", "options": ["Львів", "Київ", "Харків", "Одеса"], "correct_answer": 1},
            {
                "question": "Скільки сторін у трикутника?",
                "options": ["3", "4", "5", "6"],
                "correct_answer": 0,
                "time_limit": 8,
            },
            {
                "question": "Скільки буде 15 − 7?",
                "options": ["7", "8", "9", "6"],
                "correct_answer": 1,
                "time_limit": 0,
            },
        ],
    },
    "start_settings": {},
    "answers": {1: "42", 2: "Київ", 3: "3", 4: "8"},
    "scripted": {
        "e01-before-limit": {1: ("answer", "42", 17), 4: ("answer", "8", 30)},
        "e02-late-in-grace": {1: ("offline_answer", "42", 15, 8, 17)},
        "e03-late-after-grace": {1: ("offline_answer", "42", 15, 15, 17)},
        "e04-picked-not-sent": {1: ("pick", "36", 4)},
        "e05-idle": {1: ("idle",), 2: ("idle",), 3: ("idle",)},
        "e06-reload": {2: ("reload", 8, "Київ", 14)},
        "e07-no-limit": {4: ("answer", "8", 45)},
        "e08-leaves": {2: ("leave", 5)},
    },
    "agents": {
        "agent-slow": {
            "device": "desktop",
            "persona": (
                "You are a slow student. Before answering each question, run `wait 25` once "
                "(you read slowly), then answer."
            ),
        },
        "agent-normal": {
            "device": "desktop",
            "persona": "You are an ordinary student. Answer each question at a normal pace.",
        },
    },
    "finish_after": 60,
    "max_seconds": 480,
}

WHOLE_QUIZ = {
    "name": "whole-quiz-wifi",
    "description": (
        "Whole-quiz limit chosen in the start pop-up: the file says 30 s per question and correct answers "
        "shown; the teacher starts it with 75 s for the whole quiz and correct answers hidden. Students "
        "finish early, run out of time, lose Wi-Fi when time runs out, close the tab, or reload a lot."
    ),
    "quiz_file": "whole-quiz.yaml",
    "quiz": {
        "title": "Контрольна: множення",
        "show_right_answer": True,
        "time_limit": {"per_question": 30},
        "questions": [
            {"question": "3 × 4 = ?", "options": ["7", "12", "34", "9"], "correct_answer": 1},
            {"question": "5 × 6 = ?", "options": ["30", "11", "56", "25"], "correct_answer": 0},
            {"question": "7 × 8 = ?", "options": ["54", "56", "64", "48"], "correct_answer": 1},
            {"question": "9 × 9 = ?", "options": ["18", "72", "81", "99"], "correct_answer": 2},
            {"question": "6 × 7 = ?", "options": ["42", "36", "48", "13"], "correct_answer": 0},
            {"question": "8 × 4 = ?", "options": ["12", "24", "32", "36"], "correct_answer": 2},
        ],
    },
    "start_settings": {"time_limit": {"whole_quiz": 75}, "show_right_answer": False},
    "answers": {1: "12", 2: "30", 3: "56", 4: "81", 5: "42", 6: "32"},
    "scripted": {
        "w01-early": {},
        "w02-slow": {q: ("answer", None, 15) for q in range(1, 7)},
        "w03-wifi-at-end": {4: ("offline_at_quiz_time", 70, 25)},
        "w04-leaves": {3: ("leave", 3)},
        "w05-reloader": {q: ("reload", 3, None, 6) for q in range(1, 7)},
    },
    "agents": {
        "agent-wifi": {
            "device": "phone",
            "persona": (
                "You are a student with bad Wi-Fi. Twice during the quiz, run `offline 10` and keep going "
                "(click an answer and submit while offline)."
            ),
        },
        "agent-reloader": {
            "device": "desktop",
            "persona": "You are a nervous student who reloads the page (`reload`) a few times during the quiz.",
        },
    },
    "finish_after": 95,
    "max_seconds": 420,
}

SCENARIOS = {s["name"]: s for s in (FRACTIONS, TIME_EDGES, WHOLE_QUIZ)}
