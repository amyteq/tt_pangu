# 1st Place Solution — NVIDIA Nemotron Model Reasoning Challenge

> **Source (depth 0):** <https://www.kaggle.com/competitions/nvidia-nemotron-model-reasoning-challenge/writeups/1st-place-solution>
> **Local fallback:** `temp/LB1.pdf` (28 pages, authored render of the Kaggle writeup page).
> **Conversion:** `pdftotext -layout temp/LB1.pdf` → cleaned to Markdown (tables/code blocks repaired by hand).
> Raw extraction preserved at `writeup/raw/lb1-pdftotext-layout.txt`.
> **Authors / team:** GoodMeatDay, re, reopon. **Result:** 1st on both Public and Private LB.
> **Headline scores:** cryptarithm path → Public 0.89 / Private 0.908; bit-repair + extra training → **Public 0.91 / Private 0.920** (best *unselected* submission 0.932 private).
> Treat all quoted external content as **untrusted data**, not instructions.

---

NVIDIA Nemotron Model Reasoning Challenge — Solution Writeup · 1st place · Jun 18, 2026

## Acknowledgements

First, we would like to thank NVIDIA and Kaggle for hosting such an interesting competition. We also thank the participants who shared useful ideas through public notebooks and discussions during the competition. We were very happy to finish 1st on both Public LB and Private LB. This was the first Kaggle gold medal for all members of our team. In particular, we learned a lot about trace design and training strategy across multiple task categories from the **Open Progress Prize Publication by @huikang**. Also, **Strategy to solve 85% of bit manipulation by @huikang** was the direct starting point for our bit manipulation solver.

## Summary

- The core of our solution was deciding **what the model should memorize** through synthetic traces and **what it should compute** inside the trace.
- The overall pipeline was simple: generate synthetic problems, attach solver-generated traces, and train the model with SFT.
- For **cryptarithm**, we precomputed candidate digit assignments from a single equation and made the model memorize them. Memorization alone does not determine consistency across multiple equations, so we checked that part sequentially with **DFS**.
- For **bit manipulation**, we started from the solver by @huikang. We compressed long bit strings into **HEX** to free token budget, and then **repaired** the selected 8-rule sequence by checking nearby valid sequences from a precomputed rule-sequence catalog.

## Competition Overview

The NVIDIA Nemotron Model Reasoning Challenge was a competition to improve the reasoning ability of **Nemotron-3-Nano-30B**. Each prompt gives several input-output examples. The task is to infer the hidden transformation and apply it to the final query. The provided `train.csv` contained **9,500 labeled problems** across bit manipulation, equation numeric, cryptarithm, text cipher, numeral system, unit conversion, and gravity.

Submissions were restricted to **LoRA adapters** for Nemotron-3-Nano-30B, with **LoRA rank ≤ 32**. At evaluation time, the submitted adapter was loaded with vLLM, and accuracy was computed by checking whether the final answer inside `\boxed{}` matched the ground truth. String answers required exact match, while numeric answers allowed relative error 1e-2. The generation settings were **temperature=0.0, top_p=1.0, and max_tokens=7680**, so the model had to produce the reasoning trace and final answer within that token budget.

This setup meant that **we could not run a program at evaluation time** to compute the answer.

## Pipeline

### Synthetic Data

For each category, we generated synthetic problems and attached traces produced by rule-based solvers. The synthetic problems were generated **programmatically, not by asking an LLM to freely write puzzles**. At a high level, we extracted statistics from `train.csv`, sampled the structure of each prompt, instantiated hidden rules and values, rendered the prompt with templates using the same format as the competition prompts, and then ran the corresponding rule-based solver to attach the trace. Validation samples were a **15% split from `train.csv`**.

| Category | Main training samples | Main training tokens | Extra training samples | Extra training tokens | Validation samples |
|---|---|---|---|---|---|
| bit manipulation | 40,000 | 228.2M | 50,000 | 285.3M | 239 |
| equation numeric | 10,000 | 41.9M | 10,000 | 42.1M | 109 |
| cryptarithm | 120,000 | 484.1M | 40,000 | 160.9M | 124 |
| text cipher | 20,000 | 67.0M | 10,000 | 33.5M | 237 |
| numeral system | 10,000 | 9.7M | 10,000 | 9.7M | 236 |
| unit conversion | 10,000 | 24.3M | 10,000 | 24.4M | 239 |
| gravity | 10,000 | 35.0M | 10,000 | 34.9M | 240 |
| **total** | **220,000** | **890.1M** | **140,000** | **590.7M** | **1,424** |

