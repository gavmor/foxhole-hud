from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import time

@dataclass
class Beliefs:
    region: str = "Marban Hollow"
    subregion: str = "Maiden's Veil (Industrial Sector)"
    mode: str = "PEDESTRIAN"
    in_vehicle: bool = False
    vehicle_role: str = "Driver"
    is_bleeding: bool = False
    is_spectating: bool = False
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
    Instant arbitration across: SPECTATING, DEPLOY_MAP, MAP, VEHICLE, PEDESTRIAN.
    """
    def __init__(self, mcp_consultant=None, metadata_store=None):
        self.beliefs = Beliefs()
        self.mcp = mcp_consultant
        self.metadata = metadata_store
        self.current_intentions = GoalHierarchy(
            goal="Operation Cold Run: Marban Hollow Logistics Relief (Salt March)",
            strategic_priority="Resolve Seaport Fuel Crisis (0 Diesel in Seaport Pool)",
            tactical_priority="On Foot at Seaport: Dunnes empty. Sprint to Refinery (East) -> pull 15x Diesel to fuel fleet",
            revision_trigger="Initial Beliefs Grounded"
        )

    def update_beliefs_from_cv(self, cv_state: Dict[str, Any], banner_text: str = ""):
        b = self.beliefs
        b.mode = cv_state.get("mode", "PEDESTRIAN")
        b.in_vehicle = cv_state.get("in_vehicle", (b.mode == "VEHICLE"))
        b.is_spectating = cv_state.get("is_spectating", (b.mode == "SPECTATING"))
        b.is_bleeding = cv_state.get("is_bleeding", False)
        b.is_full_map = cv_state.get("is_full_map", (b.mode == "MAP"))
        b.has_minimap = cv_state.get("has_minimap", False)
        b.at_industrial_hub = cv_state.get("at_industrial_hub", False) or b.has_minimap
        if "subregion" in cv_state:
            b.subregion = cv_state["subregion"]

        b.last_update = time.time()
        return self.evaluate_discrepancy()

    def evaluate_discrepancy(self) -> Optional[GoalHierarchy]:
        b = self.beliefs
        old = self.current_intentions
        new_hierarchy = None

        # Priority 0: Immediate Survival (Bleeding)
        if b.is_bleeding:
            new_hierarchy = GoalHierarchy(
                goal="Immediate Survival: Stop Hemorrhage",
                strategic_priority="Locate Medic or Scavenge Bandage from fallen kits",
                tactical_priority="EMERGENCY: Drop to cover (press C), call local medic in voice/chat",
                revision_trigger="Bleed Discrepancy"
            )

        # Mode 1: SPECTATING (Observing Ally while awaiting respawn)
        elif b.mode == "SPECTATING" or b.is_spectating:
            new_hierarchy = GoalHierarchy(
                goal="Operation Cold Run: Theater Combat Observation & Respawn",
                strategic_priority="Await Respawn Wave or Teammate Reinforcement",
                tactical_priority="Spectating Ally: Observe enemy positions, defensive blindspots, and partisan activity while respawn timer elapses",
                revision_trigger="Switched to SPECTATING"
            )

        # Mode 2: DEPLOY_MAP (Conquest / World Respawn Screen)
        elif b.mode == "DEPLOY_MAP":
            new_hierarchy = GoalHierarchy(
                goal="Operation Cold Run: Theater Deployment Selection",
                strategic_priority="Select Deployment Base: Marban Hollow (Maiden's Veil Keep / Seaport)",
                tactical_priority="Deploy Map Open: Click Marban Hollow -> spawn at Maiden's Veil Town Base to resume Seaport fuel supply",
                revision_trigger="Switched to DEPLOY_MAP"
            )

        # Mode 2: MAP ('M' key tactical map)
        elif b.mode == "MAP" or b.is_full_map:
            new_hierarchy = GoalHierarchy(
                goal="Operational Reconnaissance: Marban Hollow & Deadlands Frontlines",
                strategic_priority="Survey Hex Logistics Routes: Maiden's Veil -> Spitrocks -> Salt March",
                tactical_priority="Map Recon Open: Check road watchtowers, enemy partisans, and factory queue times",
                revision_trigger="Switched to MAP"
            )

        # Mode 3: VEHICLE (Mounted in truck/transport)
        elif b.mode == "VEHICLE" or b.in_vehicle:
            if "Seaport" in b.subregion or "Docks" in b.subregion:
                new_hierarchy = GoalHierarchy(
                    goal="Operation Cold Run: Marban Hollow Logistics Relief (Salt March)",
                    strategic_priority="Resolve Seaport Fuel Crisis (0 Diesel in Seaport Pool)",
                    tactical_priority="In Dunne at Seaport: Drive to Refinery (East) -> fill fuel tank & load 15x Diesel cans for Seaport",
                    revision_trigger="Switched to VEHICLE at Seaport"
                )
            elif "Refinery" in b.subregion or "Industrial" in b.subregion:
                new_hierarchy = GoalHierarchy(
                    goal="Operation Cold Run: Marban Hollow Logistics Relief (Salt March)",
                    strategic_priority="Resolve Seaport Fuel Crisis (Refinery Haul)",
                    tactical_priority="At Refinery in Dunne: Fill vehicle fuel tank -> load 15x Diesel cans to transport to Seaport",
                    revision_trigger="Switched to VEHICLE at Refinery"
                )
            else:
                new_hierarchy = GoalHierarchy(
                    goal="Operation Cold Run: Marban Hollow Logistics Relief (Salt March)",
                    strategic_priority="Resolve Seaport Fuel Crisis (0 Diesel in Seaport Pool)",
                    tactical_priority="In Dunne Transport: Route along main road to delivery point -> watch for partisans",
                    revision_trigger="Switched to VEHICLE"
                )

        # Mode 4: PEDESTRIAN (On foot)
        else:
            if "Seaport" in b.subregion or "Docks" in b.subregion:
                new_hierarchy = GoalHierarchy(
                    goal="Operation Cold Run: Marban Hollow Logistics Relief (Salt March)",
                    strategic_priority="Resolve Seaport Fuel Crisis (0 Diesel in Seaport Pool)",
                    tactical_priority="On Foot at Seaport: Dunnes empty. Sprint to Refinery (East) -> pull 15x Diesel to fuel fleet",
                    revision_trigger="Switched to PEDESTRIAN at Seaport"
                )
            elif "Refinery" in b.subregion or "Industrial" in b.subregion:
                new_hierarchy = GoalHierarchy(
                    goal="Operation Cold Run: Marban Hollow Logistics Relief (Salt March)",
                    strategic_priority="Resolve Seaport Fuel Crisis (Refinery Haul)",
                    tactical_priority="At Refinery on Foot: Pull 15x Diesel cans from public stockpile -> load into Dunne truck",
                    revision_trigger="Switched to PEDESTRIAN at Refinery"
                )
            elif "Factory" in b.subregion:
                new_hierarchy = GoalHierarchy(
                    goal="Operation Cold Run: Marban Hollow Logistics Relief (Salt March)",
                    strategic_priority="Manufacture Munitions & Medical Supplies for Salt March",
                    tactical_priority="At Factory: Queue Small Arms (7.62mm) & Soldier Supplies crates for frontlines",
                    revision_trigger="Switched to PEDESTRIAN at Factory"
                )
            else:
                new_hierarchy = GoalHierarchy(
                    goal="Operation Cold Run: Marban Hollow Logistics Relief (Salt March)",
                    strategic_priority="Resolve Seaport Fuel Crisis (0 Diesel in Seaport Pool)",
                    tactical_priority=f"On Foot at {b.subregion}: Acquire Diesel fuel -> unbrick Seaport logistics Dunnes",
                    revision_trigger="Switched to PEDESTRIAN"
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
