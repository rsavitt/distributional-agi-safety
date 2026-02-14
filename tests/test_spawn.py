"""Tests for recursive subagent spawning."""

import pytest

from swarm.agents.base import Action, ActionType
from swarm.agents.honest import HonestAgent
from swarm.agents.opportunistic import OpportunisticAgent
from swarm.core.orchestrator import Orchestrator, OrchestratorConfig
from swarm.core.spawn import PayoffAttributionMode, SpawnConfig, SpawnTree
from swarm.metrics.spawn_metrics import SpawnMetricsCollector
from swarm.models.agent import AgentState, AgentType
from swarm.models.events import EventType

# =========================================================================
# SpawnConfig tests
# =========================================================================


class TestSpawnConfig:
    def test_defaults(self):
        cfg = SpawnConfig()
        assert cfg.enabled is False
        assert cfg.spawn_cost == 10.0
        assert cfg.max_depth == 3
        assert cfg.max_children == 3
        assert cfg.attribution_mode == PayoffAttributionMode.LEAF_ONLY

    def test_propagation_fraction_bounds(self):
        with pytest.raises(ValueError, match="propagation_fraction"):
            SpawnConfig(propagation_fraction=1.5)
        with pytest.raises(ValueError, match="propagation_fraction"):
            SpawnConfig(propagation_fraction=-0.1)

    def test_reputation_inheritance_bounds(self):
        with pytest.raises(ValueError, match="reputation_inheritance_factor"):
            SpawnConfig(reputation_inheritance_factor=2.0)

    def test_max_depth_nonneg(self):
        with pytest.raises(ValueError, match="max_depth"):
            SpawnConfig(max_depth=-1)


# =========================================================================
# SpawnTree tests
# =========================================================================


class TestSpawnTreeRegistration:
    def test_register_root(self):
        tree = SpawnTree(SpawnConfig(enabled=True))
        node = tree.register_root("agent_1")
        assert node.is_root is True
        assert node.depth == 0
        assert node.parent_id is None

    def test_can_spawn_disabled(self):
        tree = SpawnTree(SpawnConfig(enabled=False))
        tree.register_root("agent_1")
        ok, reason = tree.can_spawn("agent_1", 0, 100.0)
        assert ok is False
        assert reason == "spawn_disabled"

    def test_can_spawn_basic(self):
        tree = SpawnTree(SpawnConfig(enabled=True, spawn_cost=10.0))
        tree.register_root("parent")
        ok, reason = tree.can_spawn("parent", 0, 100.0)
        assert ok is True
        assert reason == "ok"

    def test_can_spawn_insufficient_resources(self):
        tree = SpawnTree(SpawnConfig(enabled=True, min_resources_to_spawn=50.0))
        tree.register_root("parent")
        ok, reason = tree.can_spawn("parent", 0, 30.0)
        assert ok is False
        assert reason == "insufficient_resources"

    def test_can_spawn_cannot_afford(self):
        tree = SpawnTree(
            SpawnConfig(enabled=True, spawn_cost=100.0, min_resources_to_spawn=10.0)
        )
        tree.register_root("parent")
        ok, reason = tree.can_spawn("parent", 0, 50.0)
        assert ok is False
        assert reason == "cannot_afford_spawn_cost"

    def test_can_spawn_max_depth(self):
        tree = SpawnTree(SpawnConfig(enabled=True, max_depth=1))
        tree.register_root("root")
        tree.register_spawn("root", "child1", 0, 0, 0)
        ok, reason = tree.can_spawn("child1", 10, 100.0)
        assert ok is False
        assert reason == "max_depth_reached"

    def test_can_spawn_max_children(self):
        tree = SpawnTree(
            SpawnConfig(enabled=True, max_children=2, spawn_cooldown_steps=0)
        )
        tree.register_root("root")
        tree.register_spawn("root", "c1", 0, 0, 0)
        tree.register_spawn("root", "c2", 0, 0, 1)
        ok, reason = tree.can_spawn("root", 10, 100.0)
        assert ok is False
        assert reason == "max_children_reached"

    def test_can_spawn_global_cap(self):
        tree = SpawnTree(
            SpawnConfig(enabled=True, max_total_spawned=1, spawn_cooldown_steps=0)
        )
        tree.register_root("root")
        tree.register_spawn("root", "c1", 0, 0, 0)
        ok, reason = tree.can_spawn("root", 10, 100.0)
        assert ok is False
        assert reason == "global_cap_reached"

    def test_can_spawn_cooldown(self):
        tree = SpawnTree(SpawnConfig(enabled=True, spawn_cooldown_steps=5))
        tree.register_root("root")
        tree.register_spawn("root", "c1", 0, 0, 10)
        # Global step 12 is within cooldown (5 steps since last spawn at 10)
        ok, reason = tree.can_spawn("root", 12, 100.0)
        assert ok is False
        assert reason == "cooldown_active"
        # Step 15 is ok (5 steps since 10)
        ok, reason = tree.can_spawn("root", 15, 100.0)
        assert ok is True

    def test_can_spawn_banned(self):
        tree = SpawnTree(SpawnConfig(enabled=True))
        tree.register_root("root")
        tree.cascade_ban("root")
        ok, reason = tree.can_spawn("root", 0, 100.0)
        assert ok is False
        assert reason == "parent_banned"

    def test_register_spawn(self):
        tree = SpawnTree(SpawnConfig(enabled=True))
        tree.register_root("parent")
        child = tree.register_spawn("parent", "child_1", 0, 0, 0)
        assert child.depth == 1
        assert child.parent_id == "parent"
        assert child.is_root is False
        assert "child_1" in tree.get_children("parent")
        assert tree.total_spawned == 1


