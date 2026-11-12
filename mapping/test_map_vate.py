"""
Tests of mapping/map_vate.py. They read the same VATE files as the script
(vate/ at the commit pinned in PINS), and only those.

    python3 -I -m unittest discover -s mapping -p 'test_*.py' -v
"""
import base64
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import map_vate  # noqa: E402
from map_vate import MappingError, factors  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PINS = map_vate.read_pins(ROOT / "PINS")
VECTORS = ROOT / "vate" / PINS["VATE_VECTORS"]


def rec(index, kind, **body):
    return {"index": index, "kind": kind, "at": 1792886400, "body": body}


INV = {"first.txt": {"sha256": "a", "size": 1}}


class Factors(unittest.TestCase):
    """The decisions of MAPPING.md on small journals made up for the test."""

    def test_registered_only(self):
        self.assertEqual(factors([rec(1, "registered")], INV), {"prior_attempt_registered": False})

    def test_ticket_registers_an_attempt(self):
        j = [rec(1, "registered"), rec(2, "ticket", attempt_id="a1", generation=1)]
        self.assertEqual(factors(j, INV), {"prior_attempt_registered": True})

    def test_unknown_gives_no_value(self):
        j = [rec(1, "registered"), rec(2, "ticket", attempt_id="a1"), rec(3, "accepted", attempt_id="a1"),
             rec(4, "unknown", attempt_id="a1")]
        self.assertEqual(factors(j, INV), {"prior_attempt_registered": True})

    def test_unknown_does_not_remove_completion(self):
        j = [rec(1, "registered"), rec(2, "ticket", attempt_id="a1"), rec(3, "accepted", attempt_id="a1"),
             rec(4, "native", attempt_id="a1", outputs=INV), rec(5, "unknown", attempt_id="a1")]
        self.assertIs(factors(j, INV)["prior_completed"], True)

    def test_completion_needs_accepted_and_the_inventory(self):
        base = [rec(1, "registered"), rec(2, "ticket", attempt_id="a1")]
        no_accept = base + [rec(3, "native", attempt_id="a1", outputs=INV)]
        self.assertNotIn("prior_completed", factors(no_accept, INV))
        other = base + [rec(3, "accepted", attempt_id="a1"), rec(4, "native", attempt_id="a1", outputs={})]
        self.assertNotIn("prior_completed", factors(other, INV))

    def test_effect_state_completed_is_not_read(self):
        j = [rec(1, "registered"), rec(2, "ticket", attempt_id="a1"),
             rec(3, "observed", effect_state="completed", inventory=INV, worker_excluded=True)]
        self.assertNotIn("prior_completed", factors(j, INV))

    def test_unresolved_handoff_leaves_confirmation_absent(self):
        j = [rec(1, "registered"), rec(2, "ticket", attempt_id="a1"), rec(3, "unknown", attempt_id="a1"),
             rec(4, "handoff", effect_state="unresolved", worker_excluded=True, retained_attempts=["a1"])]
        self.assertEqual(factors(j, INV), {"prior_attempt_registered": True, "prior_fenced": True})

    def test_confirmed_unexecuted(self):
        j = [rec(1, "registered"), rec(2, "ticket", attempt_id="a1"),
             rec(3, "handoff", effect_state="confirmed_unexecuted", worker_excluded=True, retained_attempts=["a1"])]
        self.assertEqual(factors(j, INV), {"prior_attempt_registered": True, "prior_completed": False,
                                           "prior_confirmed_unexecuted": True, "prior_fenced": True})

    def test_a_later_ticket_is_not_covered_by_the_handoff(self):
        j = [rec(1, "registered"), rec(2, "ticket", attempt_id="a1"),
             rec(3, "handoff", effect_state="confirmed_unexecuted", worker_excluded=True, retained_attempts=["a1"]),
             rec(4, "denied", attempt_id="a1", reason="old_generation"),
             rec(5, "ticket", attempt_id="a2", generation=2)]
        self.assertEqual(factors(j, INV), {"prior_attempt_registered": True})
        j += [rec(6, "accepted", attempt_id="a2"), rec(7, "native", attempt_id="a2", outputs=INV)]
        self.assertEqual(factors(j, INV), {"prior_attempt_registered": True, "prior_completed": True})


