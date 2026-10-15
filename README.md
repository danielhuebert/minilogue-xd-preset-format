# minilogue xd – preset format

Reverse engineering and tooling for the Korg minilogue xd preset format,
derived from the MIDI implementation (Rev. 1.01) → **TABLE 2 (PROGRAM PARAMETER)**,
verified against real presets and a full library.

**Status: complete codec.** Read, edit and JSON-export/import both single
programs *and* banks — all round-trip verified, and the generated single program
additionally confirmed on hardware (Sound Librarian → minilogue xd).

## Folder layout

- `src/`     – tools (Python, see below).
- `docs/`    – `format-notes.md`: full, verified format documentation.
- `presets/` – real `.mnlgxdprog` / `.mnlgxdlib` files for testing (ZIP containers).
- `out/`     – extracted/generated results (working output).

> `presets/` is intentionally empty in the repo. Drop your own `.mnlgxdprog` /
> `.mnlgxdlib` files there to try the tools (export one from the Korg Sound Librarian).

## File format (short version)

The program *content* is 1024 bytes (`'PROG'` magic at offset 0), described in
TABLE 2. The file itself is a **ZIP**:

- `.mnlgxdprog` (one program): `Prog_000.prog_bin` (= TABLE 2),
  `Prog_000.prog_info`, `FileInformation.xml`.
- `.mnlgxdlib` (bank): 500× `Prog_NNN.*`, `FavoriteData.fav_data`,
  6× user scale + 6× user octave, `FileInformation.xml`.

Offsets, mappings and gotchas are in [docs/format-notes.md](docs/format-notes.md).

## Tools

Run each with `python3 -I src/<tool>.py`.

| Command | Purpose |
|---|---|
| `decode.py <preset>` | Print a preset in readable form (full 1024-byte decode). |
| `diff.py <a> <b> [...]` | Byte diff (for offset calibration). |
| `encode.py <in> <out> <json>` | Change parameters, write a valid file. |
| `encode.py --json <in> [out]` | Round-trip-safe JSON export. |
| `encode.py --list` | Supported parameters + value ranges. |
| `bank.py --list <lib>` | All 500 program names of a bank. |
| `bank.py --extract <lib> <i> <out.mnlgxdprog>` | A slot as a single preset. |
| `bank.py --set <lib> <i> <json> <out.lib>` | Patch one program. |
| `bank.py --replace <lib> <i> <prog> <out.lib>` | Replace a slot. |
| `bank.py --json <lib> [out]` | Whole bank as JSON (search/filter). |

### Examples

```sh
# Inspect a preset
python3 -I src/decode.py mypatch.mnlgxdprog

# Edit parameters (enums by name, bipolar values in natural units)
python3 -I src/encode.py in.mnlgxdprog out.mnlgxdprog '{"cutoff":900,"vco1_wave":"SQR","name":"My Patch"}'

# Export to JSON, edit, write back (lossless round-trip)
python3 -I src/encode.py --json in.mnlgxdprog patch.json
python3 -I src/encode.py in.mnlgxdprog out.mnlgxdprog @patch.json

# Find all UNISON patches with delay in a bank
python3 -I src/bank.py --json lib.mnlgxdlib bank.json
```

## What has been verified

- [x] ZIP/XML wrapper (single program **and** bank).
- [x] Full synth block 0–155 (all parameters, enums, nonlinear & bipolar mappings).
- [x] Full sequencer 156–1021 (steps/notes/velocity/gate/trigger + motion slots)
      and ARP 1022–1023.
- [x] **Two different 10-bit encodings** (program little-endian;
      motion `(byte<<2)|low2`).
- [x] Bias mappings of bipolar values (swing @168, keytrack @65, etc.) via
      single-byte diff.
- [x] Encoder round-trip safe (empty patch = byte-identical) + confirmed **on hardware**.
- [x] JSON export lossless (export → JSON → encode = byte-identical).
- [x] Bank round-trip safe (all 1026 entries identical; overlay changes only
      patched programs).

## Encoder notes

- Nonlinear fields are addressed as RAW values (0..1023): `vco1_pitch_raw`,
  `vco2_pitch_raw`, `eg_int_raw`, `program_level_raw`.
- Everything else in natural units: enums by name or index, bipolar values
  directly (e.g. `scale_key: -5`, `program_tuning: 10`).

## Open / optional

No open format questions. Possible extensions: decoding the user scale/octave
tunings and `FavoriteData` (currently preserved byte-exactly, but not interpreted).

## Source

Derived from the publicly available minilogue xd MIDI implementation chart plus a
handful of deliberately crafted test presets. Preset binaries are not included in
this repository.
