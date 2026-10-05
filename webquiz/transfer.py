"""File transfer between WebQuiz servers through the SSH tunnel server

Servers connected to the same tunnel server (one SSH user, one socket
directory) reach each other at "{base_url}/{socket name}/". The transfer is
"ask first, then send":

1. Sender: the admin selects files and types the receiver's name. The sender
   keeps an outgoing offer with a random token and POSTs the file list and the
   token to the receiver (POST /api/transfer/offer).
2. Receiver: the request is shown to the admin, who accepts or rejects it.
3. On accept, the receiver downloads every file from the sender
   (GET /api/transfer/download/{token}/{type}/{filename}) and reports the
   result to the sender (POST /api/transfer/result).

The receiver downloads only from "{its own base_url}/{sender name}/", so files
can only come from a server connected to the same tunnel server. The token
protects the sender: only offered files are served, only with the token, and
only until the offer is finished or expired.

Images (quizzes/imgs/) and attachments (quizzes/attach/) used by an offered
quiz are added to the offer automatically.

For every incoming file the receiver shows its case (new file, the same file
already exists, a different file exists, or the file is used by the running
server) and the admin chooses an action: save, replace, rename or skip. Images
and attachments are saved first; if one gets a new name, the references in
the received quiz are updated.
"""

import hashlib
import logging
import os
import re
import secrets
import tempfile
from datetime import datetime, timedelta
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple
from urllib.parse import quote

import httpx
import yaml
from aiohttp import web
from ruamel.yaml import YAML as RuamelYAML

logger = logging.getLogger(__name__)

# File types that can be transferred and their allowed extensions (None: any)
FILE_TYPES = {
    "quizzes": (".yaml", ".yml"),
    "logs": (".log",),
    "csv": (".csv",),
    "images": (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".svg", ".webp"),
    "attachments": None,
}

# Files used by quizzes: sent together with the quizzes that reference them
MEDIA_TYPES = ("images", "attachments")
IMAGES_URL_PREFIX = "/imgs/"
ATTACHMENTS_URL_PREFIX = "/attach/"

# Socket names become a URL path segment and a file name prefix
SERVER_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{40,100}$")

OFFER_LIFETIME = timedelta(minutes=30)
FINISHED_OFFER_LIFETIME = timedelta(hours=24)
MAX_FILES_PER_OFFER = 100
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
MAX_INCOMING_REQUESTS = 20
HTTP_TIMEOUT = 30.0
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")

# Logs and CSV files have the same names on every server, so they get the sender name
PREFIXED_TYPES = ("logs", "csv")


class TransferError(Exception):
    """Transfer failure with a message for the admin and an HTTP status"""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


def is_valid_server_name(name: Any) -> bool:
    """Check that a name can be used as a socket name in URLs and file names"""
    return isinstance(name, str) and bool(SERVER_NAME_PATTERN.match(name)) and ".." not in name


def is_allowed_file(file_type: Any, filename: Any) -> bool:
    """Check that a file of this type and name may be sent or received

    Only plain file names (no paths, no hidden files, no characters that
    Windows does not allow) with the extension allowed for the type are
    accepted.
    """
    if file_type not in FILE_TYPES or not isinstance(filename, str):
        return False
    if not filename or len(filename) > 255 or filename.startswith("."):
        return False
    if any(ord(char) < 32 or char in '<>:"/\\|?*' for char in filename):
        return False
    extensions = FILE_TYPES[file_type]
    return extensions is None or filename.lower().endswith(extensions)


def file_sha256(path: str) -> str:
    """SHA-256 of a file's content as hex"""
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _media_file_name(file_type: str, value: Any) -> Optional[str]:
    """File name of the image or attachment that a quiz value points to

    Images are referenced as "/imgs/name.png" (in "image" and in "options"),
    attachments as "name.pdf" or "/attach/name.pdf" (in "file").
    """
    if not isinstance(value, str):
        return None
    if file_type == "images":
        if not value.startswith(IMAGES_URL_PREFIX):
            return None
        name = value[len(IMAGES_URL_PREFIX) :]
    else:
        name = value[len(ATTACHMENTS_URL_PREFIX) :] if value.startswith(ATTACHMENTS_URL_PREFIX) else value
    return name if is_allowed_file(file_type, name) else None


