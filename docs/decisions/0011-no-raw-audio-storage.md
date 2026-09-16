# 0011. No raw audio storage

- Status: Accepted
- Date: 2026-09-17

## Context
Voice recordings are sensitive and storage adds infrastructure (object storage) and cost.

## Decision
Audio is processed in memory and discarded. We store transcripts, word timings/confidence and
scores only. No object storage in Q1/Q2.

## Consequences
- Users can't replay their own recordings (possible future feature with explicit consent).
- Re-scoring old attempts with a new provider is impossible.

## Alternatives considered
- Store audio in S3/MinIO with retention — deferred.
