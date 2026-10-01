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

from foxhole_hud.telemetry_aggregator import PlayerTelemetryAggregator

def test_metadata_store_lifecycle():
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        store = MetadataStore(tmp.name)
        store.record_frame(4.5, 1.1, {"in_vehicle": True, "has_banner": True, "subregion_text": "Fort Viper"}, (500, 300))
        store.record_mcp("get_production_cost", {"name": "Bandages"}, "Cost: 80 Bmats", 15.2)
        store.record_transition("PEDESTRIAN", "VEHICLE", 45.2)
        
        metrics = store.get_recent_metrics()
        assert metrics["total_frames_recorded"] == 1
        assert metrics["total_mcp_consultations"] == 1
        assert metrics["total_mode_transitions"] == 1
        assert metrics["avg_capture_ms"] == 4.5
        assert metrics["avg_cv_ms"] == 1.1
        store.close()

def test_player_telemetry_aggregator():
    agg = PlayerTelemetryAggregator()
    
    # 1. Initial Pedestrian update
    summary = agg.update({
        "mode": "PEDESTRIAN",
        "stamina_pct": 100,
        "stance": "STAND",
        "is_bleeding": False,
        "has_minimap": True,
        "player_marker": (1000, 500)
    }, cap_ms=4.5, cv_ms=1.2)
    
    assert summary["current_mode"] == "PEDESTRIAN"
    assert summary["vitals"]["health"] == "STABLE"
    assert summary["vitals"]["stamina_pct"] == 100
    assert summary["vitals"]["stance"] == "STAND"
    assert summary["navigation"]["has_minimap"] is True
    assert summary["navigation"]["gps_coord"] == (1000, 500)
    assert summary["navigation"]["cumulative_dist_px"] == 0.0

    # 2. Movement & Stamina Drain
    for i in range(1, 10):
        summary = agg.update({
            "mode": "PEDESTRIAN",
            "stamina_pct": 100 - (i * 5),
            "stance": "STAND",
            "is_bleeding": False,
            "has_minimap": True,
            "player_marker": (1000 + i * 10, 500)
        }, cap_ms=4.8, cv_ms=1.0)
    
    assert summary["vitals"]["stamina_trend"] == "DRAINING"
    assert summary["vitals"]["stamina_pct"] == 55
    assert summary["navigation"]["cumulative_dist_px"] == pytest.approx(90.0, abs=1.0)

    # 3. Mode transition to VEHICLE
    summary = agg.update({
        "mode": "VEHICLE",
        "has_shield": True,
        "stance": "MOUNTED",
        "is_bleeding": False
    }, cap_ms=4.6, cv_ms=1.1)
    
    assert summary["current_mode"] == "VEHICLE"
    assert summary["vitals"]["has_shield"] is True
    assert summary["vitals"]["stance"] == "MOUNTED"
    assert summary["analytics"]["transition_count"] == 1
    assert agg.transitions[0][1] == "PEDESTRIAN"
    assert agg.transitions[0][2] == "VEHICLE"

    # 4. Mode transition to MAP with GPS chevron
    summary = agg.update({
        "mode": "MAP",
        "player_marker": (1234, 483)
    }, cap_ms=4.7, cv_ms=1.3)
    
    assert summary["current_mode"] == "MAP"
    assert summary["analytics"]["transition_count"] == 2
    assert summary["navigation"]["gps_coord"] == (1234, 483)
    assert summary["performance"]["total_pipeline_ms"] > 0
    assert summary["performance"]["max_possible_fps"] > 50

