from __future__ import annotations

import argparse
import copy
import json
import secrets
import threading
import time
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from .models import Campaign
from .rules import BattleEngine, RuleError

MAX_BODY = 256 * 1024 * 1024


@dataclass
class Session:
    token: str
    client_id: str
    name: str
    role: str
    character_id: str = ""
    touched: float = field(default_factory=time.time)


@dataclass
class Room:
    code: str
    owner_key: str = ""
    revision: int = 0
    state: dict[str, Any] | None = None
    sessions: dict[str, Session] = field(default_factory=dict)
    lock: threading.RLock = field(default_factory=threading.RLock)


ROOMS: dict[str, Room] = {}
ROOMS_LOCK = threading.RLock()


def _room(code: str) -> Room:
    clean = "".join(ch for ch in code.upper() if ch.isalnum() or ch in "-_")[:32]
    if not clean:
        raise ValueError("Нужен код комнаты")
    with ROOMS_LOCK:
        return ROOMS.setdefault(clean, Room(clean))


def _projection(character: dict[str, Any]) -> dict[str, Any]:
    visible = {
        "id", "name", "side", "armor_class", "hp", "max_hp", "temp_hp", "speed",
        "initiative_bonus", "conditions", "model_scale", "is_boss", "telegraph", "telegraph_dc",
    }
    return {key: copy.deepcopy(value) for key, value in character.items() if key in visible}


def state_for_session(room: Room, session: Session) -> dict[str, Any] | None:
    if room.state is None:
        return None
    if session.role == "gm":
        return copy.deepcopy(room.state)
    state = copy.deepcopy(room.state)
    positioned = set(state.get("battle", {}).get("positions", {}))
    filtered = []
    for character in state.get("characters", []):
        if character.get("id") == session.character_id:
            owned = copy.deepcopy(character)
            owned.pop("image_path", None); owned.pop("model_path", None)
            filtered.append(owned)
        elif character.get("id") in positioned and state.get("battle", {}).get("positions", {}).get(character.get("id")) != "reserve":
            filtered.append(_projection(character))
    state["characters"] = filtered
    state["assets"] = [{key: copy.deepcopy(asset.get(key, "")) for key in ("id", "name", "kind")} for asset in state.get("assets", [])]
    state["role"] = "player"
    state["assigned_character_id"] = session.character_id
    visible_ids = {character.get("id") for character in filtered}
    battle = state.setdefault("battle", {})
    battle["positions"] = {key: value for key, value in battle.get("positions", {}).items() if key in visible_ids}
    battle["initiative"] = [item for item in battle.get("initiative", []) if item.get("id") in visible_ids]
    battle["movement_left"] = {session.character_id: battle.get("movement_left", {}).get(session.character_id, 0)} if session.character_id else {}
    battle["turn_start_zone"] = {session.character_id: battle.get("turn_start_zone", {}).get(session.character_id, "reserve")} if session.character_id else {}
    battle["flags"] = {session.character_id: copy.deepcopy(battle.get("flags", {}).get(session.character_id, {}))} if session.character_id else {}
    if battle.get("target_id") not in visible_ids:
        battle["target_id"] = ""
    return state


def apply_player_state(room: Room, session: Session, incoming: dict[str, Any]) -> None:
    if room.state is None or not session.character_id:
        raise PermissionError("Игроку не назначен герой")
    old_char = next((x for x in room.state.get("characters", []) if x.get("id") == session.character_id), None)
    new_char = next((x for x in incoming.get("characters", []) if x.get("id") == session.character_id), None)
    if not old_char or not new_char:
        raise PermissionError("Назначенный герой отсутствует")
    # A player may only mutate their owned sheet's battle-facing fields.
    if "hp" in new_char:
        old_char["hp"] = max(0, min(int(new_char["hp"]), int(old_char.get("max_hp", 1))))
    if "temp_hp" in new_char:
        old_char["temp_hp"] = max(0, int(new_char["temp_hp"]))
    if "conditions" in new_char and isinstance(new_char["conditions"], list):
        old_char["conditions"] = [str(x)[:80] for x in new_char["conditions"][:20]]
    if "hit_dice_current" in new_char:
        old_char["hit_dice_current"] = max(0, min(int(new_char["hit_dice_current"]), int(old_char.get("hit_dice_max", 0))))
    incoming_resources = {x.get("id"): x for x in new_char.get("resources", []) if isinstance(x, dict)}
    for resource in old_char.get("resources", []):
        changed = incoming_resources.get(resource.get("id"))
        if changed and "current" in changed:
            resource["current"] = max(0, min(int(changed["current"]), int(resource.get("maximum", 0))))
    old_battle = room.state.setdefault("battle", {})
    new_battle = incoming.get("battle", {})
    initiative = old_battle.get("initiative", [])
    active_id = ""
    if old_battle.get("active") and initiative:
        active_id = initiative[old_battle.get("turn_index", 0) % len(initiative)].get("id", "")
    # The ordinary state channel only synchronizes target selection. Movement,
    # action economy, flags, logs and damage to other creatures are resolved by
    # authoritative operation endpoints below and cannot be forged by a client.
    if active_id == session.character_id:
        target_id = str(new_battle.get("target_id", ""))
        positioned = old_battle.get("positions", {})
        if target_id and target_id != session.character_id and positioned.get(target_id) in {"T1", "A1", "A2", "T2"}:
            old_battle["target_id"] = target_id
        elif not target_id:
            old_battle["target_id"] = ""
    room.state["recent_rolls"] = copy.deepcopy(incoming.get("recent_rolls", room.state.get("recent_rolls", [])))[:30]


