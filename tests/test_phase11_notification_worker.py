import asyncio
import json
from uuid import UUID

import httpx

from app.notifications.worker import SupabaseNotificationWorkerRepository

DELIVERY_ID = UUID("00000000-0000-0000-0000-000000001131")
CLAIM_TOKEN = UUID("00000000-0000-0000-0000-000000001132")
DEVICE_ID = UUID("00000000-0000-0000-0000-000000001133")
RAW_TOKEN = "mock-success:private-worker-token"


def test_destination_lookup_is_claim_bound_and_keeps_token_secret() -> None:
    seen_payloads: list[dict[str, object]] = []

    def transport(request: httpx.Request) -> httpx.Response:
        seen_payloads.append(json.loads(request.content.decode("utf-8")))
        return httpx.Response(
            200,
            json=[
                {
                    "id": str(DEVICE_ID),
                    "platform": "android",
                    "transport": "mock",
                    "push_token": RAW_TOKEN,
                    "synthetic": True,
                }
            ],
        )

    async def run() -> None:
        client = httpx.AsyncClient(transport=httpx.MockTransport(transport))
        repository = SupabaseNotificationWorkerRepository(
            supabase_url="https://synthetic.supabase.co",
            service_role_key="synthetic-service-role",
            client=client,
        )

        destinations = await repository.destinations_for_claim(
            delivery_id=DELIVERY_ID,
            claim_token=CLAIM_TOKEN,
        )

        assert seen_payloads == [
            {
                "p_delivery_id": str(DELIVERY_ID),
                "p_claim_token": str(CLAIM_TOKEN),
            }
        ]
        assert "user_id" not in seen_payloads[0]
        assert destinations[0].device_id == DEVICE_ID
        assert destinations[0].push_token.get_secret_value() == RAW_TOKEN
        assert RAW_TOKEN not in repr(destinations[0])
        assert RAW_TOKEN not in destinations[0].model_dump_json()

        await client.aclose()

    asyncio.run(run())
