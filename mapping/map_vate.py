#!/usr/bin/env python3
"""
Translate the journals of the VATE vectors for openid/authzen#795 into TRIEL
scenarios (grammar/examples/core/README.md, Scenarios), by the decisions of
MAPPING.md.

Usage (from the root of this repository, with the VATE repository checked out
in vate/ at the commit pinned in PINS):

    python3 -I mapping/map_vate.py            # write scenarios/ (the .scn files)
    python3 -I mapping/map_vate.py --check    # compare with the committed .scn files

What is read, and nothing else:
  - MANIFEST.json of the vectors; its sha256 must be the one in PINS;
  - for each of the eight variants, the keys of MANIFEST.json that end with
    /input-history.json: its input-history.json (the order of the snapshots)
    and one <snapshot>-history.json per snapshot.
Each file read must have the sha256 and the size that MANIFEST.json gives.
The expected files of VATE, interactions.json, operation.json, context.json,
case.json and VECTORS.json are never opened: the expected PEP condition of VATE
is a function of the same effect state as the rule of item 6, so reading it
here would make the comparison circular. No VATE code is run or imported.
Signatures and the chain of `previous` hashes are not checked.

What is written: one scenario per snapshot for specs/dispatch_rule.triel
(scenarios/dispatch) and for specs/absence_check.triel (scenarios/absence),
17 + 17, and one more for the snapshot `fenced` of case 3 under the assumption
fresh_authorization = true (MAPPING.md, decision 5): 35 scenarios. The expected
reports (.expected, .exitcode) are written by hand, not by this script.

Exit codes: 0 done (with --check: the committed scenarios are the generated
ones), 1 a difference with --check, 2 an input that does not match PINS or
MANIFEST.json, or that is not of the expected form.
"""
import argparse
import base64
import binascii
import datetime
import difflib
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DISPATCH_SPEC = "../specs/dispatch_rule.triel"   # relative to the root of grammar/
ABSENCE_SPEC = "../specs/absence_check.triel"

# Factors of specs/dispatch_rule.triel, in the order of its FACTORS block.
DISPATCH_FACTORS = ("prior_attempt_registered", "prior_completed",
                    "prior_confirmed_unexecuted", "prior_fenced", "fresh_authorization")

# The extra scenario of MAPPING.md, decision 5.
ASSUMPTION_CASE = ("03-confirmed-nonexecution-handoff", "fenced-handoff", "fenced")
ASSUMPTION_SUFFIX = "assumed-fresh-authorization"

NAME_PATTERN = r"[0-9a-z][0-9a-z-]*"


class MappingError(Exception):
    pass


def read_pins(path: Path) -> dict:
    pins = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, sep, value = line.partition("=")
        if not sep:
            raise MappingError(f"{path}: not KEY=VALUE: {line}")
        pins[key.strip()] = value.strip()
    return pins


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class Vectors:
    """The VATE vectors, read only through MANIFEST.json and the journals."""

    def __init__(self, root: Path, manifest_sha256: str):
        self.root = root
        self.read_files = []          # (path relative to the vectors, sha256), in order
        raw = (root / "MANIFEST.json").read_bytes()
        if sha256(raw) != manifest_sha256:
            raise MappingError(f"sha256 of MANIFEST.json is {sha256(raw)}, PINS has {manifest_sha256}")
        self.read_files.append(("MANIFEST.json", sha256(raw)))
        manifest = json.loads(raw)
        if not isinstance(manifest, dict) or not isinstance(manifest.get("files"), dict):
            raise MappingError("MANIFEST.json has no object `files`")
        self.manifest = manifest["files"]

    def read(self, rel: str):
        """A journal file: input-history.json or <snapshot>-history.json, and
        nothing else, checked against MANIFEST.json."""
        if not rel.endswith("-history.json"):
            raise MappingError(f"refusing to read {rel}: only journal files are read")
        entry = self.manifest.get(rel)
        if entry is None:
            raise MappingError(f"{rel} is not listed in MANIFEST.json")
        raw = (self.root / rel).read_bytes()
        if sha256(raw) != entry.get("sha256") or len(raw) != entry.get("bytes"):
            raise MappingError(f"{rel}: sha256 or size differs from MANIFEST.json")
        self.read_files.append((rel, sha256(raw)))
        return json.loads(raw)

    def variants(self):
        """(case, variant, directory, [snapshot names]) in the order of the
        keys of MANIFEST.json that end with /input-history.json, sorted."""
        keys = sorted(k for k in self.manifest if k.endswith("/input-history.json"))
        out = []
        for k in keys:
            directory = k[: -len("/input-history.json")]
            meta = self.read(k)
            snaps = meta.get("snapshots")
            case, variant = meta.get("case"), meta.get("variant")
            if directory != f"cases/{case}/{variant}":
                raise MappingError(f"{k}: case and variant do not name its directory")
            if not (isinstance(snaps, list) and snaps and all(isinstance(s, str) and re.fullmatch(NAME_PATTERN, s) for s in snaps)):
                raise MappingError(f"{k}: snapshots is not a list of names")
            out.append((case, variant, directory, snaps))
        return out


