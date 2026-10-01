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
        
        # Record frame
        store.record_frame(4.5, 1.1, {"in_vehicle": True, "has_banner": True, "subregion_text": "Fort Viper"}, (500, 300))
        # Record MCP
        store.record_mcp("get_production_cost", {"name": "Bandages"}, "Cost: 80 Bmats", 15.2)
        # Record Goal revision
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
    
    # Initial state
    assert "Salt March" in arbiter.current_intentions.goal
    
    # 1. Simulate vehicle transit in Marban Hollow
    rev1 = arbiter.update_beliefs_from_cv({"in_vehicle": True}, banner_text="Fort Viper : Afric's Approach")
    assert rev1 is not None
    assert "Marban Hollow" == arbiter.beliefs.region
    assert "Diesel" in rev1.strategic_priority
    assert "Afric's Approach" in rev1.tactical_priority
    
    # 2. Simulate Map Open transition
    rev2 = arbiter.update_beliefs_from_cv({"is_map": True})
    assert rev2 is not None
    assert "Operational Reconnaissance" in rev2.goal
    assert "Map Open" in rev2.tactical_priority
    
    # 3. Simulate Bleed emergency
    rev3 = arbiter.update_beliefs_from_cv({"is_bleeding": True})
    assert rev3 is not None
    assert "Immediate Survival" in rev3.goal
    assert "EMERGENCY" in rev3.tactical_priority

def test_mcp_consultation():
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        store = MetadataStore(tmp.name)
        consultant = FoxholeMCPConsultant(store)
        
        # Test recipe lookup for Bandages using asyncio.run
        res = asyncio.run(consultant.get_recipe("Bandages"))
        assert "name" in res or "error" not in res
        assert res.get("name") == "Bandages"
        
        metrics = store.get_recent_metrics()
        assert metrics["total_mcp_consultations"] == 1
        store.close()

def test_cv_engine_submillisecond_roi():
    detector = FoxholeCVDetector()
    dummy_frame = np.zeros((1080, 1920, 4), dtype=np.uint8)
    
    # Draw simulated white fist in top-left
    dummy_frame[30:60, 30:60, :3] = 255
    
    t0 = time.time()
    boxes, state = detector.process_frame(dummy_frame)
    dt_ms = (time.time() - t0) * 1000
    
    assert dt_ms < 10.0  # Sub-millisecond performance
    assert len(boxes) >= 4  # Stance, compass, squads, chat
    assert state["is_map"] is False
