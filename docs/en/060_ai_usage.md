## Using AI with WebQuiz

Artificial Intelligence (ChatGPT, Claude, and other tools) can significantly simplify working with WebQuiz — from analyzing test results to creating new quizzes based on existing materials.

In this section, you'll learn how to effectively use AI for:
- **Analyzing CSV files** with quiz results (with privacy considerations)
- **Generating quizzes** from text documents, Word files, and other formats

> ⚠️ **Important about privacy:** WebQuiz splits data into two files — one contains answers without names (anonymous), the other — user statistics. This allows safe AI analysis of results without disclosing students' personal data.

---

### When to Use AI

**AI is useful for:**
- Quick analysis of large volumes of answers
- Identifying questions that cause difficulties
- Generating new questions from educational materials
- Converting quizzes from other formats (Google Forms, Moodle)
- Finding patterns in student answers
- Creating multi-level quizzes

**Manual analysis is better for:**
- Small number of students (up to 10 people)
- When individual approach is needed
- Manual verification of specific questions
- Working with sensitive data

> **Tip:** To view CSV files, open **File Manager** → **CSV Files** tab (see [Administrative Interface](030_admin.md) for details).

---

### Understanding WebQuiz CSV Data Structure

WebQuiz stores quiz results in **two separate CSV files**:

1. **Answers file** — `{quiz_name}_{number}.csv`
2. **Users file** — `{quiz_name}_{number}.users.csv`

This separation ensures **anonymity during analysis** — you can share the answers file with AI without revealing student names.

---

#### Answers CSV File

**Structure:**

| user_id | question | selected_answer | correct_answer | is_correct | time_taken_seconds |
|---------|----------|-----------------|-----------------|-----------|-------------------|
| 123456 | What is 2+2? | 4 | 4 | True | 15.3 |
| 123456 | Capital of France | Paris | Paris | True | 8.7 |
| 654321 | What is 2+2? | 3 | 4 | False | 22.1 |

**Fields:**
- `user_id` — 6-digit unique identifier (not linked to name)
- `question` — question text
- `selected_answer` — student's answer
- `correct_answer` — correct answer
- `is_correct` — `True` or `False` (answer correctness)
- `time_taken_seconds` — time taken to answer (seconds)

> ✅ **Safe for AI:** This file **does not contain names** and can be safely uploaded to ChatGPT or Claude for analysis.

---

#### Users CSV File

**Structure:**

| user_id | username | email | group | registered_at | total_questions_asked | correct_answers | earned_points | total_points | total_time |
|---------|----------|-------|-------|---------------|-----------------------|-----------------|---------------|--------------|-----------|
| 123456 | John | john@example.com | 10-A | 2024-12-12T10:30:45 | 20 | 18 | 18 | 20 | 12:45 |
| 654321 | Mary | mary@example.com | 10-B | 2024-12-12T10:35:10 | 20 | 20 | 20 | 20 | 8:30 |

**Fields:**
- `user_id` — the same identifier as in answers file
- `username` — student's name
- **Custom fields** (email, group, etc.) — depends on `registration.fields` configuration
- `registered_at` — registration timestamp
- `total_questions_asked` — number of questions answered by student
- `correct_answers` — number of correct answers
- `earned_points` — points earned
- `total_points` — maximum possible points
- `total_time` — total quiz completion time (MM:SS format)

> ⚠️ **Contains personal data:** This file contains names and potentially other personal information. Be careful when uploading to AI services.

---

#### Combining Data via user_id

If you need **detailed analysis of specific students**, you can combine both files via the `user_id` column. However, for most AI analyses, the answers file alone (anonymous analysis) is sufficient.

> **Tip:** For most AI analyses, only the answers file (`{quiz}_0001.csv`) without the users file is sufficient — it's safer and simpler.

---

### AI Analysis of CSV Data

Below are practical scenarios for using AI to analyze quiz results.

---

