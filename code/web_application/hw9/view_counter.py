"""HW9 Part 1 - Redis-backed view counter for the primary entity (restaurant inspection).

    cd code
    python -m web_application.hw9.view_counter            # 25 accesses, sync every 10
    python -m web_application.hw9.view_counter --views 25 --code S2837-H9-0002

Key: s2837:views:inspection:<id>   (Redis INCR on every access)
Every 10th increment the count is written to s2837_rel.restaurant_inspection.view_count.
"""

import argparse
import sys
import time

from . import config as cfg
from .db import Db
from .util import banner, log, ms_since, redis_client, save_raw

COMPONENT = "PART1"


class InspectionStore:
    """Database + cache class for the primary entity (s2837_rel + Redis)."""

    def __init__(self, db=None, redis=None):
        self.db = db or Db()
        self.redis_client = redis or redis_client(decode=True)
        self.db.ensure_schema()
        self.db.seed_hw9_records()
        self.sync_log = []
        self.last_synced = None

    def views_key(self, inspection_id):
        return cfg.VIEWS_KEY.format(id=inspection_id)

    def increment_inspection_views(self, inspection_id):
        """INCR the Redis counter; every SYNC_EVERY increments persist it to s2837_rel."""
        key = self.views_key(inspection_id)
        count = int(self.redis_client.incr(key))
        if count % cfg.SYNC_EVERY == 0:
            self.db.set_view_count(inspection_id, count)
            self.sync_log.append({"count": count, "db_value": self.db.get_view_count(inspection_id)})
            self.last_synced = count
            log(COMPONENT, f"Synced views to database: {key} = {count} -> "
                           f"restaurant_inspection.view_count (id={inspection_id})", echo=False)
        return count

    def reset_views(self, inspection_id):
        self.redis_client.delete(self.views_key(inspection_id))
        self.db.set_view_count(inspection_id, 0)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--code", default="S2837-H9-0001")
    parser.add_argument("--views", type=int, default=25)
    args = parser.parse_args()

    store = InspectionStore()
    insp = store.db.inspection_by_code(args.code)
    if not insp:
        log(COMPONENT, f"inspection {args.code} not found")
        return 1
    iid = insp["id"]
    banner(COMPONENT, f"HW9 Part 1 - {cfg.STUDENT_NAME} - view counter for inspection "
                      f"{args.code} (id={iid}) key={store.views_key(iid)}")
    store.reset_views(iid)
    print("=== Testing Counter ===", flush=True)
    rows, redis_times = [], []
    for i in range(1, args.views + 1):
        start = time.perf_counter()
        total = store.increment_inspection_views(iid)
        redis_times.append(ms_since(start))
        print(f"Access #{i}: Total = {total}", flush=True)
        if store.last_synced == total:
            print(f"✓ Synced views to database (view_count={store.db.get_view_count(iid)})",
                  flush=True)
        rows.append({"access": i, "total": total, "ms": redis_times[-1]})

    db_value = store.db.get_view_count(iid)
    redis_value = int(store.redis_client.get(store.views_key(iid)))
    log(COMPONENT, f"final: Redis {store.views_key(iid)} = {redis_value}, "
                   f"s2837_rel.restaurant_inspection.view_count = {db_value} "
                   f"(last sync at a multiple of {cfg.SYNC_EVERY})")

    # For comparison: what the counter would cost if every view did a database UPDATE
    db_times = []
    for _ in range(args.views):
        start = time.perf_counter()
        store.db.execute("UPDATE restaurant_inspection SET view_count = view_count + 1 "
                         "WHERE id=%s", (iid,))
        db_times.append(ms_since(start))
    store.db.set_view_count(iid, db_value)  # put the synced value back
    avg_r = round(sum(redis_times) / len(redis_times), 3)
    avg_d = round(sum(db_times) / len(db_times), 3)
    log(COMPONENT, f"measured avg per view: Redis INCR path {avg_r} ms (includes the sync "
                   f"writes), direct DB UPDATE per view {avg_d} ms")
    save_raw("part1_counter.json", {
        "inspection_code": args.code, "inspection_id": iid, "key": store.views_key(iid),
        "accesses": rows, "syncs": store.sync_log, "final_redis": redis_value,
        "final_db": db_value, "avg_ms_redis_path": avg_r, "avg_ms_db_update_per_view": avg_d,
        "db_dialect": store.db.dialect})
    return 0


if __name__ == "__main__":
    sys.exit(main())
