// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: The Guardrails ADR Authors

#[path = "table_ref/mod.rs"]
mod table_ref;

use grdr_fastpath::{BundleFault, Error, arena_size, load};
use std::fs;
use std::path::PathBuf;
use table_ref::{RefVerdict, section_bounds_from_header, validate, validate_header};

struct Rng(u64);

impl Rng {
    fn next_u64(&mut self) -> u64 {
        self.0 = self.0.wrapping_add(0x9E37_79B9_7F4A_7C15);
        let mut z = self.0;
        z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
        z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
        z ^ (z >> 31)
    }

    fn next_usize(&mut self, bound: usize) -> usize {
        if bound == 0 {
            return 0;
        }
        (self.next_u64() as usize) % bound
    }
}

fn case_count(default: usize) -> usize {
    std::env::var("PROPTEST_CASES")
        .ok()
        .and_then(|v| v.parse::<usize>().ok())
        .unwrap_or(default)
}

fn fixture_dir() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("tests")
        .join("fixtures")
        .join("table")
}

fn valid_seeds() -> Vec<Vec<u8>> {
    vec![
        include_bytes!("fixtures/table/valid_empty.bin").to_vec(),
        include_bytes!("fixtures/table/valid_minimal.bin").to_vec(),
        include_bytes!("fixtures/table/valid_full.bin").to_vec(),
    ]
}

fn to_ref_verdict(res: Result<(), Error>) -> Option<RefVerdict> {
    match res {
        Ok(()) => Some(RefVerdict::Accept),
        Err(Error::Abi) => Some(RefVerdict::Reject { rule: 3, abi: true }),
        Err(Error::Bundle(BundleFault::Rule(tv))) => Some(RefVerdict::Reject {
            rule: tv.number(),
            abi: false,
        }),
        Err(_) => None,
    }
}

fn write_u32_le(buf: &mut [u8], off: usize, val: u32) {
    if let Some(dst) = buf.get_mut(off..off + 4) {
        dst.copy_from_slice(&val.to_le_bytes());
    }
}

fn read_u32_le(buf: &[u8], off: usize) -> Option<u32> {
    let chunk = buf.get(off..)?.first_chunk::<4>()?;
    Some(u32::from_le_bytes(*chunk))
}

fn assert_differential(blob: &[u8], arena_buf: &mut Vec<u8>, label: &str) {
    let hdr_res = arena_size(blob);
    let hdr_verdict = match hdr_res {
        Ok(_) => Some(RefVerdict::Accept),
        Err(e) => to_ref_verdict(Err(e)),
    };
    assert_eq!(
        hdr_verdict,
        Some(validate_header(blob)),
        "header differential mismatch ({label})"
    );

    let needed = hdr_res.unwrap_or(512);
    if arena_buf.len() < needed {
        arena_buf.resize(needed, 0);
    }
    let arena_slice = arena_buf.get_mut(..needed).unwrap_or(&mut []);
    let load_res = load(blob, arena_slice).map(|_| ());
    let load_verdict = to_ref_verdict(load_res);
    let ref_verdict = validate(blob);
    assert_eq!(
        load_verdict,
        Some(ref_verdict),
        "full differential mismatch ({label})"
    );
    if ref_verdict == RefVerdict::Accept {
        let bounds = section_bounds_from_header(blob);
        assert!(
            bounds.is_some(),
            "accepted blob missing header bounds ({label})"
        );
    }
}

