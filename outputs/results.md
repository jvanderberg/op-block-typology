# Race and ethnicity by block type, Oak Park, Illinois

Every number below is produced by the pipeline in this repository from the
sources listed in PROVENANCE.md. Blocks are 2020 Census blocks; block types come
from the Cook County Assessor's 2026 parcel data; residents come from the 2020
Census (P.L. 94-171 table P2). Totals are reported for whole categories of
blocks only, never for individual blocks.

## Block types

A block is **single-family only** when at least 95% of its housing units are
single-family houses (detached, or attached townhomes). It is **2-6 unit** or **7+ unit** when
buildings of that size hold at least half of its units. Everything else with housing is
**mixed**: typically houses alongside 2-flats, small apartment buildings or a condo building.

| category | Blocks | Units (parcels) | Units (2020 Census) | % single-family | % in 2-6 unit bldgs | % in 7+ unit bldgs | Units estimated |
|---|---|---|---|---|---|---|---|
| Single-family only | 462 | 5,973 | 6,018 | 100 | 0 | 0 | 0 |
| 2-6 unit buildings dominate | 70 | 1,295 | 1,243 | 19.1 | 68.2 | 12.7 | 0 |
| 7+ unit buildings dominate | 208 | 15,488 | 14,124 | 6.6 | 7.2 | 86.3 | 1,279 |
| Mixed (houses + apartments) | 220 | 4,413 | 4,512 | 70 | 21 | 9 | 9 |
| No housing | 98 | 0 | 56 | 0 | 0 | 0 | 0 |

## A. Who lives on each block type (2020 Census)

Oak Park's 2020 population was 54,583: 60.2% White (non-Hispanic), 18.7% Black (non-Hispanic), 9.3% Hispanic or Latino, 5.4% Asian (non-Hispanic).

| category | Blocks | Population | White | Black | Hispanic or Latino | Asian | Two or more races | Other |
|---|---|---|---|---|---|---|---|---|
| Single-family only | 462 | 18,464 | 68.7 | 10.4 | 8.6 | 4.4 | 7.3 | 0.6 |
| 2-6 unit buildings dominate | 70 | 2,837 | 45.8 | 28.9 | 12.2 | 5.9 | 6.4 | 0.8 |
| 7+ unit buildings dominate | 208 | 21,327 | 51.7 | 27.7 | 9.2 | 6.5 | 4.4 | 0.6 |
| Mixed (houses + apartments) | 220 | 11,857 | 66 | 12.8 | 9.7 | 4.9 | 6.1 | 0.6 |
| No housing | 98 | 98 | 22.4 | 33.7 | 28.6 | 5.1 | 6.1 | 4.1 |
| all blocks | 1,058 | 54,583 | 60.2 | 18.7 | 9.3 | 5.4 | 5.8 | 0.6 |

![race by block type](fig_race_by_block_type.png)

## B. Where each group lives

Share of each group's Oak Park residents living on each block type.

| category | Population | White | Black | Hispanic or Latino | Asian | Two or more races | Other |
|---|---|---|---|---|---|---|---|
| Single-family only | 18,464 | 38.6 | 18.8 | 31.4 | 27.8 | 42.3 | 32.8 |
| 2-6 unit buildings dominate | 2,837 | 4 | 8 | 6.8 | 5.7 | 5.7 | 6.7 |
| 7+ unit buildings dominate | 21,327 | 33.6 | 57.9 | 38.6 | 46.8 | 29.1 | 39 |
| Mixed (houses + apartments) | 11,857 | 23.8 | 14.9 | 22.6 | 19.6 | 22.7 | 20.2 |
| No housing | 98 | 0.1 | 0.3 | 0.6 | 0.2 | 0.2 | 1.2 |

![where groups live](fig_where_groups_live.png)

## C. Sensitivity to the single-family cutoff

Single-family cutoff at 100% of units:

