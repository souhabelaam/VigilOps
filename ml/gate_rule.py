"""The rule of the retrain gate: is a retrained model worse than the current one?

Pure Python on purpose (no torch, no data): the rule can be unit-tested in seconds in CI.

THE RULE WAS FIXED BEFORE ANY GATE RESULT WAS SEEN (same promise as the alert threshold:
never tune the rule so that a model passes). Where the numbers come from:
  - F1_DROP 0.05: ml/seed_spread.py showed the same recipe trained with 5 different seed sets moves
    F1 by +-0.009 (notes-api) and +-0.029 (report-api). A margin below that would reject good models
    by bad luck, so the margin is about two standard deviations of the noisiest app.
  - false alerts per hour: allowed to grow by 50 % plus 2 per hour. The "+2" keeps a tiny base
    (0 or 1 false alerts per hour) from turning one extra alarm into a rejection.
A candidate is rejected if it is worse than the current model on EITHER app, on EITHER measure.
"""
F1_DROP = 0.05
FALSE_FACTOR = 1.5
FALSE_SLACK = 2.0  # alerts per hour


def judge(current, candidate):
    """Compare two result dicts of ONE app (keys f1, false_alerts_per_hour).

    Returns (ok, reasons); reasons is empty when ok.
    """
    reasons = []
    if candidate["f1"] < current["f1"] - F1_DROP:
        reasons.append(f"F1 fell from {current['f1']} to {candidate['f1']} "
                       f"(more than {F1_DROP} allowed)")
    cur_fa = current["false_alerts_per_hour"] or 0.0
    cand_fa = candidate["false_alerts_per_hour"] or 0.0
    limit = cur_fa * FALSE_FACTOR + FALSE_SLACK
    if cand_fa > limit:
        reasons.append(f"false alerts per hour rose from {cur_fa} to {cand_fa} "
                       f"(limit {limit:.1f})")
    return not reasons, reasons


def verdict(per_app):
    """per_app: {app: {"current": result, "candidate": result}} -> (ok, {app: reasons})."""
    problems = {}
    for app, r in per_app.items():
        ok, reasons = judge(r["current"], r["candidate"])
        if not ok:
            problems[app] = reasons
    return not problems, problems
