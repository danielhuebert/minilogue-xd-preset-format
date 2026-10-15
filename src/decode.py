#!/usr/bin/env python3
"""Decoder for Korg minilogue xd programs (.mnlgxdprog / prog_bin).

Reads the 1024-byte prog_bin per MIDI implementation TABLE 2 and prints the
parameters in readable form. 10-bit values are little-endian (verified empirically).

Usage:
    python3 -I src/decode.py "presets/KY Redshift.mnlgxdprog"
    python3 -I src/decode.py "out/KY Redshift/Prog_000.prog_bin"
    python3 -I src/decode.py presets/*.mnlgxdprog
"""
import sys
import zipfile


# ---------------------------------------------------------------- Enums
WAVE       = {0: "SQR", 1: "TRI", 2: "SAW"}
OCTAVE_FT  = {0: "16'", 1: "8'", 2: "4'", 3: "2'"}
VOICE_MODE = {0: "ARP LATCH", 1: "ARP", 2: "CHORD", 3: "UNISON", 4: "POLY"}
MULTI_TYPE = {0: "NOISE", 1: "VPM", 2: "USER"}
NOISE_SEL  = {0: "HIGH", 1: "LOW", 2: "PEAK", 3: "DECIM"}
VPM_SEL    = {0: "SIN1", 1: "SIN2", 2: "SIN3", 3: "SIN4", 4: "SAW1", 5: "SAW2",
              6: "SQU1", 7: "SQU2", 8: "FAT1", 9: "FAT2", 10: "AIR1", 11: "AIR2",
              12: "DECAY1", 13: "DECAY2", 14: "CREEP", 15: "THROAT"}
USER_SEL   = {i: "USER%d" % (i + 1) for i in range(16)}
PCT3       = {0: "0%", 1: "50%", 2: "100%"}
EG_TARGET  = {0: "CUTOFF", 1: "PITCH2", 2: "PITCH"}
LFO_MODE   = {0: "1-SHOT", 1: "NORMAL", 2: "BPM"}
LFO_TARGET = {0: "CUTOFF", 1: "SHAPE", 2: "PITCH"}
LFO_TGTOSC = {0: "ALL", 1: "VCO1+VCO2", 2: "VCO2", 3: "MULTI"}
ONOFF      = {0: "Off", 1: "On"}
SYNC       = {0: "ON", 1: "OFF"}
MODFX_TYPE = {1: "CHORUS", 2: "ENSEMBLE", 3: "PHASER", 4: "FLANGER", 5: "USER"}
DELAY_SUB  = {0: "STEREO", 1: "MONO", 2: "PING PONG", 3: "HIPASS", 4: "TAPE",
              5: "ONE TAP", 6: "STEREO BPM", 7: "MONO BPM", 8: "PING BPM",
              9: "HIPASS BPM", 10: "TAPE BPM", 11: "DOUBLING"}
DELAY_SUB.update({12 + i: "USER%d" % (i + 1) for i in range(8)})
REVERB_SUB = {0: "HALL", 1: "SMOOTH", 2: "ARENA", 3: "PLATE", 4: "ROOM",
              5: "EARLY REF", 6: "SPACE", 7: "RISER", 8: "SUBMARINE", 9: "HORROR"}
REVERB_SUB.update({10 + i: "USER%d" % (i + 1) for i in range(8)})
STEP_RES   = {0: "1/16", 1: "1/8", 2: "1/4", 3: "1/2", 4: "1/1"}
ARP_RATE   = {0: "64th", 1: "48th", 2: "32th", 3: "24th", 4: "16th", 5: "16.th",
              6: "12th", 7: "8th", 8: "8.th", 9: "6th", 10: "4th"}
