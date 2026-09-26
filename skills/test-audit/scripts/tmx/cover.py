"""Kill-preserving test-suite reduction as weighted set cover.

The universe is every *obligation* the full suite discharges: each mutant it kills and,
optionally, each line it covers. Each test covers the obligations it discharges. A reduced
suite is valid iff the union of its tests' obligations equals the full suite's union. That
is a set-cover instance (NP-hard in general, Garey & Johnson SP5), so we solve it with the
standard reductions (essential tests, dominated tests, dominated obligations), then exact
branch-and-bound under a node budget, falling back to greedy with a proven lower bound.

Every result carries a certificate: obligation -> retained witness test. `check_certificate`
re-derives validity from the matrix alone, independent of how the plan was produced.
"""
from __future__ import annotations

import math
import time
from typing import Dict, Iterable, List, Optional, Set, Tuple


class Instance:
    """Bitset encoding. Obligations are indexed 0..n-1; each test maps to an int bitmask."""

    def __init__(self, obligations: List[str], sets: Dict[str, Set[str]], cost: Dict[str, float]):
        self.obligations = obligations
        self.index = {o: i for i, o in enumerate(obligations)}
        self.masks: Dict[str, int] = {}
        for t, s in sets.items():
            m = 0
            for o in s:
                i = self.index.get(o)
                if i is not None:
                    m |= 1 << i
            self.masks[t] = m
        self.cost = {t: float(cost.get(t, 1.0)) for t in sets}
        self.full = 0
        for m in self.masks.values():
            self.full |= m


def popcount(x: int) -> int:
    return bin(x).count("1")


def _greedy(masks: Dict[str, int], cost: Dict[str, float], universe: int, chosen: Iterable[str] = ()) -> List[str]:
    """Chvatal greedy: repeatedly take the test with the lowest cost per newly covered obligation."""
    picked = list(chosen)
    covered = 0
    for t in picked:
        covered |= masks[t]
    need = universe & ~covered
    while need:
        best, best_ratio = None, math.inf
        for t, m in masks.items():
            gain = popcount(m & need)
            if gain:
                r = cost[t] / gain
                if r < best_ratio or (r == best_ratio and best is not None and t < best):
                    best, best_ratio = t, r
        if best is None:  # uncoverable remainder; caller guarantees this cannot happen
            break
        picked.append(best)
        need &= ~masks[best]
    return _prune(picked, masks, cost, universe)


def _prune(picked: List[str], masks: Dict[str, int], cost: Dict[str, float], universe: int) -> List[str]:
    """Drop any picked test made redundant by the others, most expensive first."""
    keep = list(picked)
    for t in sorted(picked, key=lambda x: (-cost[x], x)):
        rest = 0
        for u in keep:
            if u != t:
                rest |= masks[u]
        if rest & universe == universe:
            keep.remove(t)
    return keep


def _lower_bound(masks: Dict[str, int], cost: Dict[str, float], need: int) -> float:
    """Valid lower bound on the cost to cover `need`.

    Packing bound: pick obligations whose killer sets are pairwise disjoint; each needs a
    distinct test, so the sum of their cheapest killers bounds the optimum from below.
    """
    killers: Dict[int, List[str]] = {}
    bits = need
    while bits:
        low = bits & -bits
        i = low.bit_length() - 1
        killers[i] = [t for t, m in masks.items() if m & low]
        bits ^= low
    order = sorted(killers, key=lambda i: len(killers[i]))
    used: Set[str] = set()
    bound = 0.0
    for i in order:
        ks = killers[i]
        if not ks or used.intersection(ks):
            continue
        used.update(ks)
        bound += min(cost[t] for t in ks)
    return bound


def _components(live: Dict[str, int], need: int):
    """Split the residual into components: tests connected through shared needed obligations."""
    parent = {t: t for t in live}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    owner: Dict[int, str] = {}
    for t, m in live.items():
        bits = m & need
        while bits:
            low = bits & -bits
            bits ^= low
            if low in owner:
                parent[find(t)] = find(owner[low])
            else:
                owner[low] = t
    groups: Dict[str, List[str]] = {}
    for t in live:
        groups.setdefault(find(t), []).append(t)
    for ts in groups.values():
        m = 0
        for t in ts:
            m |= live[t] & need
        yield sorted(ts), m


