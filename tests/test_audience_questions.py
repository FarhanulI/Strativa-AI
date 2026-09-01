import uuid

from httpx import ASGITransport, AsyncClient

from app.main import app


async def _create_workspace(client: AsyncClient, slug: str) -> str:
    response = await client.post(
        "/api/v1/workspaces",
        json={"name": f"Workspace {slug}", "slug": slug},
    )
    assert response.status_code == 201
    return response.json()["id"]


async def _create_profile(client: AsyncClient, workspace_id: str, name: str) -> str:
    response = await client.post(
        "/api/v1/profiles",
        params={"workspace_id": workspace_id},
        json={"type": "creator", "name": name},
    )
    assert response.status_code == 201
    return response.json()["id"]


async def _create_audience_intelligence(
    client: AsyncClient, workspace_id: str, profile_id: str
) -> str:
    response = await client.post(
        f"/api/v1/profiles/{profile_id}/audience-intelligence",
        params={"workspace_id": workspace_id},
        json={"summary": "Test audience"},
    )
    assert response.status_code == 201
    return response.json()["id"]


async def test_create_question(override_get_db) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "question-create")
        profile_id = await _create_profile(client, workspace_id, "Test Creator")
        audience_id = await _create_audience_intelligence(client, workspace_id, profile_id)

        response = await client.post(
            f"/api/v1/audience-intelligence/{audience_id}/questions",
            params={"workspace_id": workspace_id},
            json={
                "question": "Which jersey is best for hot weather?",
                "frequency": 4,
                "importance": 5,
            },
        )

    assert response.status_code == 201
    data = response.json()
    assert data["question"] == "Which jersey is best for hot weather?"
    assert data["frequency"] == 4


async def test_list_questions(override_get_db) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "question-list")
        profile_id = await _create_profile(client, workspace_id, "Test Creator")
        audience_id = await _create_audience_intelligence(client, workspace_id, profile_id)

        await client.post(
            f"/api/v1/audience-intelligence/{audience_id}/questions",
            params={"workspace_id": workspace_id},
            json={"question": "Question 1", "frequency": 3},
        )
        await client.post(
            f"/api/v1/audience-intelligence/{audience_id}/questions",
            params={"workspace_id": workspace_id},
            json={"question": "Question 2", "frequency": 4},
        )

        response = await client.get(
            f"/api/v1/audience-intelligence/{audience_id}/questions",
            params={"workspace_id": workspace_id},
        )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


async def test_get_question(override_get_db) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "question-get")
        profile_id = await _create_profile(client, workspace_id, "Test Creator")
        audience_id = await _create_audience_intelligence(client, workspace_id, profile_id)

        create_response = await client.post(
            f"/api/v1/audience-intelligence/{audience_id}/questions",
            params={"workspace_id": workspace_id},
            json={"question": "Test Question?"},
        )
        question_id = create_response.json()["id"]

        response = await client.get(
            f"/api/v1/audience-intelligence/{audience_id}/questions/{question_id}",
            params={"workspace_id": workspace_id},
        )

    assert response.status_code == 200
    assert response.json()["question"] == "Test Question?"


async def test_update_question(override_get_db) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "question-update")
        profile_id = await _create_profile(client, workspace_id, "Test Creator")
        audience_id = await _create_audience_intelligence(client, workspace_id, profile_id)

        create_response = await client.post(
            f"/api/v1/audience-intelligence/{audience_id}/questions",
            params={"workspace_id": workspace_id},
            json={"question": "Original?", "frequency": 2},
        )
        question_id = create_response.json()["id"]

        response = await client.patch(
            f"/api/v1/audience-intelligence/{audience_id}/questions/{question_id}",
            params={"workspace_id": workspace_id},
            json={"frequency": 5},
        )

    assert response.status_code == 200
    assert response.json()["frequency"] == 5


async def test_delete_question(override_get_db) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "question-delete")
        profile_id = await _create_profile(client, workspace_id, "Test Creator")
        audience_id = await _create_audience_intelligence(client, workspace_id, profile_id)

        create_response = await client.post(
            f"/api/v1/audience-intelligence/{audience_id}/questions",
            params={"workspace_id": workspace_id},
            json={"question": "To Delete?"},
        )
        question_id = create_response.json()["id"]

        response = await client.delete(
            f"/api/v1/audience-intelligence/{audience_id}/questions/{question_id}",
            params={"workspace_id": workspace_id},
        )

    assert response.status_code == 204


async def test_frequency_validation(override_get_db) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "question-frequency")
        profile_id = await _create_profile(client, workspace_id, "Test Creator")
        audience_id = await _create_audience_intelligence(client, workspace_id, profile_id)

        response = await client.post(
            f"/api/v1/audience-intelligence/{audience_id}/questions",
            params={"workspace_id": workspace_id},
            json={"question": "Test?", "frequency": 10},
        )

    assert response.status_code == 422


async def test_importance_validation(override_get_db) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace_id = await _create_workspace(client, "question-importance")
        profile_id = await _create_profile(client, workspace_id, "Test Creator")
        audience_id = await _create_audience_intelligence(client, workspace_id, profile_id)

        response = await client.post(
            f"/api/v1/audience-intelligence/{audience_id}/questions",
            params={"workspace_id": workspace_id},
            json={"question": "Test?", "importance": 0},
        )

    assert response.status_code == 422


async def test_question_workspace_isolation(override_get_db) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        workspace1_id = await _create_workspace(client, "question-iso-1")
        workspace2_id = await _create_workspace(client, "question-iso-2")
        profile_id = await _create_profile(client, workspace1_id, "Test Creator")
        audience_id = await _create_audience_intelligence(client, workspace1_id, profile_id)

        response = await client.get(
            f"/api/v1/audience-intelligence/{audience_id}/questions",
            params={"workspace_id": workspace2_id},
        )

    assert response.status_code == 404
