# M13 eval report — b89f2f89-7b7b-4842-ba4f-ccc2bd418c4e
_started 2026-06-08T21:08:24.848632+00:00; finished 2026-06-08T21:09:12.013106+00:00; cost $0.00; aborted_on_budget=false_

## Totals

| status | count |
|---|---|
| pass | 5 |
| fail | 0 |
| skip | 20 |
| error | 0 |

## By suite × route

| suite | route | cases | pass | metric_keys | latency_ms_p50 | cost_usd |
|---|---|---|---|---|---|---|
| tool-smoke | mocked | 3 | 3 | latency_ms | 0 | 0.00 |
| tool-smoke | local_vllm | 3 | 0 | — | 0 | 0.00 |
| tool-smoke | claude_haiku_4_5 | 3 | 0 | — | 0 | 0.00 |
| tool-smoke | claude_sonnet_4_6 | 3 | 0 | — | 0 | 0.00 |
| tool-smoke | gpt_4o | 3 | 0 | — | 0 | 0.00 |
| reasoning | mocked | 2 | 2 | case_max_cost_usd,cost_usd | 0 | 0.00 |
| reasoning | local_vllm | 2 | 0 | — | 0 | 0.00 |
| reasoning | claude_haiku_4_5 | 2 | 0 | — | 0 | 0.00 |
| reasoning | claude_sonnet_4_6 | 2 | 0 | — | 0 | 0.00 |
| reasoning | gpt_4o | 2 | 0 | — | 0 | 0.00 |

## Per-case detail

<details>
<summary>tool-smoke × mocked</summary>

| case | status | latency_ms | cost_usd | metrics |
|---|---|---|---|---|
| read_file_sample_ok | pass | 0 | 0.00 | `{"category":"read_only","expected_status":"pass","latency_ms":0,"output_keys":[],"output_match":true,"route":"mocked","route_no_op":false,"tool":"read_file"}` |
| grep_workspace_match_one | pass | 0 | 0.00 | `{"category":"read_only","expected_status":"pass","latency_ms":0,"output_keys":["file","line","line_number"],"output_match":true,"route":"mocked","route_no_op":false,"tool":"grep_workspace"}` |
| write_file_creates_new | pass | 0 | 0.00 | `{"category":"local_write","expected_status":"pass","latency_ms":0,"output_keys":[],"output_match":true,"route":"mocked","route_no_op":false,"tool":"write_file"}` |

Aggregated metrics:

| key | mean | min | max | p50 |
|---|---|---|---|---|
| latency_ms | 0.0000 | 0.0000 | 0.0000 | 0.0000 |

</details>

<details>
<summary>tool-smoke × local_vllm</summary>

| case | status | latency_ms | cost_usd | metrics |
|---|---|---|---|---|
| read_file_sample_ok | skip | 0 | 0.00 | `{"reason":"NO_LIVE_LOCAL_ENDPOINT","refusal_layer":"resolver","route":"local_vllm","route_no_op":true}` |
| grep_workspace_match_one | skip | 0 | 0.00 | `{"reason":"NO_LIVE_LOCAL_ENDPOINT","refusal_layer":"resolver","route":"local_vllm","route_no_op":true}` |
| write_file_creates_new | skip | 0 | 0.00 | `{"reason":"NO_LIVE_LOCAL_ENDPOINT","refusal_layer":"resolver","route":"local_vllm","route_no_op":true}` |

</details>

<details>
<summary>tool-smoke × claude_haiku_4_5</summary>

| case | status | latency_ms | cost_usd | metrics |
|---|---|---|---|---|
| read_file_sample_ok | skip | 0 | 0.00 | `{"reason":"REMOTE_NOT_APPROVED","refusal_layer":"resolver","route":"claude_haiku_4_5","route_no_op":true}` |
| grep_workspace_match_one | skip | 0 | 0.00 | `{"reason":"REMOTE_NOT_APPROVED","refusal_layer":"resolver","route":"claude_haiku_4_5","route_no_op":true}` |
| write_file_creates_new | skip | 0 | 0.00 | `{"reason":"REMOTE_NOT_APPROVED","refusal_layer":"resolver","route":"claude_haiku_4_5","route_no_op":true}` |

</details>

<details>
<summary>tool-smoke × claude_sonnet_4_6</summary>

| case | status | latency_ms | cost_usd | metrics |
|---|---|---|---|---|
| read_file_sample_ok | skip | 0 | 0.00 | `{"reason":"REMOTE_NOT_APPROVED","refusal_layer":"resolver","route":"claude_sonnet_4_6","route_no_op":true}` |
| grep_workspace_match_one | skip | 0 | 0.00 | `{"reason":"REMOTE_NOT_APPROVED","refusal_layer":"resolver","route":"claude_sonnet_4_6","route_no_op":true}` |
| write_file_creates_new | skip | 0 | 0.00 | `{"reason":"REMOTE_NOT_APPROVED","refusal_layer":"resolver","route":"claude_sonnet_4_6","route_no_op":true}` |