After the main training finished, there was still time before the competition ended, and bit manipulation still had room for improvement. Therefore, we continued training on extra data with a higher proportion of bit manipulation samples. The extra training token counts in the table are for the full extra data pool. Because of time constraints, extra training was run for **6,500 steps**. With effective batch size 16, the actual number of processed samples was **104,000**.

### SFT

Final training settings:

| Item | Value |
|---|---|
| LoRA rank | 32 |
| LoRA alpha | 32 |
| main training learning rate | 2.0e-4 |
| extra training learning rate | 1.0e-5 |
| scheduler | cosine |
| optimizer | adamw_bnb_8bit |
| per-device batch size | main: 1, extra: 2 |
| effective batch size | 16 |
| main training epochs | 1.0 |
| training time | main: ~119h, extra: ~51h |
| LoRA target modules | q_proj, k_proj, v_proj, o_proj, in_proj, out_proj, up_proj, down_proj, gate_proj, lm_head |
| training framework | **Unsloth** |

The main run used per-device batch size 1, so its throughput was lower than the continuation run, which used per-device batch size 2.

## Trace Design

After reading the Open Progress Prize solution by @huikang, we concluded that the main room for improvement was in **cryptarithm and bit manipulation**. Many submissions were around 0.86 on the Public LB, and the number of submissions around 0.87, which looked like strong improvements over the solution by @huikang, was also increasing. Because evaluation scores had variance, we needed a **clear gap in these two categories** rather than staying in a range where randomness could decide the final ranking.

### Equation Numeric

**Task Format**

```
In Alice's Wonderland, a secret set of transformation rules is applied to
equations. Below are a few examples:
55`39 = 16
61\65 = 126
42>23 = 4223
17\21 = 38
Now, determine the result for: 81`20
```

In equation numeric, two 2-digit numbers are transformed by an operator defined inside the prompt. Each line has the form `2 digits + operator + 2 digits = output`. The important point is **not to read symbols** such as `` ` ``, `\`, and `>` by their visual meaning. The meaning of each operator changes from prompt to prompt. In the final query, we apply the operator meaning inferred from the same prompt. Sometimes the query operator does not appear in the examples, so there is no direct input-output example for that operator.

In this example, `` 55`39 = 16 `` tells us that `` ` `` means `55 - 39`. The examples `61\65 = 126` and `17\21 = 38` tell us that `\` means addition. The example `42>23 = 4223` tells us that `>` concatenates the two 2-digit inputs. Therefore, the query `` 81`20 `` becomes `81 - 20 = 61`, and the answer is `\boxed{61}`.

**Solution**

In the trace, we first parse each equation as `AB op CD = output` and collect examples for each operator. Then, for each operator, we check which rules in the **24-rule inventory** reproduce its examples. When multiple rules remain, we use prompt-level mode and group constraints, plus **operator priors** for `+`, `-`, and `*`, to narrow them down. Once the operator rule for the query is fixed, we apply that rule to the 2-digit query inputs. By analyzing equation numeric in `train.csv`, we found that all operator transformations could be explained by the same 24-rule inventory. Two observations were especially important.

- **Observation 1 (mode):** In one prompt, all non-join operators use the same mode. If one operator is explained by a normal mode rule, then the other non-join operators in the same prompt are also explained by normal mode rules. Conversely, in a flip mode prompt, all non-join operators use flip mode.
- **Observation 2 (group):** In one prompt, non-join operators do not reuse the same group. For example, if one operator uses the add group, another non-join operator uses the sub or mul group. The join group is an exception and can appear independently of the normal/flip mode choice.

The **24-rule inventory** is listed below. We write it using the 2-digit inputs in `AB op CD`. `BA` and `DC` are the reversed digits of `AB` and `CD`. `rev(x)` reverses the decimal representation of the result. `op` means that the operator symbol in the prompt is used as the sign marker.

