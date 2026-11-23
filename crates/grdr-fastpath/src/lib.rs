// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: The Guardrails ADR Authors
#![no_std]
#![forbid(unsafe_code)]
#![deny(clippy::arithmetic_side_effects)]
#![deny(clippy::as_conversions)]

#[path = "table/layout/mod.rs"]
pub mod layout;
mod table;

pub use table::{ArgFault, BundleFault, Error, Tables, TvRule, arena_size, load};
