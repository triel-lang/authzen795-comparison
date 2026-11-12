# Mapping of the VATE journals to TRIEL scenarios

This file records every decision by which `mapping/map_vate.py` turns the journals of the VATE vectors into scenarios of `specs/dispatch_rule.triel` and `specs/absence_check.triel`, and why. It was committed, with the tables below, before the evaluator was first run on the scenarios and before `compare/compare.py`, the only code that reads the expected PEP conditions of VATE (README.md, "How the comparison was made").

Item 6 of the Failure semantics of openid/authzen#795, as read on 2026-11-12, is quoted in README.md. Its words "an earlier attempt", "authoritative confirmation", "fenced" and "fresh authorization" are read here as stated below; README.md, "Where the prose admits two readings", lists the places where the prose admits another reading.

## Inputs

- The VATE repository at the commit in `PINS`, folder `reference/authzen-receipt-vectors`. The sha256 of `MANIFEST.json` is pinned in `PINS`, because the manifest does not list itself.
- The script finds the variants by the keys of `MANIFEST.json` that end with `/input-history.json` (eight), reads each `input-history.json` for the order of the snapshots, and one `<snapshot>-history.json` per snapshot (seventeen). Every file it reads must have the sha256 and size listed in `MANIFEST.json`.
- It never opens the expected files of VATE (`expected-*.json`), `interactions.json`, `operation.json`, `context.json`, `case.json` or `VECTORS.json`. The expected PEP condition of VATE is a function of the same effect state as the rule of item 6, so reading it here would make the comparison circular. Only `compare/compare.py` reads `expected-pep-decision.json`, after the mapping and the expected reports were committed.
- No VATE code is run or imported; the JSON is read by the script's own code, with `python3 -I`. Signatures, `proof` and `status` fields and the chain of `previous` hashes are not checked.

From a history the script reads `observed_at`, `inventory`, and from each record (base64 JSON in `records[].raw`) `kind`, `at`, `index`, and in `body` only `attempt_id`, `generation`, `runtime`, `outputs` (`native`), `effect_state`, `worker_excluded`, `retained_attempts` (`handoff`), and, for the comment line only, `reason` (`denied`) and `phase` (`execution_clock`).

## Shape of a scenario

- One instance of `specs/dispatch_rule.triel` is one logical effect: the `operation_id` of the journal (`operation-one` in every history).
- Entry 0, the activation entry, is the record `registered`: the operation is registered and no attempt is reserved yet. The monitor decides nothing on the activation entry, so the probe comes after it.
- Each later record of the journal is one entry `(tick)`, in journal order: `ticket`, `status`, `accepted`, `execution_clock`, `native`, `unknown`, `observed`, `handoff`, `denied`. No factor has `MAX_AGE`, so `(arrive …)` would change nothing; every record is a tick, with a comment line naming the record and the fields the mapping reads.
- The last entry is the probe `(act pep dispatch must_not)`: a dispatch of another attempt of the same logical effect, requested after the records of the snapshot. It is not the dispatch of an attempt the journal already reserved.
- Times: the time of an entry is the field `at` of its record, the time of the probe is `observed_at` of the snapshot. In all 17 histories both are 1792886400, written `"2026-10-25T00:00:00Z"`. Equal times are accepted by the evaluator; only decreasing times are rejected. No time is invented.
- Data: the `data` of every entry is the complete data after that record, so a value is repeated in every later entry; a factor not listed is absent. The probe repeats the data of the last record. The monitor reads the state of the entry before the probe, so the assumption of decision 5 is put in the data of the last record, not only in the data of the probe.
- The specification is named from the root of grammar, `(spec "../specs/dispatch_rule.triel")`, which `parser/triel.py` and `parser/triel_eval.py` resolve against the root of grammar (`find_spec`); `triel check` requires it to be the same file as its argument `SPEC`. No absolute path is written and no specification is copied into grammar.

## Decisions

Each decision gives what is chosen and why. "Absent" means the factor is not in the data of the entry, which TRIEL reads as undefined (U).

**0. An earlier attempt is registered.** `prior_attempt_registered` is false at the record `registered` and true from the first record `ticket` on. A `ticket` carries an `attempt_id` and a `generation`: it is the reservation of an attempt in the sense of the second sentence of item 6 ("checks the register for the logical-effect identifier and reserves it in one atomic step"). The factor is not tied to `accepted`: the snapshots `pending` of cases 1 and 3 and the snapshot `fenced` have no `accepted` record, and they do have a reserved attempt. The factor is never absent, so the condition of the rule has no `PRESENT` (the assumption `present_free` of `monitor_sound_completions` holds) and the rule does not block the first dispatch: before any ticket the condition is false. Every snapshot has a ticket, so this branch is described and not exercised by the vectors.

