---
name: _test_fixture
description: Fixture skill for unit tests.
arguments:
  - task_path
allowed-tools:
  - read_file
  - bash
approval-policy: permissive-dev
---
Run task at $task_path.
Check output.
