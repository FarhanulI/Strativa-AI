import fakeredis.aioredis as fakeredis

from app.infrastructure.jobs.idempotency import claim_idempotency_key


async def test_first_claim_succeeds_second_within_ttl_is_rejected() -> None:
    redis = fakeredis.FakeRedis(decode_responses=True)

    first = await claim_idempotency_key(redis, "briefs.generate", "client-key-1", ttl_seconds=60)
    second = await claim_idempotency_key(redis, "briefs.generate", "client-key-1", ttl_seconds=60)

    assert first is True
    assert second is False


async def test_different_scopes_do_not_collide() -> None:
    redis = fakeredis.FakeRedis(decode_responses=True)

    briefs_claim = await claim_idempotency_key(redis, "briefs.generate", "same-key")
    drafts_claim = await claim_idempotency_key(redis, "drafts.generate", "same-key")

    assert briefs_claim is True
    assert drafts_claim is True


async def test_different_keys_in_same_scope_do_not_collide() -> None:
    redis = fakeredis.FakeRedis(decode_responses=True)

    first = await claim_idempotency_key(redis, "briefs.generate", "key-a")
    second = await claim_idempotency_key(redis, "briefs.generate", "key-b")

    assert first is True
    assert second is True
