// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: The Guardrails ADR Authors

pub fn path_entry_steps(path_chars: u64, pattern_chars: u64) -> u64 {
    path_chars
        .saturating_add(1)
        .saturating_mul(pattern_chars.saturating_add(1))
}

pub fn path_steps_from_pattern_lens<I>(path_chars: u64, pattern_chars: I) -> u64
where
    I: IntoIterator<Item = u64>,
{
    let mut sum = 0u64;
    for pat_len in pattern_chars {
        sum = sum.saturating_add(path_entry_steps(path_chars, pat_len));
    }
    sum
}

pub fn exe_lookup_steps(exe_count: u32) -> u64 {
    if exe_count == 0 {
        return 0;
    }
    u64::from(32u32.saturating_sub(exe_count.leading_zeros()))
}

pub fn total_eval_cost(run_rows: u32, path_steps: u64, host_steps: u64, exe_steps: u64) -> u64 {
    u64::from(run_rows)
        .saturating_add(path_steps)
        .saturating_add(host_steps)
        .saturating_add(exe_steps)
}
