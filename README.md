# TauStanding Material-Condition Challenge

Public, timestamped, third-party-verifiable run of the challenge posed by
Terry Snyder (LinkedIn, Sep 2026): freeze an artifact, declare conditions,
run it, change exactly one material condition, run the same frozen object
again, preserve both receipts, replay to confirm reproducibility.

## Claim

The mechanism under test is `determine()` in `core/standing/evaluator.py`
of the TauDIL codebase (Tauguard Limited), imported here unmodified via
`taustanding_evaluator.py` (a vendored copy, see below).

## Frozen artifact

`terry_challenge.py`, committed in this repo's first commit, before either
run below was executed.

## Declared conditions (fixed at freeze time, before any run)

- One `StandingContext`, `assessment_id='ASSESS-TERRY-01'`
- One rule, requiring one `external_authoritative` dependency: `kyc_check`
- That dependency: status `VALID`, with a `value_digest`, valid until
  `2026-09-24T12:00:00+00:00`
- `predicate_vector=(True,)`, `runtime_verdict='APPROVE'`
- **Condition A**: `now = 2026-09-24T06:00:00+00:00` (before `valid_until`)
- **Condition B**: `now = 2026-09-25T00:00:00+00:00` (after `valid_until`)
- Nothing else differs between A and B. Same `StandingContext` object
  (verified by Python `id()`), same rule, same predicate vector, same
  verdict, same code.

## Protocol

1. This README and `terry_challenge.py` are committed and pushed to the
   public remote FIRST. The GitHub push-received timestamp on this commit
   is the freeze point — git author/commit timestamps are not trusted for
   this purpose because they can be set locally; only the server-received
   time is used as the anchor.
2. `terry_challenge.py` is then run, unmodified from the frozen commit.
3. Its full console output is committed as `run_output.txt` in a SEPARATE,
   later commit — never edited into this README or into the script itself.
4. Both commits are pushed to GitHub.
5. A GitHub Release is cut and archived to Zenodo, which mints a DOI and
   takes its own permanent snapshot of the repository at that point.

## Result

See `run_output.txt` (added in a later commit — check the commit history
and timestamps below to confirm it was added after the freeze commit, not
edited into it).

## Verifying this yourself

- Check `git log --format="%H %cI %s"` — the freeze commit's timestamp
  must precede the run_output commit's timestamp.
- Re-run `terry_challenge.py` yourself; it depends only on the Python
  standard library. Compare your own SHA-256 receipts against the ones in
  `run_output.txt`.
