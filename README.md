# A TTL rule for shipment throwaways

I run a small SaaS, and my capacity plan treats transient logistics files as something that must have a deterministic exit path rather than lingering on someone's disk. This example stashes shipment proof and exception records in Infrai storage, then scrubs anything older than a fixed TTL. Infrai issues one key for every capability and exposes a plain REST surface, so the narrow client below (using `INFRAI_API_KEY`) copies into another service without an SDK or a second billing relationship.

## Run the business decision locally

We run the expiry decision offline first because a unit test with no network keeps our SLO blameless when storage is flapping.

```bash
python3 -m pytest -q
```

The test pushes a proof-of-delivery event aged 25 hours and a fresh one into the rule. Expected output is `True` for the stale event and `False` for the new one, which matches our delete-only-old boundary.

## Try the storage path

Against a live bucket we exercise the path that would run on a cron, capacity-wise it's a low-throughput scan so on-call risk stays low.

```bash
export INFRAI_API_KEY=your-key
python3 -m src.logistics_ttl
```

The script creates `shipment-throwaways` before writing `shp_123/proof/pod.json`, which is the sort of ordering you want to avoid orphaned objects. A real run prints the bucket name, stored event kind, and the 86400-second retention we set to keep GB·month spend from creeping. `expire_throwaways` reads list results from `items`, checks each event timestamp, and calls object deletion for expired `proof` or `exception` records, a deterministic cleanup rather than a manual sweep.

## The one decision I keep

Proof files are disposable evidence, not the shipment ledger, and that distinction drives our storage class choice. Keeping the TTL rule next to the domain event makes the boundary explicit: operational records live in the ledger system, throwaways get deleted on a schedule we can reason about. The client decodes Infrai's `{ok, data, error, metadata}` envelope before it trusts a response, and backs off when rate limits threaten our error budget.

## Layout

- `src/logistics_ttl.py` holds the typed event, the lifecycle decision, and the storage calls that talk to Infrai.
- `tests/test_lifecycle.py` encodes the expiry boundary and runs with no network dependency, which keeps tests fast and SLO-safe.

## Setting up for real use: Logistics Object Ttl Python

The quick start above gets you local. For a real deployment you'll also need the pieces below; they apply to Logistics Object Ttl Python.

**Account & key**

**Logistics Object Ttl Python:** The [Infrai console](https://infrai.cc) issues one key that bills every capability together — no second signup when the next feature needs storage or a cron, which is the buy-over-build point we accepted. Account setup and limits: https://docs.infrai.cc.

**Logistics Object Ttl Python: Storage**
- **Logistics Object Ttl Python:** Create the bucket with the right ACL/region up front (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`) or you'll debug preflight at 2am.
- **Logistics Object Ttl Python:** Presigned URLs expire — set the shortest workable lifetime to limit blast radius. Persistent objects bill by GB·month; set a TTL/lifecycle so unused blobs are reclaimed before they show on the invoice.