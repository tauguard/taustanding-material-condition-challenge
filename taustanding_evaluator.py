"""Fresh assessment-scoped TauStanding.

Material model
--------------
A rule declares the external material it needs via ``depends_on`` (a list of
condition ids). Rules that declare nothing require no external material —
freshness for such rules is trivially satisfied by the empty set.

Each supplied dependency in ``ctx.dependencies`` must carry:
    condition_id   - matches an entry in some rule's depends_on
    status         - "VALID" / anything else is treated as not valid
    value_digest   - content digest of the actual acquired value (required;
                     an entry with no digest cannot be bound to anything and
                     is treated as incomplete)
    valid_from     - optional ISO-8601 string; material not yet valid at `now`
    valid_until    - optional ISO-8601 string; material no longer valid at
                     `now` once reached

Freshness is derived from this material, not asserted: `fresh` and
`material_digest` are computed here, in every branch, from the actual
dependency set and the current time.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Tuple, Callable, Optional, Mapping
import hashlib, json

ADMISSIBLE="ADMISSIBLE"; BLOCKED="BLOCKED"; ESCALATED="ESCALATED"; REASSESSMENT_REQUIRED="REASSESSMENT_REQUIRED"; EXPIRED="EXPIRED"

@dataclass(frozen=True)
class StandingContext:
    assessment_id: str
    payload: Dict[str,Any]
    state: Dict[str,Any]
    rules: Tuple[Dict[str,Any],...]
    dependencies: Tuple[Dict[str,Any],...]
    evidence: Dict[str,Any]
    authority: Any
    purpose: str
    topology_integrity: bool

@dataclass(frozen=True)
class StandingResult:
    assessment_id: str
    state: str
    reason: str
    fresh: bool=False
    material_digest: str=""
    material_valid_until: Optional[str]=None
    external_material_ids: Tuple[str,...]=()

@dataclass(frozen=True)
class StandingSurface:
    """Whether a Standing surface currently exists for a set of rules, given
    the material available right now. This is a precondition, not a verdict:
    it says nothing about whether any rule's predicate is true, only whether
    there is currently governed ground for a rule to be evaluated on at all.

    Checking this fresh at every node (rather than once, over the whole
    batch, after every rule has already run) is what makes "no standing, no
    consequence" a per-node property instead of an end-of-run summary: a
    node evaluated after the surface has ceased to exist is not a governed
    determination, regardless of what its predicate logic would mechanically
    return, because there was nothing for it to be evaluated on.
    """
    exists: bool
    reason: str
    material_digest: str
    material_valid_until: Optional[str]=None
    external_material_ids: Tuple[str,...]=()

def check_surface(rules, dependencies, now=None) -> StandingSurface:
    """Determine whether a Standing surface exists right now for `rules`,
    given the material currently in `dependencies`. Callable at any point —
    once per assessment, or fresh before every single node — with no notion
    of "previous" material: each call is independent, evaluated only against
    what is passed in as current.
    """
    now = str(now) if now else datetime.now(timezone.utc).isoformat()
    required, source_kind = _required_condition_ids(rules)
    present, conflicted, canonical = _canonical_material(dependencies, required)
    digest = _material_digest(canonical)
    complete, expired, min_valid_until = _material_status(present, conflicted, canonical, required, now)
    external_material_ids = tuple(c for c in required if source_kind.get(c) == "external_authoritative")
    if conflicted:
        return StandingSurface(False, "TAUSTANDING_MATERIAL_CONFLICT", digest, None, external_material_ids)
    if not complete:
        return StandingSurface(False, "TAUSTANDING_MATERIAL_INCOMPLETE", digest, None, external_material_ids)
    if expired:
        return StandingSurface(False, "TAUSTANDING_MATERIAL_EXPIRED", digest, None, external_material_ids)
    return StandingSurface(True, "MATERIAL_COMPLETE_AND_CURRENT", digest, min_valid_until, external_material_ids)

def _required_condition_ids(rules):
    """Rules explicitly declare the external material they depend on. A rule
    with no `depends_on` requires nothing - it is evaluated purely from the
    ambient payload/evidence already in context.

    Each depends_on entry is either a bare condition id (string) or a dict
    ``{"condition_id":..., "source_kind":...}``. source_kind classifies how
    that material must be treated at consequence time, because different
    backends give different correctness guarantees:

      internal_atomic      - a resource this system owns (e.g. a company
                              ledger row). Correctness comes from expressing
                              the actual write as a conditional atomic
                              operation (check-and-write in one statement),
                              not from trusting an earlier read. This is the
                              default when unspecified.
      external_authoritative - a resource owned by a third party (e.g. a
                              bank API). This system cannot make a remote
                              party's write atomic with our own decision, so
                              the cached material can never be sufficient
                              grounds for success: the actual provider call's
                              own response is what must decide the outcome.

    A rule that reads a field without declaring it here gets none of this -
    Standing has no visibility into it at all (see test_material_binding.py).
    """
    required=[]; source_kind={}
    for r in rules:
        for entry in (r.get("depends_on") or ()):
            if isinstance(entry, dict):
                cid=str(entry.get("condition_id") or "").strip()
                kind=str(entry.get("source_kind") or "internal_atomic").strip()
            else:
                cid=str(entry).strip(); kind="internal_atomic"
            if not cid:
                continue
            if cid not in required:
                required.append(cid)
            # If any rule tags a dependency external_authoritative, that
            # classification wins - it is the stricter requirement.
            if source_kind.get(cid) != "external_authoritative":
                source_kind[cid]=kind
    return required, source_kind

def _canonical_material(dependencies, required):
    """Group supplied dependency entries by condition_id. Two entries for the
    same condition_id are only acceptable if they agree on content (e.g. the
    same record supplied twice) - genuinely conflicting entries for the same
    id (e.g. one reflecting an earlier value, one reflecting a later,
    different value) are a signal that the material changed mid-flight and
    must not be silently resolved by picking one; the id is marked
    conflicted and treated as incomplete."""
    by={}
    conflicted=set()
    for x in dependencies:
        if not isinstance(x,dict):
            continue
        cid=str(x.get("condition_id") or x.get("id") or "").strip()
        if not cid:
            continue
        key=(str(x.get("status","")).upper(), x.get("value_digest"), x.get("valid_from"), x.get("valid_until"))
        if cid in by and by[cid] != key:
            conflicted.add(cid)
        by[cid]=key
    canonical=[
        {"condition_id":c,
         "status":by[c][0] if c in by and c not in conflicted else None,
         "value_digest":by[c][1] if c in by and c not in conflicted else None,
         "valid_from":by[c][2] if c in by and c not in conflicted else None,
         "valid_until":by[c][3] if c in by and c not in conflicted else None,
         "conflicted": c in conflicted}
        for c in sorted(required)
    ]
    present={c for c in by if c not in conflicted}
    return present, conflicted, canonical

def _material_digest(canonical):
    encoded=json.dumps(canonical,sort_keys=True,separators=(",",":"),default=str).encode()
    return hashlib.sha256(encoded).hexdigest()

def _material_status(by, conflicted, canonical, required, now):
    """Returns (complete, expired, min_valid_until) for the required set.
    complete=False covers missing entries, conflicting duplicate entries,
    non-VALID status, or a missing value_digest (material that cannot be
    bound to a value is not material).
    expired=True means every entry was structurally complete but at least one
    has fallen outside its declared validity window at `now`."""
    if conflicted:
        return False, False, None
    if set(by) != set(required):
        return False, False, None
    lookup={c["condition_id"]:c for c in canonical}
    for c in required:
        m=lookup[c]
        if m["status"] != "VALID":
            return False, False, None
        if not str(m["value_digest"] or "").strip():
            return False, False, None
    min_valid_until=None
    for c in required:
        m=lookup[c]
        vf=m["valid_from"]; vu=m["valid_until"]
        if vf and now < vf:
            return True, True, None
        if vu and now >= vu:
            return True, True, None
        if vu and (min_valid_until is None or vu < min_valid_until):
            min_valid_until=vu
    return True, False, min_valid_until

def determine(ctx,predicate_vector,runtime_verdict,now=None):
    now=str(now) if now else datetime.now(timezone.utc).isoformat()
    if not ctx.assessment_id:
        return StandingResult("",REASSESSMENT_REQUIRED,"ASSESSMENT_ID_REQUIRED")
    v=tuple(bool(x) for x in predicate_vector); d=str(runtime_verdict or "").upper()
    if not ctx.topology_integrity:
        return StandingResult(ctx.assessment_id,REASSESSMENT_REQUIRED,"TOPOLOGY_INTEGRITY_NOT_ESTABLISHED")
    if not ctx.purpose:
        return StandingResult(ctx.assessment_id,REASSESSMENT_REQUIRED,"PURPOSE_NOT_ESTABLISHED")
    if ctx.authority is None:
        return StandingResult(ctx.assessment_id,REASSESSMENT_REQUIRED,"AUTHORITY_NOT_ESTABLISHED")
    if len(v)!=len(ctx.rules):
        return StandingResult(ctx.assessment_id,REASSESSMENT_REQUIRED,"PREDICATE_VECTOR_INCOMPLETE")

    surface = check_surface(ctx.rules, ctx.dependencies, now)
    digest = surface.material_digest
    min_valid_until = surface.material_valid_until
    external_material_ids = surface.external_material_ids

    if not surface.exists:
        # Every non-existent-surface reason maps to REASSESSMENT_REQUIRED at
        # the whole-batch level: there is no governed ground for the verdict
        # that was computed to stand on.
        return StandingResult(ctx.assessment_id,REASSESSMENT_REQUIRED,surface.reason,
                               fresh=False,material_digest=digest)

    # Material is complete and currently valid: this determination is fresh.
    if d in ("BLOCK","REJECT"):
        return StandingResult(ctx.assessment_id,BLOCKED,"RULE_RESULT_BLOCKED",
                               fresh=True,material_digest=digest,material_valid_until=min_valid_until,
                               external_material_ids=external_material_ids)
    if d in ("REVIEW","ESCALATE","ESCALATED"):
        return StandingResult(ctx.assessment_id,ESCALATED,"ADDITIONAL_GOVERNANCE_REQUIRED",
                               fresh=True,material_digest=digest,material_valid_until=min_valid_until,
                               external_material_ids=external_material_ids)
    if d in ("APPROVE","ALLOW") and all(v):
        return StandingResult(ctx.assessment_id,ADMISSIBLE,"ALL_GOVERNED_CONDITIONS_SATISFIED",
                               fresh=True,material_digest=digest,material_valid_until=min_valid_until,
                               external_material_ids=external_material_ids)
    return StandingResult(ctx.assessment_id,BLOCKED,"GOVERNED_CONDITIONS_NOT_SATISFIED",
                           fresh=True,material_digest=digest,material_valid_until=min_valid_until,
                           external_material_ids=external_material_ids)
