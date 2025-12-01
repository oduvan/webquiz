## WebQuiz Administrative Interface

The **WebQuiz** administrative interface allows you to manage quizzes, view results, approve user requests, and work with files directly through the browser.
Access to the panel opens automatically if you connect from a local address (`127.0.0.1` or `localhost`), or using a **Master Key** if connecting from another device on the network.

---

### Main Admin Panel

![WebQuiz Admin Panel](../imgs/admin_advanced.png)

The main administrative panel page contains essential tools for managing quizzes, approving users, and downloading additional question sets.

#### Main Panel Elements

- **Available Quiz Files**
  The top of the page displays a list of all quizzes available in the `quizzes` folder.
  The current active quiz is marked as **(current)**.
  You can switch between quizzes or create new ones.

- **"Create New Quiz" Button**
  Opens the interface for creating a new quiz in visual mode.
  The new file will be added to the `quizzes` directory.

- **"Delete Quiz" Button**
  Allows you to delete the selected quiz from the file system.

- **Pending Approvals**
  This block appears if manual user approval is enabled in the configuration (`registration.approve: true`).
  It displays requests from users who have registered but have not yet been allowed to take the quiz.
  Each can be approved with the **"Approve"** button.

- **Available Quizzes for Download**
  If the `quizzes` section with links (`download_path`) is defined in the configuration, available quizzes that can be downloaded from external sources are shown here.
  The **"Download"** button automatically saves the archive and extracts it to the specified folder.

- **URL for Access from Other Devices**
  At the bottom of the panel, a link is displayed that other participants on the local network can use to connect to the quiz.
  Example: `http://10.10.100.104:8080/`.

---

### File Manager

![WebQuiz File Manager](../imgs/file_manager.png)

The File Manager is accessed via the **File Manager** link at the bottom of the admin panel.
It allows you to quickly view, download, and diagnose files created by the server.

#### Main Tabs

- **CSV Files** — list of quiz result files.
  Each item shows the file name, size, and last modification date.
  You can click **View** to see the contents directly in the browser, or **Download** to save the file locally.

- **Log Files** — server launch logs.
  Useful for finding technical errors or checking how the server performed in previous sessions.

- **Config** — the current configuration file `server_config.yaml` or `webquiz.yaml`, which can be viewed directly in the interface.

At the bottom of the page, the administrator's authorization status is displayed.
If you're connected from a local address or "trusted IP", the system automatically performs authentication.

---

### Quiz Editor

![Quiz Editor in Wizard Mode](../imgs/edit_quiz.png)

The Quiz Editor allows you to create or modify questions in the selected quiz.
Available in two modes: **Wizard** (visual editor) and **Text** (working directly with YAML code).

#### Main Editor Features

- **Quiz Name**
  Can be set in the "Quiz Name (optional)" field. If not specified, the system uses the standard file name.

- **Show Correct Answers**
  If this option is enabled, participants see the correct answers during the quiz and in the final summary table.

- **Questions**
  For each question, you can specify:
  - question text;
  - path to image (for example, `/imgs/diagram.png`);
  - question type — **single correct answer** or **multiple correct answers**;
  - list of answer options (text or images).

  If options are images, their paths start with `/imgs/` or `/static/`.

- **Editing Modes**
  - **Wizard Mode** — convenient for visually filling in fields and creating new questions.
  - **Text Mode** — opens the source YAML file for manual editing of the quiz structure.

---

### Quick Access

At the bottom of each admin interface page, there are convenient links:
- **← Back to Quiz** — return to the main quiz page.
- **Quiz Home** — go to the participant interface.
- **Live Stats** — page with live statistics (number of users, quiz status, active sessions).

---

### Package Version Check

The admin panel automatically checks if the WebQuiz package has been updated while the server is running.
If a new version is detected (for example, after updating via `pip install --upgrade webquiz`), a notification will appear at the bottom of the panel:

- **"New version installed (vX.Y)" + "Restart Required"** — means a new version of the package has been installed, but the server is still running the old version.

To apply the update, you need to restart the WebQuiz server.

---

This panel provides a complete **WebQuiz** management cycle — from creating quizzes and approving users to monitoring results and downloading reports.
It is designed for local operation, so all information remains on your network without being transmitted to the internet.
