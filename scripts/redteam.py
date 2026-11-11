"""Red-team run: find inputs that evade Kalkan and save them as hard examples.

Generators (adapters implementing AttackGenerator):
  mutate (default, offline) - training transforms only; the held-out evasion split stays untouched
  llm                       - any OpenAI-compatible endpoint (KALKAN_ATTACKER_URL / _MODEL / _KEY)

Evasions go to data/redteam/round_<n>.jsonl. Review them, then retrain:
    python scripts/build_dataset.py --extra data/redteam/round_1.jsonl && python scripts/train_classical.py
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from kalkan import Decision, Kalkan  # noqa: E402
from kalkan.adapters.attackers.mutation import MutationAttacker  # noqa: E402


def seeds(path="data/processed/train.jsonl") -> list[str]:
    rows = [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines()]
    return sorted({r["text"] for r in rows if r["label"] == 1 and not r["transforms"]})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["mutate", "llm"], default="mutate")
    ap.add_argument("--round", type=int, default=1)
    ap.add_argument("--seeds", type=int, default=50)
    ap.add_argument("--variants", type=int, default=20)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    if args.mode == "llm":
        from kalkan.adapters.attackers.llm import OpenAICompatibleAttacker
        attacker = OpenAICompatibleAttacker()
    else:
        attacker = MutationAttacker(args.seed)
    guard, pool = Kalkan.from_directory(), seeds()

    tried, evasions = 0, []
    for attack in random.Random(args.seed).sample(pool, min(args.seeds, len(pool))):
        for v in attacker.variants(attack, args.variants):
            tried += 1
            verdict = guard.check(v)
            if verdict.decision == Decision.ALLOW:
                evasions.append({"text": v, "label": 1, "category": f"redteam_{args.mode}",
                                 "template_id": f"rt{args.round}", "seed_attack": attack, "score": verdict.score})

    out = Path("data/redteam") / f"round_{args.round}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in evasions), encoding="utf-8")
    print(f"{args.mode}: {tried} variants, {len(evasions)} evaded "
          f"({len(evasions) / max(tried, 1):.1%}) -> {out}. Review before retraining.")


if __name__ == "__main__":
    main()