def _bnb(live: Dict[str, int], cost: Dict[str, float], need: int, seed: List[str], budget: int,
         deadline: float):
    """Exact search for a min-cost cover of `need`, seeded with an incumbent. Returns
    (best, exhausted, nodes)."""
    best, best_cost = list(seed), sum(cost[t] for t in seed)
    nodes = 0
    exhausted = True
    max_gain = max((popcount(m & need) for m in live.values()), default=1) or 1
    min_cost = min((cost[t] for t in live), default=1.0)

    def bound(need_b):
        return max(_lower_bound(live, cost, need_b), math.ceil(popcount(need_b) / max_gain) * min_cost)

    def branch(need_b: int, picked: List[str], spent: float) -> None:
        nonlocal best, best_cost, nodes, exhausted
        if not exhausted:
            return
        nodes += 1
        if nodes > budget or time.monotonic() > deadline:
            exhausted = False
            return
        if not need_b:
            if spent < best_cost - 1e-12:
                best, best_cost = list(picked), spent
            return
        if spent + bound(need_b) >= best_cost - 1e-12:
            return
        bits, pick_ks = need_b, None
        while bits:  # branch on the obligation with the fewest killers
            low = bits & -bits
            bits ^= low
            ks = [t for t, m in live.items() if m & low]
            if pick_ks is None or len(ks) < len(pick_ks):
                pick_ks = ks
                if len(ks) <= 1:
                    break
        for t in sorted(pick_ks or [], key=lambda x: (cost[x] / max(1, popcount(live[x] & need_b)), x)):
            picked.append(t)
            branch(need_b & ~live[t], picked, spent + cost[t])
            picked.pop()

    if need:
        branch(need, [], 0.0)
    return best, exhausted, nodes


def solve(inst: Instance, forced: Iterable[str] = (), node_budget: int = 200_000,
          time_budget_s: float = 20.0) -> dict:
    masks, cost, universe = dict(inst.masks), inst.cost, inst.full
    forced = [t for t in forced if t in masks]
    stats = {"tests": len(masks), "obligations": popcount(universe)}

    chosen: List[str] = list(forced)
    need = universe
    for t in chosen:
        need &= ~masks[t]

    # Reduction 1: drop tests that discharge nothing still needed.
    live = {t: m & need for t, m in masks.items() if t not in chosen and m & need}
    changed = True
    while changed and need:
        changed = False
        # Reduction 2: essential tests (sole killer of some obligation).
        bits = need
        while bits:
            low = bits & -bits
            bits ^= low
            ks = [t for t, m in live.items() if m & low]
            if len(ks) == 1:
                t = ks[0]
                chosen.append(t)
                need &= ~masks[t]
                live = {u: m & need for u, m in live.items() if u != t and m & need}
                changed = True
                break
        if changed:
            continue
        # Reduction 3: dominated tests (subset of a no-more-expensive test).
        names = sorted(live, key=lambda t: (-popcount(live[t]), cost[t], t))
        for a in names:
            for b in names:
                if a != b and b in live and a in live:
                    ma, mb = live[a], live[b]
                    if ma | mb == mb and cost[b] <= cost[a] and (ma != mb or (cost[b], b) < (cost[a], a)):
                        del live[a]
                        changed = True
                        break
            if changed:
                break
    stats["essential_or_forced"] = len(chosen)
    stats["residual_tests"] = len(live)
    stats["residual_obligations"] = popcount(need)

    # Exact branch and bound, one connected component at a time. Components share no obligation,
    # so their optima add up exactly; searching them jointly would explore a product space.
    deadline = time.monotonic() + time_budget_s
    best: List[str] = []
    greedy_cost = 0.0
    nodes_total = 0
    exhausted = True
    lb_residual = 0.0
    for comp_tests, comp_need in _components(live, need):
        sub = {t: live[t] for t in comp_tests}
        g = _greedy(sub, cost, comp_need)
        greedy_cost += sum(cost[t] for t in g)
        picked, done, nodes = _bnb(sub, cost, comp_need, g, max(1, node_budget - nodes_total), deadline)
        nodes_total += nodes
        exhausted = exhausted and done
        best += picked
        lb_residual += sum(cost[t] for t in picked) if done else _lower_bound(sub, cost, comp_need)
    keep = sorted(set(chosen) | set(best))
    lb = sum(cost[t] for t in chosen) + lb_residual
    total = sum(cost[t] for t in keep)
    stats.update({"bnb_nodes": nodes_total, "greedy_residual_cost": greedy_cost})
    return {
        "keep": keep,
        "cost": total,
        "optimal": exhausted,
        "lower_bound": total if exhausted else lb,
        "stats": stats,
    }


