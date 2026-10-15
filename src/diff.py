#!/usr/bin/env python3
"""Byte diff of two (or more) prog_bin / .mnlgxdprog files.

Shows every offset where the files differ, in decimal and hex. Ideal for
finding which byte controls a given parameter: change exactly ONE parameter on
the device, save, then diff the result against the original.

Usage:
    python3 -I src/diff.py "presets/SEQ_base.mnlgxdprog" "presets/SEQ_swing.mnlgxdprog"
"""
import sys
import zipfile


def load(path):
    if path.lower().endswith(".mnlgxdprog") or zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as z:
            n = next(x for x in z.namelist() if x.endswith(".prog_bin"))
            return z.read(n)
    with open(path, "rb") as f:
        return f.read()


def region(off):
    if off < 4:
        return "PROG"
    if off < 16:
        return "name"
    if off < 156:
        return "synth"
    if off < 160:
        return "PRED"
    if off < 162:
        return "SQ"
    if off < 190:
        return "seq-header"
    if off <= 1021:
        step = (off - 190) // 52 + 1
        within = (off - 190) % 52
        return "step%d[+%d]" % (step, within)
    return "seq-tail"


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    files = [(p, load(p)) for p in argv]
    base_name, base = files[0]
    print("Reference: %s" % base_name)
    for name, data in files[1:]:
        print("=" * 70)
        print("vs %s" % name)
        n = min(len(base), len(data))
        diffs = [(i, base[i], data[i]) for i in range(n) if base[i] != data[i]]
        if not diffs:
            print("  (identical)")
        for off, a, b in diffs:
            print("  @%-4d 0x%03X  %-14s  %3d -> %3d   (0x%02X -> 0x%02X)"
                  % (off, off, region(off), a, b, a, b))
        if len(base) != len(data):
            print("  (lengths differ: %d vs %d)" % (len(base), len(data)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
