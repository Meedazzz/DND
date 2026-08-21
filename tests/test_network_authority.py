import threading

import pytest

from dragon_saga.models import Action, Campaign, Combatant
from dragon_saga.network import NetworkClient, NetworkError
from dragon_saga.server import ROOMS, create_server


def room_campaign(active=False):
    hero = Combatant(name="Сетевой герой", side="hero", hp=25, max_hp=25, actions=[Action(name="Волна", kind="save", save_ability="dex", save_dc=100, damage="1d4+2", range_ft=30)])
    enemy = Combatant(name="Сетевой враг", side="enemy", hp=18, max_hp=18, armor_class=12)
    campaign = Campaign(characters=[hero, enemy], assets=[{"id": "secret", "name": "map.png", "kind": "изображение", "path": "/private/gm/map.png"}])
    campaign.battle.positions = {hero.id: "A1", enemy.id: "A2"}
    if active:
        campaign.battle.active = True; campaign.battle.round_number = 1
        campaign.battle.initiative = [{"id": hero.id, "value": 20}, {"id": enemy.id, "value": 10}]
        campaign.battle.movement_left[hero.id] = 30; campaign.battle.turn_start_zone[hero.id] = "A1"
        campaign.battle.flags[hero.id] = {"action": True, "bonus": True, "reaction": True}
    return campaign, hero, enemy


@pytest.fixture
def live_server():
    ROOMS.clear()
    server = create_server("127.0.0.1", 0, quiet=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=2)


def connect_pair(base, campaign):
    gm = NetworkClient(base, "AUTH", "GM", "gm", client_id="gm")
    gm.connect(); gm.push(campaign.to_dict())
    hero = campaign.characters[0]
    player = NetworkClient(base, "AUTH", "Player", "player", hero.id, client_id="player")
    joined = player.connect()
    return gm, player, joined


def test_server_resolves_player_action_against_authoritative_full_state(live_server):
    campaign, hero, enemy = room_campaign(active=True)
    hero.image_path = "/private/gm/hero.png"; hero.model_path = "/private/gm/hero.glb"
    enemy.image_path = "/private/gm/enemy.png"
    reserve = Combatant(name="Скрытый резерв", side="enemy")
    campaign.characters.append(reserve); campaign.battle.positions[reserve.id] = "reserve"
    gm, player, joined = connect_pair(live_server, campaign)
    projection = joined["state"]
    projected_hero = next(item for item in projection["characters"] if item["id"] == hero.id)
    projected_enemy = next(item for item in projection["characters"] if item["id"] == enemy.id)
    assert "actions" not in projected_enemy and "stats" not in projected_enemy
    assert "image_path" not in projected_hero and "model_path" not in projected_hero
    assert "image_path" not in projected_enemy
    assert reserve.id not in projection["battle"]["positions"]
    assert all(item["id"] != reserve.id for item in projection["characters"])
    assert projection["assets"][0]["name"] == "map.png"
    assert "path" not in projection["assets"][0]

    response = player.resolve_action(hero.id, enemy.id, hero.actions[0].id)
    assert response["result"]["hit"] is True
    full = gm.pull()["state"]
    updated_enemy = next(item for item in full["characters"] if item["id"] == enemy.id)
    assert updated_enemy["hp"] < enemy.hp
    assert full["battle"]["flags"][hero.id]["action"] is False


def test_stale_player_revision_is_rejected(live_server):
    campaign, hero, _ = room_campaign()
    gm, player, joined = connect_pair(live_server, campaign)
    gm.pull()
    campaign.title = "Новая ревизия"
    gm.push(campaign.to_dict())
    player.revision = joined["revision"]
    with pytest.raises(NetworkError) as caught:
        player.push(joined["state"])
    assert getattr(caught.value, "status", 0) == 409


def test_player_state_push_cannot_forge_damage_movement_flags_or_log(live_server):
    campaign, hero, enemy = room_campaign(active=True)
    gm, player, joined = connect_pair(live_server, campaign)
    state = joined["state"]
    state["battle"]["target_id"] = enemy.id
    state["battle"]["positions"][hero.id] = "T2"
    state["battle"]["movement_left"][hero.id] = 999
    state["battle"]["flags"][hero.id]["action"] = False
    state["battle"]["log"].append("поддельная запись")
    projected_enemy = next(item for item in state["characters"] if item["id"] == enemy.id)
    projected_enemy["hp"] = -999
    player.push(state)
    full = gm.pull()["state"]
    authoritative_enemy = next(item for item in full["characters"] if item["id"] == enemy.id)
    assert full["battle"]["target_id"] == enemy.id
    assert full["battle"]["positions"][hero.id] == "A1"
    assert full["battle"]["movement_left"][hero.id] == 30
    assert full["battle"]["flags"][hero.id]["action"] is True
    assert "поддельная запись" not in full["battle"]["log"]
    assert authoritative_enemy["hp"] == enemy.hp


def test_player_tactical_move_is_resolved_on_server(live_server):
    campaign, hero, _ = room_campaign(active=True)
    gm, player, _ = connect_pair(live_server, campaign)
    response = player.tactic(hero.id, "move", destination="T1", mode="normal")
    assert "A1 → T1" in response["result"]["detail"]
    full = gm.pull()["state"]
    assert full["battle"]["positions"][hero.id] == "T1"
    assert full["battle"]["movement_left"][hero.id] == 20


def test_player_cannot_use_tactic_for_another_creature(live_server):
    campaign, _, enemy = room_campaign(active=True)
    _, player, _ = connect_pair(live_server, campaign)
    with pytest.raises(NetworkError) as caught:
        player.tactic(enemy.id, "move", destination="T1", mode="normal")
    assert getattr(caught.value, "status", 0) == 403


def test_player_projection_hides_boss_counter_but_investigation_can_reveal_it(live_server):
    campaign, hero, enemy = room_campaign(active=True)
    enemy.is_boss = True; enemy.telegraph = "Грозовой разлом"; enemy.telegraph_dc = 1; enemy.telegraph_counter = "Укрыться в тылу"
    _, player, joined = connect_pair(live_server, campaign)
    projected_enemy = next(item for item in joined["state"]["characters"] if item["id"] == enemy.id)
    assert "telegraph_counter" not in projected_enemy
    response = player.tactic(hero.id, "investigate", target_id=enemy.id, ability="wis")
    assert response["result"]["hit"] is True
    assert "Укрыться в тылу" in response["result"]["detail"]
    projected_after = next(item for item in response["state"]["characters"] if item["id"] == enemy.id)
    assert "telegraph_counter" not in projected_after


def test_gm_assignment_reaches_unassigned_player(live_server):
    campaign, hero, _ = room_campaign()
    gm = NetworkClient(live_server, "ASSIGN", "GM", "gm", client_id="gm")
    gm.connect(); gm.push(campaign.to_dict())
    player = NetworkClient(live_server, "ASSIGN", "Player", "player", client_id="p")
    player.connect(); gm.assign("p", hero.id)
    state = player.pull()["state"]
    assert player.character_id == hero.id
    assert state["assigned_character_id"] == hero.id
    assert next(item for item in state["characters"] if item["id"] == hero.id)["actions"]


def test_invalid_requested_character_is_not_assigned(live_server):
    campaign, _, _ = room_campaign()
    gm = NetworkClient(live_server, "INVALID", "GM", "gm", client_id="gm")
    gm.connect(); gm.push(campaign.to_dict())
    player = NetworkClient(live_server, "INVALID", "Player", "player", "missing-id", client_id="p")
    joined = player.connect()
    assert joined["character_id"] == ""
