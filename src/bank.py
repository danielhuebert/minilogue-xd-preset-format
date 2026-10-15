#!/usr/bin/env python3
"""Bank handling for Korg minilogue xd libraries (.mnlgxdlib).

A .mnlgxdlib is a ZIP of:
  - 500x Prog_NNN.prog_bin (+ .prog_info)
  - FavoriteData.fav_data
  - 6x TunS_NNN (user scale) + 6x TunO_NNN (user octave), each _bin + _info
  - FileInformation.xml  (manifest, filenames only)

Round-trip safe via overlay: on save, all original entries are copied
unchanged and only modified programs are replaced.

CLI:
    python3 -I src/bank.py --list   lib.mnlgxdlib
    python3 -I src/bank.py --extract lib.mnlgxdlib 3 out.mnlgxdprog
    python3 -I src/bank.py --set    lib.mnlgxdlib 0 '{"cutoff":900}' out.mnlgxdlib
    python3 -I src/bank.py --replace lib.mnlgxdlib 0 patch.mnlgxdprog out.mnlgxdlib
    python3 -I src/bank.py --json   lib.mnlgxdlib [out.json]   # all programs, params only
"""
import json
import os
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # own src/ (safe under -I)
import decode as D
import encode as E


def prog_bin_name(i):
    return "Prog_%03d.prog_bin" % i


class Bank:
    def __init__(self, path):
        self.path = path
        with zipfile.ZipFile(path) as z:
            self.order = z.namelist()                        # preserve order
            self.entries = {n: z.read(n) for n in self.order}
        self.count = sum(1 for n in self.order if n.endswith(".prog_bin"))

    # ---- read ----
    def name(self, i):
        b = self.entries[prog_bin_name(i)]
        return b[4:16].split(b"\x00")[0].decode("ascii", "replace")

    def names(self):
        return [self.name(i) for i in range(self.count)]

    def program(self, i):
        """Slot i as an encode.Program (no ZIP template; export then generates XML)."""
        return E.Program(self.entries[prog_bin_name(i)])

    # ---- write (overlay) ----
    def set_program(self, i, program):
        if not 0 <= i < self.count:
            raise IndexError("slot %d out of range 0..%d" % (i, self.count - 1))
        self.entries[prog_bin_name(i)] = bytes(program.b)
        return self

    def patch(self, i, changes):
        p = self.program(i).set_many(changes)
        return self.set_program(i, p)

    def save(self, path):
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            for n in self.order:
                z.writestr(n, self.entries[n])
        return path


def _idx(s):
    return int(s)


def main(argv):
    if not argv or argv[0] not in ("--list", "--extract", "--set", "--replace", "--json"):
        print(__doc__)
        return 1
    mode = argv[0]

    if mode == "--list":
        bank = Bank(argv[1])
        for i, nm in enumerate(bank.names()):
            print("  %3d  %s" % (i, nm))
        return 0

    if mode == "--extract":
        _, lib, idx, outp = argv
        bank = Bank(lib)
        p = bank.program(_idx(idx))
        p.save(outp)
        print("Slot %s ('%s') -> %s" % (idx, bank.name(_idx(idx)), outp))
        return 0

    if mode == "--set":
        _, lib, idx, patch, outp = argv
        changes = json.loads(patch[1:] and open(patch[1:]).read() if patch.startswith("@") else patch)
        bank = Bank(lib)
        bank.patch(_idx(idx), changes)
        bank.save(outp)
        print("Slot %s patched (%s) -> %s" % (idx, changes, outp))
        return 0

    if mode == "--replace":
        _, lib, idx, progpath, outp = argv
        bank = Bank(lib)
        bank.set_program(_idx(idx), E.Program.load(progpath))
        bank.save(outp)
        print("Slot %s replaced by %s -> %s" % (idx, progpath, outp))
        return 0

    if mode == "--json":
        bank = Bank(argv[1])
        arr = []
        for i in range(bank.count):
            d = bank.program(i).to_dict(include_seq=False)
            d = {"slot": i, **d}
            arr.append(d)
        js = json.dumps(arr, indent=2, ensure_ascii=False)
        if len(argv) == 3:
            open(argv[2], "w").write(js + "\n")
            print("Written: %s (%d programs)" % (argv[2], len(arr)))
        else:
            print(js)
        return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