class TestSpawnTreeLineage:
    def _build_tree(self) -> SpawnTree:
        """Build a 3-level tree: root -> A -> B."""
        tree = SpawnTree(SpawnConfig(enabled=True, spawn_cooldown_steps=0))
        tree.register_root("root")
        tree.register_spawn("root", "A", 0, 0, 0)
        tree.register_spawn("A", "B", 0, 0, 1)
        return tree

    def test_get_depth(self):
        tree = self._build_tree()
        assert tree.get_depth("root") == 0
        assert tree.get_depth("A") == 1
        assert tree.get_depth("B") == 2

    def test_get_parent(self):
        tree = self._build_tree()
        assert tree.get_parent("root") is None
        assert tree.get_parent("A") == "root"
        assert tree.get_parent("B") == "A"

    def test_get_children(self):
        tree = self._build_tree()
        assert tree.get_children("root") == ["A"]
        assert tree.get_children("A") == ["B"]
        assert tree.get_children("B") == []

    def test_get_root(self):
        tree = self._build_tree()
        assert tree.get_root("B") == "root"
        assert tree.get_root("A") == "root"
        assert tree.get_root("root") == "root"

    def test_get_ancestors(self):
        tree = self._build_tree()
        assert tree.get_ancestors("B") == ["A", "root"]
        assert tree.get_ancestors("A") == ["root"]
        assert tree.get_ancestors("root") == []

    def test_get_descendants(self):
        tree = self._build_tree()
        assert tree.get_descendants("root") == ["A", "B"]
        assert tree.get_descendants("A") == ["B"]
        assert tree.get_descendants("B") == []

    def test_get_subtree(self):
        tree = self._build_tree()
        assert tree.get_subtree("root") == ["root", "A", "B"]
        assert tree.get_subtree("A") == ["A", "B"]

    def test_is_descendant_of(self):
        tree = self._build_tree()
        assert tree.is_descendant_of("B", "root") is True
        assert tree.is_descendant_of("B", "A") is True
        assert tree.is_descendant_of("A", "B") is False
        assert tree.is_descendant_of("root", "A") is False


class TestSpawnTreeCascade:
    def test_cascade_ban(self):
        tree = SpawnTree(SpawnConfig(enabled=True, cascade_ban=True, spawn_cooldown_steps=0))
        tree.register_root("root")
        tree.register_spawn("root", "A", 0, 0, 0)
        tree.register_spawn("A", "B", 0, 0, 1)

        banned = tree.cascade_ban("A")
        assert set(banned) == {"A", "B"}
        assert tree._nodes["A"].is_banned is True
        assert tree._nodes["B"].is_banned is True
        assert tree._nodes["root"].is_banned is False

    def test_cascade_ban_disabled(self):
        tree = SpawnTree(SpawnConfig(enabled=True, cascade_ban=False, spawn_cooldown_steps=0))
        tree.register_root("root")
        tree.register_spawn("root", "A", 0, 0, 0)
        tree.register_spawn("A", "B", 0, 0, 1)

        banned = tree.cascade_ban("A")
        assert banned == ["A"]
        assert tree._nodes["B"].is_banned is False

    def test_cascade_freeze_ids(self):
        tree = SpawnTree(SpawnConfig(enabled=True, cascade_freeze=True, spawn_cooldown_steps=0))
        tree.register_root("root")
        tree.register_spawn("root", "A", 0, 0, 0)
        tree.register_spawn("A", "B", 0, 0, 1)

        frozen = tree.cascade_freeze_ids("A")
        assert set(frozen) == {"A", "B"}

    def test_cascade_freeze_disabled(self):
        tree = SpawnTree(SpawnConfig(enabled=True, cascade_freeze=False))
        tree.register_root("root")
        tree.register_spawn("root", "A", 0, 0, 0)

        frozen = tree.cascade_freeze_ids("A")
        assert frozen == ["A"]


