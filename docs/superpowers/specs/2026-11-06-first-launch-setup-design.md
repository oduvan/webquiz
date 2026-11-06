# First-launch setup — design

Date: 2026-11-06
Repositories: `oduvan/webquiz` (main work), `oduvan/webquiz-tunnel-server` (hosting the setup folders)

## Why

Teachers download the WebQuiz binary (or install it with pip) and run it. Today every new install starts
with the same example settings, and each teacher then has to fill in the same things by hand: registration
fields, the list of quizzes to download, the public access (tunnel) server, and so on. Every new install
also gets the same admin password, `a1`, from `server_config.yaml.example`.

We want a group of teachers (a school, an organization) to get ready-made settings with one short name.
The settings are prepared once, stored in the tunnel server's GitHub repository, and served by the tunnel
server. On the first launch WebQuiz asks for that name, downloads the settings and applies them.

The installer was considered and rejected: it exists only for Windows. The macOS and Linux zips, the
Windows portable zip, `pip install` and the Raspberry Pi never run it. A first-launch step covers all of
them with one piece of code.

## Goals

- On the first launch of a new install, the admin page leads the teacher through a short setup with two
  steps: a setup name, then an admin password.
- A setup name downloads a settings file from the tunnel server and applies it at once, with no restart.
- The teacher sees exactly what will change before anything changes.
- Every step can be skipped. Skipping keeps today's behaviour, with one exception: an install whose
  password step was skipped has no admin password (see "Admin password" below).
- The layout on the tunnel server is a folder per name, so more files can be added to a folder later
  (for example SSH public keys).

## Non-goals

- No language choice in the setup. The language can come from the downloaded settings file. Without a
  setup name, it stays at the default (`uk`).
- No full links (`https://…`) in the name field. Only names that are looked up on the tunnel server.
- No "run setup again" button in this version. To run it again, delete the config file or add the marker
  (below) back by hand.
- No ongoing sync. The settings are copied once. Later changes on the tunnel server do not reach installs
  that already ran the setup.
- No other files from the folder yet (only `webquiz.yaml`). The folder layout just leaves room for them.
- No change to the Windows installer.

## Anti-goals (would make it a failure even if it works)

- The setup blocks or hangs anything: a daemon, a systemd service, the Raspberry Pi, or the student pages.
- Existing installs see the setup page after updating WebQuiz.
- A downloaded file can set the admin password, change folders or the port, add trusted IPs, or choose
  where SSH key files are written.
- A setup name can point anywhere other than the setup folder on the tunnel server.

## Constraints

- Everything in a setup folder is public on the internet: anyone who guesses the name can download it.
  Private keys, passwords and other secrets must never go there. This matters for the later "SSH keys"
  extension: only public keys may be shared this way.
- The webquiz project rules apply (see `CLAUDE.md`): tests first, update `CLAUDE.md`, `README.md`,
  `docs/uk/` and `docs/en/`, and the setup page must work on phones (≤768px, `width: 100%; max-width: …`).
- The admin interface is in Ukrainian only today. The setup page follows the admin interface: Ukrainian
  text, with dark/light theme support like the other pages.
- All file writes use `flush()` + `os.fsync()`, like every other config write.

## Approaches considered

**Where the settings files live on the tunnel server**