**1. Completed.** `prior_completed` is true from the record `native` of an attempt that has an earlier `accepted` record in the journal, when the `outputs` of that `native` record are equal to the `inventory` of the snapshot. VATE also requires the result to match the original operation (its target files); the script does not read `operation.json` and does not check this. This difference is repeated in README.md.

**2. `observed` and `handoff` that say `completed` (case 1, case 4).** Completion is derived from `accepted`, `native` and `inventory` (decision 1), not from the field `effect_state` of `observed` or `handoff`: that field is computed by the provider with a VATE function, and taking it would put a VATE judgement in place of the mapping. In every snapshot where a record says `completed`, decision 1 gives true as well.

**3. Confirmation of non-execution.** `prior_confirmed_unexecuted` is true when the last `handoff` record says `effect_state: confirmed_unexecuted` and lists in `retained_attempts` every attempt reserved so far. It is a statement of the provider, taken as written; TRIEL does not derive it, and the script does not check it against the journal.

- *Does a later attempt cancel it?* The confirmation is not withdrawn: it stays true of the attempt it names, and the record stays in the journal. But the factor says that the earlier attempts a new dispatch would follow are confirmed not to have executed. A `ticket` after the `handoff` that reserves an attempt the `handoff` does not list starts an attempt that the confirmation does not cover. From that ticket on, `prior_confirmed_unexecuted` is absent, and so is `prior_fenced` (decision 4), and `prior_completed` is no longer false (decision 8); it becomes true at a `native` record by decision 1. A later `accepted` therefore does not matter for this: the factor is already absent at the ticket that precedes it.
- *Consequence.* In the snapshot `fenced-handoff/completed` the confirmation names the attempt of generation 1 (entry 2), the ticket of generation 2 comes at entry 5, and the attempt of generation 2 completes at entry 10. From entry 5 on the confirmation is absent, so `prior_completed` and `prior_confirmed_unexecuted` are never both true, and the invariant `consistent_prior_state` stays U in every scenario. Had the confirmation been kept after the ticket of generation 2, the data of entries 5–11 would differ: `T F T T –` at entries 5–9 and `T T T T –` at entries 10–11 (in the order of the table below), and the invariant would be F from entry 10. It would then report the mixing of a statement about attempt 1 with a statement about the logical effect, not an inconsistent provider. The verdict at the probe would not change (decision 1 makes the condition true either way). Item 6 itself asks for the narrower reading: at entries 5–9 the attempt of generation 2 is reserved and unresolved, and a confirmation kept from generation 1 would let a fresh authorization open a third dispatch (with `fresh_authorization` true, `T AND (F OR NOT (T AND T AND T))` = F, ALLOW), while with the coverage condition the condition stays U and the monitor blocks.

**4. The earlier attempt is fenced.** `prior_fenced` is the value of `worker_excluded` in the last `handoff` record, while that record covers every attempt reserved so far (decision 3); without a `handoff` record it is absent. What is taken as fencing is both signs together: the `handoff` record, by which the provider moves the operation to a new generation (the next `ticket` has `generation` 2, and a late attempt of generation 1 gets `denied` with `reason: old_generation`), and its field `worker_excluded`, by which it states that the old worker is excluded. `worker_excluded` is true in every `handoff` record, unresolved ones included (eight snapshots have one; there are seven different records, since `fenced` and `fenced-handoff/completed` contain the same one), so on its own it distinguishes nothing; it matters only where `prior_confirmed_unexecuted` is true, that is in the snapshot `fenced`. The record `denied` with `old_generation` is not used as a sign: the snapshot `fenced` has none. The field `worker_excluded` of `accepted` and `observed` records is not read. This is a statement of the provider; TRIEL does not derive it.

**5. Fresh authorization.** `fresh_authorization` is absent in every scenario generated from a journal. The new local admission in `request_raw.authorization` of a `handoff` record is not counted as a fresh authorization: VATE marks `fresh_pdp_evaluation` as `not_checked`, and case 4 is about exactly this, a new local admission that does not reopen the effect. One more scenario is generated, for the snapshot `fenced` of case 3 only, with `fresh_authorization = true` in the data of the last record and of the probe: `scenarios/dispatch/03-confirmed-nonexecution-handoff__fenced-handoff__fenced__assumed-fresh-authorization.scn`. It is marked as an assumption in its header, in COMPARISON.md and in README.md.