#### Scenario 1: Identifying Difficult Questions

**Goal:** Find questions that students most frequently answer incorrectly.

**Prompt for ChatGPT/Claude:**

```
I have a CSV file with quiz results. File structure:
- user_id — student identifier
- question — question text
- selected_answer — student's answer
- correct_answer — correct answer
- is_correct — True (correct) or False (incorrect)
- time_taken_seconds — time taken to answer in seconds

Analyze the data and determine:
1. The 5 most difficult questions (highest error rate)
2. Percentage of correct answers for each question
3. Average time spent on each question

Here's the data:

[paste CSV content]
```

**Expected result:**

```
Question Difficulty Analysis:

1. "What is the capital of Australia?" — 35% correct (13/20 students were wrong)
   Average time: 28.5 seconds

2. "How many planets in the Solar System?" — 40% correct
   Average time: 18.2 seconds

3. "Who wrote 'Kobzar'?" — 55% correct
   Average time: 12.1 seconds

Recommendation: The first two questions should be reformulated or hints should be added.
```

**How to interpret:**
- **Low percentage of correct answers** (<50%) — question may be too difficult or unclear
- **Long time to answer** (>30 seconds) — students are uncertain about the answer
- **High error rate + short time** — possible problem with question wording

---

#### Scenario 2: Student Performance Analysis

**Goal:** Identify students who need additional help.

**Prompt for ChatGPT/Claude:**

```
I have a CSV file with student statistics. Structure:
- user_id — identifier
- username — student name
- total_questions_asked — number of questions
- correct_answers — number of correct answers
- earned_points — points earned
- total_points — maximum points
- total_time — time in MM:SS format

Analyze the data and determine:
1. Students with results below 60% (need additional help)
2. Students who spent very little time (<5 minutes) — possibly guessing randomly
3. Students with results >90% (excellent performers)
4. Group average result

Here's the data:

[paste users.csv content]
```

**Expected result:**

```
Performance Analysis:

📉 Need help (< 60%):
- John (45%, 9/20 points, time: 15:30)
- Peter (55%, 11/20 points, time: 8:45) — too little time, possibly guessing

⚡ Quick submissions (< 5 min):
- Peter (8:45) — 55% result, likely didn't read questions carefully

🏆 Excellent performers (> 90%):
- Mary (100%, 20/20 points, time: 12:30)
- Helen (95%, 19/20 points, time: 11:45)

📊 Group average result: 75% (15/20 points)
```

> ⚠️ **Warning:** The `users.csv` file contains student names. If you don't want to share names with AI, replace the `username` column with anonymous identifiers before uploading.

---

#### Scenario 3: Finding Answer Patterns

**Goal:** Identify common mistakes and misconceptions.

**Prompt for ChatGPT/Claude:**

```
I have a file with student answers. Analyze which incorrect answers students choose most frequently and explain possible reasons for errors.

CSV structure: user_id, question, selected_answer, correct_answer, is_correct, time_taken_seconds

Pay special attention to:
1. Popular incorrect answers (which options are chosen more frequently than others)
2. Possible misconceptions (why students think it's the correct answer)
3. Recommendations for the teacher (how to better explain the topic)

Here's the data:

[paste CSV]
```

**Expected result:**

```
Common Mistakes Analysis:

Question: "How many planets in the Solar System?"
- Incorrect answer "9" — chosen by 12 out of 20 students (60%)
  Possible reason: Outdated data (before 2006, Pluto was considered a planet)
  Recommendation: Explain why Pluto is no longer a planet

Question: "What is the capital of Australia?"
- Incorrect answer "Sydney" — chosen by 15 out of 20 students (75%)
  Possible reason: Sydney is the largest city, but the capital is Canberra
  Recommendation: Emphasize the difference between largest city and capital
```

---

#### Scenario 4: Question Quality Assessment

**Goal:** Determine if questions are too easy, difficult, or unclear.

**Prompt for ChatGPT/Claude:**