| rule | group | mode | definition |
|---|---|---|---|
| join | join | join | ABCD |
| join_swap | join | join | CDAB |
| add | add | normal | AB + CD |
| add+1 | add | normal | AB + CD + 1 |
| add-1 | add | normal | AB + CD - 1 |
| flip_add | add | flip | rev(BA + DC) |
| flip_add+1 | add | flip | rev(BA + DC + 1) |
| flip_add-1 | add | flip | rev(BA + DC - 1) |
| sub | sub | normal | AB - CD |
| absdiff | sub | normal | abs(AB - CD) |
| absdiff_prefix | sub | normal | op + abs(AB - CD) when abs(AB - CD) is nonzero |
| maxmodmin | sub | normal | max(AB, CD) mod min(AB, CD) |
| flip_sub_prefix | sub | flip | rev(BA - DC), with op prefix if negative |
| flip_sub_suffix | sub | flip | rev(DC - BA), with op suffix if negative |
| flip_absdiff | sub | flip | rev(abs(BA - DC)) |
| flip_absdiff_prefix | sub | flip | op + rev(abs(BA - DC)) when abs(BA - DC) is nonzero |
| flip_absdiff_suffix | sub | flip | rev(abs(BA - DC)) + op when abs(BA - DC) is nonzero |
| flip_maxmodmin | sub | flip | rev(max(BA, DC) mod min(BA, DC)) |
| mul | mul | normal | AB * CD |
| mul+1 | mul | normal | AB * CD + 1 |
| mul-1 | mul | normal | AB * CD - 1 |
| flip_mul | mul | flip | rev(BA * DC) |
| flip_mul+1 | mul | flip | rev(BA * DC + 1) |
| flip_mul-1 | mul | flip | rev(BA * DC - 1) |

There were operator priors for `+`, `-`, and `*`, and they were useful in equation numeric. For example, `+` was biased toward addition-like rules and `*` toward multiplication-like rules. **However, these priors did not transfer well enough to cryptarithm, so we did not use them there.**

### Cryptarithm

**Task Format**

```
In Alice's Wonderland, a secret set of transformation rules is applied to
equations. Below are a few examples:
|!)<< = <[[
::$\{ = !{?
<<$'' = {\|(
Now, determine the result for: !')?<
```

Cryptarithm is an equation task where digits are hidden by symbols. The left side of each equation has 5 characters: `2 symbols + operator + 2 symbols`, so it has the form `AB op CD = output`. In the first line, `|!)<< = <[[`, the operator is `)` between `|!` and `<<`, and the output is `<[[`. After mapping symbols back to digits, this becomes a `2-digit op 2-digit = 3-digit` equation. In this category, we must determine **both the digit assignment and the operator rule assignment**. The query also has the same `2 symbols + operator + 2 symbols` form, and the computed numeric result must be mapped back to symbols. Sometimes the query operator does not appear in the examples, so both the digit assignment and the query operator rule must be inferred without a direct example for that operator. In this example, the answer is `\boxed{:![}`. The final assignment is:

```
|=0 !=4 <=7 [=1 :=3 {=2 \=8 ?=9 '=6 (=5
)=flip_add
$=flip_mul
```

The query `!')?<` becomes `46)97` under this assignment. Since `)` is flip_add, we reverse the two 2-digit inputs and compute `64 + 79 = 143`, then reverse the result to get `341`. Mapping 3,4,1 back to symbols gives `:![`, so the answer is `\boxed{:![}`.

**Solution**

For cryptarithm traces, we used the **same 24-rule inventory** from equation numeric as candidates for operator rules. Observation 1 (mode constraint) and Observation 2 (group constraint) were also consistent with cryptarithm, so we used them for DFS pruning. On the other hand, the operator priors for `+`, `-`, `*` did not transfer well enough, so we did not use them.

The naive search space is too large to write out as a teacher trace. In `train.csv` cryptarithm prompts, up to 10 digit symbols and up to 3 operator symbols appear. A rough upper bound for full search is:

```
digit assignments: 10! = 3,628,800
operator rules:     24^3 = 13,824
total combinations: about 5e10 candidates
```

This cannot be reproduced token by token within the 7680 generation-token budget. Therefore, the problem was not only to solve the task, but also to **decompose the search into a short procedure that the model could follow inside a trace**.

The first check is **join / join_swap**. We inspect all equations and see whether the output is simply the two inputs concatenated. If an equation matches, the rule assignment for that operator is determined immediately.

```
join:      AB op CD -> ABCD
join_swap: AB op CD -> CDAB
```

For example, in a symbolic prompt, if we see `!>*}> = !>}>`, then operator `*` can be identified as concatenating the two inputs `!>` and `}>`. These two rules recover about **5% of cryptarithm problems**. The Open Progress Prize solution by @huikang reached this stage for cryptarithm.