# =========================================================================
# Attribution tests
# =========================================================================


class TestSpawnAttribution:
    def test_leaf_only(self):
        tree = SpawnTree(
            SpawnConfig(
                enabled=True,
                attribution_mode=PayoffAttributionMode.LEAF_ONLY,
                spawn_cooldown_steps=0,
            )
        )
        tree.register_root("root")
        tree.register_spawn("root", "child", 0, 0, 0)

        shares = tree.compute_attribution("child", 100.0)
        assert shares == {"child": 100.0}

    def test_root_absorbs(self):
        tree = SpawnTree(
            SpawnConfig(
                enabled=True,
                attribution_mode=PayoffAttributionMode.ROOT_ABSORBS,
                spawn_cooldown_steps=0,
            )
        )
        tree.register_root("root")
        tree.register_spawn("root", "child", 0, 0, 0)

        shares = tree.compute_attribution("child", 100.0)
        assert shares == {"root": 100.0}

    def test_root_absorbs_root_agent(self):
        tree = SpawnTree(
            SpawnConfig(
                enabled=True,
                attribution_mode=PayoffAttributionMode.ROOT_ABSORBS,
            )
        )
        tree.register_root("root")
        shares = tree.compute_attribution("root", 100.0)
        assert shares == {"root": 100.0}

    def test_propagate_up_conservation(self):
        tree = SpawnTree(
            SpawnConfig(
                enabled=True,
                attribution_mode=PayoffAttributionMode.PROPAGATE_UP,
                propagation_fraction=0.3,
                spawn_cooldown_steps=0,
            )
        )
        tree.register_root("root")
        tree.register_spawn("root", "A", 0, 0, 0)
        tree.register_spawn("A", "B", 0, 0, 1)

        raw = 100.0
        shares = tree.compute_attribution("B", raw)

        # Sum of shares should equal raw payoff (conservation)
        total = sum(shares.values())
        assert abs(total - raw) < 1e-9, f"Conservation violated: {total} != {raw}"

    def test_propagate_up_two_levels(self):
        tree = SpawnTree(
            SpawnConfig(
                enabled=True,
                attribution_mode=PayoffAttributionMode.PROPAGATE_UP,
                propagation_fraction=0.3,
                spawn_cooldown_steps=0,
            )
        )
        tree.register_root("root")
        tree.register_spawn("root", "child", 0, 0, 0)

        shares = tree.compute_attribution("child", 100.0)
        # child keeps (1 - 0.3) * 100 = 70
        assert abs(shares["child"] - 70.0) < 1e-9
        # root gets remainder = 30
        assert abs(shares["root"] - 30.0) < 1e-9

    def test_propagate_up_root_gets_all_for_root(self):
        tree = SpawnTree(
            SpawnConfig(
                enabled=True,
                attribution_mode=PayoffAttributionMode.PROPAGATE_UP,
                propagation_fraction=0.3,
            )
        )
        tree.register_root("root")
        shares = tree.compute_attribution("root", 100.0)
        # Root has no ancestors, so gets everything
        assert shares == {"root": 100.0}


# =========================================================================
# Observation noise
# =========================================================================


class TestSpawnNoise:
    def test_noise_increases_with_depth(self):
        tree = SpawnTree(
            SpawnConfig(enabled=True, depth_noise_per_level=0.1, spawn_cooldown_steps=0)
        )
        tree.register_root("root")
        tree.register_spawn("root", "child", 0, 0, 0)

        assert tree.observation_noise_std("root") == 0.0
        assert abs(tree.observation_noise_std("child") - 0.1) < 1e-9


