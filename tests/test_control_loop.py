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
    assert "Map Recon Open" in rev_map.tactical_priority
    
    # 2. Simulate Bleed emergency
    rev_bleed = arbiter.update_beliefs_from_cv({"is_bleeding": True})
    assert rev_bleed is not None
    assert "Immediate Survival" in rev_bleed.goal
    assert "EMERGENCY" in rev_bleed.tactical_priority

    # 3. Simulate arrival at Seaport on foot (empty Dunnes)
    rev_seaport = arbiter.update_beliefs_from_cv({
        "at_industrial_hub": True,
        "subregion": "Maiden's Veil Seaport / Docks (West)",
        "in_vehicle": False
    })
    assert rev_seaport is not None
    assert "Seaport" in rev_seaport.tactical_priority
    assert "Sprint to Refinery" in rev_seaport.tactical_priority
    assert "Fuel Crisis" in rev_seaport.strategic_priority

    # 4. Simulate arrival at industrial hub in vehicle
    rev_hub = arbiter.update_beliefs_from_cv({
        "at_industrial_hub": True,
        "subregion": "Maiden's Veil (Industrial Sector)",
        "in_vehicle": True
    })
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
    assert state["mode"] in ("PEDESTRIAN", "VEHICLE", "MAP", "DEPLOY_MAP", "SPECTATING")

def test_five_mode_instant_recognition():
    detector = FoxholeCVDetector()
    arbiter = BDIGoalArbiter()

    # 1. SPECTATING test (Spectator banner with "SPECTATING: PLAYER_NAME")
    spec_frame = np.zeros((1080, 1920, 4), dtype=np.uint8)
    for i, x in enumerate(range(760, 1060, 20)):
        spec_frame[45:58, x:x+8, :3] = 255  # 15 letters of 13x8 = 1560 px
    boxes_s, state_s = detector.process_frame(spec_frame)
    assert state_s["mode"] == "SPECTATING"
    assert any("SPECTATOR CAM" in b["label"] for b in boxes_s)
    rev_s = arbiter.update_beliefs_from_cv(state_s)
    assert "Combat Observation" in rev_s.goal
    assert "Spectating Ally" in rev_s.tactical_priority

    # 2. DEPLOY_MAP test (Conquest letters in left panel)
    deploy_frame = np.zeros((1080, 1920, 4), dtype=np.uint8)
    for i, x in enumerate(range(30, 130, 12)):
        deploy_frame[102:114, x:x+6, :3] = 255
    boxes_d, state_d = detector.process_frame(deploy_frame)
    assert state_d["mode"] == "DEPLOY_MAP"
    assert any("DEPLOYMENT DIRECTORY" in b["label"] for b in boxes_d)
    rev_d = arbiter.update_beliefs_from_cv(state_d)
    assert "Deployment" in rev_d.goal

    # 3. MAP test ('M' key tactical map)
    map_frame = np.zeros((1080, 1920, 4), dtype=np.uint8)
    map_frame[250:800, 450:1450, :3] = 140  # Parchment canvas
    boxes_m, state_m = detector.process_frame(map_frame)
    assert state_m["mode"] == "MAP"
    assert any("REGIONAL TACTICAL MAP" in b["label"] for b in boxes_m)
    rev_m = arbiter.update_beliefs_from_cv(state_m)
    assert "Operational Reconnaissance" in rev_m.goal

    # 4. VEHICLE test (Seat dots / vehicle silhouette without stamina bar)
    veh_frame = np.zeros((1080, 1920, 4), dtype=np.uint8)
    veh_frame[20:110, 20:120, :3] = 220  # Vehicle silhouette
    veh_frame[98:108, 30:40, :3] = 255   # Seat dot 1
    veh_frame[98:108, 50:60, :3] = 255   # Seat dot 2
    boxes_v, state_v = detector.process_frame(veh_frame)
    assert state_v["mode"] == "VEHICLE"
    assert any("VEHICLE STATUS" in b["label"] for b in boxes_v)
    rev_v = arbiter.update_beliefs_from_cv(state_v)
    assert "Dunne" in rev_v.tactical_priority

    # 5. PEDESTRIAN test (Stance posture + sprint stamina bar)
    ped_frame = np.zeros((1080, 1920, 4), dtype=np.uint8)
    ped_frame[20:80, 20:80, :3] = 220     # Stance figure
    ped_frame[124:136, 22:145, :3] = 255  # Stamina bar
    boxes_p, state_p = detector.process_frame(ped_frame)
    assert state_p["mode"] == "PEDESTRIAN"
    assert any("STANCE & STAMINA" in b["label"] for b in boxes_p)
    rev_p = arbiter.update_beliefs_from_cv(state_p)
    assert "on foot" in rev_p.tactical_priority.lower()
