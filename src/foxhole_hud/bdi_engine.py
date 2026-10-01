from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import time

@dataclass
class Beliefs:
    """Current grounded world model from CV perception and MCP facts."""
    region: str = "Deadlands"
    subregion: str = "The Salt March"
    in_vehicle: bool = False
    vehicle_role: str = "Driver"
    is_bleeding: bool = False
    is_map_open: bool = False
    is_queue: bool = False
    at_seaport: bool = False
    at_shipyard: bool = False
    at_stockpile: bool = False
    fuel_deficit_known: bool = True
    last_update: float = field(default_factory=time.time)

@dataclass
class GoalHierarchy:
    """The 3-tier intention stack: Goal > Strategic Priority > Tactical Priority."""
    goal: str
    strategic_priority: str
    tactical_priority: str
    confidence: float = 1.0
    revision_trigger: str = "Initial"
    timestamp: float = field(default_factory=time.time)

class BDIGoalArbiter:
    """
    Belief-Desire-Intention (BDI) and Goal-Driven Autonomy (GDA) Engine.
    Evaluates continuous perceptual discrepancies, consults domain facts (MCP),
    and arbitrates changing goal pursuit.
    """
    def __init__(self, mcp_consultant=None, metadata_store=None):
        self.beliefs = Beliefs()
        self.mcp = mcp_consultant
        self.metadata = metadata_store
        self.current_intentions = GoalHierarchy(
            goal="Operation Cold Run: Relieve & Fortify Salt March Base",
            strategic_priority="Acquire 15 Cans of Diesel to Unbrick Maiden's Veil Seaport",
            tactical_priority="At Shipyard: Check local fuel -> Procure Dunne Transport",
            revision_trigger="Bootstrap"
        )
        self.is_thinking = False

    def update_beliefs_from_cv(self, cv_state: Dict[str, Any], banner_text: str = ""):
        b = self.beliefs
        b.in_vehicle = cv_state.get("in_vehicle", False)
        b.is_bleeding = cv_state.get("is_bleeding", False)
        b.is_map_open = cv_state.get("is_map", False)
        
        if banner_text:
            if "Fort Viper" in banner_text or "Afric" in banner_text:
                b.region = "Marban Hollow"
                b.subregion = "Fort Viper : Afric's Approach"
            elif "Salt March" in banner_text:
                b.region = "Deadlands"
                b.subregion = "The Salt March"
            elif "Maiden" in banner_text:
                b.region = "Marban Hollow"
                b.subregion = "Maiden's Veil"

        b.last_update = time.time()
        return self.evaluate_discrepancy()

    def evaluate_discrepancy(self) -> Optional[GoalHierarchy]:
        """
        GDA Discrepancy Monitor:
        Detects divergence between reality and current intention stack.
        """
        b = self.beliefs
        old = self.current_intentions
        new_hierarchy = None

        # Priority 0: Immediate Survival (Bleeding)
        if b.is_bleeding:
            new_hierarchy = GoalHierarchy(
                goal="Immediate Survival: Stop Hemorrhage",
                strategic_priority="Locate Medic or Scavenge Bandage from fallen kits",
                tactical_priority="EMERGENCY: Drop to cover, press C to crouch/prone, call local medic",
                revision_trigger="Bleed Discrepancy"
            )

        # Priority 1: Map Scouting Active
        elif b.is_map_open:
            new_hierarchy = GoalHierarchy(
                goal="Operational Reconnaissance: Hex Logistics & Frontline Intel",
                strategic_priority="Identify Nearest Active Refinery and Public Diesel Depot",
                tactical_priority="Map Open: Check Maiden's Veil & Oster Wall for factory queues",
                revision_trigger="Map Open Discrepancy"
            )

        # Priority 2: In Marban Hollow -> Resolving Fuel / Transport Deficit
        elif b.region == "Marban Hollow":
            if b.in_vehicle:
                new_hierarchy = GoalHierarchy(
                    goal="Operation Cold Run: Salt March Relief & Resupply",
                    strategic_priority="Ferry 15 Cans of Diesel from Refinery to Maiden's Veil Seaport",
                    tactical_priority=f"In Vehicle ({b.subregion}): Route along primary road to Maiden's Veil Refinery",
                    revision_trigger="Mounted Transit to Hub"
                )
            else:
                new_hierarchy = GoalHierarchy(
                    goal="Operation Cold Run: Salt March Relief & Resupply",
                    strategic_priority="Unbrick Regional Logistics: Seed Seaport with 15x Diesel",
                    tactical_priority="On Foot at Port: Mount friendly Dunne Transport or Wrench abandoned truck",
                    revision_trigger="Dismounted at Port"
                )

        # Priority 3: In Deadlands -> Frontline Lockdown
        elif b.region == "Deadlands":
            new_hierarchy = GoalHierarchy(
                goal="Defend Salt March Relic Base & Eastern Deadlands Flank",
                strategic_priority="Establish Watchtower Radar Perimeter & Stockpile Supplies",
                tactical_priority="Hold SW River Mercy Bridgehead against Colonial push from Sunken Coup",
                revision_trigger="Deadlands Sector Active"
            )

        # Commit revision if changed
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