```
Analyze quiz question quality based on student answer data.

Assessment criteria:
- Too easy questions: >95% correct answers
- Too difficult questions: <30% correct answers
- Optimal questions: 50-80% correct answers
- Problematic questions: large time variation (SD > 15 seconds)

CSV structure: user_id, question, selected_answer, correct_answer, is_correct, time_taken_seconds

Here's the data:

[paste CSV]
```

**Expected result:**

```
Question Quality Assessment:

✅ Optimal questions (50-80% success):
- "Who wrote 'Kobzar'?" — 72% correct, average time 10s
- "How many days in February in a leap year?" — 68% correct

⚠️ Too easy (>95%):
- "What is 2+2?" — 100% correct, average time 5s
  Recommendation: Can be removed or made more difficult

🚨 Too difficult (<30%):
- "What is the capital of Kazakhstan?" — 15% correct
  Recommendation: Question may be too difficult for target audience

❓ Problematic (large time variation):
- "Calculate 15% of 240" — Time SD: 22 seconds
  Possible reason: Students with different levels of math skills
```

---

### Generating Quizzes with AI

AI can help create quizzes from scratch or convert existing materials to WebQuiz YAML format.

---

#### Creating Quiz from Text Documents

**Goal:** Convert lecture materials, Word documents, or text files into a WebQuiz quiz.

**Preparation:**
1. Copy text from Word document or PDF
2. Ensure the text covers key topics
3. Decide how many questions you need (recommended 10-20)

**Prompt for ChatGPT/Claude:**

```
Create a quiz in WebQuiz YAML format based on the following text.

Requirements:
- 15 multiple choice questions
- Each question has 4 answer options
- Use 0-based indexing for correct_answer (0 = first option)
- Add 'title' and 'description' fields
- Questions should test understanding, not just memorization
- Difficulty distribution: 5 easy, 7 medium, 3 difficult questions
- For difficult questions add points: 2 field

Text:

[paste lecture text, textbook content, etc.]

Output format:

title: "Quiz Title"
description: "Quiz Description"
questions:
  - question: "Question text"
    options:
      - "Option 1"
      - "Option 2"
      - "Option 3"
      - "Option 4"
    correct_answer: 0
  - question: "Difficult question"
    options:
      - "Option 1"
      - "Option 2"
      - "Option 3"
      - "Option 4"
    correct_answer: 1
    points: 2
```

**Example result:**

```yaml
title: "Ukrainian History Quiz"
description: "Key events of 19-20th century"
questions:
  - question: "Who wrote 'Kobzar'?"
    options:
      - "Taras Shevchenko"
      - "Ivan Franko"
      - "Lesya Ukrainka"
      - "Mykhailo Kotsiubynsky"
    correct_answer: 0

  - question: "In which year did the Battle of Grunwald take place?"
    options:
      - "1410"
      - "1510"
      - "1610"
      - "1710"
    correct_answer: 0
    points: 2
```

**After generation:**
1. Copy generated YAML to a file (e.g., `history_test.yaml`)
2. Place the file in the `quizzes/` folder
3. Validate the quiz via **File Manager** → **Quizzes** → **Validate** button
4. Try the quiz yourself before using with students

---

#### Converting from Other Quiz Formats

**Goal:** Convert existing quizzes from Google Forms, Moodle, and other platforms to WebQuiz.

---

##### Converting from Google Forms

**Step 1:** Export questions from Google Forms (copy text or export to text file)

**Step 2:** Use prompt:

```
I have a quiz from Google Forms in this format:

[paste Google Forms questions]

Convert it to WebQuiz YAML format:

Requirements:
- Use 0-based indexing for correct_answer
- Preserve all questions and answer options
- Add title based on topic
- If Google Forms had multiple correct answers, use type: multiple

Format:

title: "Quiz Title"
questions:
  - question: "Question text"
    options:
      - "Option 1"
      - "Option 2"
      - "Option 3"
      - "Option 4"
    correct_answer: 0
```