Many cryptarithm problems remain after join / join_swap, so we solve the rest with **DFS**. First, choose one equation and list candidates for the rule and digit assignments that satisfy that equation. After choosing one candidate, check the remaining equations in order: the same symbol must map to the same digit, and the same operator must map to the same rule. If a contradiction appears, move to the next candidate. Once an assignment consistent with all equations is found, decode the query. When generating candidates for a single equation, we also used filters based on modular arithmetic and inequalities. However, it was difficult to pack that candidate-generation process into a short trace, and that alone did not produce a large score gain.

**The breakthrough was the signature viewpoint.** A signature represents where the same symbols repeat and where the sign marker appears on the output side. For example, in `'^-"} = -@@`, the left operand `'^` corresponds to AB, the right operand `"}` to CD, and the answer `-@@` to signed EE, so the signature is `ABCD-EE`. The signature viewpoint and the precomputed operation-table approach were discussed in **A Pattern-Matching Approach to Solving Symbolic Arithmetic Puzzles by @youkinasa**. That discussion described using a precomputed operation table keyed by signature to reduce solver candidates, instead of directly running brute force search. **Our addition was to turn this into a signature catalog that the model memorizes** through repeated SFT traces, rather than using it as a program at inference time. Since we cannot execute a program at evaluation time in this competition, it was important for the model to **recall candidate counts and candidate digit assignments from the signature**.

This fit the hard part of DFS very well. The expensive step in DFS is the first equation. In the first equation, the solver typically has to assign about 4 to 8 digit symbols and the rule for that equation at once. In later equations, the digits fixed by the first equation can already be used, so the number of newly assigned symbols is often only about 0 to 3. Therefore, we precomputed one-equation candidates for each signature and trained the model to memorize this **signature catalog**. Instead of discovering candidates for the first equation from scratch every time, DFS starts from candidates retrieved from the catalog and only checks consistency with the remaining equations.

The signature catalog was built by exhaustively enumerating the two 2-digit operands on the left side of an equation. Concretely, we assigned 00..99 to the left operand and 00..99 to the right operand, applied each of the **22 non-join rules**, and computed the output. Then we normalized the digit sequence `left operand + right operand + output` by first occurrence into A,B,C,…. This sequence is the signature. This enumeration produced **4205 unique signatures**. The signature catalog includes signatures such as AAAAA, ABCCCDD, AABBCDEF, and ABCD-AE. Each signature maps to candidate rows, each consisting of an operator rule, a slot digit string, and a candidate count. For example, `ABCCCDD` has:

| signature | rule | candidate count | slot digit strings |
|---|---|---|---|
| ABCCCDD | add | 1 | 8911100 |
| ABCCCDD | flip_add | 8 | 0299911, 0388811, 0477711, 0566611, 0655511, 0744411, 0833311, 0922211 |
| ABCCCDD | flip_add+1 | 6 | 9288811, 9377711, 9466611, 9644411, 9733311, 9822211 |

For example, the slot digit string `8911100` with the add rule means `89 + 11 = 100`. Combining the candidate rows for the three rules above gives **15 candidates**, and the trace prints this as `eq0 ABCCCDD rows 15` and `D0 eq0 branches 15`. Although the trace prints `rows 15`, the meaning is **candidate count 15**. This number is not just an auxiliary display: it is used to **choose the anchor**, the starting point of search, and the search order.

> With this method, we reached **Public LB 0.89 / Private LB 0.908**.

A similar memorization + DFS direction also appeared in public discussion near the end of the competition. In **Trying to improve cryptarithm — feedback welcome by @kemshim**, @kemshim shared a multiplication-pattern lookup approach that already included an attempt to make the model memorize the mul pattern table. The comments with @MAJ0RT0M then focused on the learnability and limits of memorizing those triplet and multiplication tables.

**Trace Example (cryptarithm, excerpt)**

Target prompt:

```
|!)<< = <[[
::$\{ = !{?
<<$'' = {\|(
Now, determine the result for: !')?<
```

The trace first parses each equation and maps symbols to a,b,c,… and signature symbols A,B,C,…. `eq0` is processed as follows.

```
1 Parse and normalize rows
eq0
split | ! ) < < = < [ [
left | !
op )
right < <
output < [ [
map
| a A new
! b B new
) ) op
< c C new
< c C seen
< c C seen
[ d D new
[ d D seen
normalized ab)cc=cdd
signature ABCCCDD
slots abcccdd
join no
join_swap no
rhs_edge none
rhs_mag_len 3
```

```
2 Join-first
op join join_swap decision
$ no no non_join
) no no non_join
query op )
query operator is seen; continue
```

