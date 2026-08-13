# Mathematical Foundations

## Scope

This document specifies the statistical methods implemented in `logsight/analyzer.py`. The methods rank or flag observed log properties; they are not a probability model of incidents and do not provide calibrated confidence.

## Message-length z-score

For $N$ parsed entries, let $\ell_i$ be the character length of entry $i$'s message. The implementation computes the population mean and population standard deviation

\[
\mu=\frac{1}{N}\sum_{i=1}^{N}\ell_i,\qquad
\sigma=\sqrt{\frac{1}{N}\sum_{i=1}^{N}(\ell_i-\mu)^2}.
\]

When $\sigma>0$, the displayed anomaly magnitude is

\[
z_i=\frac{|\ell_i-\mu|}{\sigma}.
\]

With default threshold $\tau_z=2.5$, an entry is length-anomalous when $z_i>\tau_z$. If every message has equal length, $\sigma=0$ and the implementation does not assign a z-score or length anomaly. This is exactly the `fmean`, `pstdev`, and strict greater-than comparison in `detect_anomalies()`.

## Direct error-level rule

When `flag_errors=True`, every entry whose parsed severity is ERROR or CRITICAL is flagged independently of message length. An entry satisfying both rules is emitted once, with both reasons preserved in `AnomalyEvidence`. Thus the anomaly predicate is

\[
A_i=[\text{ERROR or CRITICAL}_i]\lor[\sigma>0\land z_i>\tau_z].
\]

## Error-rate windows

For a fixed window size $W$ and threshold $\tau_r$, the implementation examines complete, non-overlapping index windows $[jW, jW+W-1]$. If $e_j$ entries have ERROR or CRITICAL severity, it computes

\[
r_j=\frac{e_j}{W}
\]

and reports a spike when $r_j\geq\tau_r$. Defaults are $W=100$ and $\tau_r=0.25$. A final partial window is not analyzed. This is a descriptive rate threshold, not a binomial test or p-value.

## Summary statistics

`compute_stats()` reports the count of entries, ERROR/CRITICAL count, WARNING count, per-level counts, and up to ten most frequent messages after truncating each message key to 120 characters. The reported overall error rate is $e/N$ when $N>0$ and zero for an empty sequence.

## Interpretation limits

The logic assumes that parsed severity and message length are meaningful proxies for operator attention. It does not model timestamps, causality, inter-event dependence, severity calibration, an incident label, or a distribution shift.
