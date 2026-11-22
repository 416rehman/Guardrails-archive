// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: The Guardrails ADR Authors
use std::collections::{HashMap, VecDeque};
use std::hash::Hash;

use crate::graph::Graph;

const PATH_SEPARATOR: &str = " -> ";

/// A breadth-first search that remembers how it reached each state, so a finding can show the
/// shortest path that brought a crate in.
pub struct Search<S> {
    start: S,
    queue: VecDeque<S>,
    parent: HashMap<S, S>,
}

impl<S: Copy + Eq + Hash> Search<S> {
    pub fn new(start: S) -> Self {
        Self {
            start,
            queue: VecDeque::from([start]),
            parent: HashMap::new(),
        }
    }

    pub fn next(&mut self) -> Option<S> {
        self.queue.pop_front()
    }

    /// Queues `state`, reached from `from`, unless the search has already reached it.
    pub fn reach(&mut self, state: S, from: S) {
        if state == self.start || self.parent.contains_key(&state) {
            return;
        }
        self.parent.insert(state, from);
        self.queue.push_back(state);
    }

    /// The states from the start to `end`, both included.
    pub fn path(&self, end: S) -> Vec<S> {
        let mut path = vec![end];
        let mut current = end;
        while let Some(&previous) = self.parent.get(&current) {
            path.push(previous);
            current = previous;
        }
        path.reverse();
        path
    }
}

/// `a -> b -> c` from package indices.
pub fn describe_path(graph: &Graph, path: impl IntoIterator<Item = usize>) -> String {
    let names: Vec<&str> = path
        .into_iter()
        .filter_map(|index| graph.package(index))
        .map(|package| package.name.as_str())
        .collect();
    names.join(PATH_SEPARATOR)
}
