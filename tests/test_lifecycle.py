from datetime import datetime, timedelta, timezone

from src.logistics_ttl import ShipmentEvent, is_expired


def test_proof_of_delivery_expires_after_ttl():
    now = datetime.now(timezone.utc)
    event = ShipmentEvent("shp_1", "proof", now - timedelta(hours=25))
    assert is_expired(event, now, 24 * 60 * 60)
    fresh = ShipmentEvent("shp_2", "proof", now - timedelta(hours=2))
    assert not is_expired(fresh, now, 24 * 60 * 60)