class Vectors(unittest.TestCase):
    """The pinned VATE vectors."""

    @classmethod
    def setUpClass(cls):
        cls.out, cls.vec = map_vate.generate(VECTORS, PINS)

    def test_reads_only_the_manifest_and_journals(self):
        names = [rel for rel, _ in self.vec.read_files]
        self.assertEqual(names[0], "MANIFEST.json")
        for rel in names[1:]:
            self.assertTrue(rel.endswith("-history.json"), rel)
        self.assertEqual(sum(r.endswith("/input-history.json") for r in names), 8)
        self.assertEqual(len(names), 1 + 8 + 17)
        self.assertEqual(len(set(names)), len(names))

    def test_every_file_read_matches_the_manifest(self):
        manifest = json.loads((VECTORS / "MANIFEST.json").read_bytes())["files"]
        for rel, digest in self.vec.read_files[1:]:
            self.assertEqual(manifest[rel]["sha256"], digest, rel)

    def test_refuses_other_files(self):
        for rel in ("VECTORS.json", "cases/01-lost-response-recovery/case.json",
                    "cases/01-lost-response-recovery/with-unknown-observation/expected-pep-decision.json",
                    "cases/01-lost-response-recovery/with-unknown-observation/interactions.json",
                    "cases/01-lost-response-recovery/with-unknown-observation/operation.json",
                    "cases/01-lost-response-recovery/with-unknown-observation/context.json"):
            with self.assertRaises(MappingError):
                self.vec.read(rel)

    def test_thirty_five_scenarios(self):
        self.assertEqual(sum(k.startswith("dispatch/") for k in self.out), 18)
        self.assertEqual(sum(k.startswith("absence/") for k in self.out), 17)
        self.assertIn("dispatch/03-confirmed-nonexecution-handoff__fenced-handoff__fenced"
                      "__assumed-fresh-authorization.scn", self.out)

    def test_times_are_those_of_the_journal(self):
        for text in self.out.values():
            times = {line.split('"')[1] for line in text.splitlines() if line.strip().startswith("(entry ")}
            self.assertEqual(times, {"2026-10-25T00:00:00Z"})

    def test_probe_is_last_and_repeats_the_last_data(self):
        for text in self.out.values():
            lines = [ln.strip() for ln in text.splitlines() if not ln.strip().startswith(";")]
            entries = [i for i, ln in enumerate(lines) if ln.startswith("(entry ")]
            self.assertIn("(activate)", lines[entries[0]])
            self.assertTrue(lines[entries[-1]].endswith("(act pep dispatch must_not)"))
            self.assertEqual(sum("(act " in ln for ln in lines), 1)
            self.assertEqual(lines[entries[-1] + 1][:-1], lines[entries[-2] + 1])

    def test_assumption_only_in_the_extra_scenario(self):
        for name, text in self.out.items():
            data = [ln for ln in text.splitlines() if ln.strip().startswith("(data")]
            if name.endswith("assumed-fresh-authorization.scn"):
                self.assertEqual([("fresh_authorization" in d) for d in data],
                                 [False] * (len(data) - 2) + [True, True])
            else:
                self.assertFalse(any("fresh_authorization" in d for d in data), name)

    def test_specification_paths(self):
        for name, text in self.out.items():
            spec = "../specs/dispatch_rule.triel" if name.startswith("dispatch/") else "../specs/absence_check.triel"
            self.assertIn(f'(spec "{spec}")', text)

    def test_committed_scenarios_are_the_generated_ones(self):
        committed = {p.relative_to(ROOT / "scenarios").as_posix(): p.read_text(encoding="utf-8")
                     for p in (ROOT / "scenarios").glob("*/*.scn")}
        self.assertEqual(committed, self.out)

    def test_each_scenario_has_hand_written_expectations(self):
        for name in self.out:
            stem = ROOT / "scenarios" / name[: -len(".scn")]
            self.assertTrue(stem.with_suffix(".expected").is_file(), name)
            self.assertIn(stem.with_suffix(".exitcode").read_text(encoding="utf-8"), ("0\n", "3\n"), name)


class Tampering(unittest.TestCase):
    """A changed journal or manifest is rejected. The files are copied into a
    temporary directory for the test only."""

    def copy(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        manifest = json.loads((VECTORS / "MANIFEST.json").read_bytes())["files"]
        shutil.copy(VECTORS / "MANIFEST.json", tmp / "MANIFEST.json")
        for rel in manifest:
            if rel.endswith("-history.json"):
                (tmp / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(VECTORS / rel, tmp / rel)
        return tmp

    def test_changed_journal(self):
        tmp = self.copy()
        p = tmp / "cases/02-accepted-interrupted/zero-effects/after-handoff-history.json"
        h = json.loads(p.read_bytes())
        x = json.loads(base64.b64decode(h["records"][-1]["raw"]))
        x["body"]["effect_state"] = "confirmed_unexecuted"
        h["records"][-1]["raw"] = base64.b64encode(json.dumps(x).encode()).decode()
        p.write_text(json.dumps(h))
        with self.assertRaises(MappingError):
            map_vate.generate(tmp, PINS)

    def test_changed_manifest(self):
        tmp = self.copy()
        p = tmp / "MANIFEST.json"
        p.write_bytes(p.read_bytes() + b"\n")
        with self.assertRaises(MappingError):
            map_vate.generate(tmp, PINS)


if __name__ == "__main__":
    unittest.main()
