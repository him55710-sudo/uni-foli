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

## Required metadata

- source URL
- publisher
- publication date
- fetched date
- source rank
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