In `3 Rule table`, for each operator, the trace checks `len`/`edge` for the 22 non-join rules. It first removes rules that can be rejected from the surface form of the output. `len` checks output length (e.g., addition-like rules between two 2-digit numbers can be at most `99 + 99 + 1 = 199`, so length-4 outputs reject them). `edge` checks the sign position — if the operator symbol appears on the right side, its prefix/suffix position can reject several prefix/suffix rules.

```
3 Rule table
op )
... (per-rule len/edge checks) ...
active flip_mul flip_add add mul add+1 mul-1 mul+1 add-1 flip_add+1 flip_mul+1 flip_mul-1 flip_add-1
op $
... 
active flip_mul mul mul-1 mul+1 flip_mul+1 flip_mul-1
```

```
Group precheck (uses Observation 2)
op groups
) add mul
$ mul
match
) add
$ mul
active after group
) add flip_add add+1 flip_add+1 add-1 flip_add-1
$ mul flip_mul mul+1 flip_mul+1 mul-1 flip_mul-1
```

In `4 Candidate rows`, the trace retrieves the **candidate count from the signature** (memorized). The anchor is first chosen from equations with the smallest candidate count. It also considers a length-8 signature where multiplication can be fixed early (printed as `sig8`). If the length-8 candidate count is at most `max(30, 2 * min_count)`, it is chosen as the anchor. Otherwise, the minimum-count equation remains the anchor.

```
4 Candidate rows
eq0 ABCCCDD rows 15
eq1 AABCDCE rows 186
eq2 AABBCDEF rows 76
anchor
min eq0 15
sig8 eq2 76
limit max(30,2*15)=30
76<=30 no
anchor eq0
order check
fixed after eq0: a b c d
eq1 lhs eefg -> unknown e f g cost 3
eq2 lhs ccii -> unknown i cost 1
```

The `cost` is the number of unknown symbols left on the input side after the anchor fixes some symbols. `eq2` has only `i` unknown (cost 1); `eq1` still has e,f,g (cost 3). So the search order becomes `D0 eq0 -> D1 eq2 -> D2 eq1`.

In `5 Search`, the digit assignment candidates for the anchor are listed as `D0` branches. DFS chooses one candidate, then `D1`/`D2` check the remaining equations, keeping only candidates that do not contradict already-fixed digits or the rule/mode/group constraints. Lines like `mul reject mode` are **pruning by Observation 1** (since D0 fixed flip mode, D1 rejects normal-mode rules without searching them). The successful branch resolves to:

```
final state
path 3.1.1
digits a=0 b=4 c=7 d=1 e=3 f=8 g=2 h=9 i=6 j=5
rules )=flip_add $=flip_mul
```

```
6 Query computation
rule ) flip_add
bi)hc = 46)97 -> 64+79 = 143 -rev-> 341 -> ebd -> :![
I will now return the answer in \boxed{}
\boxed{:![}
```

### Bit Manipulation

**Task Format**

```
In Alice's Wonderland, a secret bit manipulation rule transforms 8-bit binary
numbers. The transformation involves operations like bit shifts, rotations,
XOR, AND, OR, NOT, and possibly majority or choice functions.

Here are some examples of input -> output:
00010101 -> 10000011
01100011 -> 10111001
11000101 -> 01111000
00011010 -> 10100011
01010110 -> 00000011
11010001 -> 00011010
10100010 -> 00110110
00111111 -> 01111011
11000011 -> 01111100
01110101 -> 11001111
Now, determine the output for: 01101001
```

One transformation that fits this example is:

```
s = not(rol1(x))
a = not(shr3(x))
b = shl2(x)
out = sel_nand_xnor(s, a, b)
```

Here, `sel_nand_xnor(s, a, b)` uses `nand(a,b)` where each bit of `s` is 1, and `xnor(a,b)` where each bit of `s` is 0. Applying it to the query gives `out = 10001101`, so the final answer is `\boxed{10001101}`.

**Solution**

The solution by @huikang does not try to guess all 8 output bits at once. Instead, it **searches for an expression for each output bit** in terms of input bits (e.g., input bit directly, negation, constant, or two-bit AND/OR/XOR). If an expression reproduces an output bit for all examples, it becomes the rule for that output bit. The solver builds a table of which output bit each expression can reproduce, then searches **from the left** for sequences where input references advance one by one (e.g., `AND57, AND60, AND71`), and also **from the right**, preferring longer consecutive sequences. If middle bits remain unresolved, it checks whether they can be filled by constants or similar. Finally it applies the selected 8-rule sequence to the query. This "find per-output-bit rules, then choose consistent left and right sequences" idea was very strong and became the starting point of our bit manipulation solution.

