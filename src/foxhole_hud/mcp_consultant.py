import time
import json
import asyncio
from typing import Dict, Any, Optional

from foxhole.tools import get_production_cost, get_page_overview, get_map_intel

class FoxholeMCPConsultant:
    """
    Asynchronous client interface to local Foxhole MCP tools.
    Caches queries in-memory and writes consultation telemetry to metadata store.
    """
    def __init__(self, metadata_store=None):
        self.metadata_store = metadata_store
        self._cache: Dict[str, Any] = {}

    async def get_recipe(self, item_name: str) -> Dict[str, Any]:
        cache_key = f"recipe:{item_name}"
        if cache_key in self._cache:
            return self._cache[cache_key]
            
        t0 = time.time()
        try:
            res = await get_production_cost(name=item_name)
            if isinstance(res, str):
                try:
                    res = json.loads(res)
                except Exception:
                    res = {"raw": res}
            duration_ms = (time.time() - t0) * 1000
            summary = f"Cost: {res.get('name', item_name)}"
            if self.metadata_store:
                self.metadata_store.record_mcp("get_production_cost", {"name": item_name}, summary, duration_ms)
            self._cache[cache_key] = res
            return res
        except Exception as e:
            return {"error": str(e)}

    async def get_region_info(self, region_name: str) -> Dict[str, Any]:
        cache_key = f"region:{region_name}"
        if cache_key in self._cache:
            return self._cache[cache_key]
            
        t0 = time.time()
        try:
            res = await get_page_overview(title=region_name)
            if isinstance(res, str):
                try:
                    res = json.loads(res)
                except Exception:
                    res = {"raw": res}
            duration_ms = (time.time() - t0) * 1000
            summary = f"Region: {region_name} overview retrieved"
            if self.metadata_store:
                self.metadata_store.record_mcp("get_page_overview", {"title": region_name}, summary, duration_ms)
            self._cache[cache_key] = res
            return res
        except Exception as e:
            return {"error": str(e)}
