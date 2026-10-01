import os
import cv2
import pytest
from foxhole_hud.cv_engine import FoxholeCVDetector
from foxhole_hud.bdi_engine import BDIGoalArbiter

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")

@pytest.mark.parametrize("fixture_filename,expected_mode,expected_strategic_fragment,expected_box_label", [
    ("pedestrian.png", "PEDESTRIAN", "Field Operations", "STANCE & STAMINA"),
    ("vehicle.png", "VEHICLE", "Motorized Operations", "VEHICLE STATUS"),
    ("spectating.png", "SPECTATING", "Casualty Observation", "SPECTATOR CAM"),
    ("deploy_map.png", "DEPLOY_MAP", "Theater Reinforcement", "DEPLOYMENT DIRECTORY"),
    ("map.png", "MAP", "Theater Reconnaissance", "REGIONAL TACTICAL MAP"),
])
def test_all_game_mode_fixtures(fixture_filename, expected_mode, expected_strategic_fragment, expected_box_label):
    path = os.path.join(FIXTURE_DIR, fixture_filename)
    assert os.path.exists(path), f"Fixture missing: {path}"
    
    img = cv2.imread(path)
    assert img is not None, f"Failed to load fixture: {path}"
    assert img.shape[:2] == (1080, 1920), f"Invalid dimensions: {img.shape}"
    
    detector = FoxholeCVDetector()
    arbiter = BDIGoalArbiter()
    
    boxes, state = detector.process_frame(img)
    rev = arbiter.update_beliefs_from_cv(state)
    
    # 1. Mode Assertion
    assert state["mode"] == expected_mode, (
        f"Mode mismatch for {fixture_filename}! "
        f"Expected '{expected_mode}', got '{state['mode']}'"
    )
    
    # 2. Bounding Box Assertion
    box_labels = [b["label"] for b in boxes]
    assert any(expected_box_label in lbl for lbl in box_labels), (
        f"Missing expected box '{expected_box_label}' in {box_labels}"
    )
    
    # 3. Macro Goal Assertion (Live War 141 Conquest)
    goal = arbiter.current_intentions.goal
    assert "Active Conquest" in goal
    
    # 4. Strategic Priority Assertion
    strat = arbiter.current_intentions.strategic_priority
    assert expected_strategic_fragment.lower() in strat.lower(), (
        f"Strategic priority mismatch! Expected fragment '{expected_strategic_fragment}', got '{strat}'"
    )
