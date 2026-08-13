# Complexity Analysis

## Variables

- $N$: number of nonblank log lines / parsed entries
- $L$: total characters across all input lines
- $U$: number of distinct truncated message keys
- $W$: configured error-rate window size

The following is derived from the repository's parser and analyzer loops, not from a runtime benchmark.

## Operations

| Operation | Best | Average | Worst | Auxiliary space |
|---|---:|---:|---:|---:|
| Parse lines into entries | $O(L)$ | $O(L)$ | $O(L)$ | $O(N+L)$ for returned records and retained text |
| Compute counts and top messages | $O(N)$ | $O(N+U)$ | $O(N+U)$ | $O(U)$ besides report output |
| Message-length anomaly scan | $O(N)$ | $O(N)$ | $O(N)$ | $O(N)$ for lengths and anomaly evidence |
| Error-rate spike scan | $O(N)$ | $O(N)$ | $O(N)$ | $O(N/W)$ for reported spikes |
| End-to-end CLI analysis | $O(L+N+U)$ | $O(L+N+U)$ | $O(L+N+U)$ | $O(N+L+U)$ |

The parser attempts a fixed set of anchored regular-expression formats per line. With four fixed patterns and ordinary bounded-line matching, total parsing work is linear in input characters. The analyzer makes separate linear passes for summary counts, length statistics, and spike windows.

## Bottlenecks and scale

The implementation stores all parsed entries and raw message text, so memory grows with input volume. Unique-message cardinality grows the `Counter` state; messages are truncated to 120 characters before counting to bound key length but not the number of unique keys.

The spike implementation uses non-overlapping windows. Its slices cover each complete entry at most once, so it is linear for the current design. Overlapping windows would require either $O(NW)$ naive work or a rolling count to preserve $O(N)$ time.

The committed 1,000-line benchmark is an empirical development baseline for a particular workload and environment. It is compatible with, but cannot prove, the asymptotic analysis above.
