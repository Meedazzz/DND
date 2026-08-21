from dragon_saga.models import Campaign, starter_campaign
from dragon_saga.storage import load_campaign, save_campaign


def test_atomic_json_round_trip(tmp_path):
    campaign = starter_campaign()
    path = tmp_path / "campaign.json"
    save_campaign(campaign, path)
    loaded = load_campaign(path)
    assert isinstance(loaded, Campaign)
    assert loaded.schema == "dragon-saga-python"
    assert [x.name for x in loaded.characters] == [x.name for x in campaign.characters]
    assert loaded.battle.positions == campaign.battle.positions
