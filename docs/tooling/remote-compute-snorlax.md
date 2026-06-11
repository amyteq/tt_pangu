# Remote compute: snorlax (RTX 4090 / 24-core CPU box)

Shared local compute node for Kaggle competition work (arena runs, parameter
sweeps, GPU training/inference). Verified live 2026-06-12 from issue
[#87](https://github.com/amyteq/tt_pangu/issues/87#issuecomment-4682633197);
also relevant to issue [#83](https://github.com/amyteq/tt_pangu/issues/83)
(free/cheaper compute beyond Kaggle quotas).

## Hardware / OS (verified 2026-06-12)

| Item | Value |
|---|---|
| Hostname / IP | `snorlax` / `192.168.18.66` (WiFi `wlp13s0`, LAN 192.168.18.0/24) |
| CPU | 24 hardware threads (`nproc` = 24) |
| RAM | 123 GiB |
| GPU | NVIDIA GeForce RTX 4090, 24 GB VRAM, driver 595.71.05 |
| Disk | 1.8 TB NVMe root, ~879 GB free |
| OS | Void Linux (runit, no systemd), kernel 6.18.32 |
| Motherboard | MSI B450 GAMING PRO CARBON MAX WIFI (BIOS 7B85v2.G1) |

## Access

- SSH: `ssh snorlax` as user `harry` (key already authorized from HARRY-ARCH;
  host alias resolves via local `~/.ssh/config` / LAN DNS).
- No password prompts expected; `ssh -o BatchMode=yes snorlax` works.
- Claude Code sandbox note: both `rc.py` (cloud API) and `ssh` need
  `dangerouslyDisableSandbox` (LAN hosts and `~/.ssh` are outside the
  sandbox allow-list).

## Power control (`rc.py`)

snorlax is powered on/off remotely through a 松果电子 (Songguo) power-control
card cloud API — **not** wake-on-LAN. The CLI lives at
`/home/harry/tools/rc.py` on HARRY-ARCH (requires the `requests` package, e.g.
`micromamba activate v3.12.12`):

```bash
rc.py -l            # list devices + power state (snorlax / HARRY-ARCH / HARRY-WIN11)
rc.py -s snorlax    # power on
rc.py -q snorlax    # query status
rc.py -e snorlax    # shut down (graceful; --force for hard off)
rc.py -r snorlax    # reboot
```

Boot-to-SSH takes roughly 1–2 minutes. Pattern: `rc.py -s snorlax`, then poll
`ssh -o ConnectTimeout=5 -o BatchMode=yes snorlax 'echo ok'` every ~10 s.

## Software environment

| Item | Value |
|---|---|
| System Python | 3.14.5 (`/usr/bin/python3`) |
| micromamba | `~/micromamba` (not on non-interactive PATH); env `v3.12.12` at `/home/harry/micromamba/envs/v3.12.12` |
| Docker | installed (`docker0` up) |
| vLLM service | runit service `vllm-coder` (`/var/service/vllm-coder`), log at `/var/log/vllm-coder` |

### vLLM endpoint (auto-starts on boot)

`Qwen/Qwen2.5-Coder-14B-Instruct-AWQ` served OpenAI-compatible on
`http://192.168.18.66:8000/v1`, model name `rtx4090`, api-key `sk-local`,
32k context, prefix caching + hermes tool parsing enabled.

**The vLLM service pins ~92% of GPU VRAM.** For GPU jobs, stop it first
(`sudo sv down vllm-coder`, restore with `sudo sv up vllm-coder`); for
CPU-only jobs (e.g. Orbit Wars arena sweeps) just use the 24 cores —
vLLM idles on the GPU and leaves the CPU essentially free.

## Usage patterns for Kaggle work

- **CPU-bound arena/sweep jobs** (pure-Python engines, parameter searches):
  rsync the project subtree over, run with `--procs 24` (or equivalent),
  write results to a file, fetch back. Roughly ~3× the throughput of an
  8-core local run.
- **GPU jobs** (training, local model inference): stop `vllm-coder` first,
  24 GB VRAM available. Driver 595 supports current CUDA wheels; install
  per-project envs under micromamba.
- **LLM calls**: use the standing endpoint instead of taking the GPU — see
  `rtx4090` above. Sibling box "may" (RTX 3090, 192.168.18.77) exists but is
  usually off; same `rc.py`/ssh pattern applies if needed.
- Leave the box on for long sweeps; shut down with `rc.py -e snorlax` when a
  multi-day idle period is expected (it draws desktop-class power).
