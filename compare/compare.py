#!/usr/bin/env python3
"""
Build the comparison table COMPARISON.md from the committed expected reports
and the expected PEP conditions of VATE.

Usage (from the root of this repository, with the VATE repository checked out
in vate/ at the commit pinned in PINS):

    python3 -I compare/compare.py            # write COMPARISON.md
    python3 -I compare/compare.py --check    # compare with the committed COMPARISON.md

What is read:
  - scenarios/dispatch/*.scn and scenarios/absence/*.scn: the data of the entry
    before the probe (the factors of the table);
  - the .expected files next to them: the committed reports, which the
    workflow checks, character for character, against the output of the
    evaluator at the same commit;
  - from VATE, MANIFEST.json (its sha256 must be the one in PINS) and
    expected-pep-decision.json of each variant (its sha256 must be the one in
    MANIFEST.json). This is the only place where the expectations of VATE are
    read; mapping/map_vate.py never reads them.

The column "condition" is derived from the lines of the report, not printed by
the evaluator: ALLOW is F, BLOCK with PENDING is U, BLOCK with BREACHED is T.
This holds because the probe is the only dispatch in each trace, which is
checked here.

Exit codes: 0 done (with --check: the committed COMPARISON.md is the generated
one), 1 a difference with --check, 2 an input that does not match PINS or
MANIFEST.json, or that is not of the expected form.
"""
import argparse
import difflib
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FACTORS = ("prior_attempt_registered", "prior_completed", "prior_confirmed_unexecuted",
           "prior_fenced", "fresh_authorization")
ASSUMPTION_SUFFIX = "__assumed-fresh-authorization"


class CompareError(Exception):
    pass


def read_pins(path: Path) -> dict:
    pins = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            key, sep, value = line.partition("=")
            if not sep:
                raise CompareError(f"{path}: not KEY=VALUE: {line}")
            pins[key.strip()] = value.strip()
    return pins


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# --- Scenarios --------------------------------------------------------------------

def tokens(text: str):
    text = "\n".join(line.split(";", 1)[0] for line in text.splitlines())
    return re.findall(r'\(|\)|"[^"]*"|[^\s()"]+', text)


def sexp(text: str):
    toks = tokens(text)
    pos = 0

    def one():
        nonlocal pos
        t = toks[pos]
        pos += 1
        if t == "(":
            xs = []
            while toks[pos] != ")":
                xs.append(one())
            pos += 1
            return xs
        return t

    x = one()
    if pos != len(toks):
        raise CompareError("text after the scenario")
    return x


def probe_state(path: Path):
    """The entry of the probe and the data of the entry before it, as
    {factor: 'T' | 'F'}; the probe must be the only action of the trace."""
    scn = sexp(path.read_text(encoding="utf-8"))
    entries = [e for e in scn[3:] if isinstance(e, list) and e and e[0] == "entry"]
    acts = [i for i, e in enumerate(entries) if isinstance(e[2], list) and e[2][:1] == ["act"]]
    if acts != [len(entries) - 1] or entries[-1][2] != ["act", "pep", "dispatch", "must_not"]:
        raise CompareError(f"{path}: the probe is not the only dispatch, at the last entry")
    data = entries[-2][3]
    values = {}
    for f in data[1:]:
        if f[1][0] != "bool":
            raise CompareError(f"{path}: {f[0]} is not a Boolean")
        values[f[0]] = "T" if f[1][1] == "true" else "F"
    return len(entries) - 1, values


# --- Reports ----------------------------------------------------------------------