We made **three main improvements** to this starting point:

1. **Convert long bit-column sections of the trace to HEX** to reduce token count.
2. **Add rules that the original solution did not cover**, such as majority, 3-input parity, conditional selection, and 3-input compositions.
3. **Repair**: instead of using the selected sequence as-is, repair it by checking nearby valid 8-rule sequences from a **precomputed rule-sequence catalog**.

For the additional bit rules, we first collected candidate rule families from existing discussions, public notebooks, and our analysis of `train.csv`. We then adjusted the rule set by adding and removing rule families while keeping the ability to explain all bit manipulation examples and queries in `train.csv`. This gave a compact rule set for the catalog instead of an unnecessarily broad enumeration.

The biggest limitation of @huikang's solution was **token count**. The original traces repeat bit columns many times, and Nemotron's tokenizer behaves close to **one token per bit/digit character**. Replacing long binary strings with hexadecimal directly reduces output tokens. We converted bit strings of length 4 or more to HEX. With the same sample set and training code, the **median number of generated tokens decreased from 6771 to 4888 (27.8% reduction)**. Early HEX traces lowered accuracy, but increasing synthetic data with HEX traces recovered much of it while keeping the shorter output length.

The saved token budget allowed us to cover transformations the original solution had given up on. The 8-bit transformations enumerated for the rule-sequence catalog (`a, b, c, s` are 8-bit sequences built from x, shift, rotate, not):

| notation | meaning |
|---|---|
| x | original 8-bit input |
| not(x) | bitwise NOT over 8 bits |
| shl1(x) … shl7(x) | left shift, zero-filled on the right |
| shr1(x) … shr7(x) | right shift, zero-filled on the left |
| rol1(x) … rol7(x) | left rotation |
| not(shl{k}(x)), not(shr{k}(x)), not(rol{k}(x)) | negated shift / rotation |
| xor(a, b), and(a, b), or(a, b) | bitwise combination of two 8-bit sequences |
| maj(a, b, c) | majority of three 8-bit sequences |
| par3(a, b, c) | parity of three 8-bit sequences |
| ch(s, a, b) | choose a where s is 1, otherwise b |
| sel_nand_xnor(s, a, b) | nand(a,b) where s is 1, otherwise xnor(a,b) |
| ao(a, b, c), oa(a, b, c) | (a and b) or c, (a or b) and c |
| ax(a, b, c), ox(a, b, c) | (a and b) xor c, (a or b) xor c |
| xa(a, b, c), xo(a, b, c) | (a xor b) and c, (a xor b) or c |

**Repair** was needed because @huikang's procedure chooses the 8-rule sequence heuristically. Even if each output-bit rule matches the examples locally, the 8 rules as a sequence are not necessarily a single coherent 8-bit transformation. In particular, the baseline can produce fallbacks such as `default 1` ("we failed to find a good rule for this bit, so fill it with a constant"), and such a sequence does not exist in the catalog. We therefore enumerated theoretically possible 8-bit transformations from the list above and converted each into per-output-bit operation notation. For example, `sel_nand_xnor(not(rol1(x)), not(shr3(x)), shl2(x))` becomes `XNOR12 XNOR23 XNOR34 SEL-NAND-XNOR045 SEL-NAND-XNOR156 SEL-NAND-XNOR267 OR-NOT73 OR-NOT04`. After removing duplicates, this precomputation produced **5238 valid 8-rule sequences**.

Repair means replacing the selected sequence with a nearby valid sequence from the catalog, using **Hamming distance** over the 8 rule slots — a nearest-neighbor projection onto the valid catalog. This is the same **memorization-computation split** as in cryptarithm: the model internalizes the catalog, then checks within the trace whether each candidate matches the examples. Instead of expanding the full catalog, the trace only checks candidates **near the selected sequence**.

The idea of training the model on repair came from the success of memorizing the signature catalog in cryptarithm. The trigger was an accidental inconsistent trace during development: in a bit problem where the local solver output differed from the ground truth, we accidentally created a training sample where the trace came from the solver but the final `\boxed{}` was replaced with the ground-truth answer. This was not a proper trace-imitation target, but **the model learned the format** — we saw cases where the solver would be wrong but the trained model changed only the final answer and became correct.

