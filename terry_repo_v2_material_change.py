import sys, hashlib, json, dataclasses
sys.path.insert(0, ".")  # run from the repo root, next to taustanding_evaluator.py
from taustanding_evaluator import StandingContext, determine

def receipt(result, now_used):
    payload = {"now": now_used, "result": dataclasses.asdict(result)}
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()

RULE = {
    "rule_id": "R-KYC-1",
    "depends_on": [{"condition_id": "kyc_check", "source_kind": "external_authoritative"}],
}
NOW = "2026-09-24T06:00:00+00:00"  # IDENTICAL in both runs. The clock does not move.

print("=" * 78)
print("A GENUINE MATERIAL-REALITY CHANGE TEST")
print("(as opposed to the earlier clock/expiry test, which Terry Snyder")
print(" correctly identified was not this)")
print("=" * 78)
print(f"""
'now' is held FIXED at {NOW} in every run below. It never changes. What
changes is what the external KYC provider actually reported -- i.e. the
authoritative material itself.

One honest note on method, stated up front rather than hidden: this
mechanism's StandingContext is an immutable (frozen) dataclass by design --
material is supplied fresh on each call, never mutated in place. That
immutability is itself a governance property (material facts are asserted,
not silently edited), not a loophole. It means a genuine change in
real-world material reality is represented, correctly, as a NEW context
built from a new fetch -- exactly as a real caller would do after querying
the KYC provider again and getting a different answer back. So this test
uses two distinct context objects, not one mutated object. Their id()s
differ; every field except `dependencies` is identical between them, shown
explicitly below.
""")

def make_ctx(dependencies):
    return StandingContext(
        assessment_id="ASSESS-TERRY-02",
        payload={"applicant": "example"},
        state={"stage": "review"},
        rules=(RULE,),
        dependencies=dependencies,
        evidence={},
        authority="AUTHORITY-1",
        purpose="ORG-001",
        topology_integrity=True,
    )

predicate_vector = (True,)
runtime_verdict = "APPROVE"

# ---------------------------------------------------------------------
# TEST 1: status change -- the KYC provider REVOKES what was previously
# an unexpired, currently-valid attestation. Same clock. Same rule. Same
# predicate_vector. Same runtime_verdict.
# ---------------------------------------------------------------------
print("-" * 78)
print("TEST 1: KYC provider revokes a currently-valid, unexpired attestation")
print("-" * 78)

dep_valid = (
    {
        "condition_id": "kyc_check", "status": "VALID", "value_digest": "sha256:abc123",
        "valid_from": "2026-09-24T00:00:00+00:00", "valid_until": "2026-09-24T12:00:00+00:00",
    },
)
dep_revoked = (
    {
        "condition_id": "kyc_check", "status": "REVOKED", "value_digest": "sha256:def456",
        "valid_from": "2026-09-24T00:00:00+00:00", "valid_until": "2026-09-24T12:00:00+00:00",
    },
)

ctx1a = make_ctx(dep_valid)
ctx1b = make_ctx(dep_revoked)
diff_fields = [f.name for f in dataclasses.fields(ctx1a)
               if getattr(ctx1a, f.name) != getattr(ctx1b, f.name)]
print(f"ctx1a id={id(ctx1a)}  ctx1b id={id(ctx1b)}  (different objects, as explained above)")
print(f"Fields that differ between ctx1a and ctx1b: {diff_fields}  (must be exactly ['dependencies'])")

r1a = determine(ctx1a, predicate_vector, runtime_verdict, now=NOW)
r1b = determine(ctx1b, predicate_vector, runtime_verdict, now=NOW)
h1a, h1b = receipt(r1a, NOW), receipt(r1b, NOW)

print(f"\nBEFORE (KYC valid):   {r1a}")
print(f"receipt: {h1a}")
print(f"\nAFTER  (KYC revoked): {r1b}")
print(f"receipt: {h1b}")
print(f"\nmaterial_digest changed: {r1a.material_digest != r1b.material_digest}  "
      f"({r1a.material_digest[:16]}... vs {r1b.material_digest[:16]}...)")
print(f"state changed:           {r1a.state} -> {r1b.state}")
print(f"'now' identical in both runs: {NOW} == {NOW} -> True (clock never moved)")

# Replay each condition independently to confirm determinism under replay
r1a_replay = determine(ctx1a, predicate_vector, runtime_verdict, now=NOW)
r1b_replay = determine(ctx1b, predicate_vector, runtime_verdict, now=NOW)
print(f"\nReplay match (valid case):   {receipt(r1a_replay, NOW) == h1a}")
print(f"Replay match (revoked case): {receipt(r1b_replay, NOW) == h1b}")

# ---------------------------------------------------------------------
# TEST 2: finer grain -- the provider's attestation CONTENT changes
# (value_digest differs) while status stays VALID and the window is
# unchanged. This shows the mechanism tracks material at the content
# level, not merely at the status/expiry level: the digest moves even
# when the routing verdict does not.
# ---------------------------------------------------------------------
print()
print("-" * 78)
print("TEST 2: attestation CONTENT changes, status stays VALID, window unchanged")
print("-" * 78)

dep_content_a = (
    {
        "condition_id": "kyc_check", "status": "VALID", "value_digest": "sha256:content-v1",
        "valid_from": "2026-09-24T00:00:00+00:00", "valid_until": "2026-09-24T12:00:00+00:00",
    },
)
dep_content_b = (
    {
        "condition_id": "kyc_check", "status": "VALID", "value_digest": "sha256:content-v2",
        "valid_from": "2026-09-24T00:00:00+00:00", "valid_until": "2026-09-24T12:00:00+00:00",
    },
)
ctx2a = make_ctx(dep_content_a)
ctx2b = make_ctx(dep_content_b)
r2a = determine(ctx2a, predicate_vector, runtime_verdict, now=NOW)
r2b = determine(ctx2b, predicate_vector, runtime_verdict, now=NOW)
print(f"content v1: state={r2a.state}  material_digest={r2a.material_digest[:16]}...")
print(f"content v2: state={r2b.state}  material_digest={r2b.material_digest[:16]}...")
print(f"material_digest changed despite identical routing verdict: "
      f"{r2a.material_digest != r2b.material_digest}")
print(f"(this is the mechanism proving it is tracking WHAT was supplied, not just")
print(f" whether a rule happened to route the same way)")