# *note S2-1 (Motion Parameter ID)
MOTION_PARAM = {0: "None", 15: "PORTAMENTO", 16: "VOICE MODE DEPTH",
    17: "VOICE MODE TYPE", 18: "VCO1 WAVE", 19: "VCO1 OCTAVE", 20: "VCO1 PITCH",
    21: "VCO1 SHAPE", 22: "VCO2 WAVE", 23: "VCO2 OCTAVE", 24: "VCO2 PITCH",
    25: "VCO2 SHAPE", 26: "SYNC", 27: "RING", 28: "CROSS MOD DEPTH",
    29: "MULTI TYPE", 30: "MULTI NOISE TYPE", 31: "MULTI VPM TYPE",
    33: "MULTI SHAPE NOISE", 34: "MULTI SHAPE VPM", 35: "MULTI SHAPE USER",
    36: "MULTI SHIFT SHAPE NOISE", 37: "MULTI SHIFT SHAPE VPM",
    38: "MULTI SHIFT SHAPE USER", 39: "VCO1 LEVEL", 40: "VCO2 LEVEL",
    41: "MULTI LEVEL", 42: "CUTOFF", 43: "RESONANCE", 45: "KEYTRACK",
    46: "AMP EG ATTACK", 47: "AMP EG DECAY", 48: "AMP EG SUSTAIN",
    49: "AMP EG RELEASE", 50: "EG ATTACK", 51: "EG DECAY", 52: "EG INT",
    53: "EG TARGET", 54: "LFO WAVE", 55: "LFO MODE", 56: "LFO RATE",
    57: "LFO INT", 58: "LFO TARGET", 59: "MOD FX ON/OFF", 66: "MOD FX TIME",
    67: "MOD FX DEPTH", 68: "DELAY ON/OFF", 70: "DELAY TIME", 71: "DELAY DEPTH",
    72: "REVERB ON/OFF", 74: "REVERB TIME", 75: "REVERB DEPTH",
    126: "PITCH BEND", 129: "GATE TIME"}

# *note P19 (JOYSTICK / CV IN / AFTER TOUCH ASSIGN)
ASSIGN = {0: "GATE TIME", 1: "PORTAMENTO", 2: "V.M DEPTH", 3: "VCO1 PITCH",
    4: "VCO1 SHAPE", 5: "VCO2 PITCH", 6: "VCO2 SHAPE", 7: "CROSS MOD",
    8: "MULTI SHAPE", 9: "VCO1 LEVEL", 10: "VCO2 LEVEL", 11: "MULTI LEVEL",
    12: "CUTOFF", 13: "RESONANCE", 14: "A.EG ATTACK", 15: "A.EG DECAY",
    16: "A.EG SUSTAIN", 17: "A.EG RELEASE", 18: "EG ATTACK", 19: "EG DECAY",
    20: "EG INT", 21: "LFO RATE", 22: "LFO INT", 23: "MOD FX SPEED",
    24: "MOD FX DEPTH", 25: "REVERB TIME", 26: "REVERB DEPTH", 27: "DELAY TIME",
    28: "DELAY DEPTH"}
CV_MODE = {0: "Modulation", 1: "CV/Gate(+)", 2: "CV/Gate(-)"}
MULTI_ROUTING = {0: "Pre VCF", 1: "Post VCF"}
PORTA_MODE = {0: "Auto", 1: "On"}
# *note P21 (MICRO TUNING)
MICRO_TUNING = {0: "Equal Temp", 1: "Pure Major", 2: "Pure Minor", 3: "Pythagorean",
    4: "Werckmeister", 5: "Kirnburger", 6: "Slendro", 7: "Pelog", 8: "Ionian",
    9: "Dorian", 10: "Aeolian", 11: "Major Penta", 12: "Minor Penta", 13: "Reverse",
    14: "AFX001", 15: "AFX002", 16: "AFX003", 17: "AFX004", 18: "AFX005", 19: "AFX006",
    20: "DC001", 21: "DC002", 22: "DC003"}
MICRO_TUNING.update({128 + i: "USER SCALE %d" % (i + 1) for i in range(6)})
MICRO_TUNING.update({134 + i: "USER OCTAVE %d" % (i + 1) for i in range(6)})
# Mod-FX-Subtypen (*note P13-P16)
MODFX_CHORUS   = {0: "STEREO", 1: "LIGHT", 2: "DEEP", 3: "TRIPHASE", 4: "HARMONIC",
                  5: "MONO", 6: "FEEDBACK", 7: "VIBRATO"}
MODFX_ENSEMBLE = {0: "STEREO", 1: "LIGHT", 2: "MONO"}
MODFX_PHASER   = {0: "STEREO", 1: "FAST", 2: "ORANGE", 3: "SMALL", 4: "SMALL RESO",
                  5: "BLACK", 6: "FORMANT", 7: "TWINKLE"}
