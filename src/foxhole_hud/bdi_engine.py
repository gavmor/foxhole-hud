from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import time

@dataclass
class Beliefs:
    region: str = "Marban Hollow"
    subregion: str = "Maiden's Veil (Industrial Sector)"
    in_vehicle: bool = True
    vehicle_role: str = "Driver"
    is_bleeding: bool = False
    is_full_map: bool = False
    has_minimap: bool = True
    at_industrial_hub: bool = True
    fuel_deficit_known: bool = True
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
    Grounded in immediate surroundings: Maiden's Veil industrial hub,
    seaport fuel deficit, and Salt March resupply mandate.
    """
    def __init__(self, mcp_consultant=None, metadata_store=None):
        self.beliefs = Beliefs()
        self.mcp = mcp_consultant
        self.metadata = metadata_store
        self.current_intentions = GoalHierarchy(
            goal="Operation Cold Run: Salt March Relief & Resupply",
            strategic_priority="Unbrick Maiden's Veil Seaport Fuel (15x Diesel Run)",
            tactical_priority="Parked at Maiden's Veil: Refuel truck at Refinery & pull 15 Diesel cans",
            revision_trigger="Arrived at Maiden's Veil Hub"
        )

    def update_beliefs_from_cv(self, cv_state: Dict[str, Any], banner_text: str = ""):
        b = self.beliefs
        b.in_vehicle = cv_state.get("in_vehicle", True)
        b.is_bleeding = cv_state.get("is_bleeding", False)
        b.is_full_map = cv_state.get("is_full_map", False)
        b.has_minimap = cv_state.get("has_minimap", False)
        b.at_industrial_hub = cv_state.get("at_industrial_hub", False) or b.has_minimap

        b.last_update = time.time()
        return self.evaluate_discrepancy()

    def evaluate_discrepancy(self) -> Optional[GoalHierarchy]:
        b = self.beliefs
        old = self.current_intentions
        new_hierarchy = None

        # Priority 0: Immediate Survival
        if b.is_bleeding:
            new_hierarchy = GoalHierarchy(
                goal="Immediate Survival: Stop Hemorrhage",
                strategic_priority="Locate Medic or Scavenge Bandage from fallen kits",
                tactical_priority="EMERGENCY: Drop to cover (press C), call local medic in voice/chat",
                revision_trigger="Bleed Discrepancy"
            )

        # Priority 1: Full Map Reconnaissance ('M')
        elif b.is_full_map:
            new_hierarchy = GoalHierarchy(
                goal="Operational Reconnaissance: Marban Hollow & Deadlands Frontlines",
                strategic_priority="Scout Factory Queue Times and Seaport Stockpiles",
                tactical_priority="Map Open: Check Maiden's Veil factory load and route back to Salt March",
                revision_trigger="Full Map Discrepancy"
            )

        # Priority 2: At Maiden's Veil Industrial Hub / Refinery (Immediate Surroundings)
        elif b.at_industrial_hub:
            if b.in_vehicle:
                new_hierarchy = GoalHierarchy(
                    goal="Operation Cold Run: Salt March Relief & Resupply",
                    strategic_priority="Unbrick Maiden's Veil Seaport Fuel Reserves",
                    tactical_priority="Parked at Refinery / Scrap Pile: Pull 15 Diesel cans -> 10 to Seaport, 5 to Silo",
                    revision_trigger="At Refinery in Vehicle"
                )
            else:
                new_hierarchy = GoalHierarchy(
                    goal="Operation Cold Run: Salt March Relief & Resupply",
                    strategic_priority="Unbrick Maiden's Veil Seaport Fuel Reserves",
                    tactical_priority="Dismounted at Docks/Factory: Mount fueled Dunne -> Submit Diesel to Seaport",
                    revision_trigger="At Docks Dismounted"
                )

        # Commit revision
        if new_hierarchy and (
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
