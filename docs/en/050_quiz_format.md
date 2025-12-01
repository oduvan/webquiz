## Quiz File Format (quiz.yaml)

Tests in **WebQuiz** are stored in YAML format.
Each file contains a title, description (optional), and a list of questions.
You can create your own tests by placing them in the **`quizzes/`** folder.

---

### File Structure

The basic structure of a test file looks like this:

```
title: "Test Title"
description: "Test description (optional)"
show_right_answer: false
randomize_questions: false  # true for randomized question order for each student
questions:
  - question: "Question text"
    options: ["Option 1", "Option 2", "Option 3"]
    correct_answer: 0
```

---

### Main Test Parameters

#### `title` (required)

The test title displayed in the web interface and admin panel.

```
title: "Math Test"
```

---

#### `description` (optional)

A short description of the test. May contain information about the topic, difficulty, or other details.

```
description: "Basic arithmetic operations for 5th grade students"
```

---

#### `show_right_answer` (optional)

Determines whether to show the user the correct answer after submitting their choice, as well as the behavior for progressing to the next question.

- **`true`** (default) — after answering, the user sees visual feedback (green/red colors), the correct answer, and must click the **"Continue"** button to proceed to the next question
- **`false`** — the user **does not see** the correct answer, there is no visual feedback, and **the quiz automatically advances to the next question** immediately after submitting the answer (no button click needed)

```
show_right_answer: false  # Automatic progression to the next question
```

> **Tip:** Using `show_right_answer: false` creates a fast, seamless quiz-taking experience without interruptions, which is useful for quick surveys or tests where students should not see correct answers during the testing process.

---

#### `show_answers_on_completion` (optional)

Determines whether to show correct answers after **all** students complete the quiz. Works in combination with `show_right_answer: false`.

- **`true`** — correct answers are dynamically revealed only after all students finish the quiz
- **`false`** (default) — correct answers are never shown (if `show_right_answer: false`)

```
show_right_answer: false            # Hide answers during quiz
show_answers_on_completion: true    # Reveal after all complete
```

**How it works:**

1. During the quiz, students **do not see** correct answers
2. After completing the quiz, students see their results but **without correct answers**
3. Students see a message: _"Correct answers will be available after all students complete. Reload the page later."_
4. Once **all registered students** finish the quiz, correct answers become visible
5. If a new student registers later, answers are hidden again until they complete

> **Tip:** Using `show_answers_on_completion: true` is useful for group learning environments where you want students to discuss answers together after everyone has completed the quiz independently.

> ⚠️ **Important:** If approval mode is enabled (`registration.approve: true`), only **approved** students are counted. Students waiting for approval do not affect answer visibility.

---

#### `randomize_questions` (optional)

Determines whether each student receives a unique randomized question order. This is useful for preventing cheating and ensuring fair testing.

- **`true`** — each student receives a unique randomized question order that persists throughout the entire session
- **`false`** (default) — questions are displayed in the order defined in the YAML file

```
randomize_questions: true  # Each student gets a unique question order
```

> **Tip:** Using `randomize_questions: true` helps ensure fair testing, as students sitting next to each other will receive questions in different orders. The question order is generated server-side during student registration and persists throughout the entire session, even after page reloads.

---

### `questions` Section

The `questions` section contains a list of test questions.
Each question is a separate list item with its own parameters.

---

#### Basic Single-Choice Question

The simplest form of question with text, answer options, and the correct answer index:

```
- question: "What is 2 + 2?"
  options: ["3", "4", "5", "6"]
  correct_answer: 1
```

- **question** — question text
- **options** — list of possible answers (array of strings)
- **correct_answer** — index of correct answer (starts from 0)

In this example, the correct answer is `"4"` (index 1).

---

#### Multiple Correct Answers Question

WebQuiz supports questions with multiple correct answers.
In this case, the user must select **all correct options**.

```
- question: "Which of these are programming languages?"
  options: ["Python", "HTML", "JavaScript", "CSS"]
  correct_answer: [0, 2]
```

In this example, the correct answers are `"Python"` (index 0) and `"JavaScript"` (index 2).

> ⚠️ **Important:** By default, the user must select **all correct answers** to get a positive result.

---

#### Question with Minimum Number of Correct Answers

If you want the question to be considered correct when selecting a **minimum number** of all correct answers, use the **`min_correct`** parameter:

```
- question: "Select at least 2 primary colors:"
  options: ["Red", "Green", "Blue", "Yellow"]
  correct_answer: [0, 2, 3]
  min_correct: 2
```

In this example:
- Correct answers: `"Red"` (0), `"Blue"` (2), `"Yellow"` (3)
- User must select **at least 2** of them
- If the user selects `"Red"` and `"Blue"`, the answer will be counted as correct

---

#### Question with Image

You can add an image to a question using the **`image`** parameter.
Images should be stored in the **`quizzes/imgs/`** folder.