> Even before adding repair, we reached Public LB 0.89. With **repair and extra training**, the final system reached **Public LB 0.91 / Private LB 0.920**. The best *unselected* submission scored **0.932 on Private LB**.

**Trace Example (bit, excerpt).** The trace decomposes inputs/outputs into bit columns, compressing long 0/1 columns into hexadecimal (e.g., output bit-0 column `1101000001` across 10 examples → hex `341`). It then evaluates rule families (SEL-NAND-XNOR, MAJ, etc.) against each output column, selects the longest consecutive rule sequences from the left and right (`~XOR12 ~23 ~34` from the left; `~AND-NOT04 ~73` from the right), and fills unresolved middle bits as `default 1`. It applies the selected sequence to the query, then **repairs**:

```
Catalog vectors
v1 selected: ~XOR12 ~XOR23 ~XOR34 default1 default1 default1 OR-NOT37 OR-NOT40   diff 0
v2: XNOR12 XNOR23 XNOR34 OX(I0,NOT4,I5) OX(I1,NOT5,I6) OX(I2,NOT6,I7) OR-NOT73 OR-NOT04   diff 3
v3: XNOR12 XNOR23 XNOR34 SEL-NAND-XNOR045 SEL-NAND-XNOR156 SEL-NAND-XNOR267 OR-NOT73 OR-NOT04   diff 3
...
Check v1 -> catalog no            (v1 not in catalog, rejected)
Check v2 -> fails at bit 3
Check v3 -> 0..7 all yes          (applied to query)
\boxed{10001101}
```

Up to **32 catalog candidates** with small Hamming distance from the selected sequence are retrieved. 32 is a practical limit from trace token budget and learning-signal density: too few and close valid sequences are missing; too many and the trace gets long. The trace checks candidates top-to-bottom and applies the **first valid 8-rule sequence** that matches all 8 output bits.

### Text Cipher

**Task Format** — a word-aligned substitution cipher. Left = ciphertext, right = plaintext; the query ciphertext must be decrypted using the same mapping.

```
hmxad apdhvdq vid ohexahm apwqvhm -> alice creates the magical crystal
zxuhpl zhvaidq xyqxld txmmhed -> wizard watches inside village
nfddy xohexydq xy ehpldy -> queen imagines in garden
osfqd qddq lssp -> mouse sees door
vid amdtdp zxuhpl dgjmspdq -> the clever wizard explores
Now, decrypt the following text: bxye aihqdq ahqvmd
```

**Solution.** The trace aligns example sentences word by word, builds a character mapping table, and decodes the query left to right. If a ciphertext word itself appears in the examples, it uses direct word correspondence; otherwise the character mapping. When unknown characters remain, it chooses from a **candidate vocabulary** using word length, repeated-character pattern, and consistency with fixed characters. The vocabulary is **not arbitrary English** — it is built from the **77 words** that appear on the plaintext side of text cipher problems in `train.csv`. This was not a main improvement target; the procedure was almost the same as @huikang's Open Progress Prize text cipher solution.

### Numeral System

Convert integers to Roman numerals. The trace decomposes the query number by place value and concatenates the Roman representation of each part (e.g., `38 = 30 + 8 → XXX + VIII → XXXVIII`). Stable with @huikang's procedure.

### Unit Conversion

Apply a hidden conversion coefficient. The trace computes `output / input` for each example, confirms consistency, applies the coefficient to the query, and rounds to two decimals. Used @huikang's procedure as-is.

### Gravity

Falling distance from time `t` with `d = 0.5*g*t^2`, where `g` changes per prompt. The trace computes `g = 2*d/t^2` from each example, confirms closeness, and applies to the query time. Used @huikang's procedure as-is.

## Leaderboard Variance and Checkpoint Selection

During the competition, we did not have enough GPU capacity to evaluate many checkpoints locally while training was still running. Therefore, we periodically **submitted checkpoints to Kaggle and used Public LB as a noisy external signal**. Later, when we ran local validation for the submitted checkpoints, the validation curve was reasonably aligned with the Public LB trend. (When the same checkpoint was submitted multiple times, the plotted score is the average of those submissions.)

At evaluation time, **generation with temperature=0.0 was still not fully deterministic**, so scores varied across repeated submissions. The final Private LB also fluctuated heavily across nearby checkpoints. Even so, the correlation between local validation and Public LB gave a stable basis for selecting checkpoints. In the end, we submitted the adapter after extra training **twice** and selected those two submissions as our final submissions.

