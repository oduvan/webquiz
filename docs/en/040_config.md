## Server Configuration File


### Section `server`

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

### Section `paths`

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
  - `default_0001.users.csv` — user data with registration fields, including total quiz completion time in `MM:SS` format (minutes:seconds).
  Both files can be opened in any spreadsheet editor (Excel, Google Sheets).

- **static_dir: "static"**
  Directory with static web files.
  The main file **index.html** is a service file that is generated or updated automatically.
  You don't need to edit it manually.

---

### Section `admin`

```
admin:
  master_key: a1
```

- **master_key** — access key to the administrative interface.
  If a key **is specified**, the administrator can open the control panel from any device on the network by entering this key.
  If a key **is not specified**, the admin panel will be accessible **only from local addresses** (for example, `127.0.0.1` or `localhost`), and in this case, entering a key **is not required**.

---

### Section `registration` (optional)

```
registration:
  approve: false
  username_label: "Ім'я користувача"
  fields:
    - Grade
    - School
```

This section defines how users register before taking quizzes.

- **approve**
  If set to `true`, the user will not be able to start the quiz immediately after filling out the form — their request will be added to a waiting list, and the administrator must approve it manually.
  If the value is `false`, the user can start the quiz immediately after registration.

- **username_label**
  Customizes the label text for the username input field in the registration form.
  Default: `"Ім'я користувача"` (Ukrainian for "Username").
  Usage examples:
  ```
  username_label: "Full Name"
  username_label: "Student ID"
  username_label: "Прізвище та ім'я"
  ```
  This label appears in both the registration form and the waiting for approval form.
  Supports special characters, emojis, and multilingual text.

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

### Section `quizzes` (optional)

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

---

### Section `tunnel` (optional)

**Option 1: Fetch config from server**
```
tunnel:
  server: "tunnel.example.com"
  public_key: "keys/id_ed25519.pub"
  private_key: "keys/id_ed25519"
  socket_name: "my-quiz-socket"  # Optional: Fixed socket name (default: random 6-8 chars)
  # Config will be fetched from https://tunnel.example.com/tunnel_config.yaml
```

**Option 2: Local config (bypasses server fetch)**
```
tunnel:
  server: "tunnel.example.com"
  public_key: "keys/id_ed25519.pub"
  private_key: "keys/id_ed25519"
  config:  # Optional: Provide locally to skip fetching from server
    username: "tunneluser"
    socket_directory: "/var/run/tunnels"
    base_url: "https://tunnel.example.com/tests"
```

The `tunnel` section allows you to configure an SSH tunnel for public access to your local server through an external tunnel server. This is useful for:
- Running quizzes from a local computer without port forwarding configuration
- Temporary public access without dedicated hosting
- Classroom environments where students connect from outside the local network

**Parameters:**

- **server** — domain name or IP address of the tunnel server (e.g., `"tunnel.example.com"`).
  This is the server that provides public access to your local WebQuiz instance.

- **public_key** — path to the SSH public key file.
  If the file doesn't exist, WebQuiz will automatically generate an ED25519 key pair.
  Example: `"keys/id_ed25519.pub"`

- **private_key** — path to the SSH private key file.
  Used for authentication on the tunnel server.
  Example: `"keys/id_ed25519"`

- **socket_name** (optional) — fixed socket name instead of random generation.
  Allows having a predictable URL for public access through the tunnel.
  If not specified, a random identifier of 6-8 characters is generated.
  Example: `"my-quiz-socket"`

- **config** (optional subsection) — local tunnel configuration.
  If provided, WebQuiz will use this configuration instead of fetching from the server.
  - **username** — SSH user for tunnel server connection
  - **socket_directory** — directory on server for Unix domain sockets
  - **base_url** — base URL for tunnel access (e.g., `"https://tunnel.example.com/tests"`)

**How it works:**

1. **Automatic key generation**: If keys are missing, WebQuiz automatically creates an ED25519 key pair without a passphrase.

2. **Admin panel control**: Open the administrative panel to view the tunnel status.

3. **Copy public key**: Copy the generated public key and add it to the `~/.ssh/authorized_keys` file on your tunnel server.

4. **Connect**: Click the "Connect" button in the admin panel to establish the tunnel.

5. **Public URL**: Once connected, a public URL will be displayed (e.g., `https://tunnel.example.com/tests/a3f7b2/`).

6. **Auto-reconnect**: If the connection drops, WebQuiz automatically attempts to restore it.

**Server requirements:**
- The tunnel server must support Unix domain socket forwarding
- The server must provide a `tunnel_config.yaml` endpoint at `https://[server]/tunnel_config.yaml` with the following parameters:
  ```yaml
  username: tunneluser
  socket_directory: /var/run/tunnels
  base_url: https://tunnel.example.com/tests
  ```

**Security notes:**
- SSH keys are generated without a passphrase for automated connection
- The private key is stored with 600 permissions (owner only)
- Connection is admin-initiated (no auto-connect on startup)
- Connection status is displayed in real-time via WebSocket
