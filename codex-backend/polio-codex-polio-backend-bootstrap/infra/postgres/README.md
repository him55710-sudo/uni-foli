# Postgres Infra

Primary database for transactional data plus vector search through pgvector.

## Owns

- schema migrations
- extensions
- backup policy
- row-level access strategy
`postgres` 폴더는 `polio`의 기본 로컬 데이터베이스 구성을 담습니다.

- `docker-compose.yml`의 `postgres` 서비스는 `pgvector`가 포함된 Postgres 이미지를 사용합니다.
- `init/01-init-db.sql`은 최초 컨테이너 생성 시 `vector` extension을 켭니다.
- 운영 환경에서는 Alembic 마이그레이션을 기준으로 스키마를 맞추고, 앱의 `create_all()`은 보조 수단으로만 사용하세요.