fn mutate_blob(rng: &mut Rng, seeds: &[Vec<u8>]) -> Vec<u8> {
    let seed_idx = rng.next_usize(seeds.len());
    let mut blob = seeds.get(seed_idx).cloned().unwrap_or_default();
    let mode = rng.next_usize(7);
    match mode {
        0 => {
            let idx = rng.next_usize(blob.len());
            if let Some(byte) = blob.get_mut(idx) {
                *byte ^= 1u8 << (rng.next_usize(8) as u32);
            }
        }
        1 => {
            let flips = 1 + rng.next_usize(6);
            for _ in 0..flips {
                let idx = rng.next_usize(blob.len());
                let val = rng.next_u64() as u8;
                if let Some(byte) = blob.get_mut(idx) {
                    *byte = val;
                }
            }
        }
        2 => {
            let new_len = rng.next_usize(blob.len());
            blob.truncate(new_len);
            if blob.len() >= 20 && rng.next_usize(2) == 0 {
                write_u32_le(&mut blob, 16, new_len as u32);
            }
        }
        3 => {
            let extra = 1 + rng.next_usize(32);
            let fill = if rng.next_usize(2) == 0 {
                0u8
            } else {
                rng.next_u64() as u8
            };
            blob.resize(blob.len() + extra, fill);
            if rng.next_usize(2) == 0 {
                let len = blob.len() as u32;
                write_u32_le(&mut blob, 16, len);
            }
        }
        4 => {
            let sec = rng.next_usize(10);
            let base = 96 + 8 * sec;
            let field_off = if rng.next_usize(2) == 0 {
                base
            } else {
                base + 4
            };
            let choices = [
                0u32,
                1,
                2,
                128,
                232,
                236,
                240,
                u32::MAX,
                (blob.len() as u32).saturating_add(8),
            ];
            let val = match rng.next_usize(3) {
                0 => choices
                    .get(rng.next_usize(choices.len()))
                    .copied()
                    .unwrap_or(0),
                1 => {
                    let cur = read_u32_le(&blob, field_off).unwrap_or(0);
                    cur.wrapping_add((rng.next_usize(17) as u32).wrapping_sub(8))
                }
                _ => rng.next_u64() as u32,
            };
            write_u32_le(&mut blob, field_off, val);
        }
        5 => {
            let offsets = [
                8usize, 12, 16, 20, 62, 176, 180, 182, 183, 184, 200, 208, 216, 220, 224,
            ];
            let off = offsets
                .get(rng.next_usize(offsets.len()))
                .copied()
                .unwrap_or(8);
            let val = match rng.next_usize(4) {
                0 => 0,
                1 => 1,
                2 => 0xFF,
                _ => rng.next_u64() as u8,
            };
            if let Some(byte) = blob.get_mut(off) {
                *byte = val;
            }
        }
        _ => {
            if blob.len() > 232 {
                let body_idx = 232 + rng.next_usize(blob.len() - 232);
                let byte_choices = [0u8, b'/', b'.', b'*', b'?', b'\\', b'A', b' ', 0xFF];
                let val = if rng.next_usize(2) == 0 {
                    byte_choices
                        .get(rng.next_usize(byte_choices.len()))
                        .copied()
                        .unwrap_or(0)
                } else {
                    rng.next_u64() as u8
                };
                if let Some(byte) = blob.get_mut(body_idx) {
                    *byte = val;
                }
            }
        }
    }
    blob
}

#[test]
fn differential_all_fixtures() {
    let mut entries: Vec<PathBuf> = fs::read_dir(fixture_dir())
        .expect("read fixtures dir")
        .map(|e| e.expect("dir entry").path())
        .collect();
    entries.sort();

    let mut arena = Vec::new();
    for path in entries {
        let name = path.file_name().and_then(|n| n.to_str()).expect("ascii");
        let bytes = fs::read(&path).expect("read");
        assert_differential(&bytes, &mut arena, name);
    }
}

#[test]
fn differential_generated_mutations() {
    let seeds = valid_seeds();
    let mut rng = Rng(0x4752_4452_0409_D1FF);
    let cases = case_count(4_096);
    let mut arena = Vec::new();
    for i in 0..cases {
        let blob = mutate_blob(&mut rng, &seeds);
        assert_differential(&blob, &mut arena, &format!("case {i}"));
    }
}

#[ignore]
#[test]
fn soak_differential_validator() {
    let seeds = valid_seeds();
    let mut rng = Rng(0x534F_414B_0409_D1FF);
    let cases = case_count(1_000_000);
    let mut arena = Vec::new();
    for i in 0..cases {
        let blob = mutate_blob(&mut rng, &seeds);
        assert_differential(&blob, &mut arena, &format!("soak {i}"));
    }
}