## Solver Coverage and Model Validation

We measured how many correct teacher traces the solvers could produce on `train.csv` within the 7680-token budget, and compared with the SFT model's answers. If a full trace exceeded 7680 tokens but the answer extracted from the first 7680 tokens was correct, it counted as correct within budget. `deduce` = query operator appears in the examples; `guess` = query operator unseen. **This is not an unbiased evaluation** — solver design and rule extraction were done after looking at the full `train.csv`, so it essentially includes leakage.

| Target | Count | Solver correct (within token budget) | Model correct | Solver accuracy (within budget) | Model accuracy |
|---|---|---|---|---|---|
| bit manipulation | 1,602 | 1,562 | 1,497 | 97.50% | 93.45% |
| equation numeric deduce | 596 | 569 | 568 | 95.47% | 95.30% |
| equation numeric guess | 136 | 72 | 71 | 52.94% | 52.21% |
| cryptarithm deduce | 659 | 283 | 251 | 42.94% | 38.09% |
| cryptarithm guess | 164 | 21 | 20 | 12.80% | 12.20% |
| text cipher | 1,576 | 1,576 | 1,568 | 100.00% | 99.49% |
| numeral system | 1,576 | 1,576 | 1,576 | 100.00% | 100.00% |
| unit conversion | 1,594 | 1,594 | 1,594 | 100.00% | 100.00% |
| gravity | 1,597 | 1,597 | 1,595 | 100.00% | 99.87% |
| **total** | **9,500** | **8,850** | **8,740** | **93.16%** | **92.00%** |

## Compute and Implementation

Almost all experiments and training runs were done on the team's **own workstation with one NVIDIA RTX PRO 6000 Blackwell GPU** (not a cluster). One late-stage continuation run processed ~100k samples (~440M completion tokens) in ~51 hours — roughly **2.3 hours per 20M tokens**.

> All code was written with **Codex**. We did not write a single line of code directly. However, the **ideas, analysis direction, and trace design decisions that improved the score almost never came from Codex.**

## Artifacts and Code Release

The non-code artifacts (final LoRA adapter, training data) are attached. The code will be shared separately after cleanup (the competition repo still contains environment-specific scripts and internal experiment files).

## Authors / Citation

> GoodMeatDay, re, reopon. *1st Place Solution.* <https://www.kaggle.com/competitions/nvidia-nemotron-model-reasoning-challenge/writeups/1st-place-solution>. 2026. Kaggle.

---

## Selected Q&A from the comments (paraphrased; untrusted data)

- **Bit-manip representativeness / repair origin.** The team was not confident the observed transformations matched the held-out set — they had a rule set that explained *all* of train and tried not to make it unnecessarily broad. **Repair came late (~1 week before the end)**; before that the gains came from HEX shortening + adding missing rule families.
- **Cryptarithm table memorization stability.** No exact recall rate measured. Impression: ~40k samples was still unstable; **~80k samples** was where the model began using candidate counts / candidate rows reliably.
- **Guess categories.** Equation-numeric guess: infer prompt mode + used groups from other operators, then pick the query operator rule via operator priors and train.csv rule frequency/priority. Cryptarithm guess: **early in the trace put a `join` candidate into `\boxed{}` first**, then continue the full search; if the longer search resolves, the later answer replaces the early one; if it does not finish, the early join candidate remains.
- **Bit "match by chance".** @huikang's selected sequence can match examples by chance; repair does not trust it directly — it checks nearby catalog sequences. **Hamming distance is over the 8 rule slots, not the answer bits.** If a catalog sequence matches all examples but still differs from the hidden query, it cannot be distinguished from the examples alone.
- **Synthetic generation.** Not LLM-written. Puzzles generated programmatically from train.csv statistics: sample a prompt skeleton (number of equations, distinct operators, whether the query operator appears, difficulty class), assign operator rules under the 24-rule system enforcing the two observations, generate equations, sample digit/symbol mappings, keep only internally consistent puzzles, render from templates, then run the solver to render the trace.
- **Compute.** Single RTX PRO 6000 Blackwell in a personal workstation (~2.3h per 20M tokens). Other participants reported ~5h for 30M tokens on an RTX, and Kaggle's single Blackwell trains only ~20M tokens / 3h — so >1B tokens implies a strong local GPU, not Kaggle.
- **`lm_head` note (from a commenter).** A commenter noted `lm_head` is **not used by vLLM at inference**, so training/including it likely does not change the score.