- **Chosen: a folder per name under `setup/`.** `ansible/files/setup/<name>/webquiz.yaml` in the
  tunnel server repository is served at `https://webquiz.xyz/setup/<name>/webquiz.yaml`. The folder
  leaves room for more files later (Oleksandr's choice over one file per name). The `setup/` prefix
  keeps setup names apart from the per-user folders that already exist in `/var/www/html/<user>/`.
- One file per name (`setup/<name>.yaml`): simpler, but no room for extra files. Rejected by Oleksandr.
- Inside each tunnel user's folder (`users/<name>/webquiz.yaml` on `<name>.webquiz.xyz`): ties every
  setup name to a tunnel user, which needs an SSH user and an SSL certificate even for a school that
  never uses public access, plus a new nginx rule. Rejected.
- Straight from GitHub (`raw.githubusercontent.com`): the tunnel server already deploys on every push,
  so this gains nothing and ties WebQuiz to GitHub's address. Rejected.

**Where the setup page lives in WebQuiz**

- **Chosen: a separate `/setup/` page with its own template** (`webquiz/templates/setup.html`), like
  `files.html` and `live_stats.html`. While the marker is in the config, `/admin/` redirects to `/setup/`.
  Keeps the setup code small and testable on its own. (Claude's call; Oleksandr did not object.)
- A screen on top of `admin.html`: one page less, but `admin.html` already has about 4,000 lines.
  Rejected.

## Design

### 1. Tunnel server (`webquiz-tunnel-server`)

- New folder `ansible/files/setup/`. Each subfolder is a setup name and holds `webquiz.yaml`.
  Add a short `README.md` in `ansible/files/setup/` that explains the layout and says that everything
  here is public.
- New tasks in `ansible/playbook.yml` copy `ansible/files/setup/` to `{{ www_root }}/setup/`
  (owner `www-data`, files `0644`, folders `0755`).
- Folders and files deleted from the repository must also disappear from the server, otherwise an old
  name keeps working. How to do it is left to the builder (for example `synchronize` with `delete`,
  or finding and removing entries that are not in the repository).
- nginx needs no change: the root domain already serves `{{ www_root }}` with `try_files $uri $uri/ =404`,
  so a missing name returns 404.
- Pushing to `main` already deploys through GitHub Actions and `ansible-pull`, so adding a folder is
  enough to publish a new setup name.
- Add one example folder (for example `setup/example/webquiz.yaml`) so the end-to-end flow can be tried.

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

**Step 1: setup name**

```
Do you have a setup name?
Your school or organization may have given you one.
[ school1                ]
[ Skip ]            [ Check ]
```

- The name may only contain letters `a-z`, digits, `-` and `_` (lowercase; the field lowercases what
  is typed), 1 to 64 characters. Anything else is refused before any download.
- **Check** calls the server, which downloads `https://webquiz.xyz/setup/<name>/webquiz.yaml`. The
  server does the download, not the browser (no CORS problems, and it reuses `httpx` like
  `tunnel.py` does).
- Results:
  - **200 and valid:** the page shows a preview of what will be applied, with **Back** and **Apply**.
  - **404:** "No settings with this name." The teacher can try again or skip.
  - **No connection, timeout, other HTTP error:** "Could not connect to the settings server." Try again
    or skip.
  - **The file is not valid YAML, or nothing in it is allowed:** "The settings file is broken." The
    message names the problem so the person who prepared the file can fix it.
- **Apply** merges the allowed sections into the config file and applies them at once (see section 5).
  Then the page moves to step 2.
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
- If a master key is already active (from `--master-key` or `WEBQUIZ_MASTER_KEY`), this step is not
  shown, because the command-line value would override the file anyway.
- Both buttons remove the marker.

**Final screen**

```
✓ WebQuiz is ready
Students open: http://192.168.1.5:8080/
[ Open admin panel ]
```

The student address uses the same network address list the admin panel already shows.

### 5. What the downloaded file may change

The file has the same format as `webquiz.yaml`. Only these parts are used:

| Key | Notes |
|-----|-------|
| `language` | `uk` or `en` |
| `extra_answers_with_users_csv` | boolean |
| `registration` | `approve`, `username_label`, `fields`, `disabled_fields` |
| `quizzes` | the list of downloadable quizzes |
| `checker_templates` | the list of `{name, code}` |
| `tunnel.server` | the public access server |
| `tunnel.config` | the optional server config subsection (`username`, `socket_directory`, `base_url`) |

Everything else is ignored: `server`, `paths`, `admin` (password and trusted IPs), `tunnel.public_key`,
`tunnel.private_key` (these are file paths on the teacher's computer), `tunnel.socket_name` (one shared
name would make every install of a school clash), and any unknown key. The preview lists the ignored keys
as "not applied", so the person who prepared the file can see it.

The allowed part is checked with the existing config validator (`_validate_config_data`) before the
preview is shown. Applying goes through the same merge-and-reload path as the config form
(`PUT /api/admin/config` with `{data: …}`): round-trip merge with `ruamel.yaml`, validation, write with
fsync, hot-reload, and rollback if applying fails. The builder should move that logic into a shared helper
and not call the HTTP handler from inside the server.

The preview should be shown in plain words (for example "Registration fields: Class, School"), not as raw
YAML. The exact wording is left to the builder.

### 6. API

All under `@admin_auth_required`. All return 409 when the marker is not present (setup already done).

- `GET /setup/` — the page (`@local_network_only`). If the marker is not present, it redirects to `/admin/`.
- `POST /api/admin/setup/check` `{name}` — validates the name, downloads the file, filters it, validates
  it, and returns `{applied: {...}, ignored: [...], preview: [...]}` or an error. It does not change
  anything.
- `POST /api/admin/setup/apply` `{name}` — downloads the file again, filters and validates it again,
  and applies it. It downloads again on purpose: the server does not keep anything between the two calls.
- `POST /api/admin/setup/finish` `{master_key?}` — sets the password if one is given and removes the
  marker. Returns the student addresses for the final screen.

### 7. Tests (written first)

- Marker: added by `create_default_config_file`, absent from configs written by others, removed by
  finish, kept when the browser leaves halfway.
- `/admin/` redirects to `/setup/` only while the marker is present; `/setup/` redirects back when it is
  not.
- Name validation: refuses `../x`, `a/b`, uppercase after lowercasing is fine, empty, too long, spaces.
- Check and apply with a fake settings server: 200, 404, timeout, broken YAML, forbidden keys ignored
  and listed, validator errors.
- Apply: settings are written, comments in the config survive, changes are active without a restart.
- Finish: password works at once for login from a non-trusted IP; skip leaves no master key.
- Access: a non-trusted IP without a master key cannot use the setup API.
- Example config no longer contains an active `master_key`.
- One Selenium test for the whole flow, including the phone width.
- The tests need a local fake for `https://webquiz.xyz/setup/…`. The base address should be a
  constant that tests can override (for example an environment variable such as
  `WEBQUIZ_SETUP_BASE_URL`). The exact mechanism is left to the builder.

### 8. Documentation

- `docs/en/020_first.md` and `docs/uk/020_first.md`: describe the setup steps. While there, fix the
  table of created files: it says `config.yaml` and `results/`, but the code creates `webquiz.yaml` and
  `data/`.
- `docs/en/040_config.md` and `docs/uk/040_config.md`: describe `setup_pending`, and that the example no
  longer has a default password.
- `README.md` and `CLAUDE.md` in `webquiz`: the new page, endpoints, marker and the list of allowed keys.
- `README.md` in `webquiz-tunnel-server`: how to add a setup name.

## Left to the builder

- How the Ansible task removes deleted setup folders.
- The exact wording on the page and in the preview.
- How tests point the download at a local fake server.
- How the shared merge-and-apply helper is split out of `admin_update_config`.
- The order of the work across the two repositories. The webquiz side can be built and tested
  against a fake server before the tunnel server side is deployed.