| category | Blocks | Population | White | Black | Hispanic or Latino | Asian | Two or more races | Other |
|---|---|---|---|---|---|---|---|---|
| Single-family only | 460 | 18,330 | 68.8 | 10.2 | 8.6 | 4.5 | 7.3 | 0.6 |
| 2-6 unit buildings dominate | 70 | 2,837 | 45.8 | 28.9 | 12.2 | 5.9 | 6.4 | 0.8 |
| 7+ unit buildings dominate | 208 | 21,327 | 51.7 | 27.7 | 9.2 | 6.5 | 4.4 | 0.6 |
| Mixed (houses + apartments) | 222 | 11,991 | 65.8 | 13.1 | 9.7 | 4.8 | 6.1 | 0.6 |
| No housing | 98 | 98 | 22.4 | 33.7 | 28.6 | 5.1 | 6.1 | 4.1 |
| all blocks | 1,058 | 54,583 | 60.2 | 18.7 | 9.3 | 5.4 | 5.8 | 0.6 |

Single-family cutoff at 90% of units:

| category | Blocks | Population | White | Black | Hispanic or Latino | Asian | Two or more races | Other |
|---|---|---|---|---|---|---|---|---|
| Single-family only | 476 | 19,449 | 68.6 | 10.6 | 8.6 | 4.5 | 7.2 | 0.6 |
| 2-6 unit buildings dominate | 70 | 2,837 | 45.8 | 28.9 | 12.2 | 5.9 | 6.4 | 0.8 |
| 7+ unit buildings dominate | 208 | 21,327 | 51.7 | 27.7 | 9.2 | 6.5 | 4.4 | 0.6 |
| Mixed (houses + apartments) | 206 | 10,872 | 65.9 | 12.6 | 9.8 | 4.8 | 6.2 | 0.6 |
| No housing | 98 | 98 | 22.4 | 33.7 | 28.6 | 5.1 | 6.1 | 4.1 |
| all blocks | 1,058 | 54,583 | 60.2 | 18.7 | 9.3 | 5.4 | 5.8 | 0.6 |

Every estimated 7+ building unit count (buildings absent from the Commercial Valuation
dataset, whose units are estimated from assessed value) replaced by the class minimum of 7:

| category | Blocks | Population | White | Black | Hispanic or Latino | Asian | Two or more races | Other |
|---|---|---|---|---|---|---|---|---|
| Single-family only | 462 | 18,464 | 68.7 | 10.4 | 8.6 | 4.4 | 7.3 | 0.6 |
| 2-6 unit buildings dominate | 70 | 2,837 | 45.8 | 28.9 | 12.2 | 5.9 | 6.4 | 0.8 |
| 7+ unit buildings dominate | 208 | 21,327 | 51.7 | 27.7 | 9.2 | 6.5 | 4.4 | 0.6 |
| Mixed (houses + apartments) | 220 | 11,857 | 66 | 12.8 | 9.7 | 4.9 | 6.1 | 0.6 |
| No housing | 98 | 98 | 22.4 | 33.7 | 28.6 | 5.1 | 6.1 | 4.1 |
| all blocks | 1,058 | 54,583 | 60.2 | 18.7 | 9.3 | 5.4 | 5.8 | 0.6 |

## D. Block groups classified by their own housing mix

Census block groups are the smallest geography with published ACS estimates, and their
2020 counts carry far less disclosure-avoidance noise than blocks. Each block group is
classified by the same rule applied to all of its units. Most Oak Park block groups are
internally mixed, so this is a coarser cut.

2020 Census counts:

| category | Block groups | Population | White | Black | Hispanic or Latino | Asian | Two or more races | Other |
|---|---|---|---|---|---|---|---|---|
| Single-family only | 3 | 2,813 | 73.9 | 7.8 | 6 | 4.5 | 7.1 | 0.7 |
| 7+ unit buildings dominate | 19 | 21,689 | 54 | 23.7 | 10.1 | 6.4 | 5.2 | 0.7 |
| Mixed (houses + apartments) | 31 | 30,081 | 63.3 | 16.1 | 9.1 | 4.8 | 6.2 | 0.5 |
| all blocks | 53 | 54,583 | 60.2 | 18.7 | 9.3 | 5.4 | 5.8 | 0.6 |

ACS 2020-2024 five-year estimates (percent, with 90% margin of error):

