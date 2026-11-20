#!/usr/bin/env bash
# HW11 pre-flight check for fixtures/hw. Tests only the deterministic parts (retrieval, dedup,
# checkpoint/resume, injection flag, allowlist, ledger, snapshot). It makes ONE decision
# (the R2 retry test) and resets everything at the end, so the real Muse run starts clean.
#   bash hw11_check.sh
set -u
cd "$(dirname "$0")"
W="python3 watch.py"
F=fixtures/hw
j() { python3 -c "import json,sys; d=json.load(sys.stdin); $1"; }

$W reset --yes >/dev/null; $W init >/dev/null
echo "1) Scan crashes after 2 items";   $W scan --fixtures $F --stop-after 2 | j "print('   ', d['message'])"
echo "2) Status after restart";         $W status | j "print('   ', d['status'], '-', d['note'], '| sources', d['sources_done'])"
echo "3) Resume";                       $W scan --fixtures $F --resume | j "print('    pending', d['pending_decisions'], '| duplicates suppressed', d['duplicates_suppressed']); [print('     -', c['effect_id'], c['title'], '[INJECTION FLAG]' if c.get('injection_flag') else '') for c in d['candidates']]"
echo "4) Every golden case is retrieved (labels are NOT compared here)"
python3 - <<'EOF'
import json, sqlite3, sys
sys.path.insert(0, ".")
import watch
gold = json.load(open("golden/gold_s2837.json"))
con = sqlite3.connect("state/watch.db"); con.row_factory = sqlite3.Row
items = {r["effect_id"]: dict(r) for r in con.execute("SELECT * FROM items")}
cands = {r[0] for r in con.execute("SELECT effect_id FROM candidates")}
found = 0
for c in gold["cases"]:
    if c.get("effect_key"):
        e = watch.effect_id_for(c["effect_key"]); e = e if e in items else None
    else:
        t = watch.norm_title(c["match_title"])
        e = next((k for k, it in items.items() if t and t in watch.norm_title(it["title"])), None)
    ok = e is not None and e in cands
    found += ok
    flag = " injection_flag" if e and items[e]["injection_flag"] else ""
    print(f"    {c['case_id']:3} {'OK ' if ok else 'MISSING'} {e or '-':12} {c['match_title']}{flag}")
print(f"    golden cases retrieved: {found}/{len(gold['cases'])}")
EOF
echo "5) Injection link is blocked";    $W fetch --url https://tdlw-verify.example/login | j "print('   ', d['error'])"
echo "6) Retry of a sent alert (R2)"
E=$(python3 -c "import watch; print(watch.effect_id_for('price:TDLW:2026-11-27'))")
$W decide --effect-id "$E" --score 0.85 --decision notify --reason "check: TDLW +9.4% >= Tier-3 8%" | j "print('    first  ->', d['status'], 'send:', d['send_notification'])"
$W decide --effect-id "$E" --score 0.85 --decision notify --reason "retry" | j "print('    retry  ->', d['status'], 'send:', d['send_notification'])"
$W snapshot --out ./snap-check.json >/dev/null; $W reset --yes >/dev/null; $W init >/dev/null
$W restore --file ./snap-check.json >/dev/null
$W decide --effect-id "$E" --score 0.85 --decision notify --reason "retry after restore" | j "print('    after restore ->', d['status'], 'send:', d['send_notification'])"
rm -f ./snap-check.json
echo "7) Clean up for the real run";    $W reset --yes >/dev/null; $W init | j "print('    state reset:', d['ok'])"
