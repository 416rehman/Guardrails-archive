// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: The Guardrails ADR Authors
use std::collections::BTreeMap;
use std::fmt;

use serde::Deserialize;

const CODE_PREFIX: &str = "ARCH-";
const CODE_DIGITS: usize = 3;

/// A lint rule id, `ARCH-NNN` (design/03 section 2, "Lint rules").
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Hash, Deserialize)]
#[serde(try_from = "String")]
pub struct RuleCode(u16);

#[derive(Debug, PartialEq, Eq)]
pub struct RuleCodeError(String);

/// The parts of a message that `architecture.toml` holds for one rule: why it exists, the fix and
/// the escape route.
#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RuleText {
    pub why: String,
    pub fix: String,
    pub escape: String,
}

/// One broken rule. `what` is the first of the four message parts; the others come from the
/// rule's `RuleText`.
#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub struct Finding {
    pub rule: RuleCode,
    pub what: String,
}

impl RuleCode {
    pub const LAYERS: Self = Self(1);
    pub const ADAPTERS: Self = Self(2);
    pub const CONTENT_PARSERS: Self = Self(4);
}

impl TryFrom<String> for RuleCode {
    type Error = RuleCodeError;

    fn try_from(text: String) -> Result<Self, Self::Error> {
        let number = text
            .strip_prefix(CODE_PREFIX)
            .filter(|digits| digits.len() == CODE_DIGITS)
            .filter(|digits| digits.bytes().all(|byte| byte.is_ascii_digit()))
            .and_then(|digits| digits.parse().ok());
        match number {
            Some(number) => Ok(Self(number)),
            None => Err(RuleCodeError(text)),
        }
    }
}

impl fmt::Display for RuleCode {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{CODE_PREFIX}{:0width$}", self.0, width = CODE_DIGITS)
    }
}

impl fmt::Display for RuleCodeError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(
            f,
            "`{}` is not a rule code of the form {CODE_PREFIX}NNN",
            self.0
        )
    }
}

impl Finding {
    pub fn new(rule: RuleCode, what: String) -> Self {
        Self { rule, what }
    }

    /// The four-part message of design/03 section 2, or `None` when `texts` has no row for the
    /// rule.
    pub fn render(&self, texts: &BTreeMap<RuleCode, RuleText>) -> Option<String> {
        let text = texts.get(&self.rule)?;
        Some(format!(
            "error[{}]: {}\n  why: {}\n  fix: {}\n  {}\n",
            self.rule, self.what, text.why, text.fix, text.escape
        ))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_rule_code_round_trips_through_its_text() {
        let code = RuleCode::try_from("ARCH-005".to_owned()).unwrap();
        assert_eq!(code.to_string(), "ARCH-005");
        assert_eq!(RuleCode::LAYERS.to_string(), "ARCH-001");
    }

    #[test]
    fn a_rule_code_needs_the_prefix_and_three_digits() {
        for text in ["ARCH-01", "ARCH-0001", "ARCH-00a", "GRDR-001", "ARCH-+01"] {
            assert!(RuleCode::try_from(text.to_owned()).is_err(), "{text}");
        }
    }

    #[test]
    fn the_message_has_the_four_parts_in_order() {
        let texts = BTreeMap::from([(
            RuleCode::LAYERS,
            RuleText {
                why: "the reason".to_owned(),
                fix: "the fix".to_owned(),
                escape: "if wrong: open an RFC".to_owned(),
            },
        )]);
        let finding = Finding::new(RuleCode::LAYERS, "`a` depends on `b`.".to_owned());
        assert_eq!(
            finding.render(&texts).unwrap(),
            "error[ARCH-001]: `a` depends on `b`.\n  why: the reason\n  fix: the fix\n  if wrong: open an RFC\n"
        );
        assert!(
            Finding::new(RuleCode::ADAPTERS, String::new())
                .render(&texts)
                .is_none()
        );
    }
}