def certificate(inst: Instance, keep: Iterable[str]) -> Tuple[Dict[str, str], List[str]]:
    """Map every obligation to one retained witness; list any obligation left uncovered."""
    keep = sorted(keep, key=lambda t: (inst.cost[t], t))
    witness: Dict[str, str] = {}
    missing: List[str] = []
    for o, i in inst.index.items():
        bit = 1 << i
        if not inst.full & bit:
            continue
        w = next((t for t in keep if inst.masks[t] & bit), None)
        if w is None:
            missing.append(o)
        else:
            witness[o] = w
    return witness, missing


def check_certificate(obligation_killers: Dict[str, Set[str]], keep: Set[str],
                      witness: Dict[str, str]) -> List[str]:
    """Independent checker. Returns a list of violations (empty means the reduction is sound).

    `obligation_killers` comes straight from the matrix: obligation -> tests that discharge it
    in the FULL suite. Sound iff every dischargeable obligation has a witness that is retained
    and genuinely discharges it.
    """
    problems = []
    for o, killers in sorted(obligation_killers.items()):
        if not killers:
            continue
        w = witness.get(o)
        if w is None:
            problems.append(f"{o}: no witness")
        elif w not in keep:
            problems.append(f"{o}: witness {w} is not retained")
        elif w not in killers:
            problems.append(f"{o}: witness {w} does not discharge it")
    return problems


def classify_removed(inst: Instance, keep: Iterable[str]) -> Dict[str, dict]:
    """Explain each removed test relative to the retained set."""
    keep = set(keep)
    out: Dict[str, dict] = {}
    kept_masks = {t: inst.masks[t] for t in keep}
    for t, m in sorted(inst.masks.items()):
        if t in keep:
            continue
        if m == 0:
            out[t] = {"reason": "zero-signal"}
            continue
        dup = sorted(k for k, km in kept_masks.items() if km == m)
        if dup:
            out[t] = {"reason": "duplicate", "of": dup[0]}
            continue
        sup = sorted((k for k, km in kept_masks.items() if m | km == km),
                     key=lambda k: (popcount(kept_masks[k]), k))
        if sup:
            out[t] = {"reason": "subsumed", "by": sup[0]}
            continue
        by = sorted(k for k, km in kept_masks.items() if km & m)
        out[t] = {"reason": "jointly-covered", "by": by}
    return out


def curve(inst: Instance) -> List[Tuple[int, float, str]]:
    """Greedy order: (tests kept, fraction of obligations discharged, test added). Shows the
    size/strength trade-off (Shi et al. 2014: keeping 95% of kills buys ~17pp more reduction)."""
    total = popcount(inst.full)
    need, covered, out = inst.full, 0, []
    remaining = dict(inst.masks)
    while need and remaining:
        t = max(remaining, key=lambda x: (popcount(remaining[x] & need) / inst.cost[x], x))
        if not remaining[t] & need:
            break
        covered |= remaining.pop(t)
        need = inst.full & ~covered
        out.append((len(out) + 1, round(popcount(covered) / total, 4) if total else 1.0, t))
    return out
