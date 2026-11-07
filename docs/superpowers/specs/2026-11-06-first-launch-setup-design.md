# First-launch setup — design

Date: 2026-11-06 (updated 2026-11-07)
Repositories: `oduvan/webquiz` (main work), `oduvan/webquiz-tunnel-server` (hosting the setup folders)

## Why

Teachers download the WebQuiz binary (or install it with pip) and run it. Today every new install starts
with the same example settings, and each teacher then has to fill in the same things by hand: registration
fields, the list of quizzes to download, the public access (tunnel) server, and so on. Every new install
also gets the same admin password, `a1`, from `server_config.yaml.example`.

We want a group of teachers (a school, an organization) to get ready-made settings by typing two short
answers: their tunnel server and a setup name. The settings are prepared once, stored in the tunnel
server's GitHub repository, and served by the tunnel server as plain files. On the first launch WebQuiz
asks for the two answers, downloads the settings, applies them, and also sets up the tunnel server
locally.

The installer was considered and rejected: it exists only for Windows. The macOS and Linux zips, the
Windows portable zip, `pip install` and the Raspberry Pi never run it. A first-launch step covers all of
them with one piece of code.

## Goals

- On the first launch of a new install, the admin page leads the teacher through a short setup with two
  steps: (1) the tunnel server and the setup name, (2) an admin password.
- The two answers download a settings file from that server and apply it at once, with no restart.
- The server the teacher typed is also saved as the local tunnel server, with local key paths. The SSH
  key is generated right away if it is missing, and the admin panel shows it as it does today.
- The teacher sees exactly what will change before anything changes.
- Every step can be skipped. Skipping keeps today's behaviour, with one exception: an install whose
  password step was skipped has no admin password (see "Step 2" below).
- The layout on the tunnel server is a folder per name, so more files can be added to a folder later.

## Non-goals

- **No registration of the SSH key on the tunnel server.** The generated public key still has to be
  added to `ansible/files/users/<user>/` in the tunnel server repository by hand before the tunnel can
  connect. The setup does not try to solve this.
- No language choice in the setup. The language can come from the downloaded settings file. Without it,
  it stays at the default (`uk`).
- No full links (`https://…`). The teacher types a server and a name, and WebQuiz builds the address.
- No "run setup again" button in this version. To run it again, delete the config file or add the marker
  (below) back by hand.
- No ongoing sync. The settings are copied once. Later changes on the tunnel server do not reach installs
  that already ran the setup.
- No other files from the folder yet (only `webquiz.yaml`). The folder layout just leaves room for them.
- No change to the Windows installer.

## Anti-goals (would make it a failure even if it works)

- The setup blocks or hangs anything: a daemon, a systemd service, the Raspberry Pi, or the student pages.
- Existing installs see the setup page after updating WebQuiz.
- A downloaded file can set the admin password, change folders or the port, add trusted IPs, choose
  where SSH key files are written, or change the tunnel settings.
- The setup name can point anywhere other than `/setup/<name>/webquiz.yaml` on the server the teacher
  typed.
- A wrong setup name looks like a success.

## Constraints

- Everything in a setup folder is public on the internet: anyone who guesses the name can download it.
  Private keys, passwords and other secrets must never go there. This matters for any later extension
  that adds more files to the folder: only public data may be shared this way.
- **The tunnel server name is the teacher's user subdomain, for example `demo.webquiz.xyz`.** The tunnel
  downloads `https://<server>/tunnel_config.yaml`, and that file exists only on user subdomains. Checked
  on the live server on 2026-11-07: `https://webquiz.xyz/tunnel_config.yaml` returns 404, and
  `https://demo.webquiz.xyz/tunnel_config.yaml` returns the config for user `demo`.
- **User subdomains currently answer 200 for every unknown path.** Checked on the live server:
  `https://demo.webquiz.xyz/setup/x/webquiz.yaml` returns 200 with the text "User subdomain: demo".
  Without an nginx change, a wrong setup name would not give 404. See section 1.
- The webquiz project rules apply (see `CLAUDE.md`): tests first, update `CLAUDE.md`, `README.md`,
  `docs/uk/` and `docs/en/`, and the setup page must work on phones (≤768px, `width: 100%; max-width: …`).
- The admin interface is in Ukrainian only today. The setup page follows the admin interface: Ukrainian
  text, with dark/light theme support like the other pages.
- All file writes use `flush()` + `os.fsync()`, like every other config write.

## Approaches considered

**Where the settings files live on the tunnel server**