# =========================================================================
# Metrics helpers
# =========================================================================


class TestSpawnMetricsHelpers:
    def test_total_spawned(self):
        tree = SpawnTree(SpawnConfig(enabled=True, spawn_cooldown_steps=0))
        tree.register_root("root")
        assert tree.total_spawned == 0
        tree.register_spawn("root", "c1", 0, 0, 0)
        assert tree.total_spawned == 1

    def test_max_tree_depth(self):
        tree = SpawnTree(SpawnConfig(enabled=True, spawn_cooldown_steps=0))
        tree.register_root("root")
        assert tree.max_tree_depth() == 0
        tree.register_spawn("root", "c1", 0, 0, 0)
        assert tree.max_tree_depth() == 1

    def test_depth_distribution(self):
        tree = SpawnTree(SpawnConfig(enabled=True, spawn_cooldown_steps=0))
        tree.register_root("r1")
        tree.register_root("r2")
        tree.register_spawn("r1", "c1", 0, 0, 0)
        dist = tree.depth_distribution()
        assert dist == {0: 2, 1: 1}

    def test_tree_size_distribution(self):
        tree = SpawnTree(SpawnConfig(enabled=True, spawn_cooldown_steps=0))
        tree.register_root("r1")
        tree.register_root("r2")
        tree.register_spawn("r1", "c1", 0, 0, 0)
        sizes = tree.tree_size_distribution()
        assert sizes["r1"] == 2
        assert sizes["r2"] == 1


# =========================================================================
# SpawnMetricsCollector tests
# =========================================================================


class TestSpawnMetricsCollector:
    def test_collect_empty(self):
        collector = SpawnMetricsCollector()
        metrics = collector.collect(None)
        assert metrics.total_spawned == 0

    def test_collect_with_tree(self):
        tree = SpawnTree(SpawnConfig(enabled=True, spawn_cooldown_steps=0))
        tree.register_root("root")
        tree.register_spawn("root", "c1", 0, 0, 0)

        collector = SpawnMetricsCollector()
        collector.record_spawn(1)
        collector.record_payoff(0, 10.0)
        collector.record_payoff(1, 5.0)
        collector.record_redistribution(3.0)

        metrics = collector.collect(tree)
        assert metrics.total_spawned == 1
        assert metrics.spawns_this_epoch == 1
        assert metrics.max_depth == 1
        assert abs(metrics.avg_payoff_by_depth[0] - 10.0) < 1e-9
        assert abs(metrics.avg_payoff_by_depth[1] - 5.0) < 1e-9
        assert abs(metrics.total_payoff_redistributed - 3.0) < 1e-9

    def test_reset_epoch(self):
        collector = SpawnMetricsCollector()
        collector.record_spawn(0)
        collector.reset_epoch()
        metrics = collector.collect(None)
        assert metrics.spawns_this_epoch == 0


# =========================================================================
# AgentState.parent_id tests
# =========================================================================


class TestAgentStateParentId:
    def test_default_none(self):
        state = AgentState(agent_id="a1")
        assert state.parent_id is None

    def test_set_parent_id(self):
        state = AgentState(agent_id="child", parent_id="parent")
        assert state.parent_id == "parent"

    def test_to_dict_includes_parent_id(self):
        state = AgentState(agent_id="child", parent_id="parent")
        d = state.to_dict()
        assert d["parent_id"] == "parent"

    def test_from_dict_includes_parent_id(self):
        d = AgentState(agent_id="child", parent_id="parent").to_dict()
        restored = AgentState.from_dict(d)
        assert restored.parent_id == "parent"

    def test_from_dict_missing_parent_id(self):
        d = AgentState(agent_id="a1").to_dict()
        del d["parent_id"]
        restored = AgentState.from_dict(d)
        assert restored.parent_id is None


# =========================================================================
# ActionType tests
# =========================================================================


class TestActionTypeSpawn:
    def test_spawn_subagent_exists(self):
        assert ActionType.SPAWN_SUBAGENT.value == "spawn_subagent"


# =========================================================================
# EventType tests
# =========================================================================


class TestEventTypeSpawn:
    def test_agent_spawned_exists(self):
        assert EventType.AGENT_SPAWNED.value == "agent_spawned"

    def test_spawn_rejected_exists(self):
        assert EventType.SPAWN_REJECTED.value == "spawn_rejected"


