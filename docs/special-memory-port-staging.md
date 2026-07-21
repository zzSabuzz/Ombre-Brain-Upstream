# Plan / Letter / I staging migration

Date: 2026-07-22

## Decision and compatibility audit

This is a selective port from `P0luz/Ombre-Brain`; it is not a repository replacement.
The fork's existing MCP tools and operational features remain in place, including
`read_bucket`, `comment_bucket`, reminders, darkroom, handoff, dashboard, OAuth, and
the existing migration paths.

The upstream `/breath-hook` SessionStart injection is explicitly not part of this
port's official ChatGPT capability. ChatGPT connects through MCP and does not receive
that external hook automatically.

Compatibility choices:

- `plan`, `letter`, and `i` use dedicated `plans/`, `letters/`, and `self/` trees.
- All three types are excluded from ordinary merge, decay, archive, resurface,
  handoff continuity, breath recall seeds, and introspection/dream selection.
- `I` records also carry `self_anchor=true` and `dont_surface=true`, reusing the
  fork's existing self-anchor isolation boundary.
- Letters store a UTF-8 base64 canonical copy in frontmatter so leading/trailing
  whitespace and final newlines survive `python-frontmatter` round trips. Reads and
  semantic indexing use the restored verbatim text.
- Plans use exact active-content deduplication only. They do not replace reminders.
- `trace` owns explicit plan `status`, `weight`, and `why_remembered` changes and
  appends a `change_log` entry for each lifecycle change.
- Hold/grow completion checks are connected but default off. They require vector
  similarity plus a conservative LLM verdict and confidence threshold.

## Staging checks

Automated coverage is in `tests/test_special_memory.py`:

1. verbatim letter persistence, author/date filtering, lexical/semantic index path,
   and reload persistence;
2. plan exact deduplication, weight, reason, related bucket, lifecycle, and change log;
3. `I` dimension validation and self-anchor isolation metadata;
4. decay score isolation and archive refusal for all three special types;
5. auto-resolution disabled behavior and enabled vector-plus-LLM linkage;
6. backup/migration recognition of all special directories.

Current local result: 6 passed. The repository's pytest configuration warns that
the optional asyncio plugin is absent in the disposable test environment; these
tests intentionally use `asyncio.run` and are unaffected.

## Mandatory pre-production backup

Do not update the production service until all of the following are copied to a
timestamped, access-controlled backup outside the live volume:

- the complete buckets tree, including `.tombstones`, `embeddings.db`, `plans`,
  `letters`, and `self`;
- the complete state tree and all SQLite/JSONL state files;
- `config.yaml`, runtime config, compose/Zeabur service configuration, and mounted
  config files;
- a value-preserving export of every Zeabur environment variable and secret.

Record a file inventory and SHA-256 manifest. Restore the backup into a separate
empty directory and start a second staging instance against that restored copy.
Never test restoration by overwriting the only production volume.

The local checkout cannot export secrets held by Zeabur, so a production backup is
not claimed here. Export those variables from Zeabur immediately before any rollout.

## Acceptance and rollback gate

On the parallel staging service, verify through MCP:

- create/read each type; letter byte-for-byte content; author/date and semantic
  search; plan dedup and lifecycle; all seven `I` aspects;
- ordinary hold/grow never merge into a special bucket;
- decay cycles neither resolve nor archive special buckets;
- ordinary breath, dream/introspection, handoff, and resurface do not expose them;
- reminder behavior remains unchanged and independent from plan;
- restart persistence after a clean stop and after a forced restart;
- restoration from the backup copy produces identical counts, IDs, content hashes,
  plan change logs, and embedding/index coverage;
- with auto-resolution still off, no plan status changes occur;
- after enabling it only in staging, collect false-positive/false-negative examples
  and verify related-bucket status linkage.

Rollback means stopping the candidate deployment, pointing the service back to the
untouched previous image and restored parallel data copy, then confirming the old
MCP tool inventory and bucket counts. Production rollout remains blocked until this
checklist and the Zeabur environment export are both complete.