| category | Block groups | Population | White | Black | Hispanic or Latino | Asian | MOE White | MOE Black | MOE Hispanic | MOE Asian |
|---|---|---|---|---|---|---|---|---|---|---|
| Single-family only | 3 | 2,551 | 75.2 | 5.4 | 8.9 | 3 | 8.4 | 3.8 | 6.5 | 2.2 |
| 7+ unit buildings dominate | 19 | 21,386 | 60.1 | 21.5 | 9.1 | 4.4 | 3.5 | 3.5 | 2.1 | 1.6 |
| Mixed (houses + apartments) | 31 | 29,355 | 61.3 | 16.2 | 9.5 | 5.8 | 1.8 | 2.9 | 2.2 | 1.9 |

## E. Within-block-group contrast

Only block groups that contain more than one block type, so each comparison holds the
neighbourhood constant. This is the comparison most exposed to the 2020 disclosure-avoidance
noise, which shifts people between blocks within a block group and therefore shrinks
differences; treat it as a lower bound on the true contrast.

| category | Block groups | Blocks | Population | White | Black | Hispanic or Latino | Asian | Two or more races | Other |
|---|---|---|---|---|---|---|---|---|---|
| Single-family only | 47 | 438 | 17,603 | 68.2 | 10.6 | 8.8 | 4.4 | 7.4 | 0.6 |
| 2-6 unit buildings dominate | 34 | 70 | 2,837 | 45.8 | 28.9 | 12.2 | 5.9 | 6.4 | 0.8 |
| 7+ unit buildings dominate | 45 | 202 | 20,315 | 51.6 | 27.9 | 9.1 | 6.5 | 4.3 | 0.6 |
| Mixed (houses + apartments) | 41 | 220 | 11,857 | 66 | 12.8 | 9.7 | 4.9 | 6.1 | 0.6 |
| all blocks | 51 | 930 | 52,612 | 60.1 | 18.8 | 9.3 | 5.4 | 5.9 | 0.6 |

Paired difference in percentage points versus the single-family blocks of the same block
group (weighted by the smaller population of each pair; positive = higher share on this block type):

| category | Pairs | White | Black | Hispanic or Latino | Asian | Two or more races | Other |
|---|---|---|---|---|---|---|---|
| 2-6 unit buildings dominate | 31 | -22.8 | +20.2 | +1.7 | +2.3 | -1.6 | +0.1 |
| 7+ unit buildings dominate | 41 | -18.8 | +23.0 | -1.4 | +0.7 | -3.4 | -0.1 |
| Mixed (houses + apartments) | 39 | -3.8 | +4.9 | +0.1 | +0.7 | -1.8 | -0.1 |

## A2. Excluding group-quarters blocks

Blocks where more than 25% of residents live in group quarters (nursing homes,
dormitories) removed.

| category | Blocks | Population | White | Black | Hispanic or Latino | Asian | Two or more races | Other |
|---|---|---|---|---|---|---|---|---|
| Single-family only | 462 | 18,464 | 68.7 | 10.4 | 8.6 | 4.4 | 7.3 | 0.6 |
| 2-6 unit buildings dominate | 69 | 2,781 | 46.5 | 27.9 | 12.3 | 6 | 6.5 | 0.8 |
| 7+ unit buildings dominate | 206 | 21,147 | 51.5 | 27.8 | 9.2 | 6.5 | 4.4 | 0.6 |
| Mixed (houses + apartments) | 220 | 11,857 | 66 | 12.8 | 9.7 | 4.9 | 6.1 | 0.6 |
| No housing | 97 | 86 | 25.6 | 26.7 | 30.2 | 5.8 | 7 | 4.7 |
| all blocks | 1,054 | 54,335 | 60.2 | 18.6 | 9.3 | 5.4 | 5.9 | 0.6 |

## Notes on the 2020 Census numbers

The 2020 Census applied differential privacy (the TopDown Algorithm) to every count below
the state level. Block-level race counts are noisy and biased toward looking more diverse
than they are; total housing units per block are exact. Sums over hundreds of blocks, as
reported here, cancel most of that noise, and cancel it entirely where a block type covers
whole block groups. Section D uses block-group counts, which are much less noisy, as a check.