# =========================================================================
# Orchestrator integration tests
# =========================================================================


class TestOrchestratorSpawnIntegration:
    def _make_orchestrator(self, **spawn_overrides) -> Orchestrator:
        spawn_kwargs = {
            "enabled": True,
            "spawn_cost": 10.0,
            "max_depth": 3,
            "max_children": 3,
            "max_total_spawned": 50,
            "min_resources_to_spawn": 20.0,
            "spawn_cooldown_steps": 0,
        }
        spawn_kwargs.update(spawn_overrides)
        cfg = OrchestratorConfig(
            n_epochs=1,
            steps_per_epoch=5,
            seed=42,
            spawn_config=SpawnConfig(**spawn_kwargs),
        )
        return Orchestrator(config=cfg)

    def test_spawn_tree_initialized(self):
        orch = self._make_orchestrator()
        assert orch.get_spawn_tree() is not None

    def test_spawn_tree_none_when_disabled(self):
        cfg = OrchestratorConfig(n_epochs=1, steps_per_epoch=1)
        orch = Orchestrator(config=cfg)
        assert orch.get_spawn_tree() is None

    def test_register_agent_adds_root(self):
        orch = self._make_orchestrator()
        agent = HonestAgent(agent_id="h1")
        orch.register_agent(agent)
        tree = orch.get_spawn_tree()
        node = tree.get_node("h1")
        assert node is not None
        assert node.is_root is True

    def test_handle_spawn_subagent(self):
        orch = self._make_orchestrator()
        agent = HonestAgent(agent_id="parent")
        orch.register_agent(agent)

        action = Action(
            action_type=ActionType.SPAWN_SUBAGENT,
            agent_id="parent",
            metadata={"child_type": "honest", "child_config": {}},
        )
        result = orch._handle_spawn_subagent(action)
        assert result is True

        tree = orch.get_spawn_tree()
        children = tree.get_children("parent")
        assert len(children) == 1
        child_id = children[0]

        # Verify child is registered
        child_agent = orch.get_agent(child_id)
        assert child_agent is not None

        # Verify child state
        child_state = orch.state.get_agent(child_id)
        assert child_state is not None
        assert child_state.parent_id == "parent"

        # Verify parent resources deducted
        parent_state = orch.state.get_agent("parent")
        assert parent_state.resources == 100.0 - 10.0  # spawn_cost

    def test_spawn_rejected_insufficient_resources(self):
        orch = self._make_orchestrator(min_resources_to_spawn=200.0)
        agent = HonestAgent(agent_id="poor")
        orch.register_agent(agent)

        action = Action(
            action_type=ActionType.SPAWN_SUBAGENT,
            agent_id="poor",
            metadata={"child_type": "honest"},
        )
        result = orch._handle_spawn_subagent(action)
        assert result is False

    def test_spawn_inherits_reputation(self):
        orch = self._make_orchestrator()
        agent = HonestAgent(agent_id="parent")
        parent_state = orch.register_agent(agent)
        parent_state.reputation = 10.0

        action = Action(
            action_type=ActionType.SPAWN_SUBAGENT,
            agent_id="parent",
            metadata={"child_type": "honest"},
        )
        orch._handle_spawn_subagent(action)

        tree = orch.get_spawn_tree()
        child_id = tree.get_children("parent")[0]
        child_state = orch.state.get_agent(child_id)
        # reputation_inheritance_factor defaults to 0.5
        assert abs(child_state.reputation - 5.0) < 1e-9

    def test_spawn_defaults_to_parent_type(self):
        orch = self._make_orchestrator()
        agent = OpportunisticAgent(agent_id="opp")
        orch.register_agent(agent)

        action = Action(
            action_type=ActionType.SPAWN_SUBAGENT,
            agent_id="opp",
            metadata={},  # No child_type specified
        )
        orch._handle_spawn_subagent(action)

        tree = orch.get_spawn_tree()
        child_id = tree.get_children("opp")[0]
        child_agent = orch.get_agent(child_id)
        assert child_agent.agent_type == AgentType.OPPORTUNISTIC

    def test_spawn_unknown_type_rejected(self):
        orch = self._make_orchestrator()
        agent = HonestAgent(agent_id="parent")
        orch.register_agent(agent)

        action = Action(
            action_type=ActionType.SPAWN_SUBAGENT,
            agent_id="parent",
            metadata={"child_type": "nonexistent_type"},
        )
        result = orch._handle_spawn_subagent(action)
        assert result is False

    def test_spawn_metrics_in_epoch(self):
        orch = self._make_orchestrator()
        agent = HonestAgent(agent_id="h1")
        orch.register_agent(agent)

        # Manually trigger a spawn
        action = Action(
            action_type=ActionType.SPAWN_SUBAGENT,
            agent_id="h1",
            metadata={"child_type": "honest"},
        )
        orch._handle_spawn_subagent(action)

        metrics = orch._compute_epoch_metrics()
        assert metrics.spawn_metrics is not None
        assert metrics.spawn_metrics["total_spawned"] == 1


