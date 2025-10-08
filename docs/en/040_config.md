# Server Configuration File


## Section `server`

```
server:
  host: "0.0.0.0"
  port: 8080
```

- **host** — determines which network interfaces the server accepts connections on.
  - `"127.0.0.1"` — the server will only be accessible from the same computer (locally).
  - `"0.0.0.0"` — the server will be accessible to all devices on the local network (via Wi-Fi or Ethernet).
  Use `"0.0.0.0"` if other devices on your local network will be connecting to the quiz.
- **port** — the port on which the server runs.
  By default, `8080` is used. If this port is occupied, you can change it to another, such as `8000`.

---

## Section `paths`

```
paths:
  quizzes_dir: "quizzes"
  logs_dir: "logs"
  csv_dir: "data"
  static_dir: "static"
```

The `paths` section defines the location of service folders. If the specified directories don't exist, they are created automatically on first launch.

- **quizzes_dir: "quizzes"**
  Directory for storing quizzes in YAML format.
  On first launch, an example quiz `default.yaml` is created here.
  It can also contain an **`imgs`** subfolder where images used in questions are stored.

- **logs_dir: "logs"**
  Contains server operation logs.
  These files record messages about launches, errors, or other events.
  Each new launch creates a new log, for example `0001.log`, `0002.log`.

- **csv_dir: "data"**
  Directory where quiz results are stored in CSV format.
  For each quiz, two files are created:
  - `default_0001.csv` — user answers without personal data;
  - `default_0001.users.csv` — user data with registration fields.
  Both files can be opened in any spreadsheet editor (Excel, Google Sheets).

- **static_dir: "static"**
  Directory with static web files.
  The main file **index.html** is a service file that is generated or updated automatically.
  You don't need to edit it manually.

---

## Section `admin`

```
admin:
  master_key: a1
```

- **master_key** — access key to the administrative interface.
  If a key **is specified**, the administrator can open the control panel from any device on the network by entering this key.
  If a key **is not specified**, the admin panel will be accessible **only from local addresses** (for example, `127.0.0.1` or `localhost`), and in this case, entering a key **is not required**.

---

## Section `registration` (optional)

```
registration:
  approve: false
  fields:
    - Grade
    - School
```

This section defines how users register before taking quizzes.

- **approve**
  If set to `true`, the user will not be able to start the quiz immediately after filling out the form — their request will be added to a waiting list, and the administrator must approve it manually.
  If the value is `false`, the user can start the quiz immediately after registration.

- **fields**
  Additional registration fields that appear in the form before starting the quiz.
  For example:
  ```
  fields:
    - Grade
    - School
    - City
  ```
  All collected data is automatically saved to the CSV results file.

---

## Section `quizzes` (optional)

```
quizzes:
  - name: "Basic Math Quiz"
    download_path: "https://example.com/quizzes/math.zip"
    folder: "math_questions/"
```

This section allows the administrator to download quizzes from external sources through the administrative interface.

- **name** — the name of the quiz that appears in the admin panel.
- **download_path** — link to an archive with the quiz (for example, `.zip`).
- **folder** — the folder where the archive contents will be extracted after download.