def _media_fields(quiz: Any):
    """Yield (container, key, file_type) for every quiz field that can point to a file"""
    questions = quiz.get("questions") if isinstance(quiz, dict) else None
    for question in questions if isinstance(questions, list) else []:
        if not isinstance(question, dict):
            continue
        if "image" in question:
            yield question, "image", "images"
        if "file" in question:
            yield question, "file", "attachments"
        options = question.get("options")
        if isinstance(options, list):
            for index in range(len(options)):
                yield options, index, "images"


def quiz_media_files(quiz_path: str) -> List[Tuple[str, str]]:
    """Images and attachments used by a quiz file

    Returns:
        List of (file type, file name), without duplicates
    """
    try:
        with open(quiz_path, encoding="utf-8") as f:
            quiz = yaml.safe_load(f)
    except Exception:
        return []
    found = []
    for container, key, file_type in _media_fields(quiz):
        name = _media_file_name(file_type, container[key])
        if name and (file_type, name) not in found:
            found.append((file_type, name))
    return found


def rewrite_quiz_media(quiz_path: str, renamed: Dict[Tuple[str, str], str]) -> bool:
    """Point quiz references to images and attachments that were saved under a new name

    Uses a round-trip YAML parser, so comments and formatting are kept.

    Args:
        quiz_path: Quiz file to change in place
        renamed: {(file type, original name): saved name}

    Returns:
        True if the file was changed
    """
    parser = RuamelYAML()
    parser.preserve_quotes = True
    try:
        with open(quiz_path, encoding="utf-8") as f:
            quiz = parser.load(f)
    except Exception as e:
        logger.warning(f"Cannot update file references in received quiz: {e}")
        return False

    changed = False
    for container, key, file_type in _media_fields(quiz):
        value = container[key]
        name = _media_file_name(file_type, value)
        new_name = renamed.get((file_type, name)) if name else None
        if new_name:
            container[key] = value[: len(value) - len(name)] + new_name
            changed = True
    if changed:
        with open(quiz_path, "w", encoding="utf-8") as f:
            parser.dump(quiz, f)
    return changed


