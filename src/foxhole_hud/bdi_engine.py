from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import time

@dataclass
class Beliefs:
    mode: str = "PEDESTRIAN"
    in_vehicle: bool = False
    is_spectating: bool = False
    is_bleeding: bool = False
    is_full_map: bool = False
    is_deploy_map: bool = False
    has_minimap: bool = True
    has_shield: bool = False
    stamina_pct: int = 100
    player_marker: Optional[tuple] = None
    war_number: int = 141
    warden_score: int = 21
    colonial_score: int = 20
    required_score: int = 34
    last_update: float = field(default_factory=time.time)

@dataclass
class GoalHierarchy:
    goal: str
    strategic_priority: str
    tactical_priority: str
    confidence: float = 1.0
    revision_trigger: str = "Initial"
    timestamp: float = field(default_factory=time.time)

class BDIGoalArbiter:
    """
    Belief-Desire-Intention (BDI) and Goal-Driven Autonomy (GDA) Engine.
    Grounded in live War 141 Conquest data and real-time CV game surroundings:
    - Mode: PEDESTRIAN, VEHICLE, SPECTATING, DEPLOY_MAP, MAP
    - Health: Hemorrhage / Stable
    - Mobility: Sprint stamina %, Minimap radar, Vehicle armor status
    - Navigation: GPS map coordinates, hex recon
    """
    def __init__(self, mcp_consultant=None, metadata_store=None):
        self.beliefs = Beliefs()
        self.mcp = mcp_consultant
        self.metadata = metadata_store
        self.current_intentions = self._build_intentions(trigger="Initial Beliefs Grounded")

    def update_war_intel(self, war_summary: Dict[str, Any]):
        b = self.beliefs
        b.war_number = war_summary.get("war_number", b.war_number)
        b.warden_score = war_summary.get("warden_score", b.warden_score)
        b.colonial_score = war_summary.get("colonial_score", b.colonial_score)
        b.required_score = war_summary.get("required_score", b.required_score)
        return self.evaluate_discrepancy()

    def update_beliefs_from_cv(self, cv_state: Dict[str, Any], banner_text: str = ""):
        b = self.beliefs
        b.mode = cv_state.get("mode", "PEDESTRIAN")
        b.in_vehicle = cv_state.get("in_vehicle", (b.mode == "VEHICLE"))
        b.is_spectating = cv_state.get("is_spectating", (b.mode == "SPECTATING"))
        b.is_bleeding = cv_state.get("is_bleeding", False)
        b.is_full_map = cv_state.get("is_full_map", (b.mode == "MAP"))
        b.is_deploy_map = cv_state.get("is_deploy_map", (b.mode == "DEPLOY_MAP"))
        b.has_minimap = cv_state.get("has_minimap", False)
        b.has_shield = cv_state.get("has_shield", False)
        b.stamina_pct = cv_state.get("stamina_pct", 100)
        b.player_marker = cv_state.get("player_marker")

        b.last_update = time.time()
        return self.evaluate_discrepancy()

    def _build_intentions(self, trigger: str) -> GoalHierarchy:
        b = self.beliefs

        # 1. Macro Campaign Goal (True Live War Status)
        macro_goal = f"War {b.war_number} Active Conquest // Victory Towns: Wardens {b.warden_score} - Colonials {b.colonial_score} (Required: {b.required_score})"

        # 2. Priority 0: Immediate Survival (Bleeding)
        if b.is_bleeding:
            return GoalHierarchy(
                goal=macro_goal,
                strategic_priority="Emergency Hemorrhage Intervention // Critical Trauma",
                tactical_priority="CRITICAL: Bleeding detected! Seek immediate cover (press C), apply Bandage or request nearby Medic in voice/local comms",
                revision_trigger=trigger
            )

        # 3. Mode: MAP
        if b.mode == "MAP" or b.is_full_map:
            if b.player_marker:
                tactical = f"GPS Fix Locked: Sector Grid [{b.player_marker[0]}, {b.player_marker[1]}] | Trace roads, frontline bases & watchtower radar range"
            else:
                tactical = "Tactical Reconnaissance Active: Hex map open | Survey frontline base supply levels & partisan threats"
            return GoalHierarchy(
                goal=macro_goal,
                strategic_priority="Theater Reconnaissance: Surveying hex battle lines, logistics routes & base stockpiles",
                tactical_priority=tactical,
                revision_trigger=trigger
            )

        # 4. Mode: DEPLOY_MAP
        if b.mode == "DEPLOY_MAP" or b.is_deploy_map:
            return GoalHierarchy(
                goal=macro_goal,
                strategic_priority="Theater Reinforcement: Select deployment sector and spawn base on world map",
                tactical_priority="World Deployment Screen: Review regional casualty rates and select spawn point at Town Base or Relic Base",
                revision_trigger=trigger
            )

        # 5. Mode: SPECTATING
        if b.mode == "SPECTATING" or b.is_spectating:
            return GoalHierarchy(
                goal=macro_goal,
                strategic_priority="Casualty Observation: Monitoring allied combat engagements awaiting respawn wave",
                tactical_priority="Spectating Ally: Track enemy firing positions, defensive blindspots, and hostile movement while respawn timer elapses",
                revision_trigger=trigger
            )

        # 6. Mode: VEHICLE
        if b.mode == "VEHICLE" or b.in_vehicle:
            if b.has_shield:
                strat = "Armored Combat Operations: Vehicle armor integrity monitored | Support allied infantry push"
                tact = "In Armored Vehicle: Coordinate turret targeting, monitor track health, and maintain retreat corridor"
            else:
                strat = "Motorized Operations: Route navigation, vehicle maintenance & transport transit"
                tact = "Mounted in Vehicle: Monitor fuel level, maintain road speed, and watch for enemy roadblocks / mines"
            return GoalHierarchy(
                goal=macro_goal,
                strategic_priority=strat,
                tactical_priority=tact,
                revision_trigger=trigger
            )

        # 7. Mode: PEDESTRIAN (On Foot)
        stamina_desc = f"Stamina: {b.stamina_pct}% (Sprint Ready)" if b.stamina_pct > 60 else f"Stamina: {b.stamina_pct}% (Recovering)"
        radar_desc = "Local Minimap: Active" if b.has_minimap else "Radar: Offline"
        return GoalHierarchy(
            goal=macro_goal,
            strategic_priority="Field Operations: Infantry sector engagement, tactical positioning & squad coordination",
            tactical_priority=f"On Foot // {stamina_desc} | Posture: Mobile | {radar_desc} | Squad Comms: Monitored",
            revision_trigger=trigger
        )

    def evaluate_discrepancy(self) -> Optional[GoalHierarchy]:
        b = self.beliefs
        old = self.current_intentions
        new_hierarchy = self._build_intentions(trigger=f"Switched to {b.mode}")

        # Commit revision if state changed
        if (
            new_hierarchy.goal != old.goal or
            new_hierarchy.strategic_priority != old.strategic_priority or
            new_hierarchy.tactical_priority != old.tactical_priority
        ):
            self.current_intentions = new_hierarchy
            if self.metadata:
                self.metadata.record_goal_revision(
                    new_hierarchy.revision_trigger,
                    new_hierarchy.goal,
                    new_hierarchy.strategic_priority,
                    new_hierarchy.tactical_priority
                )
            return new_hierarchy

        return None

        return None
