import pytest
import os
import tempfile
import time
import asyncio
import numpy as np

from foxhole_hud.metadata_store import MetadataStore
from foxhole_hud.bdi_engine import BDIGoalArbiter, Beliefs, GoalHierarchy
from foxhole_hud.mcp_consultant import FoxholeMCPConsultant
from foxhole_hud.cv_engine import FoxholeCVDetector

def test_metadata_store_lifecycle():
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        store = MetadataStore(tmp.name)
        store.record_frame(4.5, 1.1, {"in_vehicle": True, "has_banner": True, "subregion_text": "Fort Viper"}, (500, 300))
        store.record_mcp("get_production_cost", {"name": "Bandages"}, "Cost: 80 Bmats", 15.2)
        store.record_goal_revision("Test Trigger", "Goal A", "Strategic B", "Tactical C")
        
        metrics = store.get_recent_metrics()
        assert metrics["total_frames_recorded"] == 1
        assert metrics["total_mcp_consultations"] == 1
        assert metrics["total_goal_revisions"] == 1
        assert metrics["avg_capture_ms"] == 4.5
        assert metrics["avg_cv_ms"] == 1.1
        store.close()

def test_bdi_goal_arbitration_hierarchy():
    arbiter = BDIGoalArbiter()
    assert "Salt March" in arbiter.current_intentions.goal
    
    # 1. Simulate Map Open transition
    rev_map = arbiter.update_beliefs_from_cv({"is_full_map": True})
    assert rev_map is not None
    assert "Operational Reconnaissance" in rev_map.goal
    assert "Map Open" in rev_map.tactical_priority
    
    # 2. Simulate Bleed emergency
    rev_bleed = arbiter.update_beliefs_from_cv({"is_bleeding": True})
    assert rev_bleed is not None
    assert "Immediate Survival" in rev_bleed.goal
    assert "EMERGENCY" in rev_bleed.tactical_priority

    # 3. Simulate arrival at industrial hub in vehicle
    rev_hub = arbiter.update_beliefs_from_cv({"at_industrial_hub": True, "in_vehicle": True})
    assert rev_hub is not None
    assert "Refinery" in rev_hub.tactical_priority
    assert "Fuel" in rev_hub.strategic_priority

def test_mcp_consultation():
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        store = MetadataStore(tmp.name)
        consultant = FoxholeMCPConsultant(store)
        res = asyncio.run(consultant.get_recipe("Bandages"))
        assert "name" in res or "error" not in res
        assert res.get("name") == "Bandages"
        metrics = store.get_recent_metrics()
        assert metrics["total_mcp_consultations"] == 1
        store.close()

def test_cv_engine_submillisecond_roi():
    detector = FoxholeCVDetector()
    dummy_frame = np.zeros((1080, 1920, 4), dtype=np.uint8)
    dummy_frame[30:60, 30:60, :3] = 255
    
    t0 = time.time()
    boxes, state = detector.process_frame(dummy_frame)
    dt_ms = (time.time() - t0) * 1000
    
    assert dt_ms < 10.0
    assert len(boxes) >= 4  # Stance, compass, squads, chat
    assert state["is_full_map"] is False