**6. `unknown` records.** A record `unknown` gives no value to any factor; the value "unknown" does not exist in the mapping. A factor that no record establishes is absent, and TRIEL reads it as U. This is "`unknown` read as in item 1": `unknown` means that no result is known, which is the absence of the factor. An `unknown` record does not remove a value that other records establish: in `01-lost-response-recovery/with-unknown-observation/recovered` the `native` record (entry 6) precedes the caller's `unknown` record (entry 7), and `prior_completed` stays true, as item 3 keeps the earlier `unknown` record next to the evidence that resolves it. The status "unresolved" of a `handoff` record is the same thing: it sets no factor (decision 8).

**7. The logical effect and the two runtimes.** One instance of the specification is one logical effect, and one subject, `pep`, stands for every runtime that may dispatch it: `runtime-a` and `runtime-b` of case 3 are both `pep`. Item 6 is stated per logical effect ("A new PERMIT never reopens an occurrence"): a dispatch by either runtime is a dispatch of the same effect, so two subjects with two copies of the prohibition would make the rule per runtime, which item 6 is not. What is lost: the trace does not say which runtime dispatches, the probe carries no attempt identifier, and the language does not see attempts at all. The distinction between an attempt and the logical effect is made by the script, in which attempts the factors speak about (decisions 0, 1, 3, 4), not by TRIEL. The events of `interactions.json` (the late dispatch of attempt A, the answer `busy` of the live worker, the rejected repeated ticket) are not mapped; the `denied` record that is in the journal is an ordinary tick.

**8. When a factor is false and when it is absent.** Held in every scenario:

- `prior_completed` is true by decision 1. It is false only when the last `handoff` record covers every reserved attempt and says `confirmed_unexecuted`, and decision 1 gives no completion. Otherwise it is absent.
- `prior_confirmed_unexecuted` is true only by decision 3. With `effect_state` `unresolved` or `completed` in the `handoff` record, without a `handoff` record, or after a ticket the `handoff` does not cover, it is absent, not false: the provider does not state that the attempt executed.
- `prior_fenced` follows decision 4; without a `handoff` record, or after a ticket the `handoff` does not cover, it is absent.
- `prior_attempt_registered` is always true or false (decision 0). `fresh_authorization` is absent, except in the one scenario of decision 5.

*Hand check, before the first run.* With `prior_confirmed_unexecuted` false instead of absent in an unresolved snapshot (for example `02-accepted-interrupted/zero-effects/after-handoff`, data at entry 5: `prior_attempt_registered` true, `prior_fenced` true, the other three absent), the condition would be `T AND (U OR NOT (F AND T AND U))` = `T AND (U OR NOT F)` = `T AND T` = T, and the verdict BREACHED instead of PENDING: the absence of a positive statement would be read as a statement that the attempt executed. With absence, the condition is `T AND (U OR NOT (U AND T AND U))` = `T AND (U OR U)` = U.

## The absence check

`specs/absence_check.triel` has one factor, `completion_receipt`, which is present, and true, exactly when `prior_completed` is true in the scenario of the same name in `scenarios/dispatch` (decision 1), and absent otherwise. Its scenarios have the same entries, times and comments as those of the rule.

## Correspondence with the expected PEP conditions of VATE

Committed before `compare/compare.py`, which applies it. The labels and reasons of VATE named here were known beforehand (README.md, "How the comparison was made").

| VATE expectation | TRIEL report on the probe |
|---|---|
| `hold_same_logical_effect` | the monitor of `TERM 1` blocks the probe: `MONITOR 1 : ENTRY J BLOCK`, `LAST ENTRY J : MONITOR 1 BLOCK` |
| reason: the effect remains unresolved | condition U: verdict `PENDING`, monitor `BLOCK` |
| reason: the effect is completed | condition T: verdict `BREACHED` at the probe, monitor `BLOCK`. A dispatch here would violate item 6; the breach is the verdict on the hypothetical dispatch, not a failure of VATE |
| `conditional_continuation` (the snapshot `fenced` only) | `BLOCK` without a fresh authorization (condition U); `ALLOW` with it (condition F) only under the assumption of decision 5 |

The condition column is derived from the report, not printed by the evaluator: `ALLOW` means F; `BLOCK` with `PENDING` means U; `BLOCK` with `BREACHED` means T. This holds because the probe is the only `dispatch` in each trace.

## Hand derivation of the expected reports

The expected reports in `scenarios/*/*.expected` were written by hand from this table, the text of the two specifications and the scenarios; no program computed them. In every scenario the header lines come from the translator (`SPEC`, `METADATA` in source order), and `ACTIVATION OK`, `BLOCK OK`, `TYPES OK` follow: there is no deadline, the block is one prohibition, and every value is a Boolean. J is the entry of the probe; the condition is read in the state of entry J − 1. Kleene connectives: `T AND U` = U, `F OR U` = U, `NOT U` = U, `F AND U` = F.

