# Item 6 of AuthZEN #795 as a TRIEL rule, compared with the VATE vectors

This repository is an aid for comparison: it writes the dispatch rule of item 6 of the Failure semantics of [openid/authzen#795](https://github.com/openid/authzen/issues/795) as a TRIEL specification, with `unknown` read as in item 1, translates the eight variants of the VATE vectors into its input with a mapping script, and puts the reports of the TRIEL evaluator next to the expected PEP conditions of VATE. It is not a test suite that an implementation must pass, and its tables are not a judgement on VATE or on the proposal.

Individual comparison; not an OpenID Foundation or VATE work product. It has not been reviewed or endorsed by the AuthZEN working group or by the author of the VATE vectors. The VATE files are not redistributed here; they are fetched at the pinned commit.

## Item 6, as read

Item 6 of the Failure semantics in the description of openid/authzen#795, read on 2026-11-12:

> 6. **A new PERMIT never reopens an occurrence.** Before dispatch, the PEP checks the register for the logical-effect identifier and reserves it in one atomic step. If an earlier attempt is still `unknown`, the PEP MUST NOT dispatch. If a recovery receipt confirms completion, the occurrence stays closed. Another attempt is allowed only when there is authoritative confirmation that the earlier attempt did not execute, the earlier attempt is fenced so that it can no longer take effect, and a fresh authorization covers the new attempt. The absence of a completion receipt, or a missing `outcome` read as a default value, is not such confirmation: a late recovery receipt can still arrive. A new PERMIT alone is never evidence that an earlier attempt did not run. (Credit for items 2 and 6: Iman Schrock suggested preserving a stable logical-effect identity and preventing a new PERMIT from reopening an unresolved or completed occurrence.)

Item 1, which says how `unknown` is read, on the same date:

> 1. **Outcome values.** `outcome` is one of `success`, `failure` or `unknown`. `unknown` means the operation was forwarded and no result is known to the PEP. `failure` means the operation ran and did not succeed; it is not by itself confirmation that the attempt did not execute (item 6). (The eKYC & IDA execution layer has success, failure, network-error and partial; `unknown` is the missing value.)

## Pins

[`PINS`](PINS) holds everything this comparison depends on:

- TRIEL: [`triel-lang/grammar`](https://github.com/triel-lang/grammar/tree/09c25273e69d3987a12b2a75cfd4a2817b6acb2d) at `09c25273e69d3987a12b2a75cfd4a2817b6acb2d`, the head of `main` on 2026-11-12. The evaluator and `triel check` (`parser/triel.py`) are taken from this commit.
- VATE: [`Poke-nushi/Verifiable-Agent-Trust-Envelope`](https://github.com/Poke-nushi/Verifiable-Agent-Trust-Envelope/tree/c7533ad70c20e71b7912cdf708f33220e49c1f00/reference/authzen-receipt-vectors) at `c7533ad70c20e71b7912cdf708f33220e49c1f00`, folder `reference/authzen-receipt-vectors`.
- The sha256 of the VATE `MANIFEST.json`, `66bfe7c9a51319241891cb2407901a2edaae3e99235bdc92d6898f19525f8073`, since the manifest lists the sha256 of every other file and omits itself. Every VATE file that a script reads is checked against the manifest.

The workflow and a local run fetch the two repositories into `grammar/` and `vate/` (both in `.gitignore`).

## Files

| File | What it is |
|---|---|
| [`specs/dispatch_rule.triel`](specs/dispatch_rule.triel) | the dispatch rule of item 6 |
| [`specs/absence_check.triel`](specs/absence_check.triel) | a contrast: the dispatch is forbidden only when a completion receipt is present |
| [`MAPPING.md`](MAPPING.md) | every decision of the mapping, and why; the correspondence with the VATE expectations; the hand derivation of the reports |
| [`mapping/map_vate.py`](mapping/map_vate.py), [`mapping/test_map_vate.py`](mapping/test_map_vate.py) | the mapping script and its tests |
| `scenarios/dispatch/*.scn`, `scenarios/absence/*.scn` | 35 scenarios written by the script: 17 per specification, and one for the snapshot `fenced` under an assumption |
| `scenarios/*/*.expected`, `scenarios/*/*.exitcode` | the expected report of `triel check SPEC TRACE --last`, written by hand, and its exit code: 3 when the `LAST` line has BLOCK, 0 when it has ALLOW (`grammar/evaluator/README.md`, Exit codes). The exit codes of the rule were written by hand; those of the absence check were filled in by a one-line shell loop from the `LAST` line of the hand-written report |
| [`compare/compare.py`](compare/compare.py), [`COMPARISON.md`](COMPARISON.md) | the comparison table and the script that builds it |
| [`.github/workflows/compare.yml`](.github/workflows/compare.yml) | the workflow that checks all of the above |

## The rule

```
TERMS {
  pep MUST_NOT dispatch
    WHEN prior_attempt_registered
         AND (prior_completed
              OR NOT (prior_confirmed_unexecuted AND prior_fenced AND fresh_authorization))
}
```

Five Boolean factors, sourced from the provider and the PDP. The condition is read in the state of the entry just before the dispatch. A factor that the journal does not establish is absent, and TRIEL reads an absent factor as undefined (U), as in TRIEL 2.5.1; the fail-closed monitor of the prohibition blocks the dispatch unless the condition is known to be false. `prior_attempt_registered` is always true or false, never absent, so that the rule does not block the first dispatch and needs no `PRESENT`; the condition has no `PRESENT` and no `DEFAULT`.

`unknown` is read as in item 1: an outcome that is not known. In the mapping a record `unknown` gives no value to any factor, and a `handoff` record whose effect state is `unresolved` gives none either; both are the absence of a factor, not two different notions, and TRIEL has no separate kinds of "unknown".

The grammar requires an `INVARIANTS` block. On a finite trace `ALWAYS` is never T, only U or F (`always_never_true`); the invariants are evaluated in the style of LTL3, and correspondence with LTL3 is not proved (`formal/core/CORE.md`, 10.1). The invariant of the absence check takes no part in the comparison.

## How the comparison was made

1. The scenarios, the expected reports and `MAPPING.md` with its tables were committed first, before the evaluator was run on them and before the expected PEP conditions of VATE were read.
2. `compare/compare.py` was written and run after that commit; it is the only code that reads `expected-pep-decision.json`. The mapping was not changed after those files were read.
3. The workflow was added after both. It fetches the two repositories at the pinned commits, checks the commits and the sha256 of the manifest, builds the evaluator with GHC 9.6.7 as `grammar/evaluator/README.md` describes, runs the tests of the mapping script, generates the scenarios again and compares them with the committed ones, runs `python3 grammar/parser/triel.py check SPEC TRACE --last` on each of the 35 scenarios and compares the output, character for character, with the `.expected` file and the exit code with the `.exitcode` file, and builds `COMPARISON.md` again and compares it with the committed file.

The expected reports were committed in `c85a555b2062cbb66e602077aad1ef192adcb0a9`, earlier than commit `eb7d76ad679e2d6f71dde5cd0a17ed9aab3a139f`, which added the CI step with the first run of the evaluator (run 1). Run 1 stopped before the evaluator was built: the workflow did not read the pinned sha256 of the manifest from `PINS` (a pattern without digits). Commit `3add11b0cc5c7d626ced89e59079f8ed20938672` changed only that pattern, and the evaluator first ran in run 2 on it ([run 2](https://github.com/triel-lang/authzen795-comparison/actions/runs/43188635519)). In run 2 the output of `triel check` was the committed expected report, character for character, and its exit code the committed one, in all 35 scenarios, and `COMPARISON.md` was the table the script builds. No expected report, scenario or mapping decision was changed after the first run.

The expected reports were written by hand from `MAPPING.md` (section "Hand derivation of the expected reports"), the text of the specifications and the scenarios; no program computed a verdict for them. The evaluator was not built outside the workflow.

## What the mapping does

`MAPPING.md` gives each decision, with its reason; Poke-nushi offered to check exactly these. In short:

- One instance of the specification is one logical effect; the subject `pep` stands for both runtimes. The attempt and the logical effect are distinguished in the mapping script, not in the language: the script decides which attempts the factors speak about, and the trace does not carry attempt identifiers.
- Each journal record is one entry, in order, at its time `at`; the activation entry is the record `registered`. The last entry is a probe: a dispatch of another attempt of the same logical effect at `observed_at` of the snapshot. All 17 journals have one time, 2026-10-25T00:00:00Z: the clock of the vectors is fixed.
- `prior_attempt_registered` is true from the first `ticket`. `prior_completed` is true from a `native` record of an accepted attempt whose outputs equal the inventory of the snapshot; the field `effect_state` of `observed` and `handoff` is not read for this. VATE also requires the result to match the original operation; the script does not read `operation.json` and does not check this.
- Confirmation of non-execution and fencing are statements of the provider, read from the last `handoff` record (`effect_state: confirmed_unexecuted`, and the record with `worker_excluded: true`). TRIEL does not derive them, and the script does not verify them. They cover the attempts that the `handoff` record lists; a later ticket for another attempt is not covered.
- `fresh_authorization` is absent: VATE marks `fresh_pdp_evaluation` as `not_checked`, and the new local admission in the `handoff` record is not counted. One extra scenario sets it true, as an assumption, for the snapshot `fenced`.
- The script reads only `MANIFEST.json`, `input-history.json` and the `*-history.json` journals. It does not check signatures or the chain of `previous` hashes, and it does not run or import any VATE code.

## Results

From [`COMPARISON.md`](COMPARISON.md):

- The monitor of the rule blocks the probe in 17 of 17 snapshots. VATE expects `hold_same_logical_effect` in 16 and `conditional_continuation` in 1 (`fenced`), so a constant BLOCK would agree with the VATE decision in 16 of 17 snapshots: the decision alone says little.
- The information is in the split between U and T and in the contrast with the absence check. Where VATE gives the reason that the earlier attempt remains unresolved (10 snapshots), the condition is U and the verdict PENDING in 10 of 10. Where VATE gives the reason that the earlier effect is completed (6 snapshots), the condition is T and the verdict BREACHED in 6 of 6. A BREACHED verdict is the verdict on the hypothetical dispatch of the probe: a dispatch there would violate item 6; it is not a failure of VATE.
- In the snapshot `fenced` (`conditional_continuation`), the condition is U and the monitor blocks the probe without a fresh authorization.
- All 17 rows match the correspondence written in `MAPPING.md` before the VATE expectations were read.
- The absence check allows the probe in 11 of 17 snapshots: in all 10 snapshots where VATE holds because the earlier attempt remains unresolved, and in `fenced`, where VATE asks for three further conditions. It differs from `hold_same_logical_effect` in 10 of 17.

### The extra run for `fenced`

`scenarios/dispatch/03-confirmed-nonexecution-handoff__fenced-handoff__fenced__assumed-fresh-authorization.scn` adds `fresh_authorization = true`, which the journal does not give. The monitor allows the probe there. This ALLOW means only that the condition of the rule is false under the assumption `fresh_authorization = true`. The PEP-side atomic check and reservation and the registration of a signed receipt, the two other `additional_requirements` of VATE, are not modelled by the rule, and the ALLOW does not replace them.

## Where the prose admits two readings

Each place in items 6 and 1 that admits two readings, with the reading taken and why.

1. *"If an earlier attempt is still `unknown`"*, with item 1: *"`unknown` means the operation was forwarded and no result is known to the PEP."* (a) Only an attempt known to have been forwarded, with no result. (b) Any reserved attempt whose result is not established, including one reserved and not known to have been forwarded (the snapshots `pending`, with a ticket only) and one accepted and interrupted. Taken: (b), by the mapping: a reserved attempt without a result sets no factor. Why: from the register a reserved attempt cannot be told apart from one forwarded whose response was lost, and under either reading the next sentences of item 6 still forbid another attempt without confirmation, fencing and a fresh authorization, so the condition is not false in these snapshots.
2. *"If a recovery receipt confirms completion, the occurrence stays closed."* (a) Only a recovery receipt, which resolves an earlier `unknown`, closes the occurrence. (b) Any evidence of completion closes it, also a result recorded with no earlier `unknown`. Taken: (b) (`MAPPING.md`, decisions 1 and 2). In `live-worker/completed` and in both snapshots of `04-…/completed` there is no `unknown` record, and the effect is completed. And "stays closed" is read as a prohibition that applies (condition T), not only as a dispatch that is not allowed: a dispatch there is reported BREACHED.
3. *"Another attempt is allowed only when …"* (a) The three conditions are necessary: without one of them the dispatch is forbidden, and with all three item 6 does not forbid it. (b) They are also sufficient: with all three the dispatch is permitted. Taken: (a). The rule is a prohibition; ALLOW of its monitor means that its condition is false, not that item 6 grants the dispatch. This is also how VATE treats `fenced`: `conditional_continuation` with further requirements.
4. *"authoritative confirmation that the earlier attempt did not execute"* (a) A statement of the provider suffices. (b) Only a statement the PEP or a verifier can check. Taken: (a), as a trust assumption: the script takes the `handoff` record of the provider as written and checks no signature. The new sentence of item 6 is followed: the absence of a completion receipt is never read as confirmation (`MAPPING.md`, decision 8). Reading false where the journal says nothing would turn the 10 unresolved snapshots from PENDING into BREACHED (`MAPPING.md`, the hand check of decision 8).
5. *"the earlier attempt"*, singular, when there are several. (a) The most recent attempt. (b) Every attempt reserved so far. Taken: (b): confirmation and fencing count only while the last `handoff` record lists every reserved attempt (`MAPPING.md`, decision 3). Item 9 supports this: a confirmation of non-execution is final for its attempt, and "For a logical effect, only completion is final: an effect whose earlier attempt was confirmed as not executed may later be completed by a new attempt". In `fenced-handoff/completed` the confirmation names the attempt of generation 1; from the ticket of generation 2 it does not cover the latest attempt, so it is absent there, and the invariant `consistent_prior_state` stays U. Had the confirmation been kept as a statement about the logical effect, the invariant would be F at the completion of generation 2. The verdict on the probe is BREACHED either way.
6. *"the earlier attempt is fenced so that it can no longer take effect"* (a) The provider states that the old worker is excluded. (b) The register moves to a new generation, so that the old attempt is refused. Taken: both together, from the `handoff` record and its field `worker_excluded` (`MAPPING.md`, decision 4). `worker_excluded` is true in all eight `handoff` records, so on its own it distinguishes nothing; the record `denied` with `old_generation`, which shows the fence working, is not used, since the snapshot `fenced` has none.
7. *"a fresh authorization covers the new attempt"* (a) A new evaluation at the PDP for this attempt, as item 4 says of a retry. (b) Any new local admission or PERMIT. Taken: (a). The journals have only (b), a new local admission in the `handoff` record, and VATE marks `fresh_pdp_evaluation` as `not_checked`, so the factor is absent and the extra run for `fenced` is an assumption.
8. *"checks the register for the logical-effect identifier and reserves it in one atomic step"* (a) The reservation made for the dispatch in question is not an earlier attempt. (b) Every reservation in the register is. Taken: the probe is the dispatch of another attempt, after the records of the snapshot, so every `ticket` in the journal is an earlier attempt (`MAPPING.md`, decision 0). The atomicity of check and reservation is a property of the PEP, which the rule, read on states between entries, does not model; VATE lists it among the `additional_requirements`.
9. Item 1: *"`failure` … is not by itself confirmation that the attempt did not execute"*. The journals have no `failure` outcome; the nearest is the record `denied`, by which the provider refuses a late attempt of the old generation. It could be read as evidence that the attempt did not execute. Taken: it is not; confirmation is read only from a `handoff` record (decisions 3 and 4).
10. *"a missing `outcome` read as a default value"*. The rule has no `DEFAULT`. Reading a missing value as a default is not monotone: `T3_default_not_monotone` (below) shows a condition `DEFAULT(x, w) = w` that is T while x is absent and F once x arrives with a value v ≠ w.

## What is proved and what is trusted

The theorems are proved in Isabelle/HOL about the functions of the TRIEL core (`formal/core` at the pinned commit). The evaluator is Haskell code that Isabelle exports from those functions; every verdict and every monitor decision in a report is computed by the exported code. Trusted, not proved (`formal/core/CORE.md`, end of section 10.6; `grammar/evaluator/README.md`, section `triel check`):

- Isabelle's code generator and GHC;
- the translator, and the reading and printing of the input and the report: `evaluator/Main.hs`, `parser/triel_eval.py`, `parser/triel.py`;
- the mapping script of this repository, which does not check signatures or the chain of `previous` hashes, and whose statements of the provider (confirmation, fencing) are taken as written.

Each theorem, with its assumptions as stated in the theory files (type annotations left out):

- [`monitor_sound_completions`](https://github.com/triel-lang/grammar/blob/09c25273e69d3987a12b2a75cfd4a2817b6acb2d/formal/core/TRIEL_Completions.thy#L102) (`TRIEL_Completions.thy`). Assumes `present_free c`, `¬ blocks c σ` and `completion σ σ'`; shows `eval c σ' = Some False`. If the condition has no `PRESENT` and no `DEFAULT` and the monitor does not block, the condition is false however the missing data turn out. Here it concerns only an ALLOW, that is, only the extra run for `fenced`; there all five factors are present at the entry before the probe, so the theorem adds nothing beyond the data. It does not apply to the absence check, whose condition is `PRESENT(completion_receipt)`.
- [`undefined_guard_blocks_not_breach`](https://github.com/triel-lang/grammar/blob/09c25273e69d3987a12b2a75cfd4a2817b6acb2d/formal/core/TRIEL_Breach.thy#L369) (`TRIEL_Breach.thy`). Assumes `eval c (st π (j - 1)) = None`; shows `blocks c (st π (j - 1))` and `¬ forbidden s a c π j`. When the condition is undefined in the state before the action at entry j, the monitor blocks the action, and the action is not a breach: the 11 rows with condition U (BLOCK, PENDING).
- [`T3_present_not_monotone`](https://github.com/triel-lang/grammar/blob/09c25273e69d3987a12b2a75cfd4a2817b6acb2d/formal/core/TRIEL_Core.thy#L337) (`TRIEL_Core.thy`). An existence statement, with no assumption: `∃σ σ' x. σ ⊑ σ' ∧ eval (EPresent x) σ ≠ eval (EPresent x) σ'`. There are states σ ⊑ σ′ and a name x on which `PRESENT(x)` changes its value. This is why the absence check is unfit for item 6: its ALLOW, given while the receipt is absent, does not survive the arrival of a late recovery receipt. On the vectors: the absence check allows the probe at `01-…/pending` and blocks it at `01-…/recovered`, the later snapshot of the same journal.
- [`T3_default_not_monotone`](https://github.com/triel-lang/grammar/blob/09c25273e69d3987a12b2a75cfd4a2817b6acb2d/formal/core/TRIEL_Core.thy#L354) (`TRIEL_Core.thy`). Assumes `v ≠ w`; shows `Map.empty ⊑ [x ↦ v]`, `evalV (VDefault x (VConst w)) Map.empty = Some w`, `evalV (VDefault x (VConst w)) [x ↦ v] = Some v`, `eval (EEq (VDefault x (VConst w)) (VConst w)) Map.empty = Some True` and `eval (EEq (VDefault x (VConst w)) (VConst w)) [x ↦ v] = Some False`. A missing value read as a default w gives a definite answer that the arrival of the real value v ≠ w reverses: the reading that item 6 now excludes ("a missing `outcome` read as a default value").
- [`run_final`](https://github.com/triel-lang/grammar/blob/09c25273e69d3987a12b2a75cfd4a2817b6acb2d/formal/core/TRIEL_Exec.thy#L3445) (`TRIEL_Exec.thy`). Assumes `i < length (run sp obs)` and `decided (run sp obs ! i)`; shows `same_verdict (run sp obs ! i) (run sp (obs @ more) ! i) ∨ (∃j. run sp (obs @ more) = [LTimeOrder j]) ∨ (∃e. LTypes (Some e) ∈ set (run sp (obs @ more)))`. A decided line of the report stays the same when observations are appended, unless the longer trace is rejected for its time order or for the types of its data. A `MONITOR` line is always decided, and for it "the same" means that its list of decisions is extended, not revised (`same_verdict`); a BREACHED verdict is decided; a PENDING verdict and an invariant U are not. So the decision that is final is the one in the `MONITOR` line, not PENDING. The `LAST` line is printed by `Main.hs`, which selects it from the `MONITOR` lines; it is not a line of `run`.
- [`breach_certain_completions`](https://github.com/triel-lang/grammar/blob/09c25273e69d3987a12b2a75cfd4a2817b6acb2d/formal/core/TRIEL_Completions.thy#L133) (`TRIEL_Completions.thy`). Assumes `present_free c`, `eval c σ = Some True` and `completion σ σ'`; shows `eval c σ' = Some True`. For the 6 completed snapshots: the condition is true while `prior_confirmed_unexecuted` and `fresh_authorization` are absent, and stays true however they turn out.
- [`always_never_true`](https://github.com/triel-lang/grammar/blob/09c25273e69d3987a12b2a75cfd4a2817b6acb2d/formal/core/TRIEL_Invariants.thy#L45) (`TRIEL_Invariants.thy`). No assumption: `inv_eval (Always φ) π ≠ Some True`. Why both invariants are U, not T.

## What the vectors do not cover

- **Deadlines.** The clock of the vectors is fixed (every record and every snapshot is at 2026-10-25T00:00:00Z), so no deadline is tested: neither `complete_within` nor the status of item 8 (fulfilled, breached, pending). The integration checks of the description list two variants with a moving clock for item 8, "one where the register passes the deadline without a receipt (breached) and one where it does not (pending)"; they are not in the vectors and not here.
- **Item 7** (accepted duplicate risk, a separate new effect linked to the unresolved occurrence): the vectors have no case for it, and the integration checks list one as needed.
- **Item 9** (finality): not checked here. The scenarios of the two snapshots of a variant are separate traces; nothing here checks that what is decided at one snapshot stays the same at the later one.
- **No earlier attempt.** The branch in which no attempt was reserved before the dispatch (`prior_attempt_registered` false, condition F, ALLOW) is described and not exercised: every snapshot has a ticket.
- **The integration checks of VATE** (`fresh_pdp_evaluation`, `pep_atomic_check_and_reserve`, `signed_receipt_registration`) and the events of `interactions.json` (the late dispatch of attempt A, the answer `busy` of the live worker, the rejected repeated ticket) are not modelled.
- **The original operation.** VATE checks a completed result against the inventory of the original operation; the mapping compares the native outputs only with the inventory of the snapshot.

## Running it

From the root of this repository, with Python 3.12 and `lark==1.3.1`:

```bash
git clone https://github.com/triel-lang/grammar grammar && git -C grammar checkout 09c25273e69d3987a12b2a75cfd4a2817b6acb2d
git init vate && git -C vate fetch --depth 1 https://github.com/Poke-nushi/Verifiable-Agent-Trust-Envelope c7533ad70c20e71b7912cdf708f33220e49c1f00 && git -C vate checkout FETCH_HEAD
python3 -I -m unittest discover -s mapping -p 'test_*.py'
python3 -I mapping/map_vate.py --check
(cd grammar && ghc -O1 -ievaluator/generated -outputdir evaluator/build -o evaluator/triel-eval evaluator/Main.hs)
python3 -I grammar/parser/triel.py check specs/dispatch_rule.triel scenarios/dispatch/01-lost-response-recovery__with-unknown-observation__pending.scn --last
python3 -I compare/compare.py --check
```

## Licence

Apache-2.0 ([`LICENSE`](LICENSE)).
