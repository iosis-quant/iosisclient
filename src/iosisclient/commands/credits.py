from __future__ import annotations

import sys

from iosisclient.client import IosisClient
from iosisclient.config import Config


def credits(args: object, config: Config) -> int:
    if not config.cloud.api_key:
        print("Error: no API key. Run `iosis init` or set IOSIS_API_KEY.", file=sys.stderr)
        return 1

    client = IosisClient(api_key=config.cloud.api_key, base_url=config.cloud.base_url)
    result = client.get_credits()
    data = result.get("credits", result) if isinstance(result, dict) else {}

    print(f"Remaining: {data.get('remaining', '-')}")
    print(f"Total:     {data.get('total', '-')}")
    print(f"Consumed:  {data.get('consumedCredits', data.get('consumed_credits', '-'))}")

    return 0
