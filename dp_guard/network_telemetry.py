"""Real network telemetry ingestion and aggregation for the Telemetry Plane."""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Dict, List, Mapping

from dp_guard.types import NetworkSlice, UESessionRecord


class NetworkTelemetrySource:
    """
    Loads and aggregates real structured UE session records.

    This component simulates a 6G RAN telemetry collector that ingests
    per-UE session records and computes aggregate KPIs. Raw records remain
    encapsulated; only aggregated values are exposed to TelemetryPlane.
    """

    def __init__(
        self,
        records_path: Path,
        topology_path: Path,
        target_slice: str = "eMBB-1",
    ) -> None:
        """
        Initialize the telemetry source from JSON data files.

        Args:
            records_path: Path to UE session records JSON array.
            topology_path: Path to network slice topology JSON.
            target_slice: Slice filter for slice-scoped aggregations.
        """
        self._records: List[UESessionRecord] = self._load_records(records_path)
        self._slices: List[NetworkSlice] = self._load_slices(topology_path)
        self._topology = self._load_topology_meta(topology_path)
        self._target_slice = target_slice
        self._epoch = 0

    @staticmethod
    def _load_records(path: Path) -> List[UESessionRecord]:
        """Parse UE session records from JSON."""
        with path.open(encoding="utf-8") as handle:
            raw = json.load(handle)
        return [
            UESessionRecord(
                ue_id=item["ue_id"],
                slice=item["slice"],
                threat_score=float(item["threat_score"]),
                anomaly_flag=int(item["anomaly_flag"]),
                bytes_tx=float(item["bytes_tx"]),
                auth_failures=int(item["auth_failures"]),
            )
            for item in raw
        ]

    @staticmethod
    def _load_slices(path: Path) -> List[NetworkSlice]:
        """Parse network slice definitions from topology JSON."""
        with path.open(encoding="utf-8") as handle:
            raw = json.load(handle)
        return [
            NetworkSlice(
                id=s["id"],
                type=s["type"],
                description=s["description"],
                capacity_ue=int(s["capacity_ue"]),
                sla_latency_ms=int(s["sla_latency_ms"]),
            )
            for s in raw["slices"]
        ]

    @staticmethod
    def _load_topology_meta(path: Path) -> Dict[str, str]:
        """Load gNB and region metadata from topology file."""
        with path.open(encoding="utf-8") as handle:
            raw = json.load(handle)
        return {"gnb_id": raw["gNB_id"], "region": raw["region"]}

    @property
    def slices(self) -> List[NetworkSlice]:
        """Return network slice catalog."""
        return list(self._slices)

    @property
    def gnb_id(self) -> str:
        """Return gNodeB identifier."""
        return self._topology["gnb_id"]

    @property
    def region(self) -> str:
        """Return deployment region."""
        return self._topology["region"]

    def _filtered_records(self) -> List[UESessionRecord]:
        """Return records for the configured target slice."""
        return [r for r in self._records if r.slice == self._target_slice]

    def aggregate_metrics(self) -> Dict[str, float]:
        """
        Compute raw aggregate metrics q(X) from UE session records.

        Aggregations follow typed metric semantics with bounded per-record
        contribution (used to calibrate L1 sensitivity in the catalog).

        Returns:
            Mapping of metric name to raw aggregate value.
        """
        records = self._filtered_records()
        if not records:
            raise ValueError(f"No UE records for slice {self._target_slice}")

        slice_def = next((s for s in self._slices if s.id == self._target_slice), None)
        capacity = float(slice_def.capacity_ue if slice_def else 5000)

        max_threat = max(r.threat_score for r in records)
        active_count = float(len(records))
        anomaly_ratio = sum(r.anomaly_flag for r in records) / len(records) * 100.0
        total_auth_failures = float(sum(r.auth_failures for r in records))

        # Simulated KPIs derived from session statistics
        total_bytes = sum(r.bytes_tx for r in records)
        load_percent = min(100.0, (total_bytes / (capacity * 50000)) * 100.0)
        packet_loss = min(5.0, 0.1 * sum(r.anomaly_flag for r in records) + self._epoch * 0.05)

        return {
            "threat_level": max_threat,
            "active_connections": active_count,
            "anomaly_score": anomaly_ratio,
            "failed_auth_attempts": total_auth_failures,
            "slice_load_percent": load_percent,
            "packet_loss_rate": packet_loss,
        }

    def advance_epoch(self, threat_delta: float = 3.0) -> None:
        """
        Simulate network evolution between orchestration epochs.

        Increments threat scores for anomalous sessions to model escalating
        attack activity between closed-loop decision cycles.

        Args:
            threat_delta: Amount to increase threat for flagged sessions.
        """
        updated: List[UESessionRecord] = []
        for record in self._records:
            if record.anomaly_flag and record.slice == self._target_slice:
                updated.append(
                    UESessionRecord(
                        ue_id=record.ue_id,
                        slice=record.slice,
                        threat_score=min(100.0, record.threat_score + threat_delta + random.uniform(0, 2)),
                        anomaly_flag=record.anomaly_flag,
                        bytes_tx=record.bytes_tx * random.uniform(1.0, 1.15),
                        auth_failures=record.auth_failures + (1 if random.random() > 0.7 else 0),
                    )
                )
            else:
                updated.append(record)
        self._records = updated
        self._epoch += 1

    def apply_action_effects(self, action_type: str, parameters: Mapping[str, object]) -> None:
        """
        Apply side effects of executed control actions to raw telemetry.

        Args:
            action_type: Executed action identifier.
            parameters: Action parameters from the orchestrator.
        """
        if action_type == "block_traffic":
            self._records = [
                r for r in self._records
                if not (r.anomaly_flag and r.slice == self._target_slice)
            ]
        elif action_type == "isolate_segment":
            slice_id = str(parameters.get("slice", self._target_slice))
            self._records = [r for r in self._records if r.slice != slice_id]
        elif action_type == "rate_limit_slice":
            self._records = [
                UESessionRecord(
                    ue_id=r.ue_id,
                    slice=r.slice,
                    threat_score=r.threat_score,
                    anomaly_flag=r.anomaly_flag,
                    bytes_tx=r.bytes_tx * 0.5,
                    auth_failures=r.auth_failures,
                )
                for r in self._records
            ]
