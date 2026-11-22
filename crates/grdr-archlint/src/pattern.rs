// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: The Guardrails ADR Authors
use std::fmt;

use serde::Deserialize;

const WILDCARD: char = '*';

/// A crate name, or a name prefix written with one trailing `*` (`rsigma-*`).
#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord, Deserialize)]
#[serde(try_from = "String")]
pub enum NamePattern {
    Exact(String),
    Prefix(String),
}

#[derive(Debug, PartialEq, Eq)]
pub struct PatternError(String);

impl NamePattern {
    pub fn matches(&self, name: &str) -> bool {
        match self {
            Self::Exact(exact) => exact == name,
            Self::Prefix(prefix) => name.starts_with(prefix.as_str()),
        }
    }
}

impl TryFrom<String> for NamePattern {
    type Error = PatternError;

    fn try_from(text: String) -> Result<Self, Self::Error> {
        let stem = text.strip_suffix(WILDCARD).unwrap_or(&text);
        if stem.is_empty() || stem.contains(WILDCARD) {
            return Err(PatternError(text));
        }
        Ok(match text.strip_suffix(WILDCARD) {
            Some(prefix) => Self::Prefix(prefix.to_owned()),
            None => Self::Exact(text),
        })
    }
}

impl fmt::Display for NamePattern {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Exact(name) => f.write_str(name),
            Self::Prefix(prefix) => write!(f, "{prefix}{WILDCARD}"),
        }
    }
}

impl fmt::Display for PatternError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(
            f,
            "`{}` is not a crate name or a name prefix ending in one `{WILDCARD}`",
            self.0
        )
    }
}

pub fn any_matches(patterns: &[NamePattern], name: &str) -> bool {
    patterns.iter().any(|pattern| pattern.matches(name))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_prefix_pattern_matches_names_that_start_with_it() {
        let pattern = NamePattern::try_from("rsigma-*".to_owned()).unwrap();
        assert!(pattern.matches("rsigma-parser"));
        assert!(!pattern.matches("rsigma"));
    }

    #[test]
    fn an_exact_pattern_matches_only_its_name() {
        let pattern = NamePattern::try_from("regex".to_owned()).unwrap();
        assert!(pattern.matches("regex"));
        assert!(!pattern.matches("regex-syntax"));
    }

    #[test]
    fn a_wildcard_anywhere_but_the_end_is_refused() {
        assert!(NamePattern::try_from("a*b".to_owned()).is_err());
        assert!(NamePattern::try_from("*".to_owned()).is_err());
        assert!(NamePattern::try_from(String::new()).is_err());
    }
}