MODFX_FLANGER  = {0: "STEREO", 1: "LIGHT", 2: "MONO", 3: "HIGH SWEEP", 4: "MID SWEEP",
                  5: "PAN SWEEP", 6: "MONO SWEEP", 7: "TRIPHASE"}

_NOTES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def note_name(n):
    return "%s%d" % (_NOTES[n % 12], n // 12 - 1)   # MIDI 60 = C4


def modfx_subtype(type_idx, b):
    """Active mod-FX subtype depending on type (offsets 90-94)."""
    if type_idx == 1:
        return MODFX_CHORUS.get(b[90])
    if type_idx == 2:
        return MODFX_ENSEMBLE.get(b[91])
    if type_idx == 3:
        return MODFX_PHASER.get(b[92])
    if type_idx == 4:
        return MODFX_FLANGER.get(b[93])
    if type_idx == 5:
        return USER_SEL.get(b[94])
    return None


def voice_mode_depth(vtype, v):
    """VOICE MODE DEPTH (0..1023) interpreted per voice mode (*note P2)."""
    if vtype == 4:      # POLY
        return "Poly" if v <= 255 else "Duo %d" % v
    if vtype == 3:      # UNISON
        return "Detune %d cent" % round(v / 1023 * 50)
    if vtype == 2:      # CHORD
        chords = ["5th", "sus2", "m", "Maj", "sus4", "m7", "7", "7sus4", "Maj7",
                  "aug", "dim", "m7b5", "mMaj7", "Maj7b5"]
        return chords[min(v * 14 // 1024, 13)]
    if vtype in (0, 1):  # ARP
        arps = ["MANUAL 1", "MANUAL 2", "RISE 1", "RISE 2", "FALL 1", "FALL 2",
                "RISE FALL 1", "RISE FALL 2", "POLY 1", "POLY 2", "RANDOM 1",
                "RANDOM 2", "RANDOM 3"]
        return arps[min(v * 13 // 1024, 12)]
    return v


def user_param(v, ptype):
    """USER PARAM interpreted per type (*note P24)."""
    if ptype == 0:      # Percent 0~101 = 0..100%
        return "%d%%" % v
    if ptype == 1:      # Bipolar 0~200 = -100..+100
        return "%+d" % (v - 100)
    if ptype == 2:      # Select 0~100 = 1..101
        return "sel %d" % (v + 1)
    return v


# ------------------------------------------------------- nonlinear maps
def _lerp(v, a0, a1, b0, b1):
    if a1 == a0:
        return b0
    return b0 + (b1 - b0) * (v - a0) / (a1 - a0)


def pitch_to_cent(v):
    """*note P5: VCO1/2 PITCH (0..1023) -> cents."""
    segs = [(0, 4, -1200, -1200), (4, 356, -1200, -256), (356, 476, -256, -16),
            (476, 492, -16, 0), (492, 532, 0, 0), (532, 548, 0, 16),
            (548, 668, 16, 256), (668, 1020, 256, 1200), (1020, 1023, 1200, 1200)]
    for a0, a1, b0, b1 in segs:
        if v <= a1:
            return round(_lerp(v, a0, a1, b0, b1))
    return 1200


def eg_int_to_pct(v):
    """*note P10: EG INT (0..1023) -> percent."""
    if v <= 11:
        return -100.0
    if v < 492:
        return -((492 - v) ** 2 * 4641 * 100) / 0x40000000
    if v <= 532:
        return 0.0
    if v < 1013:
        return ((v - 532) ** 2 * 4641 * 100) / 0x40000000
    return 100.0


# ------------------------------------------------------- byte readers
def u8(b, off):
    return b[off]


def bit10(b, off):
    """Program parameter: 10-bit value, little-endian (low byte first)."""
    return (b[off] | (b[off + 1] << 8)) & 0x3FF


def bit16le(b, off):
    return b[off] | (b[off + 1] << 8)


def motion_points(b, off):
    """Motion data block (7 bytes) -> 5 ten-bit points.
    Packing: byte gives bits 2-9 (high 8), a packed byte gives the low 2 (*note S3-2).
    """
    lo14, lo5 = b[off + 5], b[off + 6]
    lows = [lo14 & 3, (lo14 >> 2) & 3, (lo14 >> 4) & 3, (lo14 >> 6) & 3, lo5 & 3]
    return [(b[off + j] << 2) | lows[j] for j in range(5)]


def bits_to_steps(lo, hi):
    """Two bytes (steps 1-8, 9-16) -> list of active step numbers (1-based)."""
    mask = lo | (hi << 8)
    return [s + 1 for s in range(16) if mask & (1 << s)]


# --------------------------------------------------------------- Decoder
def decode(b):
    assert b[0:4] == b"PROG", "missing PROG header"
    name = b[4:16].split(b"\x00")[0].decode("ascii", "replace").rstrip()
    o = {}
    o["name"]            = name
    o["octave"]          = u8(b, 16) - 2                     # -2..+2
    o["portamento"]      = u8(b, 17)
    o["key_trig"]        = ONOFF.get(u8(b, 18))
    vtype = u8(b, 21)
    o["voice_mode_type"] = VOICE_MODE.get(vtype, vtype)
    o["voice_mode_depth"] = voice_mode_depth(vtype, bit10(b, 19))

    o["vco1_wave"]       = WAVE.get(u8(b, 22))
    o["vco1_octave"]     = OCTAVE_FT.get(u8(b, 23))
    o["vco1_pitch"]      = "%+d cent" % pitch_to_cent(bit10(b, 24))
    o["vco1_shape"]      = bit10(b, 26)
    o["vco2_wave"]       = WAVE.get(u8(b, 28))
    o["vco2_octave"]     = OCTAVE_FT.get(u8(b, 29))
    o["vco2_pitch"]      = "%+d cent" % pitch_to_cent(bit10(b, 30))
    o["vco2_shape"]      = bit10(b, 32)

    o["sync"]            = SYNC.get(u8(b, 34))
    o["ring"]            = SYNC.get(u8(b, 35))               # 0=ON,1=OFF
    o["cross_mod_depth"] = bit10(b, 36)

    o["multi_type"]      = MULTI_TYPE.get(u8(b, 38))
    o["select_noise"]    = NOISE_SEL.get(u8(b, 39))
    o["select_vpm"]      = VPM_SEL.get(u8(b, 40))
    o["select_user"]     = USER_SEL.get(u8(b, 41))
    o["shape_noise"]     = bit10(b, 42)
    o["shape_vpm"]       = bit10(b, 44)
    o["shape_user"]      = bit10(b, 46)
    o["shiftshape_noise"] = bit10(b, 48)
    o["shiftshape_vpm"]  = bit10(b, 50)
    o["shiftshape_user"] = bit10(b, 52)

    o["vco1_level"]      = bit10(b, 54)
    o["vco2_level"]      = bit10(b, 56)
    o["multi_level"]     = bit10(b, 58)
    o["cutoff"]          = bit10(b, 60)
    o["resonance"]       = bit10(b, 62)
    o["cutoff_drive"]    = PCT3.get(u8(b, 64))
    o["cutoff_keytrack"] = PCT3.get(u8(b, 65))

    o["amp_eg_attack"]   = bit10(b, 66)
    o["amp_eg_decay"]    = bit10(b, 68)
    o["amp_eg_sustain"]  = bit10(b, 70)
    o["amp_eg_release"]  = bit10(b, 72)
    o["eg_attack"]       = bit10(b, 74)
    o["eg_decay"]        = bit10(b, 76)
    o["eg_int"]          = "%.1f%%" % eg_int_to_pct(bit10(b, 78))
    o["eg_target"]       = EG_TARGET.get(u8(b, 80))

    o["lfo_wave"]        = WAVE.get(u8(b, 81))
    o["lfo_mode"]        = LFO_MODE.get(u8(b, 82))
    o["lfo_rate"]        = bit10(b, 83)
    o["lfo_int"]         = bit10(b, 85)
    o["lfo_target"]      = LFO_TARGET.get(u8(b, 87))

    o["mod_fx_onoff"]    = ONOFF.get(u8(b, 88))
    mfx_type = u8(b, 89)
    o["mod_fx_type"]     = MODFX_TYPE.get(mfx_type)
    o["mod_fx_subtype"]  = modfx_subtype(mfx_type, b)
    o["mod_fx_time"]     = bit10(b, 95)
    o["mod_fx_depth"]    = bit10(b, 97)
    o["delay_onoff"]     = ONOFF.get(u8(b, 99))
    o["delay_sub_type"]  = DELAY_SUB.get(u8(b, 100))
    o["delay_time"]      = bit10(b, 101)
    o["delay_depth"]     = bit10(b, 103)
    o["reverb_onoff"]    = ONOFF.get(u8(b, 105))
    o["reverb_sub_type"] = REVERB_SUB.get(u8(b, 106))
    o["reverb_time"]     = bit10(b, 107)
    o["reverb_depth"]    = bit10(b, 109)

    # Bend / Joystick / CV (111-121)
    o["bend_range_pos"]  = "Off" if u8(b, 111) == 0 else "+%d" % u8(b, 111)
    o["bend_range_neg"]  = "Off" if u8(b, 112) == 0 else "-%d" % u8(b, 112)
    o["joystick_assign_pos"] = ASSIGN.get(u8(b, 113), u8(b, 113))
    o["joystick_range_pos"]  = "%+d%%" % (u8(b, 114) - 100)
    o["joystick_assign_neg"] = ASSIGN.get(u8(b, 115), u8(b, 115))
    o["joystick_range_neg"]  = "%+d%%" % (u8(b, 116) - 100)
    o["cv_in_mode"]      = CV_MODE.get(u8(b, 117))
    o["cv_in1_assign"]   = ASSIGN.get(u8(b, 118), u8(b, 118))
    o["cv_in1_range"]    = "%+d%%" % (u8(b, 119) - 100)
    o["cv_in2_assign"]   = ASSIGN.get(u8(b, 120), u8(b, 120))
    o["cv_in2_range"]    = "%+d%%" % (u8(b, 121) - 100)

    # Tuning / LFO-Sync (122-127)
    o["micro_tuning"]    = MICRO_TUNING.get(u8(b, 122), u8(b, 122))
    o["scale_key"]       = "%+d" % (u8(b, 123) - 12)      # 0..24 = -12..+12
    o["program_tuning"]  = "%+d cent" % (u8(b, 124) - 50)  # 0..100 = -50..+50
    o["lfo_key_sync"]    = ONOFF.get(u8(b, 125))
    o["lfo_voice_sync"]  = ONOFF.get(u8(b, 126))
    o["lfo_target_osc"]  = LFO_TGTOSC.get(u8(b, 127))

    # Velocity / Multi / EG / Portamento (128-135)
    o["cutoff_velocity"] = u8(b, 128)
    o["amp_velocity"]    = u8(b, 129)
    o["multi_octave"]    = OCTAVE_FT.get(u8(b, 130))
    o["multi_routing"]   = MULTI_ROUTING.get(u8(b, 131))
    o["eg_legato"]       = ONOFF.get(u8(b, 132))
    o["portamento_mode"] = PORTA_MODE.get(u8(b, 133))
    o["portamento_bpm_sync"] = ONOFF.get(u8(b, 134))
    o["program_level"]   = "%+d (%d)" % (u8(b, 135) - 102, u8(b, 135))  # 12..132 = -18..+6 dB

    # VPM params (136-141), bipolar 0..200 = -100..+100%
    for i in range(6):
        o["vpm_param%d" % (i + 1)] = "%+d" % (u8(b, 136 + i) - 100)

    # User params (142-147) + their types (148/149, 2 bits each)
    utype149, utype148 = u8(b, 149), u8(b, 148)
    utypes = [(utype149 >> 0) & 3, (utype149 >> 2) & 3, (utype149 >> 4) & 3,
              (utype149 >> 6) & 3, (utype148 >> 0) & 3, (utype148 >> 2) & 3]
    for i in range(6):
        o["user_param%d" % (i + 1)] = user_param(u8(b, 142 + i), utypes[i])

    o["program_transpose"] = "%+d" % (u8(b, 150) - 13)   # 1..25 = -12..+12
    o["delay_dry_wet"]   = bit10(b, 151)
    o["reverb_dry_wet"]  = bit10(b, 153)
    o["aftertouch_assign"] = ASSIGN.get(u8(b, 155), u8(b, 155))

    o["_sequencer"] = decode_sequencer(b)
    return o


STEP_BASE = 190     # start of step-1 event
STEP_STRIDE = 52    # bytes per step (*note S3)
MOTION_OFF = (24, 31, 38, 45)   # offsets of the 4 motion slots within a step block


def decode_sequencer(b):
    seq = {}
    seq["marker_PRED"]   = b[156:160] == b"PRED"
    seq["marker_SQ"]     = b[160:162] == b"SQ"
    seq["bpm"]           = bit16le(b, 164) / 10.0
    seq["step_length"]   = u8(b, 166)
    seq["step_resolution"] = STEP_RES.get(u8(b, 167))
    seq["swing"]         = u8(b, 168) - 75    # Byte 0..150 = Swing -75..+75
    seq["default_gate"]  = "%d%%" % round(u8(b, 169) / 72 * 100)
    seq["arp_gate"]      = "%d%%" % round(u8(b, 1022) / 72 * 100)
    seq["arp_rate"]      = ARP_RATE.get(u8(b, 1023))
    seq["active_steps"]  = bits_to_steps(b[162], b[163])
    seq["on_steps"]      = bits_to_steps(b[170], b[171])
    seq["motion_steps"]  = bits_to_steps(b[172], b[173])

    # Motion slots (parameter assignment + active steps per slot)
    slots = []
    for i in range(4):
        cfg, pid = b[174 + i * 2], b[175 + i * 2]
        slots.append({
            "on":     bool(cfg & 1),
            "smooth": bool(cfg & 2),
            "param":  MOTION_PARAM.get(pid, "id=%d" % pid),
            "steps":  bits_to_steps(b[182 + i * 2], b[183 + i * 2]),
        })
    seq["motion_slots"] = slots

    # Steps with notes/velocity/gate and motion values
    steps = []
    for s in range(16):
        base = STEP_BASE + s * STEP_STRIDE
        notes = [(b[base + k], b[base + 8 + k]) for k in range(8)
                 if b[base + 8 + k] > 0]           # (note, velocity), only velocity>0
        gate_raw = b[base + 16]
        step = {
            "notes": [(note_name(n), n, v) for n, v in notes],
            "gate":  "%d%%" % round((gate_raw & 0x7F) / 72 * 100) if (gate_raw & 0x7F) <= 72 else "TIE",
            "trigger": bool(gate_raw & 0x80),
            "motion": [motion_points(b, base + MOTION_OFF[i]) for i in range(4)],
        }
        steps.append(step)
    seq["steps"] = steps
    return seq


def load_prog_bin(path):
    if path.lower().endswith(".mnlgxdprog") or zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as z:
            binname = next(n for n in z.namelist() if n.endswith(".prog_bin"))
            return z.read(binname)
    with open(path, "rb") as f:
        return f.read()


def main(argv):
    if not argv:
        print(__doc__)
        return 1
    for path in argv:
        b = load_prog_bin(path)
        if len(b) != 1024:
            print("WARN %s: %d bytes (expected 1024)" % (path, len(b)))
        o = decode(b)
        print("=" * 60)
        print("File: %s" % path)
        seq = o.pop("_sequencer")
        for k, v in o.items():
            print("  %-18s %s" % (k, v))
        print_sequencer(seq)
    return 0


def print_sequencer(seq):
    print("  --- sequencer ---")
    for k in ("bpm", "step_length", "step_resolution", "swing", "default_gate",
              "arp_gate", "arp_rate", "on_steps", "motion_steps"):
        print("  %-18s %s" % (k, seq[k]))
    for i, sl in enumerate(seq["motion_slots"], 1):
        if sl["on"]:
            print("  motion slot %d     -> %s  (smooth=%s, steps=%s)"
                  % (i, sl["param"], sl["smooth"], sl["steps"]))
    for s in seq["on_steps"]:
        st = seq["steps"][s - 1]
        notes = ", ".join("%s(v%d)" % (nm, v) for nm, n, v in st["notes"]) or "-"
        line = "  step %-2d           notes=%s  gate=%s  trig=%s" % (
            s, notes, st["gate"], st["trigger"])
        print(line)
        for i, sl in enumerate(seq["motion_slots"], 1):
            if sl["on"] and s in sl["steps"]:
                print("      motion%d (%s): %s" % (i, sl["param"], st["motion"][i - 1]))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