---

##### Converting from Moodle XML

**Prompt:**

```
I have a quiz in Moodle XML format. Convert it to WebQuiz YAML.

Consider:
- <question type="multichoice"> → single correct answer question
- <question type="multichoice" single="false"> → multiple choice (type: multiple)
- Fraction="100" indicates correct answer
- Use 0-based indexing for correct_answer

Here's the XML:

[paste Moodle XML]

Output format: WebQuiz YAML (as in example above)
```

---

### Prompt Engineering Tips

To get the best results from AI when generating quizzes:

1. **Be specific:** Indicate exact number of questions, difficulty level, topic

   ❌ Bad: "Create a math quiz"
   ✅ Good: "Create 10 algebra questions for 9th grade: equations, inequalities, functions"

2. **Always request YAML format:** Specify structure in prompt

   ```
   Output format: WebQuiz YAML
   title: "..."
   questions:
     - question: "..."
       options:
         - "..."
   ```

3. **Check indexing:** Remind AI about 0-based indexing

   ```
   correct_answer: 0  # first option
   correct_answer: 1  # second option
   ```

4. **Specify difficulty:** Ask AI to distribute questions by level

   ```
   Distribution: 30% easy, 50% medium, 20% difficult
   Difficult questions should have points: 2 or points: 3
   ```

5. **Request validation:** Ask AI to check syntax

   ```
   After generation, verify:
   - All correct_answer values are correct (0-based)
   - No YAML syntax errors
   - All questions have 4 options
   ```

---

> ⚠️ **Important:** AI can make mistakes in YAML syntax, factual correctness of questions, and answer indexing. Always verify generated quizzes yourself before using with students.

---

### Ready-to-Use Prompts Library

Below are ready-to-use prompts for different scenarios. Copy, paste into ChatGPT/Claude, and replace `[...]` with your data.

---

#### Prompt 1: Difficulty Distribution Analysis

```
Analyze the difficulty distribution of quiz questions.

For each question, determine:
- Percentage of correct answers
- Difficulty category: easy (>80%), medium (50-80%), difficult (<50%)
- Average time to answer

Data (CSV with columns: user_id, question, selected_answer, correct_answer, is_correct, time_taken_seconds):

[paste CSV]

Provide results as a table:

| Question | Success | Category | Avg Time |
|---------|---------|----------|----------|
| ...     | ...     | ...      | ...      |

Also calculate overall statistics:
- How many easy/medium/difficult questions
- Is the quiz balanced
```

---

#### Prompt 2: Identifying Students Needing Help

```
I have student statistics after a quiz.

Find students who:
1. Have results <50% (critically low level)
2. Have results 50-60% (need additional help)
3. Spent very little time (<8 minutes on 20 questions) — possibly guessing

For each group, provide:
- Student name (username)
- Result (correct_answers / total_questions_asked)
- Completion time (total_time)

Data (CSV with columns: user_id, username, total_questions_asked, correct_answers, earned_points, total_points, total_time):

[paste users.csv]
```

---

#### Prompt 3: Time Anomaly Detection

```
Analyze time spent by students on each question. Find:

1. Questions where students spend too much time (>30 seconds average) — possibly unclear wording
2. Questions students answer very quickly (<5 seconds) — possibly too easy or guessing
3. Questions with large time variation (standard deviation >15 seconds) — ambiguous question

Data (CSV: user_id, question, selected_answer, correct_answer, is_correct, time_taken_seconds):

[paste CSV]
```

---

#### Prompt 4: Cheating Detection

```
Analyze student answers for possible signs of cheating.

Look for:
1. Pairs of students with very similar errors (same incorrect answers on 5+ questions)
2. Students with identical answer sequences
3. Students with suspicious answer time synchronization (difference <2 seconds on same questions)

Consider: WebQuiz can randomize question order (randomize_questions: true), so check if matches are random.

Data (CSV: user_id, question, selected_answer, correct_answer, is_correct, time_taken_seconds):

[paste CSV]
```