def test_bdi_goal_arbitration_hierarchy():
    arbiter = BDIGoalArbiter()
    assert "Active Conquest" in arbiter.current_intentions.goal
    
    # 1. Simulate Map Open transition
    rev_map = arbiter.update_beliefs_from_cv({"is_full_map": True, "player_marker": (1234, 483)})
    assert rev_map is not None
    assert "Theater Reconnaissance" in rev_map.strategic_priority
    assert "GPS Fix Locked" in rev_map.tactical_priority
    
    # 2. Simulate Bleed emergency
    rev_bleed = arbiter.update_beliefs_from_cv({"is_bleeding": True})
    assert rev_bleed is not None
    assert "Hemorrhage" in rev_bleed.strategic_priority
    assert "CRITICAL" in rev_bleed.tactical_priority

    # 3. Simulate Vehicle transition
    rev_veh = arbiter.update_beliefs_from_cv({"in_vehicle": True, "has_shield": True})
    assert rev_veh is not None
    assert "Armored Combat" in rev_veh.strategic_priority

    # 4. Simulate Pedestrian transition
    rev_ped = arbiter.update_beliefs_from_cv({"mode": "PEDESTRIAN", "stamina_pct": 100, "has_minimap": True})
    assert rev_ped is not None
    assert "Field Operations" in rev_ped.strategic_priority
    assert "Sprint Ready" in rev_ped.tactical_priority

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
    
    # Warm-up call
    detector.process_frame(dummy_frame)

    t0 = time.time()
    for _ in range(5):
        boxes, state = detector.process_frame(dummy_frame)
    dt_ms = ((time.time() - t0) / 5) * 1000
    
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
    assert "Casualty Observation" in rev_s.strategic_priority
    assert "Spectating Ally" in rev_s.tactical_priority

    # 2. DEPLOY_MAP test (Conquest letters in left panel with world map parchment)
    deploy_frame = np.zeros((1080, 1920, 4), dtype=np.uint8)
    deploy_frame[200:800, 400:1500, :3] = 160  # World map parchment
    for i, x in enumerate(range(30, 130, 12)):
        deploy_frame[102:114, x:x+6, :3] = 255  # CONQUEST header
    boxes_d, state_d = detector.process_frame(deploy_frame)
    assert state_d["mode"] == "DEPLOY_MAP"
    assert any("DEPLOYMENT DIRECTORY" in b["label"] for b in boxes_d)
    rev_d = arbiter.update_beliefs_from_cv(state_d)
    assert "Theater Reinforcement" in rev_d.strategic_priority

    # 3. MAP test ('M' key tactical map)
    map_frame = np.zeros((1080, 1920, 4), dtype=np.uint8)
    map_frame[250:800, 450:1450, :3] = 160  # Parchment canvas
    boxes_m, state_m = detector.process_frame(map_frame)
    assert state_m["mode"] == "MAP"
    assert any("REGIONAL TACTICAL MAP" in b["label"] for b in boxes_m)
    rev_m = arbiter.update_beliefs_from_cv(state_m)
    assert "Theater Reconnaissance" in rev_m.strategic_priority

    # 4. VEHICLE test (Seat dots / vehicle silhouette without stamina bar)
    veh_frame = np.zeros((1080, 1920, 4), dtype=np.uint8)
    veh_frame[20:110, 20:120, :3] = 220  # Vehicle silhouette
    veh_frame[98:108, 30:40, :3] = 255   # Seat dot 1
    veh_frame[98:108, 50:60, :3] = 255   # Seat dot 2
    boxes_v, state_v = detector.process_frame(veh_frame)
    assert state_v["mode"] == "VEHICLE"
    assert any("VEHICLE STATUS" in b["label"] for b in boxes_v)
    rev_v = arbiter.update_beliefs_from_cv(state_v)
    assert "Motorized Operations" in rev_v.strategic_priority

    # 5. PEDESTRIAN test (Stance posture + sprint stamina bar)
    ped_frame = np.zeros((1080, 1920, 4), dtype=np.uint8)
    ped_frame[20:80, 20:80, :3] = 220     # Stance figure
    ped_frame[124:136, 22:145, :3] = 255  # Stamina bar
    boxes_p, state_p = detector.process_frame(ped_frame)
    assert state_p["mode"] == "PEDESTRIAN"
    assert any("STANCE & STAMINA" in b["label"] for b in boxes_p)
    rev_p = arbiter.update_beliefs_from_cv(state_p)
    assert "Field Operations" in rev_p.strategic_priority
