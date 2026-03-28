# 05 Source Ingestion

This is the backend pipeline for non-user knowledge sources.

## Source ladder

Rank sources before indexing them.

1. official university admissions pages and guidebooks
2. official school or ministry guidance
3. official statistics and public research
4. curated expert notes with provenance
5. low-trust web content as weak context only

## Pipeline

1. discover source
2. fetch raw content
3. normalize content and metadata
4. classify source rank
5. chunk and embed
6. index for retrieval
7. freshness monitoring

## Current repo boundary

- Student uploads and external research are stored separately.
- External research is indexed for RAG as `EXTERNAL_RESEARCH`.
- Student records remain the only admissible proof for student actions and achievements.
- External research can support industry context, trend analysis, or recommendation rationale only.
- In the current API, `source_type` means the ingestion format (`web_article`, `youtube_transcript`, `paper`, `pdf_document`).
- Trust policy is carried separately as `source_classification` so the repo does not overload one field with two meanings.

## Required metadata

- source URL
- publisher
- publication date
- fetched date
- source classification
- trust rank
- content type
- usage notes
- jurisdiction or target school

## Do not ingest by default

- copyrighted commercial books as reusable corpora
- private consultancy documents
- unverifiable social posts
- anonymously uploaded "tips"

## Freshness policy

- official admissions documents must carry cycle year
- stale sources must be flagged or excluded from high-confidence answers
- source refresh jobs should run on a schedule and on-demand