class DragonSagaHandler(BaseHTTPRequestHandler):
    server_version = "DragonSagaPython/3.2"

    def log_message(self, fmt: str, *args: object) -> None:
        if getattr(self.server, "quiet", False):
            return
        super().log_message(fmt, *args)

    def _json(self, status: int, body: Any) -> None:
        encoded = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(encoded)

    def _body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length > MAX_BODY:
            raise OverflowError("Состояние превышает 256 МБ")
        data = self.rfile.read(length)
        decoded = json.loads(data.decode("utf-8")) if data else {}
        if not isinstance(decoded, dict):
            raise ValueError("Тело запроса должно быть JSON-объектом")
        return decoded

    def _parts(self) -> list[str]:
        return [x for x in urlparse(self.path).path.split("/") if x]

    def _session(self, room: Room) -> Session | None:
        header = self.headers.get("Authorization", "")
        token = header[7:] if header.startswith("Bearer ") else ""
        return room.sessions.get(token)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        parts = self._parts()
        if parts == ["api", "health"]:
            return self._json(200, {"ok": True, "service": "Драконья Сага", "version": "3.2.0"})
        if len(parts) == 4 and parts[:2] == ["api", "rooms"] and parts[3] == "state":
            room = _room(parts[2])
            session = self._session(room)
            if not session:
                return self._json(401, {"error": "Нужна сессия комнаты"})
            with room.lock:
                session.touched = time.time()
                return self._json(200, {"state": state_for_session(room, session), "revision": room.revision, "members": self._members(room)})
        self._json(404, {"error": "Не найдено"})

    def do_POST(self) -> None:  # noqa: N802
        try:
            parts = self._parts()
            if len(parts) != 4 or parts[:2] != ["api", "rooms"]:
                return self._json(404, {"error": "Не найдено"})
            room, action, body = _room(parts[2]), parts[3], self._body()
            with room.lock:
                if action == "session":
                    return self._join(room, body)
                session = self._session(room)
                if not session:
                    return self._json(401, {"error": "Нужна сессия комнаты"})
                if action == "state":
                    if int(body.get("base_revision", -1)) != room.revision:
                        return self._json(409, {"error": "Конфликт ревизий", "state": state_for_session(room, session), "revision": room.revision})
                    incoming = body.get("state")
                    if not isinstance(incoming, dict):
                        return self._json(400, {"error": "Нет состояния"})
                    if room.state is None:
                        if session.role != "gm":
                            return self._json(403, {"error": "Только мастер создаёт состояние"})
                        room.state = copy.deepcopy(incoming)
                    elif session.role == "gm":
                        room.state = copy.deepcopy(incoming)
                    else:
                        apply_player_state(room, session, incoming)
                    room.revision += 1
                    return self._json(200, {"ok": True, "state": state_for_session(room, session), "revision": room.revision})
                if action == "action":
                    if int(body.get("base_revision", -1)) != room.revision:
                        return self._json(409, {"error": "Конфликт ревизий", "state": state_for_session(room, session), "revision": room.revision})
                    if room.state is None:
                        return self._json(404, {"error": "Стол ещё не создан"})
                    actor_id = str(body.get("actor_id", "")); target_id = str(body.get("target_id", "")); action_id = str(body.get("action_id", ""))
                    if session.role != "gm" and actor_id != session.character_id:
                        return self._json(403, {"error": "Игрок управляет только назначенным героем"})
                    campaign = Campaign.from_dict(room.state)
                    result = BattleEngine(campaign).resolve_action(actor_id, target_id, action_id)
                    room.state = campaign.to_dict(); room.revision += 1
                    return self._json(200, {"ok": True, "result": {"title": result.title, "detail": result.detail, "hit": result.hit, "damage": result.damage}, "state": state_for_session(room, session), "revision": room.revision})
                if action == "tactic":
                    if int(body.get("base_revision", -1)) != room.revision:
                        return self._json(409, {"error": "Конфликт ревизий", "state": state_for_session(room, session), "revision": room.revision})
                    if room.state is None:
                        return self._json(404, {"error": "Стол ещё не создан"})
                    actor_id = str(body.get("actor_id", "")); operation = str(body.get("operation", ""))
                    if session.role != "gm" and actor_id != session.character_id:
                        return self._json(403, {"error": "Игрок управляет только назначенным героем"})
                    campaign = Campaign.from_dict(room.state); engine = BattleEngine(campaign)
                    result_payload: dict[str, Any] = {"title": operation, "detail": ""}
                    if operation == "move":
                        engine.move(actor_id, str(body.get("destination", "")), str(body.get("mode", "normal")))
                        result_payload["detail"] = campaign.battle.log[-1] if campaign.battle.log else "Перемещение выполнено"
                    elif operation == "breather":
                        healed = engine.tactical_breather(actor_id)
                        result_payload.update({"detail": f"Тактическая передышка: +{healed} ОЗ", "healed": healed})
                    elif operation == "investigate":
                        result = engine.investigate_telegraph(actor_id, str(body.get("target_id", "")), str(body.get("ability", "wis")))
                        result_payload.update({"title": result.title, "detail": result.detail, "hit": result.hit})
                    elif operation == "rest":
                        kind = str(body.get("kind", "short")); spent = max(0, min(20, int(body.get("spend_hit_dice", 0))))
                        healed = engine.rest(actor_id, kind, spent)
                        result_payload.update({"detail": campaign.battle.log[-1], "healed": healed})
                    else:
                        return self._json(400, {"error": "Неизвестный тактический приём"})
                    room.state = campaign.to_dict(); room.revision += 1
                    return self._json(200, {"ok": True, "result": result_payload, "state": state_for_session(room, session), "revision": room.revision})
                if action == "assignment":
                    if session.role != "gm":
                        return self._json(403, {"error": "Назначает только мастер"})
                    target = next((x for x in room.sessions.values() if x.client_id == body.get("client_id") and x.role == "player"), None)
                    if not target:
                        return self._json(404, {"error": "Игрок не найден"})
                    character_id = str(body.get("character_id", ""))
                    if character_id and not any(x.get("id") == character_id and x.get("side") == "hero" for x in (room.state or {}).get("characters", [])):
                        return self._json(400, {"error": "Герой не найден"})
                    for other in room.sessions.values():
                        if other is not target and other.character_id == character_id:
                            other.character_id = ""
                    target.character_id = character_id
                    room.revision += 1
                    return self._json(200, {"ok": True, "revision": room.revision, "members": self._members(room)})
                return self._json(404, {"error": "Неизвестное действие"})
        except OverflowError as exc:
            self._json(413, {"error": str(exc)})
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            self._json(400, {"error": str(exc)})
        except PermissionError as exc:
            self._json(403, {"error": str(exc)})
        except RuleError as exc:
            self._json(422, {"error": str(exc)})

    def _join(self, room: Room, body: dict[str, Any]) -> None:
        requested_role = "gm" if body.get("role") == "gm" else "player"
        owner_key = str(body.get("owner_key", ""))
        role = "player"
        returned_owner_key = ""
        if requested_role == "gm":
            if not room.owner_key:
                room.owner_key = secrets.token_urlsafe(32)
                role = "gm"
                returned_owner_key = room.owner_key
            elif secrets.compare_digest(owner_key, room.owner_key):
                role = "gm"
        token = secrets.token_urlsafe(32)
        session = Session(token, str(body.get("client_id") or secrets.token_hex(8))[:100], str(body.get("name") or "Участник")[:80], role)
        if role == "player":
            requested_character = str(body.get("character_id", ""))
            claimed = any(x.character_id == requested_character for x in room.sessions.values())
            valid_hero = any(
                item.get("id") == requested_character and item.get("side") == "hero"
                for item in (room.state or {}).get("characters", [])
            )
            if requested_character and valid_hero and not claimed:
                session.character_id = requested_character
        room.sessions[token] = session
        self._json(200, {"token": token, "owner_key": returned_owner_key, "role": role, "character_id": session.character_id, "state": state_for_session(room, session), "revision": room.revision, "members": self._members(room)})

    @staticmethod
    def _members(room: Room) -> list[dict[str, str]]:
        return [{"client_id": x.client_id, "name": x.name, "role": x.role, "character_id": x.character_id} for x in room.sessions.values()]


def create_server(host: str = "0.0.0.0", port: int = 4173, quiet: bool = False) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), DragonSagaHandler)
    server.daemon_threads = True
    server.quiet = quiet  # type: ignore[attr-defined]
    return server


def serve(host: str = "0.0.0.0", port: int = 4173) -> None:
    server = create_server(host, port)
    print(f"Драконья Сага: сетевой стол готов на http://{host}:{server.server_port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Сетевой сервер «Драконьей Саги»")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=4173)
    args = parser.parse_args()
    serve(args.host, args.port)


if __name__ == "__main__":
    main()