class TransferManager:
    """Keeps outgoing offers and incoming requests of one WebQuiz server"""

    def __init__(
        self,
        get_directories: Callable[[], Dict[str, str]],
        get_endpoint: Callable[[], Optional[Tuple[str, str]]],
        notify: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
        get_files_in_use: Optional[Callable[[], List[Optional[str]]]] = None,
    ):
        """Initialize transfer manager

        Args:
            get_directories: Returns {"quizzes": dir, "logs": dir, "csv": dir,
                "images": dir, "attachments": dir}
            get_endpoint: Returns (base_url, own socket name) while the tunnel
                is connected, otherwise None
            notify: Async function called with admin WebSocket messages
            get_files_in_use: Returns paths the running server writes or uses
                (current log, CSV files, active quiz); they cannot be replaced
        """
        self.get_directories = get_directories
        self.get_endpoint = get_endpoint
        self.notify = notify
        self.get_files_in_use = get_files_in_use or (lambda: [])
        self.outgoing: Dict[str, Dict[str, Any]] = {}  # token -> offer
        self.incoming: Dict[str, Dict[str, Any]] = {}  # request id -> request

    async def _notify(self, message: Dict[str, Any]):
        if self.notify:
            try:
                await self.notify(message)
            except Exception as e:
                logger.error(f"Error sending transfer notification: {e}")

    def _require_endpoint(self) -> Tuple[str, str]:
        endpoint = self.get_endpoint()
        if not endpoint:
            raise TransferError("SSH tunnel is not connected", 409)
        return endpoint

    def _remove_expired(self):
        """Expire waiting offers and forget old requests"""
        now = datetime.now()
        for token, offer in list(self.outgoing.items()):
            age = now - offer["created"]
            if offer["status"] == "waiting" and age > OFFER_LIFETIME:
                offer["status"] = "expired"
            if offer["status"] != "waiting" and age > FINISHED_OFFER_LIFETIME:
                del self.outgoing[token]
        for request_id, request in list(self.incoming.items()):
            if request["status"] == "pending" and now - request["received"] > OFFER_LIFETIME:
                del self.incoming[request_id]

    @staticmethod
    def _offer_view(offer: Dict[str, Any]) -> Dict[str, Any]:
        """Outgoing offer without the token"""
        return {
            "id": offer["id"],
            "to": offer["to"],
            "files": offer["files"],
            "created": offer["created"].isoformat(),
            "status": offer["status"],
        }

    def _request_view(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Incoming request without the token, with the case and actions of every file"""
        files = []
        for entry, plan in zip(request["files"], self._plan_files(request)):
            files.append({"type": entry["type"], "name": entry["name"], "size": entry["size"], **plan})
        return {
            "id": request["id"],
            "from": request["from"],
            "files": files,
            "received": request["received"].isoformat(),
            "status": request["status"],
        }

    def list_incoming(self) -> List[Dict[str, Any]]:
        self._remove_expired()
        return [self._request_view(r) for r in self.incoming.values() if r["status"] == "pending"]

    def get_state(self) -> Dict[str, Any]:
        """State for the admin pages"""
        endpoint = self.get_endpoint()
        self._remove_expired()
        outgoing = sorted(self.outgoing.values(), key=lambda o: o["created"], reverse=True)
        return {
            "available": endpoint is not None,
            "name": endpoint[1] if endpoint else None,
            "outgoing": [self._offer_view(o) for o in outgoing],
            "incoming": self.list_incoming(),
        }

    @staticmethod
    def _parse_file_list(files: Any) -> List[Dict[str, Any]]:
        if not isinstance(files, list) or not files:
            raise TransferError("No files selected")
        if len(files) > MAX_FILES_PER_OFFER:
            raise TransferError(f"Too many files (maximum {MAX_FILES_PER_OFFER})")
        result = []
        for item in files:
            file_type = item.get("type") if isinstance(item, dict) else None
            name = item.get("name") if isinstance(item, dict) else None
            if not is_allowed_file(file_type, name):
                raise TransferError(f"This file cannot be transferred: {name}")
            result.append({"type": file_type, "name": name})
        return result

    @staticmethod
    def _response_error(response: httpx.Response) -> str:
        try:
            return str(response.json().get("error") or response.status_code)
        except Exception:
            return f"HTTP {response.status_code}"

    # ----- Sender side -----

    async def send_offer(self, target: Any, files: Any) -> Dict[str, Any]:
        """Offer files to another server

        Images and attachments used by offered quizzes are added automatically.

        Args:
            target: Socket name of the receiving server
            files: List of {"type": "quizzes"|"logs"|"csv"|..., "name": filename}

        Returns:
            Outgoing offer view
        """
        base_url, own_name = self._require_endpoint()
        if not is_valid_server_name(target):
            raise TransferError("Invalid server name. Use letters, digits, '-', '_' and '.'")
        if target == own_name:
            raise TransferError("This is the name of this server")

        directories = self.get_directories()
        entries = []
        for item in self._parse_file_list(files):
            path = os.path.join(directories[item["type"]], item["name"])
            if not os.path.isfile(path):
                raise TransferError(f"File not found: {item['name']}", 404)
            entries.append({**item, "path": path})

        # Files used by the quizzes; a missing file is skipped (the quiz shows it as broken anyway)
        quizzes = [entry for entry in entries if entry["type"] == "quizzes"]
        for quiz in quizzes:
            for file_type, name in quiz_media_files(os.path.join(directories["quizzes"], quiz["name"])):
                path = os.path.join(directories[file_type], name)
                if os.path.isfile(path):
                    entries.append({"type": file_type, "name": name, "path": path})

        unique = {}
        for entry in entries:
            unique.setdefault((entry["type"], entry["name"]), entry)
        if len(unique) > MAX_FILES_PER_OFFER:
            raise TransferError(f"Too many files with images and attachments (maximum {MAX_FILES_PER_OFFER})")
        # The checksum lets the receiver see if it already has the same file
        entries = [
            {
                "type": entry["type"],
                "name": entry["name"],
                "size": os.path.getsize(entry["path"]),
                "sha256": file_sha256(entry["path"]),
            }
            for entry in unique.values()
        ]

        self._remove_expired()
        token = secrets.token_urlsafe(32)
        offer = {
            "id": secrets.token_hex(8),
            "token": token,
            "to": target,
            "files": entries,
            "created": datetime.now(),
            "status": "waiting",
        }
        # Register before sending: the receiver may download right after accepting
        self.outgoing[token] = offer

        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                response = await client.post(
                    f"{base_url}/{target}/api/transfer/offer",
                    json={"from": own_name, "token": token, "files": entries},
                )
        except httpx.HTTPError as e:
            del self.outgoing[token]
            raise TransferError(f"Cannot reach the tunnel server: {e}", 502)

        if response.status_code >= 400:
            del self.outgoing[token]
            if response.status_code in (502, 503, 504):
                raise TransferError(f"Server '{target}' is not online", 404)
            if response.status_code in (404, 405):
                raise TransferError(f"Server '{target}' does not support file transfer. Update WebQuiz there", 404)
            raise TransferError(f"Server '{target}' refused the request: {self._response_error(response)}", 502)

        logger.info(f"Offered {len(entries)} file(s) to '{target}'")
        return self._offer_view(offer)

    def _find_waiting_offer(self, token: Any) -> Optional[Dict[str, Any]]:
        if not isinstance(token, str):
            return None
        self._remove_expired()
        offer = self.outgoing.get(token)
        if not offer or offer["status"] != "waiting":
            return None
        return offer

    async def handle_download(self, request: web.Request) -> web.StreamResponse:
        """Public endpoint: serve one offered file to the receiver"""
        file_type = request.match_info["type"]
        filename = request.match_info["filename"]
        offer = self._find_waiting_offer(request.match_info["token"])
        offered = offer and any(f["type"] == file_type and f["name"] == filename for f in offer["files"])
        if not offered or not is_allowed_file(file_type, filename):
            return web.json_response({"error": "Not found"}, status=404)

        path = os.path.join(self.get_directories()[file_type], filename)
        if not os.path.isfile(path):
            return web.json_response({"error": "Not found"}, status=404)
        return web.FileResponse(path, headers={"Content-Type": "application/octet-stream"})

    async def handle_result(self, request: web.Request) -> web.Response:
        """Public endpoint: the receiver reports accept / reject"""
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"error": "Invalid JSON"}, status=400)
        if not isinstance(data, dict) or data.get("status") not in ("accepted", "rejected", "failed"):
            return web.json_response({"error": "Invalid status"}, status=400)

        offer = self._find_waiting_offer(data.get("token"))
        if not offer:
            return web.json_response({"error": "Not found"}, status=404)

        offer["status"] = data["status"]
        logger.info(f"File transfer to '{offer['to']}': {offer['status']}")
        await self._notify({"type": "transfer_result", "offer": self._offer_view(offer)})
        return web.json_response({"success": True})

    # ----- Receiver side -----

    def add_incoming(self, data: Any) -> Dict[str, Any]:
        """Validate and store an offer from another server"""
        _, own_name = self._require_endpoint()
        if not isinstance(data, dict):
            raise TransferError("Invalid request")
        sender = data.get("from")
        token = data.get("token")
        if not is_valid_server_name(sender) or sender == own_name:
            raise TransferError("Invalid sender name")
        if not isinstance(token, str) or not TOKEN_PATTERN.match(token):
            raise TransferError("Invalid token")

        entries = self._parse_file_list(data.get("files"))
        for entry, item in zip(entries, data["files"]):
            size = item.get("size")
            entry["size"] = size if isinstance(size, int) and not isinstance(size, bool) and size >= 0 else 0
            checksum = item.get("sha256")
            entry["sha256"] = checksum if isinstance(checksum, str) and SHA256_PATTERN.match(checksum) else None

        self._remove_expired()
        if len(self.incoming) >= MAX_INCOMING_REQUESTS:
            raise TransferError("Too many waiting requests on this server", 429)

        request = {
            "id": secrets.token_hex(8),
            "from": sender,
            "token": token,
            "files": entries,
            "received": datetime.now(),
            "status": "pending",
        }
        self.incoming[request["id"]] = request
        return request

    async def handle_offer(self, request: web.Request) -> web.Response:
        """Public endpoint: another server offers files"""
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"error": "Invalid JSON"}, status=400)
        try:
            incoming = self.add_incoming(data)
        except TransferError as e:
            return web.json_response({"error": e.message}, status=e.status)

        logger.info(f"File transfer request from '{incoming['from']}': {len(incoming['files'])} file(s)")
        await self._notify({"type": "transfer_request", "request": self._request_view(incoming)})
        return web.json_response({"success": True}, status=202)

    def _is_in_use(self, path: str) -> bool:
        in_use = {os.path.abspath(p) for p in self.get_files_in_use() if p}
        return os.path.abspath(path) in in_use

    @staticmethod
    def _free_name(directory: str, name: str, sender: str, taken: set) -> str:
        """First name for a renamed file that is not used yet: "{sender}_{name}", then "_2", "_3", ..."""
        prefixed = name if name.startswith(f"{sender}_") else f"{sender}_{name}"
        stem, extension = os.path.splitext(prefixed)
        candidate = prefixed
        counter = 2
        while candidate in taken or os.path.exists(os.path.join(directory, candidate)):
            candidate = f"{stem}_{counter}{extension}"
            counter += 1
        return candidate

    def _plan_files(self, request: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Case, possible actions, default action and suggested new name of every incoming file

        Cases:
            new        - no file with this name: save (default), rename, skip
            same       - a file with the same content exists: skip (default), replace, rename
            different  - another file with this name exists: rename (default), replace, skip
            in_use     - the running server uses this file: rename (default), skip
        """
        directories = self.get_directories()
        sender = request["from"]
        targets = [
            f"{sender}_{entry['name']}" if entry["type"] in PREFIXED_TYPES else entry["name"]
            for entry in request["files"]
        ]
        taken = {(entry["type"], target) for entry, target in zip(request["files"], targets)}

        plans = []
        for entry, target in zip(request["files"], targets):
            directory = directories[entry["type"]]
            path = os.path.join(directory, target)
            if not os.path.exists(path):
                case, actions, default = "new", ["save", "rename", "skip"], "save"
            elif not os.path.isfile(path) or self._is_in_use(path):
                case, actions, default = "in_use", ["rename", "skip"], "rename"
            elif entry.get("sha256") and file_sha256(path) == entry["sha256"]:
                case, actions, default = "same", ["replace", "rename", "skip"], "skip"
            else:
                case, actions, default = "different", ["replace", "rename", "skip"], "rename"
            same_type_taken = {name for file_type, name in taken if file_type == entry["type"]}
            plans.append(
                {
                    "target": target,
                    "case": case,
                    "actions": actions,
                    "default_action": default,
                    "suggested_name": self._free_name(directory, target, sender, same_type_taken),
                }
            )
        return plans

    def _build_plan(self, request: Dict[str, Any], choices: Any) -> List[Tuple[Dict[str, Any], str, Optional[str]]]:
        """Check the admin's choices against the current files

        Nothing is changed on disk here, so on an error the request stays open
        and the admin can choose again.

        Args:
            choices: List of {"type", "name", "action", "new_name"}; files
                without a choice get their default action

        Returns:
            List of (file entry, action, file name to save as or None for skip)
        """
        by_file = {}
        for choice in choices if isinstance(choices, list) else []:
            if isinstance(choice, dict):
                by_file[(choice.get("type"), choice.get("name"))] = choice

        directories = self.get_directories()
        plan, errors, chosen = [], [], set()
        for entry, file_plan in zip(request["files"], self._plan_files(request)):
            choice = by_file.get((entry["type"], entry["name"]), {})
            action = choice.get("action") or file_plan["default_action"]
            if action not in file_plan["actions"]:
                errors.append(f"{entry['name']}: '{action}' is not possible for this file now")
                continue
            if action == "skip":
                plan.append((entry, action, None))
                continue

            name = file_plan["target"]
            if action == "rename":
                name = choice.get("new_name") or file_plan["suggested_name"]
                if not is_allowed_file(entry["type"], name):
                    errors.append(f"{entry['name']}: '{name}' is not a valid name for this file")
                    continue
                if os.path.exists(os.path.join(directories[entry["type"]], name)):
                    errors.append(f"{entry['name']}: a file named '{name}' already exists")
                    continue
            if (entry["type"], name) in chosen:
                errors.append(f"'{name}' is chosen for two files")
                continue
            chosen.add((entry["type"], name))
            plan.append((entry, action, name))

        if errors:
            raise TransferError("; ".join(errors), 400)
        return plan

    async def _download_file(
        self,
        client: httpx.AsyncClient,
        sender_url: str,
        token: str,
        sender: str,
        entry: Dict[str, Any],
        save_as: str,
        overwrite: bool,
        renamed_media: Dict[Tuple[str, str], str],
    ):
        """Download one file and save it under the chosen name

        Args:
            save_as: File name in the directory of the file type
            overwrite: Replace an existing file with this name
            renamed_media: Images and attachments saved under a new name;
                references in a downloaded quiz are updated to them
        """
        url = f"{sender_url}/api/transfer/download/{token}/{entry['type']}/{quote(entry['name'])}"
        directory = self.get_directories()[entry["type"]]
        os.makedirs(directory, exist_ok=True)
        fd, temp_path = tempfile.mkstemp(prefix=".transfer-", suffix=".part", dir=directory)
        try:
            with os.fdopen(fd, "wb") as temp_file:
                async with client.stream("GET", url) as response:
                    if response.status_code in (502, 503, 504):
                        raise TransferError(f"Server '{sender}' is not online")
                    if response.status_code != 200:
                        raise TransferError("The sender does not offer this file anymore")
                    size = 0
                    async for chunk in response.aiter_bytes():
                        size += len(chunk)
                        if size > MAX_FILE_SIZE:
                            raise TransferError(f"File is larger than {MAX_FILE_SIZE // (1024 * 1024)} MB")
                        temp_file.write(chunk)
            if entry["type"] == "quizzes" and renamed_media:
                rewrite_quiz_media(temp_path, renamed_media)
            final_path = os.path.join(directory, save_as)
            if not overwrite and os.path.exists(final_path):
                raise TransferError(f"A file named '{save_as}' appeared meanwhile")
            if overwrite and self._is_in_use(final_path):
                raise TransferError(f"'{save_as}' is used by the running server")
            os.replace(temp_path, final_path)
        except httpx.HTTPError as e:
            raise TransferError(f"Download failed: {e}")
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    async def _report_result(self, client: httpx.AsyncClient, sender_url: str, token: str, status: str):
        try:
            await client.post(f"{sender_url}/api/transfer/result", json={"token": token, "status": status})
        except httpx.HTTPError as e:
            logger.warning(f"Could not report transfer result to sender: {e}")

    def _take_pending(self, request_id: Any) -> Dict[str, Any]:
        request = self.incoming.get(request_id) if isinstance(request_id, str) else None
        if not request or request["status"] != "pending":
            raise TransferError("Request not found or expired", 404)
        return request

    async def accept(self, request_id: Any, choices: Any = None) -> Dict[str, Any]:
        """Download the files of an incoming request as the admin chose

        Args:
            choices: List of {"type", "name", "action": "save"|"replace"|"rename"|"skip",
                "new_name"}; files without a choice get their default action

        Returns:
            {"from": name, "saved": [...], "skipped": [...], "failed": [...]}
        """
        request = self._take_pending(request_id)
        base_url, _ = self._require_endpoint()
        plan = self._build_plan(request, choices)
        request["status"] = "downloading"
        sender_url = f"{base_url}/{request['from']}"
        saved, skipped, failed = [], [], []
        renamed_media = {}
        # Images and attachments first, so quizzes can point to their saved names
        plan.sort(key=lambda item: item[0]["type"] not in MEDIA_TYPES)
        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                for entry, action, save_as in plan:
                    file_info = {"type": entry["type"], "name": entry["name"], "action": action}
                    if action == "skip":
                        skipped.append(file_info)
                        continue
                    try:
                        await self._download_file(
                            client,
                            sender_url,
                            request["token"],
                            request["from"],
                            entry,
                            save_as,
                            overwrite=action == "replace",
                            renamed_media=renamed_media,
                        )
                        if entry["type"] in MEDIA_TYPES and save_as != entry["name"]:
                            renamed_media[(entry["type"], entry["name"])] = save_as
                        saved.append({**file_info, "saved_as": save_as})
                    except TransferError as e:
                        failed.append({**file_info, "error": e.message})
                status = "failed" if failed and not saved else "accepted"
                await self._report_result(client, sender_url, request["token"], status)
        finally:
            self.incoming.pop(request["id"], None)
            await self._notify({"type": "transfer_request_removed", "id": request["id"]})

        logger.info(
            f"File transfer from '{request['from']}': "
            f"{len(saved)} saved, {len(skipped)} skipped, {len(failed)} failed"
        )
        return {"from": request["from"], "saved": saved, "skipped": skipped, "failed": failed}

    async def reject(self, request_id: Any):
        """Forget an incoming request and tell the sender"""
        request = self._take_pending(request_id)
        del self.incoming[request["id"]]
        endpoint = self.get_endpoint()
        if endpoint:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                await self._report_result(client, f"{endpoint[0]}/{request['from']}", request["token"], "rejected")
        logger.info(f"File transfer from '{request['from']}' rejected")
        await self._notify({"type": "transfer_request_removed", "id": request["id"]})
