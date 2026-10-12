"""Shared, deterministic building blocks for Architecture Analysis V2's
confidence/context model: a stable finding identifier, and the
runtime-vs-supporting-structure classifier detectors use as contextual
evidence (CLAUDE.md's "the graph provides the evidence" -- nothing here is a
judgment call, every function is a pure, reproducible rule over data the
backend already reconstructed).
"""
import hashlib

from analysis.reconstruction.models import ArchitectureComponent

# Mirrors frontend/src/lib/architectureModel.ts's SUPPORTING_DIR_SEGMENTS
# exactly, so "supporting structure" means the same thing on both sides of
# the API. Kept as an explicit backend copy (Python analysis code cannot
# import a TypeScript module) rather than duplicated ad hoc per detector --
# if the frontend's list changes, this one must be updated to match.
# Deliberately excludes "examples": example apps are often genuine runnable
# applications, not scaffolding (same reasoning as the frontend comment).
SUPPORTING_DIR_SEGMENTS = frozenset(
    {
        "doc", "docs", "documentation",
        "tool", "tools",
        "script", "scripts",
        "build",
        "benchmark", "benchmarks",
        ".github",
        "ci",
    }
)


def is_supporting_component(component: ArchitectureComponent) -> bool:
    """True for test code (role == "test", already a deterministic backend
    signal) or an exact supporting-directory-segment match. Runtime vs
    supporting is a structural fact the reconstruction engine's own grouping
    already implies; this just makes it queryable from the analysis layer."""
    if component.role == "test":
        return True
    segments = component.id.lower().split("/")
    return any(seg in SUPPORTING_DIR_SEGMENTS for seg in segments)


def compute_finding_id(repo_id: str, smell_type: str, *identity_parts: str) -> str:
    """Deterministic, content-addressed finding ID.

    Canonicalization rule: sha256 of `repo_id`, `smell_type`, and the
    detector-supplied `identity_parts` -- the minimal set of stable
    attributes that identify *this specific structural condition* --
    joined with a separator (0x1F, "unit separator") that cannot appear in a
    qualified name or component id. Truncated to the first 16 hex characters
    (64 bits) -- ample collision resistance for the handful of findings one
    repository produces, while staying short enough to use as a UI key or
    URL fragment.

    Deliberately excludes anything *derived* from the finding (title,
    evidence text, severity, confidence) so the ID identifies the underlying
    condition, not today's scoring of it -- the same condition keeps the
    same ID even if a threshold or confidence rule changes later.

    Per-detector identity_parts (each caller documents its own choice):
      - circular_dependency: every member's qualified_name, sorted
      - god_class / large_function / dead_code_candidate: the symbol's
        qualified_name
      - architecture_boundary_violation / layer_skip: (source_component_id,
        target_component_id) in order -- direction is semantically part of
        the finding
      - circular_component_dependency: the two component ids, sorted (the
        relationship is symmetric)
      - excessive_component_coupling: the component's id

    Stability: for two requests against the same analyzed repository state
    (repo_id), the same underlying graph produces the same identity_parts
    for the same condition regardless of Neo4j result ordering, dict
    iteration order, or any other incidental nondeterminism upstream --
    because identity_parts are always sorted/ordered by the caller before
    being passed in, never taken from iteration order directly.
    """
    raw = "\x1f".join((repo_id, smell_type, *identity_parts))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