---

#### Prompt 5: Summary Report Generation

```
Create a summary report on group quiz results.

Include:
1. Overall group statistics (average result, median, min/max)
2. Distribution by levels: excellent (>90%), good (70-90%), satisfactory (50-70%), unsatisfactory (<50%)
3. Top-5 most difficult questions
4. Top-3 students with best results
5. Students needing additional attention (<60%)
6. Recommendations for teacher

Data:

Answers CSV:
[paste answers.csv]

Users CSV:
[paste users.csv]
```

---

#### Prompt 6: Basic Quiz Generation

```
Create a WebQuiz YAML quiz with 10 multiple choice questions on topic: [TOPIC].

Requirements:
- Each question has 4 answer options
- 0-based indexing for correct_answer
- Difficulty distribution: 3 easy, 5 medium, 2 difficult
- Difficult questions with points: 2
- Add title and description

Content for quiz:

[paste text or specify topic]

Format:

title: "..."
description: "..."
questions:
  - question: "..."
    options:
      - "..."
      - "..."
      - "..."
      - "..."
    correct_answer: 0
```

---

#### Prompt 7: Converting from Google Forms

```
Convert a quiz from Google Forms to WebQuiz YAML.

Source (Google Forms format):

[paste Google Forms text]

Requirements:
- Use 0-based indexing
- Preserve original question order
- Add title based on form name
- If form had "Multiple answers", use type: multiple

Output format: WebQuiz YAML
```

---

#### Prompt 8: Multi-Level Quiz Generation

```
Create a quiz with three difficulty levels for topic: [TOPIC].

Structure:
- Level 1 (Basic): 5 questions, points: 1 each
- Level 2 (Intermediate): 5 questions, points: 2 each
- Level 3 (Advanced): 5 questions, points: 3 each

Total: 15 questions, maximum 30 points

Each question has:
- 4 answer options
- points field with appropriate value
- YAML comment about difficulty level

Content:

[paste text or topic]

Format: WebQuiz YAML
```

---

#### Prompt 9: Adding Text Questions with Checkers

```
Add 3 text questions with open-ended answers to existing quiz.

Requirements:
- Use checker field for answer validation
- default_value field for initial value in text field
- correct_value field to display correct answer
- points field (2-3 points for text questions)

Example format:

  - question: "What is the distance from Kyiv to Lviv?"
    checker: "return distance(answer) == 540"
    default_value: ""
    correct_value: "540 km"
    points: 2

Functions for checker:
- to_int(str) — convert to integer
- distance(str) — parse distance ("540km", "540 km", "540")
- direction_angle(str) — parse direction angle ("20-30" = 2030)

Existing quiz:

[paste quiz YAML]

Add 3 text questions to end of questions list.
```

---

### Advanced Workflows

---

#### Iterative Quiz Improvement

Process of continuous quiz improvement based on AI analysis:

**Step 1:** Conduct quiz with students

**Step 2:** Export CSV results via **File Manager** → **CSV Files**

**Step 3:** Use AI for difficulty analysis (Prompt 1)

**Step 4:** Identify problematic questions:
- Too easy (>95% correct) → make harder or remove
- Too difficult (<30% correct) → simplify or add hints
- Unclear (large time variation) → reformulate

**Step 5:** Ask AI to generate improved versions of problematic questions:

```
Improve the following questions based on analysis:

Question 1: "What is the capital of Australia?" (25% correct)
Problem: Students confuse it with Sydney
Task: Reformulate to add hint

Question 2: "What is 2+2?" (100% correct)
Problem: Too easy
Task: Make harder or replace with another

Output format: WebQuiz YAML (only these 2 questions)
```

**Step 6:** Replace problematic questions in YAML file via **File Manager** → **Quizzes** → **Edit** button

