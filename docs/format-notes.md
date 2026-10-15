# minilogue xd program format — verified notes

Source: MIDI implementation Rev 1.01, TABLE 2 + empirical checks against 3 real
presets (KY Redshift, LD Neon, PD Solitude) and a full library (`test.mnlgxdlib`),
all exported from the Korg Sound Librarian.

## File container (`.mnlgxdprog`)
Plain ZIP (deflate), 3 entries:
- `Prog_000.prog_bin`  — 1024 bytes, binary structure = TABLE 2.
- `Prog_000.prog_info` — XML: `<xd_ProgramInformation>` with `<Programmer>`, `<Comment>`.
- `FileInformation.xml` — Librarian manifest (`<KorgMSLibrarian_Data>`,
  Product="minilogue xd", references prog_bin + prog_info).

## Bank container (`.mnlgxdlib`)
Same ZIP principle; a full library = 1026 entries (verified on `test.mnlgxdlib`):
- **500×** `Prog_NNN.prog_bin` (+ `.prog_info`), NNN = 000..499 (always all slots).
- `FavoriteData.fav_data` (441 B).
- **6×** `TunS_NNN` (user scale) + **6×** `TunO_NNN` (user octave), each `_bin` + `_info`.
- `FileInformation.xml` — manifest, lists filenames only (no names/checksums);
  counters in the `<Contents>` tag: NumFavoriteData/NumProgramData/NumTuneScaleData/NumTuneOctData.
Program names live solely in each prog_bin (offset 4–15), not in the manifest.
`src/bank.py` handles this overlay-safe (only changed programs are replaced).

## prog_bin layout (excerpt, verified)
- 0–3    `'PROG'` (ASCII magic).
- 4–15   program name, 12 bytes ASCII. Padding is **inconsistent**: sometimes `0x00`
         (e.g. "LD Neon"), sometimes `0x20`/space (e.g. "KY Redshift "). For an
         exact round-trip, cut the name only at `0x00`, do NOT rstrip.
- 16     OCTAVE (0~4 = −2..+2).
- ...    synth parameters per TABLE 2.
- 156–159 `'PRED'`, 160–161 `'SQ'` → sequencer block.

## IMPORTANT: 10-bit parameters are little-endian
Every value marked "H:0~7 / L:0~7" (0~1023) is stored across **two consecutive
bytes, low byte first**:

    value = b[offset] | (b[offset+1] << 8)   # only the lower 10 bits matter

The "H/L" column labels in TABLE 2 are **misleading** (they suggest high-first).
Proven by VCO1/VCO2 PITCH = 512 (= 0 cents, dead center) in all three presets.
BPM (164/165) is also low-first.

## Enum correction: VOICE MODE TYPE (offset 21)
TABLE 2 states range 1~4, *note P3 is faulty (two "2"s).
Real data + NRPN *3-5 confirm the 5-value mapping:
`0=ARP LATCH, 1=ARP, 2=CHORD, 3=UNISON, 4=POLY` (KY Redshift = 4 = POLY).

## Nonlinear mappings (implemented in the decoder)
- VCO1/2 PITCH → cents: piecewise linear (*note P5).
- EG INT → %: piecewise quadratic (*note P10).

## Verified via single-byte diff (init preset + one change each)
Method: `src/diff.py base variant` → exactly one changed byte.
- **Cutoff Keytrack = offset 65** (confirmed). Mapping `0=0%, 1=50%, 2=100%`.
  The "100%" in the factory presets was real, not an offset error.
- **Swing = offset 168**, mapping with a **bias of 75**, NOT two's complement:
  `swing = byte168 - 75`  (byte 0..150 = swing -75..+75; 75 = neutral).
  Explains why all presets initially showed "75" = swing 0.
  Bias 75 = magnitude of the menu range end (a common pattern for bipolar values).

## Synth block complete (offsets 0–155)
Fully mapped in the decoder. Notable mappings:
- Bipolar values with a bias (like swing): program tuning `byte-50`, scale key `byte-12`,
  program transpose (150) `byte-13`, joystick/CV/VPM range (0..200) `byte-100`.
- The mod-FX subtype lives in separate bytes per type (90=Chorus … 94=User);
  only the one matching the type (89) is active.
- USER PARAM types are packed 2 bits each: byte 149 = params 1..4 (bits 0-1,2-3,4-5,6-7),
  byte 148 = params 5..6 (bits 0-1,2-3). Type 0=Percent, 1=Bipolar, 2=Select.
  Unused params (depending on the multi engine) often carry type 3 → shown raw.
- VOICE MODE DEPTH (19) is read differently depending on VOICE MODE TYPE (21)
  (Poly/Duo, Unison detune, Chord selection, Arp pattern; *note P2).

The synth block ends at 155 (Aftertouch Assign), right before `'PRED'` (156).

## Sequencer block (verified via SEQ_notes / SEQ_motion)
Header offsets (all confirmed):
- 162/163 active-step bitmask (16 bit, LE); 166 step length; 167 step resolution.
- 168 swing (see above); 169 default gate time (`% = byte/72*100`).
- 170/171 step on/off bitmask; 172/173 step-motion on/off bitmask.
- 174..181 motion slot 1–4 config: byte0 bit0=Motion On, bit1=Smooth On; byte1=param ID (*note S2-1, e.g. 42=CUTOFF).
- 182..189 per-slot motion-step bitmask (16 bit, LE).
- 1022 ARP gate time; 1023 ARP rate.

Step events: **start 190, stride 52 bytes/step** (*note S3), 16 steps.
Per step (relative offsets):
- +0..+7   note no (up to 8 = chord).
- +8..+15  velocity (0 = no event; default velocity = **127**).
- +16..+23 gate/trigger per note: bits0-6 = gate (0..72 = 0..100%, 73..127 = TIE), bit7 = trigger switch.
- +24..+30 / +31..+37 / +38..+44 / +45..+51  motion slot 1–4 data.

## 2nd 10-bit encoding: motion data (DIFFERENT from program parameters!)
A motion data point is NOT little-endian. 7 bytes per slot for 5 points (*note S3-2):
- byte0..4: high 8 bits (bits 2-9) of DATA 1..5 each.
- byte5: low 2 bits of DATA1..4 (2 bits each); byte6 bits0-1: low 2 of DATA5.
- `value = (byteN << 2) | low2`.
Proven on the cutoff sweep: steps 1..4 = 0 / 338 / 654 / 1023.
Smooth=On uses all 5 points (interpolated over quarters of the step); here each
step has all 5 equal = a flat value per step.
