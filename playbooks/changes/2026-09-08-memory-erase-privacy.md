# Change: make Memory erase remove recoverable child content

**Commit binding:** Same commit as this record.

## Summary

Memory erase now clears every in-memory session owned by the requested child,
or every cached session for `purge_all`. Deletion manifests contain opaque record
identifiers instead of copied child content. Write and recall audit entries retain
operational metadata without utterance or query excerpts. Because each SQLite
snapshot contains all children, every existing restore point and its vector index
is removed whenever an erase completes; live data for other children remains.

## Layer

Shared State and Trust Boundary.

## Contract impact

Backward-compatible HTTP response shape. Existing fields remain; `stats` adds a
`snapshots` count. Manifest rows intentionally narrow to deletion metadata:
`type`, opaque `id`, erase job metadata, requester, deadline and purpose.

## Files

- `backend/memory_store/memstore/working.py`
- `backend/memory_store/memstore/snapshot.py`
- `backend/memory_store/memstore/erase.py`
- `backend/memory_store/memstore/service.py`
- `backend/memory_store/tests/test_erase_privacy.py`
- `backend/memory_store/tests/test_nfr.py`

## TDD evidence

Run from `backend/memory_store` before implementation:

```sh
python -m pytest tests/test_erase_privacy.py tests/test_nfr.py::test_audit_covers_all_stores -q -p no:cacheprovider
```

Observed RED: 6 failed. The failures independently showed child-owned cached
sessions surviving erase, `purge_all` retaining cache, raw child fields in the
manifest, original text in audit summaries, missing snapshot purge statistics and
the pre-existing audit test requiring the leaked utterance.

Run after the minimal implementation:

```sh
python -m pytest tests/test_erase_privacy.py tests/test_nfr.py::test_audit_covers_all_stores -q -p no:cacheprovider
```

Observed GREEN: 6 passed. A subsequent collection check reported five focused
privacy tests plus the updated audit regression.

## Verification

Run from `backend/memory_store`:

```sh
python -m pytest tests -q -p no:cacheprovider
```

Observed: 73 passed. The only warning is the existing FAISS import warning for
NumPy's deprecated private `numpy.core._multiarray_umath` namespace.

## Rollback

Revert the implementation, regression tests and this record together only when a
replacement privacy-safe erase path is ready. Reverting alone restores raw data in
manifests and audit summaries, leaves deleted-child cache resident, and makes old
SQLite snapshots capable of restoring erased records.

## Reusable knowledge

No new skill. The invariant is deterministic and is enforced by focused automated
regression tests. Shared SQLite snapshots cannot be selectively retained after a
single-child erase unless the snapshot format is redesigned around per-child
encryption or partitioning.