# --- The records of a journal ---------------------------------------------------

def decode_record(r) -> dict:
    try:
        x = json.loads(base64.b64decode(r["raw"], validate=True))
    except (KeyError, TypeError, binascii.Error, ValueError) as e:
        raise MappingError(f"a record that is not base64 JSON: {e}") from None
    if not isinstance(x, dict) or not isinstance(x.get("kind"), str) or not isinstance(x.get("at"), int):
        raise MappingError("a record without kind or at")
    if not isinstance(x.get("body", {}), dict):
        raise MappingError("a record whose body is not an object")
    return x


def journal(history) -> list:
    if not isinstance(history, dict) or not isinstance(history.get("records"), list):
        raise MappingError("a history without records")
    records = [decode_record(r) for r in history["records"]]
    if [x.get("index") for x in records] != list(range(1, len(records) + 1)):
        raise MappingError("the records are not numbered 1, 2, ... in order")
    if not records or records[0]["kind"] != "registered":
        raise MappingError("the first record is not `registered`")
    return records


def body(x) -> dict:
    return x.get("body", {})


def factors(prefix: list, inventory) -> dict:
    """The data of the entry of the last record of `prefix`: the factors of
    specs/dispatch_rule.triel that are known after these records (MAPPING.md,
    decisions 0-8). A factor that is not in the result is absent."""
    tickets = [body(x).get("attempt_id") for x in prefix if x["kind"] == "ticket"]
    data = {"prior_attempt_registered": bool(tickets)}                     # decision 0

    # Decisions 1 and 2: an accepted attempt whose native result is the
    # inventory of the snapshot. The effect_state of `observed` and `handoff`
    # is not read for this.
    completed, accepted = False, set()
    for x in prefix:
        if x["kind"] == "accepted":
            accepted.add(body(x).get("attempt_id"))
        elif x["kind"] == "native" and body(x).get("attempt_id") in accepted \
                and body(x).get("outputs") == inventory:
            completed = True

    # Decisions 3 and 4: the claims of the last `handoff`, which speak about the
    # attempts it lists in retained_attempts. Once a later ticket reserves an
    # attempt that is not listed, the latest attempt is not covered by them.
    handoffs = [x for x in prefix if x["kind"] == "handoff"]
    last = body(handoffs[-1]) if handoffs else None
    covered = last is not None and isinstance(last.get("retained_attempts"), list) \
        and all(t in last["retained_attempts"] for t in tickets)
    confirmed = covered and last.get("effect_state") == "confirmed_unexecuted"

    if completed:                                                           # decision 8
        data["prior_completed"] = True
    elif confirmed:
        data["prior_completed"] = False
    if confirmed:
        data["prior_confirmed_unexecuted"] = True
    if covered and isinstance(last.get("worker_excluded"), bool):
        data["prior_fenced"] = last["worker_excluded"]
    # fresh_authorization: absent (decision 5). `unknown` records give no value
    # to any factor (decision 6).
    return data


# --- Scenarios ------------------------------------------------------------------