**Step 7:** Run quiz again and compare results

---

#### Bulk Quiz Creation

If you need to create quizzes from multiple documents:

**Step 1:** Prepare all documents (separate by topics)

**Step 2:** For each topic use the same prompt:

```
Create a WebQuiz quiz with 12 questions on topic: [TOPIC_1]

Requirements:
- 4 answer options
- 0-based correct_answer
- Distribution: 4 easy, 6 medium, 2 difficult (with points: 2)
- Add title: "[TOPIC_1]" and description

Content:

[paste topic 1 text]
```

**Step 3:** Save generated quizzes with logical names:
- `topic1_algebra.yaml`
- `topic2_geometry.yaml`
- `topic3_trigonometry.yaml`

**Step 4:** Place all files in `quizzes/` folder

**Step 5:** Switch between quizzes via **Admin Panel** → **Available Quiz Files**

---

#### Combining AI Tools

**ChatGPT:**
- Better for generating quizzes from texts
- Faster for simple format conversions
- Works well with structured data

**Claude:**
- Better for deep results analysis
- More detailed recommendations for teachers
- Better understanding of context in Ukrainian language

**Strategy:**
1. Use **ChatGPT** for quiz generation
2. Use **Claude** for CSV results analysis
3. For complex format conversions (Moodle XML) try both and compare

---

### Limitations and Best Practices

---

#### AI Limitations

⚠️ **AI can make mistakes:**
- Generate factually incorrect statements
- Create ambiguous wordings
- Incorrectly determine correct_answer
- Make syntax errors in YAML

⚠️ **AI doesn't replace teacher:**
- Always verify generated questions for factual correctness
- Consider your students' preparation level
- Adapt question difficulty for your audience

⚠️ **AI doesn't understand context:**
- May generate questions not suitable for your curriculum
- Doesn't know specifics of your students
- Doesn't account for previous topics you covered

---

#### Best Practices

✅ **Always verify:**
- Factual correctness of statements
- Correctness of right answers
- Logic of wrong options (they should be plausible)

✅ **Test before use:**
- Take the quiz yourself
- Have a colleague review
- Test on 1-2 students before launching for whole class

✅ **Keep backups:**
- Make copies of quizzes before editing
- Save original versions of successful quizzes
- Use versioning (e.g., `test_v1.yaml`, `test_v2.yaml`)

✅ **Be careful with personal data:**
- Don't upload `users.csv` to public AI without necessity
- Anonymize data before sharing with AI
- Follow your school/institution's policy on personal data

✅ **Use AI as assistant, not replacement:**
- AI speeds up work but doesn't replace professional expertise
- Combine AI generation with manual editing
- Use AI for analysis but interpret results yourself

---

### Security and Privacy

> ⚠️ **Critically important:** When working with student data, always follow your institution's privacy policy and legislation (GDPR, personal data protection laws).

**Safe actions:**
- ✅ Upload **answers.csv** (doesn't contain names) for AI analysis
- ✅ Anonymize `users.csv` before sharing (remove `username` column)
- ✅ Use AI to generate quizzes from public materials
- ✅ Analyze aggregated statistics without linking to specific students

**Unsafe actions:**
- ❌ Upload `users.csv` with names and personal data to public AI services without permission
- ❌ Share quiz results with third parties without consent
- ❌ Store personal data in ChatGPT prompts (they may be used for training)

**Recommendations:**
- Before using AI for student data analysis, check your school's policy
- If in doubt, use only anonymous data (answers.csv without users.csv)
- Consider using local AI models (Ollama, LM Studio) for sensitive data

---

Now you know how to effectively use AI with WebQuiz! Start with simple scenarios (difficulty analysis, basic quiz generation) and gradually move to more complex tasks.

> **Summary:** AI is a powerful tool for teachers, but it works best in combination with professional expertise. Use AI to automate routine tasks and analyze data, but always apply critical thinking and pedagogical experience when working with results.
