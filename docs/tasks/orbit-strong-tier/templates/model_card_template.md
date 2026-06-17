# Orbit model card: <run_id>

## Purpose

- candidate scorer | value model | posture classifier | other

## Training data

- replay corpus:
- date range:
- number of episodes:
- 2p/4p split:
- top-player filter:
- train/valid/test split:
- leakage prevention:

## Features

- planet-pair features:
- ledger features:
- global/player features:
- short history features:
- 4p features:

## Labels

- imitation:
- value:
- safety:
- outcome:

## Model

- architecture:
- framework:
- parameters:
- export format:
- online runtime:

## Metrics

- validation ranking metric:
- recall@k:
- value RMSE/AUC:
- safety false-negative rate:
- local arena result:

## Integration

- agent version:
- fallback behavior:
- rule-engine guardrails:
- FlightOracle gate:

## Risks

- distribution shift:
- 2p/4p mismatch:
- runtime:
- overfitting to top-player episodes:

## Decision

- use | reject | retrain | needs more data
