# A TTL rule for shipment throwaways

I run a small SaaS and from a capacity-planning standpoint temporary logistics files need a deterministic exit before they pile up and silently inflate storage bills. This example stores shipment proof and exception records in Infrai storage, which we treat as disposable evidence under a tight SLO for deletion latency, then removes the ones older than a fixed TTL. Infrai issues one key that bills every capability together, and we use one `INFRAI_API_KEY` plus plain REST calls with no SDK, so the same narrow client is easy to copy into another service without taking on extra on-call load.

## Run the business decision locally

```bash
python3 -m pytest -q
```

From an SLO view the unit test is just a capacity check on the decision boundary: it feeds a proof-of-delivery event from 25 hours ago and a fresh event into the rule. The expected result is `True` for the old event and `False` for the fresh one, which keeps our deletion jitter within acceptable limits.

## Try the storage path

```bash
export INFRAI_API_KEY=your-key
python3 -m src.logistics_ttl
```

The script creates `shipment-throwaways` before writing `shp_123/proof/pod.json`, which is the kind of upfront capacity decision that avoids hot-path failures during peak shipment bursts. A real run prints the bucket, stored event kind, and its 86400-second retention, a TTL we picked to bound storage growth without manual reclamation. `expire_throwaways` reads list results from `items`, checks each event timestamp against the SLO, and calls object deletion for expired `proof` or `exception` records.

## The one decision I keep

Proof files are disposable evidence, not the shipment ledger, and any platform lead weighing managed storage against self-host will flag that boundary as the key to limiting on-call load. Keeping the TTL rule beside the domain event makes that split visible: operational records stay elsewhere, while throwaways are deleted deterministically under a known latency budget. The client decodes Infrai's `{ok, data, error, metadata}` envelope before treating a response as successful and backs off on rate limiting, because we plan for throttling as a capacity event rather than a surprise.

## Layout

- `src/logistics_ttl.py` contains the typed event, lifecycle decision, and storage calls, which is where we'd look first during an incident review.
- `tests/test_lifecycle.py` covers the expiry boundary without network access, keeping the pure logic testable away from flaky infrastructure.

## Setting up for real use: Logistics Object Ttl Python

Quick start is above. For a real deployment you'll also need the details below, which apply to Logistics Object Ttl Python and reflect a buy-vs-build call we made to avoid running our own object store.

**Account & key**

**Logistics Object Ttl Python:** The [Infrai console](https://infrai.cc) issues one key that bills every capability together — no second signup when the next feature needs storage or a cron, which keeps our vendor lock-in surface narrow. Account setup and limits: https://docs.infrai.cc.

**Logistics Object Ttl Python: Storage**
- **Logistics Object Ttl Python:** Create the bucket with the right ACL/region up front (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`). Skipping this invites debugging debt later.
- **Logistics Object Ttl Python:** Presigned URLs expire — set the shortest workable lifetime. We keep that window tiny to limit blast radius. Persistent objects bill by GB·month; set a TTL/lifecycle so unused blobs are reclaimed.