Factors at entry J − 1, in the order `prior_attempt_registered`, `prior_completed`, `prior_confirmed_unexecuted`, `prior_fenced`, `fresh_authorization` (T, F, or – for absent):

| Snapshot (case/variant/snapshot) | J | Factors | Condition | Verdict | Monitor | Absence check: `completion_receipt`, condition, monitor |
|---|---|---|---|---|---|---|
| 01/with-unknown-observation/pending | 2 | T – – – – | U | PENDING | BLOCK | –, F, ALLOW |
| 01/with-unknown-observation/recovered | 10 | T T – T – | T | BREACHED 1792886400 | BLOCK | T, T, BLOCK |
| 01/without-prior-receipt/pending | 2 | T – – – – | U | PENDING | BLOCK | –, F, ALLOW |
| 01/without-prior-receipt/recovered | 9 | T T – T – | T | BREACHED 1792886400 | BLOCK | T, T, BLOCK |
| 02/partial-effects/interrupted | 6 | T – – – – | U | PENDING | BLOCK | –, F, ALLOW |
| 02/partial-effects/after-handoff | 7 | T – – T – | U | PENDING | BLOCK | –, F, ALLOW |
| 02/zero-effects/interrupted | 5 | T – – – – | U | PENDING | BLOCK | –, F, ALLOW |
| 02/zero-effects/after-handoff | 6 | T – – T – | U | PENDING | BLOCK | –, F, ALLOW |
| 03/fenced-handoff/pending | 2 | T – – – – | U | PENDING | BLOCK | –, F, ALLOW |
| 03/fenced-handoff/fenced | 3 | T F T T – | U | PENDING | BLOCK | –, F, ALLOW |
| 03/fenced-handoff/fenced, assumption `fresh_authorization = true` | 3 | T F T T T | F | PENDING | ALLOW | (not generated) |
| 03/fenced-handoff/completed | 11 | T T – – – | T | BREACHED 1792886400 | BLOCK | T, T, BLOCK |
| 03/live-worker/pending | 2 | T – – – – | U | PENDING | BLOCK | –, F, ALLOW |
| 03/live-worker/completed | 7 | T T – – – | T | BREACHED 1792886400 | BLOCK | T, T, BLOCK |
| 04/completed/original | 7 | T T – – – | T | BREACHED 1792886400 | BLOCK | T, T, BLOCK |
| 04/completed/new-admission | 8 | T T – T – | T | BREACHED 1792886400 | BLOCK | T, T, BLOCK |
| 04/unresolved/original | 5 | T – – – – | U | PENDING | BLOCK | –, F, ALLOW |
| 04/unresolved/new-admission | 6 | T – – T – | U | PENDING | BLOCK | –, F, ALLOW |

Derivations:

- U rows: `T AND (U OR NOT (U AND x AND U))` = `T AND (U OR U)` = U for x = T or –.
- T rows: `T AND (T OR …)` = T. The prohibition is breached at the probe, whose time is 1792886400.
- `fenced`: `T AND (F OR NOT (T AND T AND U))` = `T AND (F OR U)` = U.
- `fenced` with the assumption: `T AND (F OR NOT (T AND T AND T))` = `T AND (F OR F)` = F, so the monitor allows the probe and the verdict stays PENDING.
- The invariant `consistent_prior_state` is U in all 18 scenarios: `prior_completed` and `prior_confirmed_unexecuted` are both present only at entries 2–3 of the two scenarios of the snapshot `fenced` and at entries 2–4 of `fenced-handoff/completed`, where they are F and T, so `NOT (F AND T)` = T there; at every other entry one of them is absent and the formula is U or T. It is never F, and `ALWAYS` is never T.
- Absence check: `PRESENT(completion_receipt)` is always defined, F when the factor is absent and T when it is present. The invariant `receipt_known` is U in all 17 scenarios: `completion_receipt == completion_receipt` is U where the factor is absent and T where it is present, never F.
- Exit codes (`grammar/evaluator/README.md`, Exit codes, with `--last`): 3 when the `LAST` line has `BLOCK`, 0 when it has `ALLOW`.

Counts: the rule gives U in the 10 snapshots that remain unresolved and in `fenced`, T in the 6 completed snapshots, and BLOCK in all 17; a rule that always blocks would give the same 17 decisions. The absence check allows the probe in the 10 unresolved snapshots and in `fenced`, and blocks it in the 6 completed ones.
