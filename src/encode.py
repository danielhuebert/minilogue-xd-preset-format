#!/usr/bin/env python3
"""Encoder: load a .mnlgxdprog / prog_bin, change parameters, write it back.

Round-trip safe: ONLY the bytes of the parameters you set are changed,
everything else (sequencer, reserved bytes, companion XML) stays byte-identical.

CLI (JSON patch as a string or @file.json):
    python3 -I src/encode.py in.mnlgxdprog out.mnlgxdprog '{"cutoff":900,"name":"My Patch"}'
    python3 -I src/encode.py --json in.mnlgxdprog [out.json]   # export (round-trip safe)
    python3 -I src/encode.py --list        # show supported parameters

Python API:
    from encode import Program
    p = Program.load("in.mnlgxdprog")
    p.set("cutoff", 900); p.set("vco1_wave", "SQR")
    p.save("out.mnlgxdprog")
"""
import json
import os
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # own src/ (safe under -I)
import decode as D


def _rev(d):
    """Reverse map name->index; on duplicates the smallest index wins."""
    out = {}
    for k in sorted(d, reverse=True):
        out[d[k]] = k
    return out


# Registry: name -> (offset, kind, extra)
#   u8     : raw byte 0..255
#   bit10  : 10-bit little-endian (0..1023)       -> 2 bytes
#   enum   : extra = enum dict (value as name string OR index)
#   bias   : extra = bias n; stored as (value + n) in a u8
#   name   : extra = length; ASCII, padded with 0x00
REG = {
    "name": (4, "name", 12),
    "octave": (16, "bias", 2),
    "portamento": (17, "u8", None),
    "key_trig": (18, "enum", D.ONOFF),
    "voice_mode_type": (21, "enum", D.VOICE_MODE),
    "voice_mode_depth": (19, "bit10", None),
    "vco1_wave": (22, "enum", D.WAVE),
    "vco1_octave": (23, "enum", D.OCTAVE_FT),
    "vco1_pitch_raw": (24, "bit10", None),
    "vco1_shape": (26, "bit10", None),
    "vco2_wave": (28, "enum", D.WAVE),
    "vco2_octave": (29, "enum", D.OCTAVE_FT),
    "vco2_pitch_raw": (30, "bit10", None),
    "vco2_shape": (32, "bit10", None),
    "sync": (34, "enum", D.SYNC),
    "ring": (35, "enum", D.SYNC),
    "cross_mod_depth": (36, "bit10", None),
    "multi_type": (38, "enum", D.MULTI_TYPE),
    "select_noise": (39, "enum", D.NOISE_SEL),
    "select_vpm": (40, "enum", D.VPM_SEL),
    "select_user": (41, "enum", D.USER_SEL),
    "shape_noise": (42, "bit10", None),
    "shape_vpm": (44, "bit10", None),
    "shape_user": (46, "bit10", None),
    "shiftshape_noise": (48, "bit10", None),
    "shiftshape_vpm": (50, "bit10", None),
    "shiftshape_user": (52, "bit10", None),
    "vco1_level": (54, "bit10", None),
    "vco2_level": (56, "bit10", None),
    "multi_level": (58, "bit10", None),
    "cutoff": (60, "bit10", None),
    "resonance": (62, "bit10", None),
    "cutoff_drive": (64, "enum", D.PCT3),
    "cutoff_keytrack": (65, "enum", D.PCT3),
    "amp_eg_attack": (66, "bit10", None),
    "amp_eg_decay": (68, "bit10", None),
    "amp_eg_sustain": (70, "bit10", None),
    "amp_eg_release": (72, "bit10", None),
    "eg_attack": (74, "bit10", None),
    "eg_decay": (76, "bit10", None),
    "eg_int_raw": (78, "bit10", None),
    "eg_target": (80, "enum", D.EG_TARGET),
    "lfo_wave": (81, "enum", D.WAVE),
    "lfo_mode": (82, "enum", D.LFO_MODE),
    "lfo_rate": (83, "bit10", None),
    "lfo_int": (85, "bit10", None),
    "lfo_target": (87, "enum", D.LFO_TARGET),
    "mod_fx_onoff": (88, "enum", D.ONOFF),
    "mod_fx_type": (89, "enum", D.MODFX_TYPE),
    "mod_fx_time": (95, "bit10", None),
    "mod_fx_depth": (97, "bit10", None),
    "delay_onoff": (99, "enum", D.ONOFF),
    "delay_sub_type": (100, "enum", D.DELAY_SUB),
    "delay_time": (101, "bit10", None),
    "delay_depth": (103, "bit10", None),
    "reverb_onoff": (105, "enum", D.ONOFF),
    "reverb_sub_type": (106, "enum", D.REVERB_SUB),
    "reverb_time": (107, "bit10", None),
    "reverb_depth": (109, "bit10", None),
    "bend_range_pos": (111, "u8", None),
    "bend_range_neg": (112, "u8", None),
    "joystick_assign_pos": (113, "enum", D.ASSIGN),
    "joystick_range_pos": (114, "bias", 100),
    "joystick_assign_neg": (115, "enum", D.ASSIGN),
    "joystick_range_neg": (116, "bias", 100),
    "cv_in_mode": (117, "enum", D.CV_MODE),
    "cv_in1_assign": (118, "enum", D.ASSIGN),
    "cv_in1_range": (119, "bias", 100),
    "cv_in2_assign": (120, "enum", D.ASSIGN),
    "cv_in2_range": (121, "bias", 100),
    "micro_tuning": (122, "enum", D.MICRO_TUNING),
    "scale_key": (123, "bias", 12),
    "program_tuning": (124, "bias", 50),
    "lfo_key_sync": (125, "enum", D.ONOFF),
    "lfo_voice_sync": (126, "enum", D.ONOFF),
    "lfo_target_osc": (127, "enum", D.LFO_TGTOSC),
    "cutoff_velocity": (128, "u8", None),
    "amp_velocity": (129, "u8", None),
    "multi_octave": (130, "enum", D.OCTAVE_FT),
    "multi_routing": (131, "enum", D.MULTI_ROUTING),
    "eg_legato": (132, "enum", D.ONOFF),
    "portamento_mode": (133, "enum", D.PORTA_MODE),
    "portamento_bpm_sync": (134, "enum", D.ONOFF),
    "program_level_raw": (135, "u8", None),   # 12..132 = -18..+6 dB (nonlinear)
    "vpm_param1": (136, "bias", 100),
    "vpm_param2": (137, "bias", 100),
    "vpm_param3": (138, "bias", 100),
    "vpm_param4": (139, "bias", 100),
    "vpm_param5": (140, "bias", 100),
    "vpm_param6": (141, "bias", 100),
    "user_param1": (142, "u8", None),
    "user_param2": (143, "u8", None),
    "user_param3": (144, "u8", None),
    "user_param4": (145, "u8", None),
    "user_param5": (146, "u8", None),
    "user_param6": (147, "u8", None),
    "program_transpose": (150, "bias", 13),
    "delay_dry_wet": (151, "bit10", None),
    "reverb_dry_wet": (153, "bit10", None),
    "aftertouch_assign": (155, "enum", D.ASSIGN),
}