def iso(t: int) -> str:
    return datetime.datetime.fromtimestamp(t, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def short(attempt) -> str:
    return attempt if isinstance(attempt, str) else "?"


def describe(x, inventory) -> str:
    """A comment line for a record: its kind and the fields the mapping reads."""
    b, k = body(x), x["kind"]
    if k == "ticket":
        return f"ticket {short(b.get('attempt_id'))}, generation {b.get('generation')}, {b.get('runtime')}"
    if k in ("accepted", "unknown"):
        return f"{k} {short(b.get('attempt_id'))}"
    if k == "denied":
        return f"denied {short(b.get('attempt_id'))}, reason {b.get('reason')}"
    if k == "native":
        same = "equal to" if b.get("outputs") == inventory else "different from"
        return f"native {short(b.get('attempt_id'))}, outputs {same} the inventory of the snapshot"
    if k == "observed":
        return f"observed, effect_state {b.get('effect_state')} (not read)"
    if k == "handoff":
        return (f"handoff, effect_state {b.get('effect_state')}, worker_excluded "
                f"{str(b.get('worker_excluded')).lower()}, retained_attempts "
                + ", ".join(short(a) for a in b.get("retained_attempts", [])))
    if k == "execution_clock":
        return f"execution_clock, phase {b.get('phase')}"
    return k


def data_sexp(data: dict, order) -> str:
    items = " ".join(f"({f} (bool {'true' if data[f] else 'false'}))" for f in order if f in data)
    return f"(data {items})" if items else "(data)"


def scenario(name: str, spec: str, header: list, records: list, snapshot: dict,
             datas: list, order) -> str:
    """The text of a scenario: the records as entries, then the probe."""
    out = [f"; {line}" if line else ";" for line in header]
    out.append(f"(scenario {name}")
    out.append(f'  (spec "{spec}")')
    inventory = snapshot["inventory"]
    for i, (x, data) in enumerate(zip(records, datas)):
        event = "(activate)" if i == 0 else "(tick)"
        out.append(f"  ; entry {i}: record {x['index']}, {describe(x, inventory)}")
        out.append(f'  (entry "{iso(x["at"])}" {event}')
        out.append(f"    {data_sexp(data, order)})")
    n = len(records)
    out.append(f"  ; entry {n}: the probe, a dispatch of another attempt of the same logical effect, at observed_at")
    out.append(f'  (entry "{iso(snapshot["observed_at"])}" (act pep dispatch must_not)')
    out.append(f"    {data_sexp(datas[-1], order)}))")
    return "\n".join(out) + "\n"


def generate(vate_root: Path, pins: dict):
    """The scenarios, as {path relative to scenarios/: text}, and the Vectors
    object, whose read_files lists every file read."""
    vec = Vectors(vate_root, pins["VATE_MANIFEST_SHA256"])
    out = {}
    for case, variant, directory, snaps in vec.variants():
        for snap in snaps:
            rel = f"{directory}/{snap}-history.json"
            history = vec.read(rel)
            if not isinstance(history.get("observed_at"), int) or not isinstance(history.get("inventory"), dict):
                raise MappingError(f"{rel}: no observed_at or inventory")
            records = journal(history)
            datas = [factors(records[: i + 1], history["inventory"]) for i in range(len(records))]
            name = f"{case}__{variant}__{snap}"
            source = [
                "Generated by mapping/map_vate.py; do not edit (README.md, MAPPING.md).",
                f"VATE {pins['VATE_COMMIT']}, {pins['VATE_VECTORS']}/{rel},",
                f"sha256 {vec.read_files[-1][1]}.",
                "Entry 0 is the record `registered`; the other records of the journal follow in",
                "order, each at its time `at`; the last entry is the probe at observed_at.",
            ]
            out[f"dispatch/{name}.scn"] = scenario(
                name, DISPATCH_SPEC, source, records, history, datas, DISPATCH_FACTORS)
            absence = [{"completion_receipt": True} if d.get("prior_completed") is True else {}
                       for d in datas]
            out[f"absence/{name}.scn"] = scenario(
                name, ABSENCE_SPEC,
                source + ["completion_receipt is present, and true, exactly when prior_completed is true",
                          "in the scenario of the same name in scenarios/dispatch (MAPPING.md, decision 1)."],
                records, history, absence, ("completion_receipt",))
            if (case, variant, snap) == ASSUMPTION_CASE:
                assumed = [dict(d) for d in datas]
                assumed[-1]["fresh_authorization"] = True
                aname = f"{name}__{ASSUMPTION_SUFFIX}"
                out[f"dispatch/{aname}.scn"] = scenario(
                    aname, DISPATCH_SPEC,
                    source + ["ASSUMPTION, not read from the journal: fresh_authorization = true in the data",
                              "of the last record and of the probe (MAPPING.md, decision 5). VATE marks",
                              "fresh_pdp_evaluation as not_checked; the journal has only a new local",
                              "admission in the handoff record, which is not counted as a fresh authorization."],
                    records, history, assumed, DISPATCH_FACTORS)
    return out, vec


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vate", default=str(ROOT / "vate"), help="the VATE checkout (default: vate/)")
    ap.add_argument("--pins", default=str(ROOT / "PINS"))
    ap.add_argument("--out", default=str(ROOT / "scenarios"))
    ap.add_argument("--check", action="store_true", help="compare with the committed scenarios")
    args = ap.parse_args(argv)
    try:
        pins = read_pins(Path(args.pins))
        out, vec = generate(Path(args.vate) / pins["VATE_VECTORS"], pins)
    except (MappingError, OSError, KeyError, ValueError) as e:
        print(f"map_vate: {e}", file=sys.stderr)
        return 2
    target = Path(args.out)
    if args.check:
        on_disk = {p.relative_to(target).as_posix() for p in target.glob("*/*.scn")}
        status = 0
        for rel in sorted(on_disk | set(out)):
            have = (target / rel).read_text(encoding="utf-8") if rel in on_disk else ""
            want = out.get(rel, "")
            if have != want:
                status = 1
                sys.stdout.writelines(difflib.unified_diff(
                    have.splitlines(True), want.splitlines(True), f"committed/{rel}", f"generated/{rel}"))
        print(f"map_vate: {len(out)} scenarios, {len(vec.read_files)} VATE files read"
              + (", committed scenarios match" if status == 0 else ", DIFFERENCES above"))
        return status
    for rel, text in sorted(out.items()):
        p = target / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    print(f"map_vate: wrote {len(out)} scenarios; {len(vec.read_files)} VATE files read:")
    for rel, digest in vec.read_files:
        print(f"  {digest}  {rel}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
