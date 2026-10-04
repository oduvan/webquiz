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
"""

import logging
import os
import re
import secrets
import tempfile
from datetime import datetime, timedelta
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple
from urllib.parse import quote

import httpx
from aiohttp import web

logger = logging.getLogger(__name__)

# File types that can be transferred and their allowed extensions
FILE_TYPES = {
    "quizzes": (".yaml", ".yml"),
    "logs": (".log",),
    "csv": (".csv",),
}

# Socket names become a URL path segment and a file name prefix
SERVER_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{40,100}$")

OFFER_LIFETIME = timedelta(minutes=30)
FINISHED_OFFER_LIFETIME = timedelta(hours=24)
MAX_FILES_PER_OFFER = 100
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
MAX_INCOMING_REQUESTS = 20
HTTP_TIMEOUT = 30.0


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
    return filename.lower().endswith(FILE_TYPES[file_type])


class TransferManager:
    """Keeps outgoing offers and incoming requests of one WebQuiz server"""

    def __init__(
        self,
        get_directories: Callable[[], Dict[str, str]],
        get_endpoint: Callable[[], Optional[Tuple[str, str]]],
        notify: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
    ):
        """Initialize transfer manager

        Args:
            get_directories: Returns {"quizzes": dir, "logs": dir, "csv": dir}
            get_endpoint: Returns (base_url, own socket name) while the tunnel
                is connected, otherwise None
            notify: Async function called with admin WebSocket messages
        """
        self.get_directories = get_directories
        self.get_endpoint = get_endpoint
        self.notify = notify
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

    @staticmethod
    def _request_view(request: Dict[str, Any]) -> Dict[str, Any]:
        """Incoming request without the token"""
        return {
            "id": request["id"],
            "from": request["from"],
            "files": request["files"],
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

        Args:
            target: Socket name of the receiving server
            files: List of {"type": "quizzes"|"logs"|"csv", "name": filename}

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
        seen = set()
        for item in self._parse_file_list(files):
            path = os.path.join(directories[item["type"]], item["name"])
            if not os.path.isfile(path):
                raise TransferError(f"File not found: {item['name']}", 404)
            if (item["type"], item["name"]) not in seen:
                seen.add((item["type"], item["name"]))
                entries.append({**item, "size": os.path.getsize(path)})

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

    def _target_file_name(self, file_type: str, name: str, sender: str) -> str:
        """Choose a file name that does not overwrite an existing file

        Quizzes keep their name when it is free. Logs and CSV files always get
        the sender name as prefix, because every server uses the same names.
        """
        directory = self.get_directories()[file_type]
        prefixed = f"{sender}_{name}"
        if len(prefixed) > 250:
            raise TransferError("File name is too long")
        candidates = [name, prefixed] if file_type == "quizzes" else [prefixed]
        for candidate in candidates:
            if not os.path.exists(os.path.join(directory, candidate)):
                return candidate

        stem, extension = os.path.splitext(prefixed)
        counter = 2
        while os.path.exists(os.path.join(directory, f"{stem}_{counter}{extension}")):
            counter += 1
        return f"{stem}_{counter}{extension}"

    async def _download_file(
        self, client: httpx.AsyncClient, sender_url: str, token: str, sender: str, entry: Dict[str, Any]
    ) -> str:
        """Download one file into its directory, return the saved file name"""
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
            saved_name = self._target_file_name(entry["type"], entry["name"], sender)
            os.replace(temp_path, os.path.join(directory, saved_name))
            return saved_name
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

    async def accept(self, request_id: Any) -> Dict[str, Any]:
        """Download all files of an incoming request

        Returns:
            {"from": name, "saved": [...], "failed": [...]}
        """
        request = self._take_pending(request_id)
        base_url, _ = self._require_endpoint()
        request["status"] = "downloading"
        sender_url = f"{base_url}/{request['from']}"
        saved, failed = [], []
        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                for entry in request["files"]:
                    try:
                        saved_name = await self._download_file(
                            client, sender_url, request["token"], request["from"], entry
                        )
                        saved.append({"type": entry["type"], "name": entry["name"], "saved_as": saved_name})
                    except TransferError as e:
                        failed.append({"type": entry["type"], "name": entry["name"], "error": e.message})
                await self._report_result(client, sender_url, request["token"], "accepted" if saved else "failed")
        finally:
            self.incoming.pop(request["id"], None)
            await self._notify({"type": "transfer_request_removed", "id": request["id"]})

        logger.info(f"File transfer from '{request['from']}': {len(saved)} saved, {len(failed)} failed")
        return {"from": request["from"], "saved": saved, "failed": failed}

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
