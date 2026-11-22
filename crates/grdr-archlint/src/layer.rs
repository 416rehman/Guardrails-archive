// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: The Guardrails ADR Authors
use std::fmt;

use serde::de::{self, Deserialize, Deserializer, Unexpected, Visitor};

const TOOL: &str = "tool";

/// A crate's layer as `architecture.toml` and `[package.metadata.grdr]` write it: a number, or
/// `"tool"` for test and tool crates.
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub enum Layer {
    Numbered(u8),
    Tool,
}

struct LayerVisitor;

impl fmt::Display for Layer {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Numbered(number) => write!(f, "{number}"),
            Self::Tool => f.write_str(TOOL),
        }
    }
}

impl<'de> Deserialize<'de> for Layer {
    fn deserialize<D: Deserializer<'de>>(deserializer: D) -> Result<Self, D::Error> {
        deserializer.deserialize_any(LayerVisitor)
    }
}

impl Visitor<'_> for LayerVisitor {
    type Value = Layer;

    fn expecting(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "a layer number or \"{TOOL}\"")
    }

    fn visit_u64<E: de::Error>(self, value: u64) -> Result<Layer, E> {
        u8::try_from(value)
            .map(Layer::Numbered)
            .map_err(|_| E::invalid_value(Unexpected::Unsigned(value), &self))
    }

    fn visit_i64<E: de::Error>(self, value: i64) -> Result<Layer, E> {
        u8::try_from(value)
            .map(Layer::Numbered)
            .map_err(|_| E::invalid_value(Unexpected::Signed(value), &self))
    }

    fn visit_str<E: de::Error>(self, value: &str) -> Result<Layer, E> {
        if value == TOOL {
            Ok(Layer::Tool)
        } else {
            Err(E::invalid_value(Unexpected::Str(value), &self))
        }
    }
}