PROG_BIN = "Prog_000.prog_bin"


class Program:
    def __init__(self, raw, template_zip=None):
        if len(raw) != 1024:
            raise ValueError("prog_bin must be 1024 bytes, not %d" % len(raw))
        if raw[0:4] != b"PROG":
            raise ValueError("missing PROG header")
        self.b = bytearray(raw)
        self.template_zip = template_zip   # source for the companion files in the ZIP

    # ---- load ----
    @classmethod
    def load(cls, path):
        if path.lower().endswith(".mnlgxdprog") or zipfile.is_zipfile(path):
            with zipfile.ZipFile(path) as z:
                name = next(n for n in z.namelist() if n.endswith(".prog_bin"))
                return cls(z.read(name), template_zip=path)
        with open(path, "rb") as f:
            return cls(f.read())

    # ---- set a single parameter ----
    def set(self, key, value):
        if key not in REG:
            raise KeyError("unknown parameter: %s" % key)
        off, kind, extra = REG[key]
        if kind == "u8":
            self._put_u8(off, value)
        elif kind == "bit10":
            self._put_bit10(off, value)
        elif kind == "bias":
            self._put_u8(off, value + extra)
        elif kind == "enum":
            self._put_u8(off, self._enum_index(extra, value))
        elif kind == "name":
            self._put_name(off, extra, value)
        return self

    def set_many(self, d):
        for k, v in d.items():
            if k.startswith("_"):   # skip read-only metadata (e.g. _sequencer)
                continue
            self.set(k, v)
        return self

    # ---- export (round-trip safe: feeds straight back into set_many) ----
    def to_dict(self, include_seq=True):
        out = {}
        for key, (off, kind, extra) in sorted(REG.items(), key=lambda kv: kv[1][0]):
            if kind == "u8":
                out[key] = self.b[off]
            elif kind == "bit10":
                out[key] = D.bit10(self.b, off)
            elif kind == "bias":
                out[key] = self.b[off] - extra
            elif kind == "enum":
                out[key] = extra.get(self.b[off], self.b[off])
            elif kind == "name":
                # cut only at the null byte; preserve trailing spaces
                # (some names are padded with 0x20 instead of 0x00 -> exact round-trip)
                out[key] = (bytes(self.b[off:off + extra]).split(b"\x00")[0]
                            .decode("ascii", "replace"))
        if include_seq:
            out["_sequencer"] = D.decode_sequencer(bytes(self.b))  # read-only view
        return out

    def to_json(self, include_seq=True, indent=2):
        return json.dumps(self.to_dict(include_seq), indent=indent, ensure_ascii=False)

    # ---- low level ----
    def _put_u8(self, off, v):
        v = int(v)
        if not 0 <= v <= 255:
            raise ValueError("value %d for @%d out of range 0..255" % (v, off))
        self.b[off] = v

    def _put_bit10(self, off, v):
        v = int(v)
        if not 0 <= v <= 1023:
            raise ValueError("10-bit value %d for @%d out of range 0..1023" % (v, off))
        self.b[off] = v & 0xFF
        self.b[off + 1] = (v >> 8) & 0x03   # upper 2 bits, rest stays 0

    def _put_name(self, off, length, value):
        data = str(value).encode("ascii", "replace")[:length]
        self.b[off:off + length] = data + b"\x00" * (length - len(data))

    @staticmethod
    def _enum_index(enum, value):
        if isinstance(value, int):
            if value not in enum:
                raise ValueError("index %d not in enum %s" % (value, list(enum)))
            return value
        rev = _rev(enum)
        if value not in rev:
            raise ValueError("'%s' not in enum; allowed: %s"
                             % (value, sorted(rev)))
        return rev[value]

    # ---- save ----
    def save(self, path):
        if path.lower().endswith(".mnlgxdprog"):
            self._save_zip(path)
        else:
            with open(path, "wb") as f:
                f.write(self.b)
        return path

    def _save_zip(self, path):
        if self.template_zip:
            # copy all original entries, replace only prog_bin
            with zipfile.ZipFile(self.template_zip) as zin:
                items = [(i.filename, zin.read(i.filename)) for i in zin.infolist()]
            with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zout:
                for fn, data in items:
                    zout.writestr(fn, bytes(self.b) if fn.endswith(".prog_bin") else data)
        else:
            # no template: generate minimal, valid companion files
            with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zout:
                zout.writestr(PROG_BIN, bytes(self.b))
                zout.writestr("Prog_000.prog_info", _PROG_INFO)
                zout.writestr("FileInformation.xml", _FILEINFO)


