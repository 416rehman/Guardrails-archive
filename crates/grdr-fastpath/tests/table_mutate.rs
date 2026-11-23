// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: The Guardrails ADR Authors

use grdr_fastpath::{BundleFault, Error, arena_size, load};

const HEADER_LEN: usize = 232;
const RECORD_SIZES: [u64; 10] = [64, 16, 40, 40, 48, 16, 40, 4, 16, 1];

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

fn valid_seeds() -> Vec<Vec<u8>> {
    vec![
        include_bytes!("fixtures/table/valid_empty.bin").to_vec(),
        include_bytes!("fixtures/table/valid_minimal.bin").to_vec(),
        include_bytes!("fixtures/table/valid_full.bin").to_vec(),
    ]
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

fn mutate_blob(rng: &mut Rng, seeds: &[Vec<u8>]) -> Vec<u8> {
    let seed_idx = rng.next_usize(seeds.len());
    let mut blob = seeds.get(seed_idx).cloned().unwrap_or_default();
    match rng.next_usize(6) {
        0 => {
            let idx = rng.next_usize(blob.len());
            if let Some(byte) = blob.get_mut(idx) {
                *byte ^= 1u8 << (rng.next_usize(8) as u32);
            }
        }
        1 => {
            let flips = 1 + rng.next_usize(8);
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
            blob.resize(blob.len() + extra, 0);
            if rng.next_usize(2) == 0 {
                let len = blob.len() as u32;
                write_u32_le(&mut blob, 16, len);
            }
        }
        4 => {
            let sec = rng.next_usize(10);
            let field_off = 96 + 8 * sec + if rng.next_usize(2) == 0 { 0 } else { 4 };
            let val = match rng.next_usize(4) {
                0 => 0u32,
                1 => HEADER_LEN as u32,
                2 => u32::MAX,
                _ => rng.next_u64() as u32,
            };
            write_u32_le(&mut blob, field_off, val);
        }
        _ => {
            if blob.len() > HEADER_LEN {
                let idx = HEADER_LEN + rng.next_usize(blob.len() - HEADER_LEN);
                let val = rng.next_u64() as u8;
                if let Some(byte) = blob.get_mut(idx) {
                    *byte = val;
                }
            }
        }
    }
    blob
}

fn check_mutation_bounds(blob: &[u8], arena_buf: &mut Vec<u8>) -> Result<(), String> {
    let needed = match arena_size(blob) {
        Ok(sz) => sz,
        Err(Error::Abi | Error::Bundle(BundleFault::Rule(_))) => 512,
        Err(other) => return Err(format!("arena_size returned unexpected error: {other:?}")),
    };
    if arena_buf.len() < needed {
        arena_buf.resize(needed, 0);
    }
    let arena_slice = arena_buf.get_mut(..needed).unwrap_or(&mut []);

    match load(blob, arena_slice) {
        Ok(tables) => {
            if blob.len() < HEADER_LEN {
                return Err(String::from("accepted blob shorter than header"));
            }
            let mut prev_end = HEADER_LEN as u64;
            for (idx, rec_size) in RECORD_SIZES.iter().enumerate() {
                let base = 96 + 8 * idx;
                let count = read_u32_le(blob, base).ok_or_else(|| String::from("read count"))?;
                let offset =
                    read_u32_le(blob, base + 4).ok_or_else(|| String::from("read offset"))?;
                let hdr_sec = tables.header().sections.get(idx).copied();
                if hdr_sec.map(|s| s.count) != Some(count)
                    || hdr_sec.map(|s| s.offset) != Some(offset)
                {
                    return Err(String::from("header section mismatch"));
                }
                if count > 0 {
                    let start = u64::from(offset);
                    let len = u64::from(count) * rec_size;
                    if start < HEADER_LEN as u64 || start % 8 != 0 || start < prev_end {
                        return Err(format!("section {idx} alignment/order invalid"));
                    }
                    let end = start
                        .checked_add(len)
                        .ok_or_else(|| String::from("section end overflow"))?;
                    if end > blob.len() as u64 {
                        return Err(format!("section {idx} past blob end"));
                    }
                    prev_end = end;
                } else if offset != 0 {
                    return Err(format!("empty section {idx} has non-zero offset"));
                }
            }
            Ok(())
        }
        Err(Error::Abi | Error::Bundle(BundleFault::Rule(_))) => Ok(()),
        Err(other) => Err(format!(
            "load on valid-sized arena returned unexpected error: {other:?}"
        )),
    }
}

#[test]
fn mutate_bounds_property() {
    let seeds = valid_seeds();
    let mut rng = Rng(0x4752_4452_0409_B00D);
    let cases = case_count(4_096);
    let mut arena = Vec::new();
    for _ in 0..cases {
        let blob = mutate_blob(&mut rng, &seeds);
        assert_eq!(check_mutation_bounds(&blob, &mut arena), Ok(()));
    }
}

#[ignore]
#[test]
fn soak_mutate_bounds_property() {
    let seeds = valid_seeds();
    let mut rng = Rng(0x534F_414B_0409_B00D);
    let cases = case_count(1_000_000);
    let mut arena = Vec::new();
    for _ in 0..cases {
        let blob = mutate_blob(&mut rng, &seeds);
        assert_eq!(check_mutation_bounds(&blob, &mut arena), Ok(()));
    }
}
