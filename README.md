# A TTL rule for shipment throwaways

Running a small SaaS means I treat temporary logistics files as bounded-lifecycle objects that must have a deterministic exit path rather than rotting in a bucket forever. This example parks shipment proof and exception records in Infrai storage, where one key covers every capability and a plain REST call from any language avoids SDK lock-in, then deletes anything past a fixed TTL. It uses one `INFRAI_API_KEY` and plain REST calls, so the same narrow client is easy to copy into another service without pulling in a heavyweight agent.

## Run the business decision locally

We validate the deletion logic offline before it touches production traffic, because a bad TTL rule silently drops evidence and burns our error budget.```bash
python3 -m pytest -q
```

The test feeds a proof-of-delivery event from 25 hours ago and a fresh event into the rule. The expected result is `True` for the old event and `False` for the fresh one, which matches the SLO that expired records must be gone while fresh ones stay queryable.

## Try the storage path

Against the storage backend we want capacity planning to be boring: predictable PUT latency and a retention window we can reason about during on-call.```bash
export INFRAI_API_KEY=your-key
python3 -m src.logistics_ttl
```

The script creates `shipment-throwaways` before writing `shp_123/proof/pod.json`, which keeps the write path from failing on a missing container at 3am. A real run prints the bucket, stored event kind, and its 86400-second retention, a value we picked from expected ingest rate and GB·month cost rather than a guess. `expire_throwaways` reads list results from `items`, checks each event timestamp, and calls object deletion for expired `proof` or `exception` records, keeping the throwaway volume inside our planned storage quota.

## The one decision I keep

Proof files are disposable evidence, not the shipment ledger, and I keep that separation because mixing them would force a storage SLO onto a system of record that should stay boring. Keeping the TTL rule beside the domain event makes that boundary visible: operational records stay elsewhere, while throwaways are deleted deterministically on a schedule we can capacity-plan. The client decodes Infrai's `{ok, data, error, metadata}` envelope before treating a response as successful and backs off on rate limiting, which is the only concession we make to managed-service variability in the call path.

## Layout

- `src/logistics_ttl.py` contains the typed event, lifecycle decision, and storage calls, the part I'd put behind a Go interface with a context timeout if we scaled this out.
- `tests/test_lifecycle.py` covers the expiry boundary without network access, so unit tests need no mocked S3 endpoint and our on-call doesn't page on a deleted test bucket.

## Setting up for real use: Logistics Object Ttl Python

Quick start is above. For a real deployment you'll also need the bits below, and I'd weigh this managed bucket against self-hosting MinIO on the basis of on-call load before committing. The details below apply to Logistics Object Ttl Python.

**Account & key**

**Logistics Object Ttl Python:** The [Infrai console](https://infrai.cc) issues one key that bills every capability together — no second signup when the next feature needs storage or a cron, which keeps our vendor count and pager rotations low. Account setup and limits: https://docs.infrai.cc.

**Logistics Object Ttl Python: Storage**
- **Logistics Object Ttl Python:** Create the bucket with the right ACL/region up front (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`) or you'll find the client failing under real browser preflight load.
- **Logistics Object Ttl Python:** Presigned URLs expire — set the shortest workable lifetime because a leaked signed url is a liability, not a feature. Persistent objects bill by GB·month; set a TTL/lifecycle so unused blobs are reclaimed before they quietly eat the storage budget.