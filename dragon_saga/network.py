from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class NetworkError(RuntimeError):
    pass


@dataclass
class NetworkClient:
    base_url: str
    room_code: str
    name: str
    role: str = "player"
    character_id: str = ""
    owner_key: str = ""
    client_id: str = ""
    token: str = ""
    revision: int = 0
    members: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.base_url = self.base_url.rstrip("/")

    def _request(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
        request = Request(f"{self.base_url}/api/rooms/{self.room_code}/{path}", data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=3) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            try:
                detail = json.loads(exc.read().decode("utf-8")).get("error", str(exc))
            except Exception:
                detail = str(exc)
            error = NetworkError(detail)
            error.status = exc.code  # type: ignore[attr-defined]
            raise error from exc
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise NetworkError(f"Сервер недоступен: {exc}") from exc

    def connect(self) -> dict[str, Any]:
        result = self._request("POST", "session", {
            "name": self.name, "role": self.role, "character_id": self.character_id,
            "owner_key": self.owner_key, "client_id": self.client_id,
        })
        self.token = result["token"]
        self.owner_key = result.get("owner_key") or self.owner_key
        self.role = result.get("role", "player")
        self.character_id = result.get("character_id", "")
        self.revision = int(result.get("revision", 0))
        self.members = result.get("members", [])
        return result

    def pull(self) -> dict[str, Any]:
        result = self._request("GET", "state")
        self.revision = int(result.get("revision", self.revision))
        self.members = result.get("members", [])
        if result.get("state") and self.role == "player":
            self.character_id = result["state"].get("assigned_character_id", self.character_id)
        return result

    def push(self, state: dict[str, Any]) -> dict[str, Any]:
        result = self._request("POST", "state", {"base_revision": self.revision, "state": state})
        self.revision = int(result.get("revision", self.revision))
        return result

    def resolve_action(self, actor_id: str, target_id: str, action_id: str) -> dict[str, Any]:
        result = self._request("POST", "action", {
            "base_revision": self.revision, "actor_id": actor_id,
            "target_id": target_id, "action_id": action_id,
        })
        self.revision = int(result.get("revision", self.revision))
        return result

    def tactic(self, actor_id: str, operation: str, **parameters: Any) -> dict[str, Any]:
        payload = {"base_revision": self.revision, "actor_id": actor_id, "operation": operation, **parameters}
        result = self._request("POST", "tactic", payload)
        self.revision = int(result.get("revision", self.revision))
        if result.get("state") and self.role == "player":
            self.character_id = result["state"].get("assigned_character_id", self.character_id)
        return result

    def assign(self, client_id: str, character_id: str) -> dict[str, Any]:
        result = self._request("POST", "assignment", {"client_id": client_id, "character_id": character_id})
        self.revision = int(result.get("revision", self.revision))
        self.members = result.get("members", self.members)
        return result
