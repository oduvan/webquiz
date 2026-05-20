"""Translation strings for quiz interface and user-facing error messages."""

TRANSLATIONS = {
    "uk": {
        # Loading state
        "loading": "Завантаження...",
        "checking_data": "Перевірка ваших даних...",

        # Registration
        "register_title": "Зареєструйтеся для початку тесту",
        "register_button": "Зареєструватися",
        "please_enter_username": "Будь ласка, введіть ім'я користувача",
        "please_fill_field": 'Будь ласка, заповніть поле "{field}"',

        # Waiting for approval
        "waiting_title": "Очікування підтвердження",
        "waiting_description": "Ваша реєстрація очікує підтвердження адміністратором.",
        "waiting_hint": 'Ви можете змінити свої дані нижче та натиснути кнопку "Перевірити", щоб дізнатися чи вас підтвердили.',
        "save_changes": "💾 Зберегти зміни",
        "check_status": "🔄 Перевірити",
        "data_updated": "✓ Дані успішно оновлено!",
        "not_approved_yet": "Ви ще не підтверджені. Будь ласка, зачекайте.",

        # Quiz interface
        "question_n_of_m": "Питання {n} з {m}",
        "submit_answer": "Відправити відповідь",
        "continue_button": "Продовжити",
        "toggle_theme": "Перемкнути тему",
        "enter_answer_label": "✍️ Введіть вашу відповідь:",
        "enter_answer_placeholder": "Введіть відповідь...",
        "multiple_choice_hint": "📋 Можна обрати кілька відповідей",

        # Points (Ukrainian declension)
        "points_label": "Бали:",
        "points_2_4": "бали",
        "points_other": "балів",

        # Answer validation
        "please_enter_answer": "Будь ласка, введіть відповідь",
        "please_select_at_least_one": "Будь ласка, оберіть хоча б одну відповідь",
        "please_select_answer": "Будь ласка, оберіть відповідь",

        # Answer feedback (CSS)
        "correct_answer_label": "✓ Правильна відповідь",
        "your_answer_label": "✗ Ваша відповідь",
        "also_correct_label": "✓ Теж правильна відповідь",

        # Answer feedback (JS)
        "correct_answer_value": "✓ Правильна відповідь: ",

        # Error messages
        "error_prefix": "Помилка: ",
        "registration_error": "Помилка реєстрації",
        "update_error": "Помилка оновлення даних",
        "status_check_error": "Помилка перевірки статусу",
        "submit_error": "Помилка відправки відповіді: ",

        # Results
        "result_label": "Результат:",
        "result_correct_header": "Правильна: ",
        "question_header": "Питання",
        "your_answer_header": "Ваша відповідь",
        "correct_header": "Зараховано",
        "correct_header_alt": "Правильно",
        "points_header": "Бали",
        "unknown": "не відомо",
        "no_question_content": "Немає контенту питання",

        # Show answers on completion
        "answers_available_later": "ℹ️ Правильні відповіді будуть доступні після завершення тесту всіма учнями.",
        "reload_later": "Перезавантажте сторінку пізніше, щоб побачити правильні відповіді.",
        "reload_page": "🔄 Перезавантажити сторінку",

        # Server-side error messages (user-facing)
        "server_username_empty": "Ім'я користувача не може бути порожнім",
        "server_username_exists": "Ім'я користувача вже існує",
        "server_field_empty": 'Поле "{field}" не може бути порожнім',
        "server_user_not_found": "Користувача не знайдено",
        "server_all_answered": "Ви вже відповіли на всі питання",
        "server_question_order_error": "Помилка валідації порядку питань",
        "server_only_current_question": "Ви можете відповідати лише на поточне питання",
        "server_question_not_found": "Питання не знайдено",
        "server_access_denied_local": "Доступ заборонено: тільки для локальної мережі",
        "server_access_denied_ip": "Доступ заборонено: невірна IP адреса",
        "server_invalid_session": "Недійсний або відсутній сеанс",
        "server_invalid_master_key": "Недійсний або відсутній головний ключ",
        "server_update_not_found": "User not found",
        "server_update_after_approval": "Cannot update registration data after approval",
        "server_user_id_generation_failed": "Could not generate unique user ID",
    },
    "en": {
        # Loading state
        "loading": "Loading...",
        "checking_data": "Checking your data...",

        # Registration
        "register_title": "Register to start the quiz",
        "register_button": "Register",
        "please_enter_username": "Please enter your username",
        "please_fill_field": 'Please fill in the "{field}" field',

        # Waiting for approval
        "waiting_title": "Waiting for approval",
        "waiting_description": "Your registration is pending administrator approval.",
        "waiting_hint": 'You can edit your data below and click "Check" to see if you have been approved.',
        "save_changes": "💾 Save changes",
        "check_status": "🔄 Check",
        "data_updated": "✓ Data updated successfully!",
        "not_approved_yet": "You have not been approved yet. Please wait.",

        # Quiz interface
        "question_n_of_m": "Question {n} of {m}",
        "submit_answer": "Submit answer",
        "continue_button": "Continue",
        "toggle_theme": "Toggle theme",
        "enter_answer_label": "✍️ Enter your answer:",
        "enter_answer_placeholder": "Enter answer...",
        "multiple_choice_hint": "📋 You can select multiple answers",

        # Points
        "points_label": "Points:",
        "points_2_4": "points",
        "points_other": "points",

        # Answer validation
        "please_enter_answer": "Please enter an answer",
        "please_select_at_least_one": "Please select at least one answer",
        "please_select_answer": "Please select an answer",

        # Answer feedback (CSS)
        "correct_answer_label": "✓ Correct answer",
        "your_answer_label": "✗ Your answer",
        "also_correct_label": "✓ Also correct",

        # Answer feedback (JS)
        "correct_answer_value": "✓ Correct answer: ",

        # Error messages
        "error_prefix": "Error: ",
        "registration_error": "Registration error",
        "update_error": "Update error",
        "status_check_error": "Status check error",
        "submit_error": "Error submitting answer: ",

        # Results
        "result_label": "Result:",
        "result_correct_header": "Correct: ",
        "question_header": "Question",
        "your_answer_header": "Your answer",
        "correct_header": "Accepted",
        "correct_header_alt": "Correct",
        "points_header": "Points",
        "unknown": "unknown",
        "no_question_content": "No question content",

        # Show answers on completion
        "answers_available_later": "ℹ️ Correct answers will be available after all students complete the quiz.",
        "reload_later": "Reload the page later to see the correct answers.",
        "reload_page": "🔄 Reload page",

        # Server-side error messages (user-facing)
        "server_username_empty": "Username cannot be empty",
        "server_username_exists": "Username already exists",
        "server_field_empty": 'Field "{field}" cannot be empty',
        "server_user_not_found": "User not found",
        "server_all_answered": "You have already answered all questions",
        "server_question_order_error": "Question order validation error",
        "server_only_current_question": "You can only answer the current question",
        "server_question_not_found": "Question not found",
        "server_access_denied_local": "Access denied: local network only",
        "server_access_denied_ip": "Access denied: invalid IP address",
        "server_invalid_session": "Invalid or missing session",
        "server_invalid_master_key": "Invalid or missing master key",
        "server_update_not_found": "User not found",
        "server_update_after_approval": "Cannot update registration data after approval",
        "server_user_id_generation_failed": "Could not generate unique user ID",
    },
}


def get_translations(language: str) -> dict:
    """Get translations for the specified language.

    Args:
        language: Language code ("uk" or "en")

    Returns:
        Dictionary of translation strings for the specified language.
        Falls back to Ukrainian if language is not found.
    """
    return TRANSLATIONS.get(language, TRANSLATIONS["uk"])
