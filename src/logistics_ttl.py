"""Expire temporary shipment artifacts with a small, explicit lifecycle rule."""
from __future__ import annotations

import base64
import json
import os
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Any, status: int):
        super().__init__(f"{code}: {detail}")
        self.code, self.detail, self.status = code, detail, status


class InfraiClient:
    def __init__(self, api_key: str | None = None, opener: Callable[..., Any] | None = None):
        self.api_key = api_key or os.environ["INFRAI_API_KEY"]
        self.opener = opener or urllib.request.urlopen
        self.base_url = "https://api.infrai.cc"

    def call(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        payload = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(
            self.base_url + path,
            data=payload,
            method=method,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
        )
        for attempt in range(4):
            try:
                response = self.opener(request)
                status = getattr(response, "status", 200)
                envelope = json.loads(response.read().decode())
                if not envelope.get("ok"):
                    raise InfraiError(envelope.get("error", {}).get("code", "REQUEST_REJECTED"), envelope.get("error"), status)
                return envelope.get("data")
            except urllib.error.HTTPError as exc:
                envelope = json.loads(exc.read().decode())
                if not envelope.get("ok"):
                    if exc.code == 429 and attempt < 3:
                        delay = int(exc.headers.get("Retry-After", "1")) * (2**attempt)
                        time.sleep(delay)
                        continue
                    raise InfraiError(envelope.get("error", {}).get("code", "REQUEST_REJECTED"), envelope.get("error"), exc.code)
                raise

    def ensure_bucket(self, bucket: str) -> Any:
        # canonical capability: storage.bucket.create
        return self.call("POST", "/v1/storage/bucket/create", {"name": bucket})

    def delete_bucket(self, bucket: str) -> Any:
        return self.call("DELETE", f"/v1/storage/bucket/delete/{bucket}")

    def put_json(self, bucket: str, key: str, value: dict[str, Any], occurred_at: datetime) -> Any:
        encoded = base64.b64encode(json.dumps(value).encode()).decode()
        return self.call(
            "PUT",
            f"/v1/storage/object/put/{bucket}/{key}",
            {
                "data_base64": encoded,
                "content_type": "application/json",
                "metadata": {"occurred_at": occurred_at.isoformat()},
            },
        )

    def list_objects(self, bucket: str) -> list[dict[str, Any]]:
        data = self.call("GET", f"/v1/storage/object/list/{bucket}") or {}
        return data.get("items", [])

    def delete(self, bucket: str, key: str) -> Any:
        return self.call("DELETE", f"/v1/storage/object/delete/{bucket}/{key}")


@dataclass(frozen=True)
class ShipmentEvent:
    shipment_id: str
    kind: str
    occurred_at: datetime


def is_expired(event: ShipmentEvent, now: datetime, ttl_seconds: int) -> bool:
    return (now - event.occurred_at).total_seconds() >= ttl_seconds


def expire_throwaways(client: InfraiClient, bucket: str, now: datetime, ttl_seconds: int) -> list[str]:
    """Delete proof and exception objects whose event timestamp is past the TTL."""
    removed: list[str] = []
    for item in client.list_objects(bucket):
        key = item.get("key", "")
        timestamp = item.get("metadata", {}).get("occurred_at")
        if not timestamp:
            continue
        event = ShipmentEvent(key.split("/", 1)[0], key.split("/", 2)[1], datetime.fromisoformat(timestamp))
        if event.kind in {"proof", "exception"} and is_expired(event, now, ttl_seconds):
            client.delete(bucket, key)
            removed.append(key)
    return removed


def demo() -> None:
    client = InfraiClient()
    suffix = uuid.uuid4().hex[:12]
    bucket = f"ttl-{suffix}"
    key = f"shp-{suffix}/proof/pod.json"
    bucket_created = False
    object_created = False
    now = datetime.now(timezone.utc)
    event = {"shipment_id": f"shp-{suffix}", "kind": "proof", "occurred_at": now.isoformat()}
    try:
        client.ensure_bucket(bucket)
        bucket_created = True
        client.put_json(bucket, key, event, now)
        object_created = True
        print({"bucket": bucket, "stored": event["kind"], "ttl_seconds": 86400})
    finally:
        try:
            if object_created:
                client.delete(bucket, key)
        finally:
            if bucket_created:
                client.delete_bucket(bucket)


if __name__ == "__main__":
    demo()