_PROG_INFO = ('<?xml version="1.0" encoding="UTF-8"?>\n\n'
              '<xd_ProgramInformation>\n  <Programmer></Programmer>\n'
              '  <Comment></Comment>\n</xd_ProgramInformation>\n')
_FILEINFO = ('<?xml version="1.0" encoding="UTF-8"?>\n\n<KorgMSLibrarian_Data>\n'
             '  <Product>minilogue xd</Product>\n'
             '  <Contents NumFavoriteData="0" NumProgramData="1" NumPresetInformation="0"\n'
             '            NumTuneScaleData="0" NumTuneOctData="0">\n    <ProgramData>\n'
             '      <Information>Prog_000.prog_info</Information>\n'
             '      <ProgramBinary>Prog_000.prog_bin</ProgramBinary>\n'
             '    </ProgramData>\n  </Contents>\n</KorgMSLibrarian_Data>\n')


def _print_list():
    print("Supported parameters (name  @offset  kind  [values]):")
    for k, (off, kind, extra) in sorted(REG.items(), key=lambda kv: kv[1][0]):
        hint = ""
        if kind == "enum":
            hint = "{%s}" % ", ".join(str(x) for x in extra.values())
        elif kind == "bit10":
            hint = "0..1023"
        elif kind == "u8":
            hint = "0..255"
        elif kind == "bias":
            hint = "stored as value+%d" % extra
        elif kind == "name":
            hint = "ASCII, max %d chars" % extra
        print("  %-22s @%-4d %-6s %s" % (k, off, kind, hint))


def main(argv):
    if not argv or argv[0] == "--list":
        _print_list() if argv[:1] == ["--list"] else print(__doc__)
        return 0 if argv else 1
    if argv[0] == "--json":        # export: --json <in> [out.json]
        if len(argv) not in (2, 3):
            print("Usage: --json <in.mnlgxdprog> [out.json]")
            return 1
        js = Program.load(argv[1]).to_json()
        if len(argv) == 3:
            with open(argv[2], "w") as f:
                f.write(js + "\n")
            print("Written: %s" % argv[2])
        else:
            print(js)
        return 0
    if len(argv) != 3:
        print(__doc__)
        return 1
    inp, outp, patch = argv
    if patch.startswith("@"):
        with open(patch[1:], "r") as f:
            changes = json.load(f)
    else:
        changes = json.loads(patch)
    p = Program.load(inp)
    before = bytes(p.b)
    p.set_many(changes)
    p.save(outp)
    diffs = [i for i in range(1024) if before[i] != p.b[i]]
    print("Set: %s" % ", ".join("%s=%r" % (k, v) for k, v in changes.items()))
    print("Changed bytes: %s" % (diffs if diffs else "none"))
    print("Written: %s" % outp)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