```
- question: "What is the capital of Ukraine?"
  image: "/imgs/ukraine_map.png"
  options: ["Kyiv", "Lviv", "Odesa", "Kharkiv"]
  correct_answer: 0
```

The image path is specified relative to the web root (`/imgs/`).

---

#### Image-Only Question (Without Text)

If a question consists only of an image (e.g., "What is shown in the picture?"), you can **omit the `question` field**:

```
- image: "/imgs/coordinate_system.png"
  options: ["MGRS", "UTM", "UCS-2000", "WGS84"]
  correct_answer: 2
```

In this case, the user will see only the image and answer options.

---

#### Question with Image-Based Answer Options

Answer options can also be images.
To do this, instead of text in the `options` list, specify paths to images:

```
- question: "Which symbol indicates the correct answer?"
  options:
    - "/imgs/checkmark.png"
    - "/imgs/cross.png"
    - "/imgs/question.png"
  correct_answer: 0
```

---

#### Combined Question: Image + Text Options

You can combine an image in the question with text answer options:

```
- question: "What coordinate system is shown in the picture?"
  image: "/imgs/coordinate_grid.png"
  options: ["Cartesian", "Polar", "Cylindrical", "Spherical"]
  correct_answer: 1
```

---

#### Question with Downloadable File

You can add a downloadable file to a question using the **`file`** parameter.
Files should be stored in the **`quizzes/attach/`** folder.

```
- question: "Analyze the data from the file and find the average"
  file: "data.xlsx"
  options: ["42", "56", "78", "91"]
  correct_answer: 1
```

Students will see a download button next to the question text.
Clicking it will automatically download the file to the student's device.

---

#### Combined Question: Image + File

You can combine an image and a file in the same question:

```
- question: "Compare the diagram with the data in the file"
  image: "/imgs/diagram.png"
  file: "analysis.csv"
  options: ["Data matches", "Data differs", "Insufficient data"]
  correct_answer: 0
```

---

### Complete Test File Example

Below is an example of a complete test file with different types of questions:

```
title: "Comprehensive Test with Various Question Types"
description: "Example test demonstrating all formatting capabilities"
show_right_answer: true
show_answers_on_completion: false  # Show answers after all students complete
randomize_questions: false  # Set to true for randomized question order

questions:
  # Simple question with one correct option
  - question: "What is 5 × 3?"
    options: ["8", "12", "15", "18"]
    correct_answer: 2

  # Question with multiple correct answers
  - question: "Which of these are programming languages?"
    options: ["Python", "HTML", "JavaScript", "CSS", "Ruby"]
    correct_answer: [0, 2, 4]

  # Question with minimum number of correct answers
  - question: "Select at least 2 European capitals:"
    options: ["Paris", "New York", "London", "Tokyo", "Berlin"]
    correct_answer: [0, 2, 4]
    min_correct: 2

  # Question with image
  - question: "Which country is shown on the map?"
    image: "/imgs/france_map.png"
    options: ["Germany", "France", "Spain", "Italy"]
    correct_answer: 1

  # Image-only question (no text)
  - image: "/imgs/python_logo.png"
    options: ["Java", "Python", "Ruby", "JavaScript"]
    correct_answer: 1

  # Question with image-based answer options
  - question: "Which flag belongs to Ukraine?"
    options:
      - "/imgs/flag_poland.png"
      - "/imgs/flag_ukraine.png"
      - "/imgs/flag_russia.png"
    correct_answer: 1

  # Question with downloadable file
  - question: "Analyze the data from the spreadsheet"
    file: "sales_data.xlsx"
    options: ["Growth 15%", "Growth 25%", "Decline 10%"]
    correct_answer: 1
```

---

### Rules and Recommendations

#### Index Numbering

Indexes in `correct_answer` always start from **0**.

| Index | Answer Option |
|-------|---------------|
| 0     | First option  |
| 1     | Second option |
| 2     | Third option  |
| 3     | Fourth option |

---

#### Saving Images

All images should be stored in the **`quizzes/imgs/`** folder.
Image paths in the test file are specified as `/imgs/filename.png`.

Supported formats:
- PNG (.png)
- JPEG (.jpg, .jpeg)
- GIF (.gif)
- SVG (.svg)

---

#### File Encoding

Test files should be saved in **UTF-8** encoding to correctly display text in Ukrainian, Russian, and other languages with Cyrillic characters.

---

#### Syntax Validation

**Recommended method:** Use the **administrator web interface** to create and edit tests.
The admin panel automatically validates YAML syntax before saving the file and shows errors if any exist.

If you're editing files manually and the test doesn't load after editing, check:
- Correct indentation (YAML requires exact indentation)
- Quotes around text values with special characters
- Index correspondence in `correct_answer` to the number of options in `options`

---

### Creating a New Test

#### Through Admin Interface (Recommended)