def report(path: Path, j: int):
    """(verdict, monitor decision, derived condition) of TERM 1 at the probe j."""
    lines = path.read_text(encoding="utf-8").splitlines()
    term = [ln for ln in lines if ln.startswith("TERM 1 MUST_NOT pep dispatch : ")]
    mon = [ln for ln in lines if ln.startswith("MONITOR 1 : ")]
    last = lines[-1] if lines else ""
    if len(term) != 1 or len(mon) != 1:
        raise CompareError(f"{path}: no TERM 1 or MONITOR 1 line")
    verdict = term[0].split(" : ", 1)[1]
    m = re.fullmatch(rf"MONITOR 1 : ENTRY {j} (BLOCK|ALLOW)", mon[0])
    if not m or last != f"LAST ENTRY {j} : MONITOR 1 {m.group(1)}":
        raise CompareError(f"{path}: the monitor does not decide on the probe, entry {j}, alone")
    decision = m.group(1)
    if decision == "ALLOW" and verdict == "PENDING":
        condition = "F"
    elif decision == "BLOCK" and verdict == "PENDING":
        condition = "U"
    elif decision == "BLOCK" and re.fullmatch(r"BREACHED \d+", verdict):
        condition = "T"
    else:
        raise CompareError(f"{path}: verdict {verdict} with {decision}")
    return verdict, decision, condition


# --- VATE ---------------------------------------------------------------------------

class Expectations:
    def __init__(self, root: Path, manifest_sha256: str):
        self.root = root
        raw = (root / "MANIFEST.json").read_bytes()
        if sha256(raw) != manifest_sha256:
            raise CompareError(f"sha256 of MANIFEST.json is {sha256(raw)}, PINS has {manifest_sha256}")
        self.manifest = json.loads(raw)["files"]
        self.read_files = [("MANIFEST.json", sha256(raw))]
        self.cache = {}

    def phase(self, case: str, variant: str, snapshot: str) -> dict:
        rel = f"cases/{case}/{variant}/expected-pep-decision.json"
        if rel not in self.cache:
            entry = self.manifest.get(rel)
            raw = (self.root / rel).read_bytes()
            if entry is None or sha256(raw) != entry.get("sha256") or len(raw) != entry.get("bytes"):
                raise CompareError(f"{rel}: sha256 or size differs from MANIFEST.json")
            self.read_files.append((rel, sha256(raw)))
            self.cache[rel] = json.loads(raw)
        phases = self.cache[rel].get("phases", {})
        if snapshot not in phases:
            raise CompareError(f"{rel}: no phase {snapshot}")
        return phases[snapshot]


def expected_condition(phase: dict):
    """The condition that the correspondence of MAPPING.md asks for."""
    reason = phase.get("reason", "")
    if phase.get("comparison_expectation") == "hold_same_logical_effect":
        if "remains unresolved" in reason:
            return "U"
        if "is completed" in reason:
            return "T"
    if phase.get("comparison_expectation") == "conditional_continuation":
        return "U"          # BLOCK without a fresh authorization
    return None


# --- The table ---------------------------------------------------------------------

def rows(pins: dict):
    exp = Expectations(ROOT / "vate" / pins["VATE_VECTORS"], pins["VATE_MANIFEST_SHA256"])
    out = []
    for scn in sorted((ROOT / "scenarios" / "dispatch").glob("*.scn")):
        name = scn.stem
        assumed = name.endswith(ASSUMPTION_SUFFIX)
        base = name[: -len(ASSUMPTION_SUFFIX)] if assumed else name
        case, variant, snapshot = base.split("__")
        j, data = probe_state(scn)
        verdict, decision, condition = report(scn.with_suffix(".expected"), j)
        absence = None
        if not assumed:
            aj, _ = probe_state(ROOT / "scenarios" / "absence" / f"{name}.scn")
            if aj != j:
                raise CompareError(f"{name}: the probes of the two scenarios differ")
            absence = report(ROOT / "scenarios" / "absence" / f"{name}.expected", j)
        phase = exp.phase(case, variant, snapshot)
        out.append({"case": case, "variant": variant, "snapshot": snapshot, "assumed": assumed,
                    "j": j, "factors": " ".join(data.get(f, "–") for f in FACTORS),
                    "verdict": verdict, "decision": decision, "condition": condition,
                    "absence": absence, "phase": phase})
    return out, exp


