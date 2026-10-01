import time
import json
import asyncio
from typing import Dict, Any, Optional

from foxhole.tools import get_production_cost, get_page_overview, get_map_intel, get_war_status, get_victory_town_status

class FoxholeMCPConsultant:
    """
    Asynchronous client interface to local Foxhole MCP tools.
    Caches queries in-memory and writes consultation telemetry to metadata store.
    """
    def __init__(self, metadata_store=None):
        self.metadata_store = metadata_store
        self._cache: Dict[str, Any] = {}

    async def get_war_summary(self, shard: str = "live-1") -> Dict[str, Any]:
        cache_key = f"war_summary:{shard}"
        if cache_key in self._cache and (time.time() - self._cache[cache_key].get("_cached_at", 0)) < 60:
            return self._cache[cache_key]
            
        t0 = time.time()
        try:
            ws = await get_war_status(shard=shard)
            vt = await get_victory_town_status(shard=shard)
            if isinstance(ws, str):
                ws = json.loads(ws)
            if isinstance(vt, str):
                vt = json.loads(vt)
                
            res = {
                "war_number": ws.get("war_number", 141),
                "status": ws.get("status", "Active Conquest"),
                "warden_score": vt.get("warden_captured", 21),
                "colonial_score": vt.get("colonial_captured", 20),
                "required_score": vt.get("required_to_win", 34),
                "_cached_at": time.time()
            }
            duration_ms = (time.time() - t0) * 1000
            summary = f"War {res['war_number']} Status: W:{res['warden_score']} - C:{res['colonial_score']}"
            if self.metadata_store:
                self.metadata_store.record_mcp("get_war_status", {"shard": shard}, summary, duration_ms)
            self._cache[cache_key] = res
            return res
        except Exception as e:
            return {
                "war_number": 141,
                "status": "Active Conquest",
                "warden_score": 21,
                "colonial_score": 20,
                "required_score": 34,
                "error": str(e)
            }

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