- **Chosen: a shared folder per name under `setup/`.** `ansible/files/setup/<name>/webquiz.yaml` in the
  tunnel server repository is served at `https://<any user subdomain>/setup/<name>/webquiz.yaml` (and
  at `https://webquiz.xyz/setup/<name>/webquiz.yaml`). The folder leaves room for more files later
  (Oleksandr's choice over one file per name). The `setup/` prefix keeps setup names apart from the
  per-user folders that already exist in `/var/www/html/<user>/`.
- One file per name (`setup/<name>.yaml`): simpler, but no room for extra files. Rejected by Oleksandr.
- Inside each tunnel user's folder (`users/<name>/…`): ties every setup name to one tunnel user, so a
  school with several teachers (several tunnel users) would need a copy per teacher. Rejected.
- Straight from GitHub (`raw.githubusercontent.com`): the tunnel server already deploys on every push,
  so this gains nothing. Rejected.

**Where the setup page lives in WebQuiz**

- **Chosen: a separate `/setup/` page with its own template** (`webquiz/templates/setup.html`), like
  `files.html` and `live_stats.html`. While the marker is in the config, `/admin/` redirects to `/setup/`.
  (Claude's call; Oleksandr did not object.)
- A screen on top of `admin.html`: one page less, but `admin.html` already has about 4,000 lines.
  Rejected.

**What the setup does for public access (the tunnel)**

- **Chosen (Oleksandr): the tunnel server is only a host of files for the setup.** The teacher types the
  server. WebQuiz saves it as `tunnel.server` with local key paths, and the key is generated if missing.
  Registering the key on the tunnel server stays manual.
- Rejected: making the tunnel connect right after setup with extra work around the key (showing the key
  on the final screen with instructions, or registering it automatically).

## Design

### 1. Tunnel server (`webquiz-tunnel-server`)

- New folder `ansible/files/setup/`. Each subfolder is a setup name and holds `webquiz.yaml`.
  Add a short `README.md` in `ansible/files/setup/` that explains the layout, says that everything
  here is public, and says that teachers type their user subdomain as the server.
- New tasks in `ansible/playbook.yml` copy `ansible/files/setup/` to `{{ www_root }}/setup/`
  (owner `www-data`, files `0644`, folders `0755`).
- Folders and files deleted from the repository must also disappear from the server, otherwise an old
  name keeps working. How to do it is left to the builder.
- **nginx change on user subdomains:** `ansible/templates/nginx-user-subdomain.conf.j2` gets a
  `location /setup/` that serves `{{ www_root }}/setup/` and returns 404 for missing files. It goes in
  both the HTTP and the HTTPS server blocks, before the catch-all `location /` that returns 200. The
  root domain needs no change: it already serves `{{ www_root }}` with `try_files … =404`.
- The same setup folder is visible on every subdomain. The server answer decides which tunnel user the
  install belongs to; the name decides which settings it gets.
- Pushing to `main` already deploys through GitHub Actions and `ansible-pull`.
- Add one example folder (for example `setup/example/webquiz.yaml`) so the whole flow can be tried.

### 2. When the setup appears (`webquiz`)

- The marker is a top-level key in the config file: `setup_pending: true`, with a comment above it that
  explains it.
- The marker is added only when WebQuiz itself creates the config file from the example, which is
  `create_default_config_file()` in `webquiz/server.py`. It is called on a first run without a config
  file, and when `--config` points to a file that does not exist yet.
- Config files written by someone else never have the marker, so these never see the setup page:
  existing installs, the Raspberry Pi (Ansible writes its own `server.conf`), and the test fixtures
  (`tests/conftest.py` writes its own config).
- The config validator already accepts unknown top-level keys; it must also accept `setup_pending` as
  a boolean.
- While the marker is present, `GET /admin/` redirects to `/setup/`. Nothing else changes: the student
  page, live stats and the file manager keep working.
- The marker is removed (round-trip with `ruamel.yaml`, so comments survive) when the teacher finishes
  the last step, whether they used it or skipped it. If they close the browser halfway, the marker
  stays and the setup shows again next time.

### 3. Who can open the setup

- Same rules as the admin panel: `@local_network_only` for the page, `@admin_auth_required` for the API.
- The example config no longer sets `master_key: a1` (the line becomes a comment). On a new install
  there is no master key, so only trusted IPs (by default only `127.0.0.1`, the same computer) can run
  the setup. Someone else on the network cannot open it first and set the password.
- If a master key was given with `--master-key` or `WEBQUIZ_MASTER_KEY`, admins on other computers can
  log in as usual and run the setup from there (useful for headless pip installs).

### 4. The setup page

Ukrainian text, mobile-friendly, theme switcher like the other pages. Two steps, then a final screen.

**Step 1: server and setup name**

```
Do you have setup details?
Your school or organization may have given them to you.

Server:      [ demo.webquiz.xyz       ]
Setup name:  [ school1                ]

[ Skip ]                       [ Check ]
```

- **Server:** a host name or an IP address, lowercased. Only letters, digits, dots and hyphens (or a
  valid IP). HTTPS for host names, HTTP for IP addresses: the same rule `tunnel.py` already uses, so the
  builder should share that code.
- **Setup name:** only `a-z`, digits, `-` and `_`, 1 to 64 characters, lowercased.
- Both fields are needed for **Check**. **Skip** skips both. (Claude's call.)
- **Check** calls the WebQuiz server, which downloads `<protocol>://<server>/setup/<name>/webquiz.yaml`.
  The WebQuiz server does the download, not the browser (no CORS problems; it reuses `httpx` like
  `tunnel.py` does).
- Results:
  - **200 and valid:** the page shows a preview of what will be applied, with **Back** and **Apply**.
  - **404:** "No settings with this name on this server." The teacher can try again or skip.
  - **No connection, timeout, other HTTP error:** "Could not connect to the server." Try again or skip.
  - **The file is not a YAML mapping, or nothing in it is allowed:** "The settings file is broken." The
    message names the problem so the person who prepared the file can fix it.
- **Apply** does two things, then moves to step 2:
  1. Applies the allowed parts of the file (see section 5).
  2. Sets up the tunnel locally (see section 6).
- **Skip** moves to step 2 without changes.

**Step 2: admin password**

```
Password for the admin panel
Needed only to open the admin panel from other computers in your network.
[ ••••••••   ]
[ Skip ]            [ Finish ]
```

- **Finish** saves the password as `admin.master_key` and makes it active right away (set
  `self.master_key` directly; the normal config save does not change the master key without a restart).
- **Skip** leaves the install without a master key: the admin panel opens only from trusted IPs.
- If a master key is already active, from any source (`--master-key`, `WEBQUIZ_MASTER_KEY`, or the config
  file when the setup runs again), this step is not shown and the existing key is kept. (Claude's call.)
- Both buttons remove the marker.

**Final screen**

```
✓ WebQuiz is ready
Students open: http://192.168.1.5:8080/
[ Open admin panel ]
```

The student address uses the same network address list the admin panel already shows. The final screen
says nothing about the SSH key; the admin panel's tunnel section already shows the public key with a
Copy button (`admin.html`, `copyPublicKey()`).

### 5. What the downloaded file may change

The file has the same format as `webquiz.yaml`. Only these parts are used:

| Key | Notes |
|-----|-------|
| `language` | `uk` or `en` |
| `extra_answers_with_users_csv` | boolean |
| `registration` | `approve`, `username_label`, `fields`, `disabled_fields` |
| `quizzes` | the list of downloadable quizzes |
| `checker_templates` | the list of `{name, code}` |

Everything else is ignored: `server`, `paths`, `admin` (password and trusted IPs), the whole `tunnel`
section (the tunnel server comes from the teacher's answer, and key paths are local), and any unknown
key. The preview lists the ignored keys as "not applied", so the person who prepared the file can see it.

**How the file's settings replace what is already there (Claude's call).** Usually the config is fresh
from the example, so there is nothing to replace. But the setup can run on a config that already has
settings: when the marker is added back by hand, or when a teacher applies once, closes the browser
before step 2, and applies different details next time. In that case each allowed key the file sets
replaces that key in the config **whole**. Nothing from an earlier setup or from hand edits is mixed in.
Keys the file does not set are left alone. The preview says "replaces" for every key that already has a
value in the config.

This differs from the config form's merge, which sets values key by key inside a section. The shared
helper therefore needs a "replace" mode next to the form's "merge" mode.

The allowed part is checked with the existing config validator (`_validate_config_data`) before the
preview is shown. Applying goes through the same save-and-reload path as the config form
(`PUT /api/admin/config` with `{data: …}`): round-trip with `ruamel.yaml`, validation, write with fsync,
hot-reload, and rollback if applying fails. The builder should move that logic into a shared helper and
not call the HTTP handler from inside the server.

The preview should be shown in plain words (for example "Registration fields: Class, School"), not as raw
YAML. It also lists the tunnel change from section 6 ("Public access server: demo.webquiz.xyz"). The
exact wording is left to the builder.

### 6. Tunnel setup on Apply

In the same save as section 5:

- `tunnel.server` is set to the server the teacher typed.
- `tunnel.public_key` and `tunnel.private_key` are set to `keys/id_ed25519.pub` and `keys/id_ed25519`
  (the paths from the example comment), **only if they are not set already**. These paths are chosen by
  WebQuiz, never by the downloaded file. They are resolved next to the binary like today.
- `tunnel.config` is removed if present, because it would belong to an old server.
- `tunnel.socket_name` is left as it is.

After the save, WebQuiz calls the existing `initialize_tunnel()` (`webquiz/server.py`). It creates the
tunnel manager and calls `ensure_keys_exist()`, which generates the key pair if both files are missing.
It does not connect. (Claude's call: without this call, the key would only be generated on the next
start, because today `initialize_tunnel()` runs only at startup and `apply_config_changes()` never creates
a tunnel manager.) If a tunnel manager already exists (setup run again), disconnect it first and replace
it.

The tunnel can connect only after the public key is added on the tunnel server by hand (non-goal above).
Until then, **Connect** in the admin panel fails with the SSH error it shows today.

### 7. API

All under `@admin_auth_required`. All return 409 when the marker is not present (setup already done).

- `GET /setup/` — the page (`@local_network_only`). If the marker is not present, it redirects to `/admin/`.
- `POST /api/admin/setup/check` `{server, name}` — validates both, downloads the file, filters it,
  validates it, and returns `{applied: {...}, ignored: [...], preview: [...]}` or an error. It does not
  change anything.
- `POST /api/admin/setup/apply` `{server, name}` — downloads the file again, filters and validates it
  again, applies it, and sets up the tunnel (section 6). It downloads again on purpose: the server does
  not keep anything between the two calls.
- `POST /api/admin/setup/finish` `{master_key?}` — sets the password if one is given and removes the
  marker. Returns the student addresses for the final screen.

### 8. Tests (written first)

- Marker: added by `create_default_config_file`, absent from configs written by others, removed by
  finish, kept when the browser leaves halfway.
- `/admin/` redirects to `/setup/` only while the marker is present; `/setup/` redirects back when it is
  not.
- Validation: server (host names, IPs, refuses `a/b`, `a b`, `user@host`, ports and paths) and name
  (refuses `../x`, `a/b`, empty, too long, spaces; uppercase is lowercased).
- Check and apply with a fake settings server: 200, 404, timeout, a 200 that is not YAML (like the
  subdomain info page), forbidden keys ignored and listed, validator errors.
- Apply: settings are written, comments in the config survive, allowed keys are replaced whole, changes
  are active without a restart.
- Tunnel on apply: `tunnel.server` set, key paths set only when missing, `tunnel.config` removed, a key
  pair generated in a temporary folder, no connection attempted.
- Finish: password works at once for login from a non-trusted IP; skip leaves no master key; an
  existing key is kept.
- Access: a non-trusted IP without a master key cannot use the setup API.
- Example config no longer contains an active `master_key`.
- One Selenium test for the whole flow, including the phone width.
- The tests need a local fake server for the download. The protocol and base address should be
  overridable in tests (for example an environment variable). The exact mechanism is left to the
  builder.
- Tunnel server repository: run its existing checks (`validate.sh`) after the playbook and nginx changes.

### 9. Documentation

- `docs/en/020_first.md` and `docs/uk/020_first.md`: describe the setup steps. While there, fix the
  table of created files: it says `config.yaml` and `results/`, but the code creates `webquiz.yaml` and
  `data/`.
- `docs/en/040_config.md` and `docs/uk/040_config.md`: describe `setup_pending`, and that the example no
  longer has a default password.
- `README.md` and `CLAUDE.md` in `webquiz`: the new page, endpoints, marker, the list of allowed keys,
  and the tunnel setup on Apply.
- `README.md` in `webquiz-tunnel-server`: how to add a setup name, and that teachers type their user
  subdomain as the server.

## Left to the builder

- How the Ansible task removes deleted setup folders.
- The exact nginx `location` for `/setup/` on user subdomains.
- The exact wording on the page and in the preview.
- How tests point the download at a local fake server.
- How the shared save-and-apply helper is split out of `admin_update_config`.
- The order of the work across the two repositories. The webquiz side can be built and tested
  against a fake server before the tunnel server side is deployed.
