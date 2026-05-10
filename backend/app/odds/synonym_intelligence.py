from sqlalchemy import text
from sqlalchemy.orm import Session

from app.odds.market_normalizer import normalize_market_and_selection


def ensure_odds_synonym_table(session: Session) -> None:
    session.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS odds_market_synonyms (
                id SERIAL PRIMARY KEY,
                raw_market_name TEXT NOT NULL,
                raw_selection_name TEXT NOT NULL,
                canonical_market TEXT NOT NULL,
                confidence NUMERIC(6, 4) NOT NULL DEFAULT 1.0,
                usage_count INTEGER NOT NULL DEFAULT 1,
                provider TEXT,
                bookmaker TEXT,
                reason TEXT,
                active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
                UNIQUE(raw_market_name, raw_selection_name, canonical_market)
            );

            CREATE INDEX IF NOT EXISTS ix_odds_synonyms_canonical_market
            ON odds_market_synonyms(canonical_market);

            CREATE INDEX IF NOT EXISTS ix_odds_synonyms_raw_lookup
            ON odds_market_synonyms(raw_market_name, raw_selection_name);
            """
        )
    )
    session.commit()


def rebuild_odds_synonym_intelligence(session: Session, limit: int = 100000) -> dict:
    ensure_odds_synonym_table(session)

    rows = session.execute(
        text(
            """
            SELECT
                market AS raw_market_name,
                selection AS raw_selection_name,
                COUNT(*) AS usage_count
            FROM match_odds
            WHERE market IS NOT NULL
              AND selection IS NOT NULL
            GROUP BY market, selection
            ORDER BY usage_count DESC
            LIMIT :limit
            """
        ),
        {"limit": limit},
    ).mappings().all()

    inserted_or_updated = 0
    unsupported = 0

    for row in rows:
        result = normalize_market_and_selection(
            market_name=row["raw_market_name"],
            selection_name=row["raw_selection_name"],
        )

        if not result.canonical_market:
            unsupported += 1
            continue

        session.execute(
            text(
                """
                INSERT INTO odds_market_synonyms (
                    raw_market_name,
                    raw_selection_name,
                    canonical_market,
                    confidence,
                    usage_count,
                    reason,
                    active,
                    updated_at
                )
                VALUES (
                    :raw_market_name,
                    :raw_selection_name,
                    :canonical_market,
                    :confidence,
                    :usage_count,
                    :reason,
                    TRUE,
                    NOW()
                )
                ON CONFLICT (raw_market_name, raw_selection_name, canonical_market)
                DO UPDATE SET
                    confidence = EXCLUDED.confidence,
                    usage_count = EXCLUDED.usage_count,
                    reason = EXCLUDED.reason,
                    active = TRUE,
                    updated_at = NOW()
                """
            ),
            {
                "raw_market_name": row["raw_market_name"],
                "raw_selection_name": row["raw_selection_name"],
                "canonical_market": result.canonical_market,
                "confidence": result.confidence,
                "usage_count": int(row["usage_count"]),
                "reason": result.reason,
            },
        )

        inserted_or_updated += 1

    session.commit()

    return {
        "status": "ok",
        "synonyms_inserted_or_updated": inserted_or_updated,
        "unsupported_pairs_skipped": unsupported,
    }


def lookup_synonym(
    session: Session,
    raw_market_name: str,
    raw_selection_name: str,
) -> dict | None:
    row = session.execute(
        text(
            """
            SELECT
                raw_market_name,
                raw_selection_name,
                canonical_market,
                confidence,
                usage_count,
                reason
            FROM odds_market_synonyms
            WHERE raw_market_name = :raw_market_name
              AND raw_selection_name = :raw_selection_name
              AND active = TRUE
            ORDER BY confidence DESC, usage_count DESC
            LIMIT 1
            """
        ),
        {
            "raw_market_name": raw_market_name,
            "raw_selection_name": raw_selection_name,
        },
    ).mappings().first()

    return dict(row) if row else None


def synonym_summary(session: Session) -> dict:
    rows = session.execute(
        text(
            """
            SELECT
                canonical_market,
                COUNT(*) AS synonym_pairs,
                SUM(usage_count) AS total_usage
            FROM odds_market_synonyms
            WHERE active = TRUE
            GROUP BY canonical_market
            ORDER BY total_usage DESC
            """
        )
    ).mappings().all()

    return {
        "status": "ok",
        "markets": [dict(row) for row in rows],
    }