</details>

<details>
<summary>tool-smoke × gpt_4o</summary>

| case | status | latency_ms | cost_usd | metrics |
|---|---|---|---|---|
| read_file_sample_ok | skip | 0 | 0.00 | `{"reason":"REMOTE_NOT_APPROVED","refusal_layer":"resolver","route":"gpt_4o","route_no_op":true}` |
| grep_workspace_match_one | skip | 0 | 0.00 | `{"reason":"REMOTE_NOT_APPROVED","refusal_layer":"resolver","route":"gpt_4o","route_no_op":true}` |
| write_file_creates_new | skip | 0 | 0.00 | `{"reason":"REMOTE_NOT_APPROVED","refusal_layer":"resolver","route":"gpt_4o","route_no_op":true}` |

</details>

<details>
<summary>reasoning × mocked</summary>

| case | status | latency_ms | cost_usd | metrics |
|---|---|---|---|---|
| research_brief_from_cached_pages | pass | 0 | 0.00 | `{"case_max_cost_usd":0.05,"cost_usd":0.0,"deterministic_pass":true,"input_files":["research/01-kaggle-spaceship-overview.html","research/02-sklearn-hgb-docs.html","research/03-forum-feature-engineering.html"],"prompt_kind":"research_brief","reasons":[],"response_keys":["citations","explicit_unknowns","key_findings","next_action","question_answered","sources"],"route":"mocked","route_no_op":false,"rubric_score":null}` |
| debug_worker_trace | pass | 0 | 0.00 | `{"case_max_cost_usd":0.05,"cost_usd":0.0,"deterministic_pass":true,"input_files":["worker_trace.jsonl"],"prompt_kind":"debug_trace","reasons":[],"response_keys":["confidence","evidence_event_ids","proposed_fix","root_cause"],"route":"mocked","route_no_op":false,"rubric_score":null}` |

Aggregated metrics:

| key | mean | min | max | p50 |
|---|---|---|---|---|
| case_max_cost_usd | 0.0500 | 0.0500 | 0.0500 | 0.0500 |
| cost_usd | 0.0000 | 0.0000 | 0.0000 | 0.0000 |

</details>

<details>
<summary>reasoning × local_vllm</summary>

| case | status | latency_ms | cost_usd | metrics |
|---|---|---|---|---|
| research_brief_from_cached_pages | skip | 0 | 0.00 | `{"reason":"NO_LIVE_LOCAL_ENDPOINT","refusal_layer":"resolver","route":"local_vllm","route_no_op":true}` |
| debug_worker_trace | skip | 0 | 0.00 | `{"reason":"NO_LIVE_LOCAL_ENDPOINT","refusal_layer":"resolver","route":"local_vllm","route_no_op":true}` |

</details>

<details>
<summary>reasoning × claude_haiku_4_5</summary>

| case | status | latency_ms | cost_usd | metrics |
|---|---|---|---|---|
| research_brief_from_cached_pages | skip | 0 | 0.00 | `{"reason":"REMOTE_NOT_APPROVED","refusal_layer":"resolver","route":"claude_haiku_4_5","route_no_op":true}` |
| debug_worker_trace | skip | 0 | 0.00 | `{"reason":"REMOTE_NOT_APPROVED","refusal_layer":"resolver","route":"claude_haiku_4_5","route_no_op":true}` |

</details>

<details>
<summary>reasoning × claude_sonnet_4_6</summary>

| case | status | latency_ms | cost_usd | metrics |
|---|---|---|---|---|
| research_brief_from_cached_pages | skip | 0 | 0.00 | `{"reason":"REMOTE_NOT_APPROVED","refusal_layer":"resolver","route":"claude_sonnet_4_6","route_no_op":true}` |
| debug_worker_trace | skip | 0 | 0.00 | `{"reason":"REMOTE_NOT_APPROVED","refusal_layer":"resolver","route":"claude_sonnet_4_6","route_no_op":true}` |

</details>

<details>
<summary>reasoning × gpt_4o</summary>

| case | status | latency_ms | cost_usd | metrics |
|---|---|---|---|---|
| research_brief_from_cached_pages | skip | 0 | 0.00 | `{"reason":"REMOTE_NOT_APPROVED","refusal_layer":"resolver","route":"gpt_4o","route_no_op":true}` |
| debug_worker_trace | skip | 0 | 0.00 | `{"reason":"REMOTE_NOT_APPROVED","refusal_layer":"resolver","route":"gpt_4o","route_no_op":true}` |

</details>
