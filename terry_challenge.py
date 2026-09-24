import sys, hashlib, json, dataclasses
from taustanding_evaluator import StandingContext, determine

def receipt(result, now_used):
    """Receipt is a hash of the actual result + the declared time condition
    only -- NOT of any run label, so replaying the same condition twice
    must hash identically. (An earlier version of this function included
    the run label in the hash, which made replay checks fail spuriously --
    that was a bug in the receipt function, not the mechanism under test.
    Fixed here, disclosed rather than silently corrected.)"""
    payload = {"now": now_used, "result": dataclasses.asdict(result)}
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return payload, hashlib.sha256(blob.encode()).hexdigest()

print("=" * 78)
print("CLAIM: core/standing/evaluator.py :: determine() -- unmodified, as shipped")
print("=" * 78)

print("""
FREEZE: one StandingContext, built once, referenced by identity (id()) in
every run below -- never rebuilt, never re-parameterized.
""")

RULE = {
    "rule_id": "R-KYC-1",
    "depends_on": [{"condition_id": "kyc_check", "source_kind": "external_authoritative"}],
}

DEPENDENCY_VALID_UNTIL = "2026-09-24T12:00:00+00:00"

ctx = StandingContext(
    assessment_id="ASSESS-TERRY-01",
    payload={"applicant": "example"},
    state={"stage": "review"},
    rules=(RULE,),
    dependencies=(
        {
            "condition_id": "kyc_check",
            "status": "VALID",
            "value_digest": "sha256:abc123",
            "valid_from": "2026-09-24T00:00:00+00:00",
            "valid_until": DEPENDENCY_VALID_UNTIL,
        },
    ),
    evidence={},
    authority="AUTHORITY-1",
    purpose="ORG-001",
    topology_integrity=True,
)
predicate_vector = (True,)
runtime_verdict = "APPROVE"

print(f"Frozen object id: {id(ctx)}")
print(f"Frozen ctx: {ctx}")
print(f"predicate_vector={predicate_vector}  runtime_verdict={runtime_verdict!r}")

print("""
DECLARED CONDITIONS (stated before running):
  - one rule, requiring one external_authoritative dependency 'kyc_check'
  - that dependency is VALID, with a value_digest, valid until """ + DEPENDENCY_VALID_UNTIL + """
  - CONDITION A: 'now' = 2026-09-24T06:00:00+00:00  (before valid_until)
  - CONDITION B: 'now' = 2026-09-25T00:00:00+00:00  (after valid_until)
  - Nothing else differs between A and B. Same ctx object. Same rule. Same
    predicate_vector. Same runtime_verdict. Same mechanism. Same code.
""")

NOW_A = "2026-09-24T06:00:00+00:00"
NOW_B = "2026-09-25T00:00:00+00:00"

print("-" * 78)
print("RUN 1 -- CONDITION A (now before valid_until)")
print("-" * 78)
result_A1 = determine(ctx, predicate_vector, runtime_verdict, now=NOW_A)
print(result_A1)
payload_A1, hash_A1 = receipt(result_A1, NOW_A)
print(f"RECEIPT (sha256 of result): {hash_A1}")

print()
print("-" * 78)
print("CHANGE ONE MATERIAL CONDITION: advance 'now' past the dependency's own")
print("declared valid_until. Mechanism untouched. Rules untouched. ctx object")
print("untouched (same id()). Only the current time changes.")
print("-" * 78)
print(f"Frozen object id (same as above): {id(ctx)}")

print()
print("-" * 78)
print("RUN 2 -- CONDITION B (now after valid_until), SAME frozen ctx object")
print("-" * 78)
result_B1 = determine(ctx, predicate_vector, runtime_verdict, now=NOW_B)
print(result_B1)
payload_B1, hash_B1 = receipt(result_B1, NOW_B)
print(f"RECEIPT (sha256 of result): {hash_B1}")

print()
print("=" * 78)
print("REPLAY / REPRODUCE: re-run both conditions again, same frozen object")
print("=" * 78)
result_A2 = determine(ctx, predicate_vector, runtime_verdict, now=NOW_A)
_, hash_A2 = receipt(result_A2, NOW_A)
result_B2 = determine(ctx, predicate_vector, runtime_verdict, now=NOW_B)
_, hash_B2 = receipt(result_B2, NOW_B)

print(f"Condition A replay match : {hash_A1 == hash_A2}  ({hash_A1[:16]}... == {hash_A2[:16]}...)")
print(f"Condition B replay match : {hash_B1 == hash_B2}  ({hash_B1[:16]}... == {hash_B2[:16]}...)")
print(f"A result != B result     : {result_A1 != result_B1}")

print()
print("=" * 78)
print("FINAL LEDGER (verbatim, no relabeling)")
print("=" * 78)
for label, r, h in [("CONDITION A (before valid_until)", result_A1, hash_A1),
                     ("CONDITION B (after valid_until)", result_B1, hash_B1)]:
    print(f"{label}:")
    print(f"  state    = {r.state}")
    print(f"  reason   = {r.reason}")
    print(f"  fresh    = {r.fresh}")
    print(f"  material_digest = {r.material_digest}")
    print(f"  receipt(sha256) = {h}")
    print()