# =========================================================================
# Observation spawn fields
# =========================================================================


class TestObservationSpawnFields:
    def test_spawn_fields_populated(self):
        cfg = OrchestratorConfig(
            n_epochs=1,
            steps_per_epoch=5,
            seed=42,
            spawn_config=SpawnConfig(
                enabled=True,
                spawn_cooldown_steps=0,
            ),
        )
        orch = Orchestrator(config=cfg)
        agent = HonestAgent(agent_id="h1")
        orch.register_agent(agent)

        obs = orch._build_observation("h1")
        assert obs.spawn_depth == 0
        assert obs.spawn_children_count == 0
        assert obs.can_spawn is True  # root with enough resources

    def test_spawn_fields_default_when_no_tree(self):
        cfg = OrchestratorConfig(n_epochs=1, steps_per_epoch=1)
        orch = Orchestrator(config=cfg)
        agent = HonestAgent(agent_id="h1")
        orch.register_agent(agent)

        obs = orch._build_observation("h1")
        assert obs.can_spawn is False
        assert obs.spawn_depth == 0
        assert obs.spawn_children_count == 0


# =========================================================================
# Scenario loader integration
# =========================================================================


class TestScenarioLoaderSpawn:
    def test_parse_spawn_config(self):
        from swarm.scenarios.loader import parse_spawn_config

        data = {
            "enabled": True,
            "spawn_cost": 15.0,
            "max_depth": 2,
            "attribution_mode": "propagate_up",
        }
        cfg = parse_spawn_config(data)
        assert cfg is not None
        assert cfg.enabled is True
        assert cfg.spawn_cost == 15.0
        assert cfg.max_depth == 2
        assert cfg.attribution_mode == PayoffAttributionMode.PROPAGATE_UP

    def test_parse_spawn_config_empty(self):
        from swarm.scenarios.loader import parse_spawn_config

        assert parse_spawn_config({}) is None

    def test_parse_spawn_config_disabled(self):
        from swarm.scenarios.loader import parse_spawn_config

        assert parse_spawn_config({"enabled": False}) is None

    def test_parse_spawn_config_bad_mode(self):
        from swarm.scenarios.loader import parse_spawn_config

        with pytest.raises(ValueError, match="Unknown attribution mode"):
            parse_spawn_config({"enabled": True, "attribution_mode": "bogus"})

    def test_load_scenario_with_spawn(self, tmp_path):
        from swarm.scenarios.loader import load_scenario

        yaml_content = """
scenario_id: test_spawn
agents:
  - type: honest
    count: 2
spawn:
  enabled: true
  spawn_cost: 5.0
  max_depth: 2
  attribution_mode: leaf_only
simulation:
  n_epochs: 1
  steps_per_epoch: 1
"""
        p = tmp_path / "test.yaml"
        p.write_text(yaml_content)

        scenario = load_scenario(p)
        assert scenario.orchestrator_config.spawn_config is not None
        assert scenario.orchestrator_config.spawn_config.enabled is True
        assert scenario.orchestrator_config.spawn_config.spawn_cost == 5.0


# =========================================================================
# BaseAgent.create_spawn_subagent_action
# =========================================================================


class TestCreateSpawnAction:
    def test_create_spawn_action(self):
        agent = HonestAgent(agent_id="h1")
        action = agent.create_spawn_subagent_action(child_type="honest")
        assert action.action_type == ActionType.SPAWN_SUBAGENT
        assert action.agent_id == "h1"
        assert action.metadata["child_type"] == "honest"

    def test_create_spawn_action_defaults(self):
        agent = HonestAgent(agent_id="h1")
        action = agent.create_spawn_subagent_action()
        assert action.metadata["child_type"] is None
        assert action.metadata["child_config"] == {}