def build(pins: dict) -> str:
    table, exp = rows(pins)
    main = [r for r in table if not r["assumed"]]
    if len(main) != 17:
        raise CompareError(f"{len(main)} snapshots, not 17")
    hold = [r for r in main if r["phase"]["comparison_expectation"] == "hold_same_logical_effect"]
    unresolved = [r for r in hold if expected_condition(r["phase"]) == "U"]
    completed = [r for r in hold if expected_condition(r["phase"]) == "T"]
    other = [r for r in main if r not in hold]

    def n(rs, pred):
        return sum(1 for r in rs if pred(r))

    lines = [
        "# Comparison with the expected PEP conditions of VATE",
        "",
        "Generated by `compare/compare.py`; do not edit. The workflow checks that this file is what the "
        "script prints at the same commit.",
        "",
        f"Sources: the committed scenarios and expected reports of this repository, and "
        f"`expected-pep-decision.json` of the VATE vectors at {pins['VATE_COMMIT']} "
        f"(`{pins['VATE_VECTORS']}`), each checked against `MANIFEST.json`, whose sha256 is pinned in `PINS`. "
        "The workflow checks every expected report, character for character, against the output of "
        "`triel check SPEC TRACE --last` at the same commit, and its exit code.",
        "",
        "Columns:",
        "",
        "- *Factors*: the data of the entry before the probe, in the order `prior_attempt_registered`, "
        "`prior_completed`, `prior_confirmed_unexecuted`, `prior_fenced`, `fresh_authorization`; "
        "T, F, or – for absent. Read from the committed scenario.",
        "- *Condition*: derived from the lines of the report, not printed by the evaluator: ALLOW is F, "
        "BLOCK with PENDING is U, BLOCK with BREACHED is T. This holds because the probe is the only "
        "`dispatch` in each trace.",
        "- *Monitor* and *Verdict*: the decision of `MONITOR 1` on the probe and the verdict of `TERM 1` "
        "(`specs/dispatch_rule.triel`).",
        "- *Absence check, for contrast*: the decision of the monitor of `specs/absence_check.triel` on the "
        "same probe, with its verdict. It is not a decision of the rule of item 6.",
        "- *Matches*: whether the report is the one that the correspondence of `MAPPING.md` asks for: BLOCK "
        "for `hold_same_logical_effect`, condition U for a reason that says the earlier attempt remains "
        "unresolved, condition T for a reason that says the earlier effect is completed, and BLOCK with "
        "condition U for `conditional_continuation` without a fresh authorization.",
        "",
        "| Snapshot | VATE expectation | VATE reason | J | Factors | Condition | Monitor | Verdict "
        "| Absence check, for contrast | Matches |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in table:
        ph = r["phase"]
        want = expected_condition(ph)
        if r["assumed"]:
            snap = f"{r['case']}/{r['variant']}/{r['snapshot']} — assumption: fresh_authorization = true [1]"
            matches = "— (assumption)"
            absence = "—"
        else:
            snap = f"{r['case']}/{r['variant']}/{r['snapshot']}"
            ok = r["decision"] == "BLOCK" and r["condition"] == want
            matches = "yes" if ok else "**no**"
            av, ad, _ = r["absence"]
            absence = f"{ad} ({av})"
        expectation = ph["comparison_expectation"]
        if ph.get("additional_requirements"):
            expectation += " (additional requirements: " + ", ".join(ph["additional_requirements"]) + ")"
        lines.append(f"| {snap} | {expectation} | {ph.get('reason', '')} | {r['j']} | {r['factors']} "
                     f"| {r['condition']} | {r['decision']} | {r['verdict']} | {absence} | {matches} |")
    lines += [
        "",
        "[1] An assumption, not read from the journal: VATE marks `fresh_pdp_evaluation` as `not_checked`, "
        "and the mapping does not count the new local admission of the `handoff` record as a fresh "
        "authorization (`MAPPING.md`, decision 5). ALLOW here means only that the condition of the rule is "
        "false under this assumption. The two other `additional_requirements` of VATE, the PEP-side atomic "
        "check and reservation and the registration of a signed receipt, are not modelled by the rule, and "
        "ALLOW does not replace them.",
        "",
        "## Counts",
        "",
        f"- Snapshots: {len(main)}. VATE expects `hold_same_logical_effect` in {len(hold)}, and "
        + ", ".join(f"`{e}` in {n(other, lambda r, e=e: r['phase']['comparison_expectation'] == e)}"
                    for e in sorted({r['phase']['comparison_expectation'] for r in other}))
        + ".",
        f"- The monitor of the rule blocks the probe in {n(main, lambda r: r['decision'] == 'BLOCK')} of "
        f"{len(main)} snapshots. A constant BLOCK would agree with the VATE decision in "
        f"{len(hold)} of {len(main)} snapshots: the decision alone carries little information.",
        f"- Reason \"remains unresolved\": {len(unresolved)} snapshots; condition U in "
        f"{n(unresolved, lambda r: r['condition'] == 'U')}, verdict PENDING in "
        f"{n(unresolved, lambda r: r['verdict'] == 'PENDING')}.",
        f"- Reason \"is completed\": {len(completed)} snapshots; condition T in "
        f"{n(completed, lambda r: r['condition'] == 'T')}, verdict BREACHED in "
        f"{n(completed, lambda r: r['verdict'].startswith('BREACHED'))}.",
    ]
    for r in other:
        lines.append(
            f"- `{r['phase']['comparison_expectation']}` ({r['case']}/{r['variant']}/{r['snapshot']}): "
            f"condition {r['condition']}, monitor {r['decision']} without a fresh authorization"
            + "".join(f"; condition {a['condition']}, monitor {a['decision']} under the assumption "
                      "fresh_authorization = true"
                      for a in table if a["assumed"] and a["snapshot"] == r["snapshot"]
                      and a["variant"] == r["variant"]) + ".")
    lines += [
        f"- Rows that match the correspondence of `MAPPING.md`: "
        f"{n(main, lambda r: r['decision'] == 'BLOCK' and r['condition'] == expected_condition(r['phase']))} "
        f"of {len(main)}.",
        f"- Absence check, for contrast: ALLOW in {n(main, lambda r: r['absence'][1] == 'ALLOW')} of "
        f"{len(main)} snapshots; it differs from `hold_same_logical_effect` in "
        f"{n(hold, lambda r: r['absence'][1] == 'ALLOW')} of {len(main)}, all with a reason that says the "
        f"earlier attempt remains unresolved ({n(unresolved, lambda r: r['absence'][1] == 'ALLOW')} of "
        f"{len(unresolved)}), and it allows the probe in "
        + ", ".join(f"`{r['snapshot']}` ({r['phase']['comparison_expectation']})"
                    for r in other if r["absence"][1] == "ALLOW")
        + ", counted separately.",
        "",
        "## VATE files read",
        "",
    ]
    lines += [f"- `{rel}` sha256 `{digest}`" for rel, digest in exp.read_files]
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="compare with the committed COMPARISON.md")
    args = ap.parse_args(argv)
    try:
        text = build(read_pins(ROOT / "PINS"))
    except (CompareError, OSError, KeyError, ValueError, IndexError) as e:
        print(f"compare: {e}", file=sys.stderr)
        return 2
    target = ROOT / "COMPARISON.md"
    if args.check:
        have = target.read_text(encoding="utf-8") if target.is_file() else ""
        if have != text:
            sys.stdout.writelines(difflib.unified_diff(
                have.splitlines(True), text.splitlines(True), "committed/COMPARISON.md", "generated/COMPARISON.md"))
            print("compare: COMPARISON.md differs from the generated table")
            return 1
        print("compare: COMPARISON.md is the generated table")
        return 0
    target.write_text(text, encoding="utf-8")
    print(f"compare: wrote {target.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
