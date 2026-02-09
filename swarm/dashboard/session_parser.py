"""Discovers and parses simulation sessions from runs/ and logs/ directories."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


def discover_sessions(base_dir: Path) -> List[Dict[str, Any]]:
    """Discover simulation sessions from runs/ and logs/ directories.

    Scans for:
    - runs/<name>/history.json  (exported JSON histories)
    - logs/*.jsonl              (event log files)
    - logs/*.json               (exported JSON files)

    Returns list of session metadata dicts (lightweight, no full parse).
    """
    sessions: List[Dict[str, Any]] = []

    # Scan runs/ directory for history.json files
    runs_dir = base_dir / "runs"
    if runs_dir.is_dir():
        for run_dir in sorted(runs_dir.iterdir()):
            if not run_dir.is_dir():
                continue
            history_file = run_dir / "history.json"
            if history_file.exists():
                meta = _extract_json_metadata(history_file)
                if meta:
                    meta["source"] = "runs"
                    meta["path"] = str(history_file)
                    meta["run_dir"] = str(run_dir)
                    sessions.append(meta)

    # Scan logs/ directory for JSONL event logs and JSON exports
    logs_dir = base_dir / "logs"
    if logs_dir.is_dir():
        for f in sorted(logs_dir.iterdir()):
            if f.suffix == ".jsonl":
                meta = _extract_jsonl_metadata(f)
                if meta:
                    meta["source"] = "logs"
                    meta["path"] = str(f)
                    sessions.append(meta)
            elif f.suffix == ".json":
                meta = _extract_json_metadata(f)
                if meta:
                    meta["source"] = "logs"
                    meta["path"] = str(f)
                    sessions.append(meta)

    return sessions


def parse_session(path: str) -> Dict[str, Any]:
    """Fully parse a session file and return structured data for the dashboard.

    Handles both JSON history files and JSONL event logs.
    """
    p = Path(path)
    if p.suffix == ".json":
        return _parse_json_session(p)
    elif p.suffix == ".jsonl":
        return _parse_jsonl_session(p)
    return {"error": f"Unsupported file type: {p.suffix}"}


def _extract_json_metadata(path: Path) -> Optional[Dict[str, Any]]:
    """Extract lightweight metadata from a JSON history file."""
    try:
        with open(path) as f:
            data = json.load(f)
        return {
            "session_id": data.get("simulation_id", path.stem),
            "n_epochs": data.get("n_epochs", 0),
            "n_agents": data.get("n_agents", 0),
            "seed": data.get("seed"),
            "started_at": data.get("started_at"),
            "ended_at": data.get("ended_at"),
            "file_type": "json",
        }
    except (json.JSONDecodeError, OSError):
        return None


def _extract_jsonl_metadata(path: Path) -> Optional[Dict[str, Any]]:
    """Extract lightweight metadata from a JSONL event log (first/last lines)."""
    try:
        first_event = None
        last_event = None
        event_count = 0
        agent_ids: set = set()
        scenario_id = None

        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                event = json.loads(line)
                event_count += 1
                if first_event is None:
                    first_event = event
                last_event = event

                # Collect agent IDs
                for key in ("agent_id", "initiator_id", "counterparty_id"):
                    aid = event.get(key)
                    if aid:
                        agent_ids.add(aid)

                if event.get("scenario_id"):
                    scenario_id = event["scenario_id"]

        if first_event is None:
            return None

        # Derive epoch count from last event
        max_epoch = 0
        if last_event and last_event.get("epoch") is not None:
            max_epoch = last_event["epoch"] + 1

        return {
            "session_id": scenario_id or path.stem,
            "n_epochs": max_epoch,
            "n_agents": len(agent_ids),
            "seed": first_event.get("seed"),
            "started_at": first_event.get("timestamp"),
            "ended_at": last_event.get("timestamp") if last_event else None,
            "event_count": event_count,
            "file_type": "jsonl",
        }
    except (json.JSONDecodeError, OSError):
        return None


def _parse_json_session(path: Path) -> Dict[str, Any]:
    """Parse a JSON history file into dashboard-ready data."""
    with open(path) as f:
        data = json.load(f)

    # Build agent map from agent_snapshots
    agents: Dict[str, Dict[str, Any]] = {}
    for snap in data.get("agent_snapshots", []):
        aid = snap["agent_id"]
        if aid not in agents:
            agents[aid] = {
                "agent_id": aid,
                "name": snap.get("name", aid),
                "type": _infer_agent_type(snap.get("name", aid)),
                "epochs": [],
            }
        agents[aid]["epochs"].append({
            "epoch": snap.get("epoch", 0),
            "reputation": snap.get("reputation", 0.0),
            "resources": snap.get("resources", 100.0),
            "interactions_initiated": snap.get("interactions_initiated", 0),
            "interactions_received": snap.get("interactions_received", 0),
            "avg_p_initiated": snap.get("avg_p_initiated", 0.5),
            "avg_p_received": snap.get("avg_p_received", 0.5),
            "total_payoff": snap.get("total_payoff", 0.0),
            "is_frozen": snap.get("is_frozen", False),
            "is_quarantined": snap.get("is_quarantined", False),
        })

    # Build epoch metrics timeline
    epochs = []
    for snap in data.get("epoch_snapshots", []):
        epochs.append({
            "epoch": snap.get("epoch", 0),
            "total_interactions": snap.get("total_interactions", 0),
            "accepted_interactions": snap.get("accepted_interactions", 0),
            "toxicity_rate": snap.get("toxicity_rate", 0.0),
            "quality_gap": snap.get("quality_gap", 0.0),
            "avg_p": snap.get("avg_p", 0.5),
            "total_welfare": snap.get("total_welfare", 0.0),
            "avg_payoff": snap.get("avg_payoff", 0.0),
            "gini_coefficient": snap.get("gini_coefficient", 0.0),
            "n_agents": snap.get("n_agents", 0),
            "ecosystem_threat_level": snap.get("ecosystem_threat_level", 0.0),
            "ecosystem_collusion_risk": snap.get("ecosystem_collusion_risk", 0.0),
        })

    # Build interaction edges (aggregate agent-to-agent flows)
    edges = _build_edges_from_agent_snapshots(agents)

    return {
        "session_id": data.get("simulation_id", path.stem),
        "n_epochs": data.get("n_epochs", 0),
        "n_agents": data.get("n_agents", 0),
        "seed": data.get("seed"),
        "started_at": data.get("started_at"),
        "ended_at": data.get("ended_at"),
        "agents": agents,
        "epochs": epochs,
        "edges": edges,
    }


def _parse_jsonl_session(path: Path) -> Dict[str, Any]:
    """Parse a JSONL event log into dashboard-ready data."""
    agents: Dict[str, Dict[str, Any]] = {}
    interactions: List[Dict[str, Any]] = []
    epoch_data: Dict[int, Dict[str, Any]] = {}
    scenario_id = None
    seed = None
    started_at = None
    ended_at = None

    # Per-agent-per-epoch accumulators
    agent_epoch_stats: Dict[str, Dict[int, Dict[str, Any]]] = {}

    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            event = json.loads(line)
            etype = event.get("event_type", "")
            epoch = event.get("epoch")
            ts = event.get("timestamp")

            if scenario_id is None and event.get("scenario_id"):
                scenario_id = event["scenario_id"]
            if seed is None and event.get("seed") is not None:
                seed = event["seed"]
            if started_at is None:
                started_at = ts
            ended_at = ts

            # Track agents
            for key in ("initiator_id", "counterparty_id", "agent_id"):
                aid = event.get(key)
                if aid and aid not in agents:
                    agents[aid] = {
                        "agent_id": aid,
                        "name": aid,
                        "type": "unknown",
                        "events": 0,
                    }
                if aid and aid in agents:
                    agents[aid]["events"] = agents[aid].get("events", 0) + 1

            # Track interactions
            payload = event.get("payload", {})
            if etype == "interaction_proposed":
                iid = event.get("interaction_id")
                init_id = event.get("initiator_id", "")
                cp_id = event.get("counterparty_id", "")
                interactions.append({
                    "interaction_id": iid,
                    "initiator": init_id,
                    "counterparty": cp_id,
                    "epoch": epoch,
                    "p": payload.get("p", 0.5),
                    "v_hat": payload.get("v_hat", 0.0),
                    "accepted": None,
                })

            elif etype in ("interaction_accepted", "interaction_rejected"):
                iid = event.get("interaction_id")
                for ix in reversed(interactions):
                    if ix["interaction_id"] == iid:
                        ix["accepted"] = etype == "interaction_accepted"
                        break

            elif etype == "payoff_computed":
                iid = event.get("interaction_id")
                for ix in reversed(interactions):
                    if ix["interaction_id"] == iid:
                        comps = payload.get("components", {})
                        ix["payoff_initiator"] = payload.get("payoff_initiator", 0.0)
                        ix["payoff_counterparty"] = payload.get("payoff_counterparty", 0.0)
                        ix["tau"] = comps.get("tau", 0.0)
                        break

            elif etype == "reputation_updated":
                aid = event.get("agent_id")
                if aid and aid in agents:
                    agents[aid]["reputation"] = payload.get("new_reputation", 0.0)

            elif etype == "agent_created":
                aid = event.get("agent_id")
                if aid:
                    agent_type = payload.get("agent_type", "unknown")
                    name = payload.get("name", aid)
                    agents[aid] = {
                        "agent_id": aid,
                        "name": name,
                        "type": agent_type,
                        "events": agents.get(aid, {}).get("events", 0),
                    }

            # Accumulate per-epoch stats
            if epoch is not None:
                if epoch not in epoch_data:
                    epoch_data[epoch] = {
                        "epoch": epoch,
                        "total_interactions": 0,
                        "accepted_interactions": 0,
                        "p_values": [],
                        "accepted_p": [],
                        "rejected_p": [],
                        "payoffs": [],
                    }
                ed = epoch_data[epoch]
                if etype == "interaction_proposed":
                    ed["total_interactions"] += 1
                    ed["p_values"].append(payload.get("p", 0.5))
                elif etype == "interaction_accepted":
                    ed["accepted_interactions"] += 1
                    # Find p for this interaction
                    iid = event.get("interaction_id")
                    for ix in reversed(interactions):
                        if ix["interaction_id"] == iid:
                            ed["accepted_p"].append(ix["p"])
                            break
                elif etype == "interaction_rejected":
                    iid = event.get("interaction_id")
                    for ix in reversed(interactions):
                        if ix["interaction_id"] == iid:
                            ed["rejected_p"].append(ix["p"])
                            break

    # Build epoch summaries
    epochs = []
    for ep_num in sorted(epoch_data.keys()):
        ed = epoch_data[ep_num]
        p_vals = ed["p_values"]
        acc_p = ed["accepted_p"]
        rej_p = ed["rejected_p"]
        avg_p = sum(p_vals) / len(p_vals) if p_vals else 0.5
        toxicity = 1.0 - (sum(acc_p) / len(acc_p)) if acc_p else 0.0
        quality_gap = 0.0
        if acc_p and rej_p:
            quality_gap = (sum(acc_p) / len(acc_p)) - (sum(rej_p) / len(rej_p))

        epochs.append({
            "epoch": ep_num,
            "total_interactions": ed["total_interactions"],
            "accepted_interactions": ed["accepted_interactions"],
            "toxicity_rate": toxicity,
            "quality_gap": quality_gap,
            "avg_p": avg_p,
        })

    # Build edges from interactions
    edges = _build_edges_from_interactions(interactions)

    return {
        "session_id": scenario_id or path.stem,
        "n_epochs": len(epoch_data),
        "n_agents": len(agents),
        "seed": seed,
        "started_at": started_at,
        "ended_at": ended_at,
        "agents": agents,
        "epochs": epochs,
        "edges": edges,
        "interactions": interactions,
    }


def _build_edges_from_interactions(
    interactions: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Aggregate interactions into directional edges between agents."""
    edge_map: Dict[tuple, Dict[str, Any]] = {}

    for ix in interactions:
        init_id = ix.get("initiator", "")
        cp_id = ix.get("counterparty", "")
        if not init_id or not cp_id:
            continue
        key = (init_id, cp_id)
        if key not in edge_map:
            edge_map[key] = {
                "source": init_id,
                "target": cp_id,
                "count": 0,
                "accepted": 0,
                "avg_p": 0.0,
                "p_sum": 0.0,
            }
        edge_map[key]["count"] += 1
        edge_map[key]["p_sum"] += ix.get("p", 0.5)
        if ix.get("accepted"):
            edge_map[key]["accepted"] += 1

    edges = []
    for e in edge_map.values():
        e["avg_p"] = e["p_sum"] / e["count"] if e["count"] > 0 else 0.5
        del e["p_sum"]
        edges.append(e)

    return edges


def _build_edges_from_agent_snapshots(
    agents: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Build approximate edges from agent snapshot data.

    JSON histories don't store per-interaction detail, so we create
    edges based on which agents had interactions in the same epochs.
    """
    edges = []
    agent_ids = list(agents.keys())
    for i, a_id in enumerate(agent_ids):
        for b_id in agent_ids[i + 1:]:
            a_data = agents[a_id]
            b_data = agents[b_id]
            # Check if agents overlapped (both had activity)
            a_epochs = {e["epoch"] for e in a_data.get("epochs", [])}
            b_epochs = {e["epoch"] for e in b_data.get("epochs", [])}
            overlap = a_epochs & b_epochs
            if overlap:
                a_initiated = sum(
                    e.get("interactions_initiated", 0)
                    for e in a_data.get("epochs", [])
                )
                b_initiated = sum(
                    e.get("interactions_initiated", 0)
                    for e in b_data.get("epochs", [])
                )
                if a_initiated > 0 or b_initiated > 0:
                    edges.append({
                        "source": a_id,
                        "target": b_id,
                        "count": len(overlap),
                        "bidirectional": True,
                    })
    return edges


def _infer_agent_type(name: str) -> str:
    """Infer agent type from name string."""
    name_lower = name.lower() if name else ""
    type_keywords = {
        "honest": "honest",
        "opportunistic": "opportunistic",
        "deceptive": "deceptive",
        "adversarial": "adversarial",
        "adaptive": "adaptive_adversary",
        "diligent": "diligent",
        "spam": "spam_bot",
        "collusi": "collusive",
        "vandal": "vandal",
        "llm": "llm",
    }
    for keyword, agent_type in type_keywords.items():
        if keyword in name_lower:
            return agent_type
    return "unknown"