1. Open the admin panel at `http://localhost:8080/admin/`
2. Enter the master key for access
3. Use the built-in editor to create a new test
4. The editor will automatically validate syntax before saving
5. If there are errors in the file, you'll see messages about them

#### Manually Through File System

1. Open the **`quizzes/`** folder in your WebQuiz working directory.
2. Create a new file with `.yaml` extension, for example `my_test.yaml`.
3. Fill the file according to the structure described above.
4. Save the file in UTF-8 encoding.
5. Restart the WebQuiz server or switch tests in the admin panel.

The new test will appear in the list of available tests in the **Administration** section.

---

### Editing Existing Tests

#### Through Admin Interface (Recommended)

1. Open the admin panel
2. Select a test to edit
3. Make changes in the built-in editor
4. Click "Save" — validation will happen automatically
5. If there are errors, they will be displayed on screen

#### Manually Through File System

1. Open the corresponding `.yaml` file in the **`quizzes/`** folder in a text editor.
2. Make the necessary changes.
3. Save the file.
4. In the admin panel, switch to a different test and then back to the edited one — changes will apply automatically.

> **Tip:** Use the **administrator web interface** to create and edit tests — it has built-in YAML validation and will warn you about errors before saving.

---

### Common Errors

#### Incorrect Indentation

YAML is sensitive to indentation. All elements at the same level must have the same indentation.

**Incorrect:**
```
questions:
- question: "Text"
   options: ["A", "B"]
  correct_answer: 0
```

**Correct:**
```
questions:
  - question: "Text"
    options: ["A", "B"]
    correct_answer: 0
```

---

#### Index Mismatch

If `correct_answer` specifies an index that doesn't exist in `options`, the test won't load.

**Incorrect:**
```
options: ["A", "B", "C"]
correct_answer: 3  # Index 3 doesn't exist (only 0, 1, 2)
```

**Correct:**
```
options: ["A", "B", "C"]
correct_answer: 2  # Index 2 = option "C"
```

---

#### Missing Quotes in Text with Special Characters

If question or option text contains special characters (`:`, `#`, `{`, `}`), it must be enclosed in quotes.

**Incorrect:**
```
question: What is 2:1?
```

**Correct:**
```
question: "What is 2:1?"
```

> **Tip:** The admin interface will automatically detect these errors and show them before saving the file.

---

### Additional Features

#### Downloading Tests Through Admin Interface

If the `config.yaml` configuration file has the **`quizzes`** section filled in, the administrator can download tests directly from the web interface.

Example section in `config.yaml`:

```
quizzes:
  - name: "Geography Test"
    download_path: "https://example.com/tests/geography.zip"
    folder: "geography/"
```

After downloading, the archive is automatically unpacked into the specified folder inside `quizzes/`.

---

#### Switching Between Tests

The administrator can switch the active test at any time through the **Administration** panel.
When changing tests:
- All active user sessions are reset
- Previous test results are saved in corresponding CSV files
- A new set of questions is loaded

---

### Real Test Examples

#### Math Test

```
title: "Basic Arithmetic"
description: "Test on arithmetic operations knowledge"

questions:
  - question: "What is 7 + 5?"
    options: ["10", "11", "12", "13"]
    correct_answer: 2

  - question: "What is 9 × 6?"
    options: ["45", "54", "63", "72"]
    correct_answer: 1

  - question: "What is 20 ÷ 4?"
    options: ["4", "5", "6", "8"]
    correct_answer: 1
```

---

#### Geography Test with Images

```
title: "Countries and Flags"
description: "Recognizing flags of world countries"

questions:
  - image: "/imgs/flag_france.png"
    options: ["Italy", "France", "Belgium", "Netherlands"]
    correct_answer: 1

  - image: "/imgs/flag_japan.png"
    options: ["China", "Korea", "Japan", "Vietnam"]
    correct_answer: 2

  - question: "What is the capital of Germany?"
    options: ["Munich", "Berlin", "Frankfurt", "Hamburg"]
    correct_answer: 1
```

---

#### Programming Test with Multiple Choice

```
title: "Programming Basics"
show_right_answer: true

questions:
  - question: "Which languages are object-oriented?"
    options: ["Python", "C", "Java", "Assembly", "C#"]
    correct_answer: [0, 2, 4]

  - question: "Which data structures are linear?"
    options: ["Array", "Tree", "List", "Graph", "Stack"]
    correct_answer: [0, 2, 4]
    min_correct: 2
```

---

### Summary

The YAML format for tests in **WebQuiz** allows:

✅ Creating questions with single and multiple choice
✅ Adding images to questions and answer options
✅ Setting minimum number of correct answers
✅ Showing or hiding correct answers after completion
✅ Randomizing question order for each student to prevent cheating
✅ Easily editing tests in web interface with automatic validation

**Recommendation:** Use the administrator web interface to create and edit tests — it automatically validates syntax and warns about errors!
