import json
import threading
from urllib.request import Request, urlopen

from dragon_saga.models import starter_campaign
from dragon_saga.server import ROOMS, create_server


def request(base, method, path, body=None, token=""):
    headers = {"Content-Type": "application/json"}
    if token: headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    with urlopen(Request(base + path, data=data, headers=headers, method=method), timeout=3) as response:
        return json.loads(response.read())


def test_room_filters_sheets_but_keeps_positioned_projections():
    ROOMS.clear()
    server = create_server("127.0.0.1", 0, quiet=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        gm = request(base, "POST", "/api/rooms/TEST/session", {"role": "gm", "name": "GM"})
        campaign = starter_campaign()
        pushed = request(base, "POST", "/api/rooms/TEST/state", {"base_revision": 0, "state": campaign.to_dict()}, gm["token"])
        own = campaign.characters[0]
        player = request(base, "POST", "/api/rooms/TEST/session", {"role": "player", "name": "P", "character_id": own.id})
        state = player["state"]
        assert player["role"] == "player"
        assert len(state["characters"]) == 4  # all staged actors, but not the reserve sheet
        full = next(x for x in state["characters"] if x["id"] == own.id)
        other = next(x for x in state["characters"] if x["id"] != own.id)
        assert full["actions"] and "source_text" in full
        assert "actions" not in other and "source_text" not in other and "class_name" not in other
        assert state["assigned_character_id"] == own.id
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=2)
