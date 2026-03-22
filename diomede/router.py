from __future__ import annotations

import logging
from pathlib import Path

import pydicom

from diomede.endpoints import DEFAULT_NODES, DicomEndpoint
from diomede.routing import RoutingStrategy, get_strategy
from diomede.sender import SendError, send_file

logger = logging.getLogger(__name__)


class DynamicRouter:
    """
    Routes DICOM files to the best available destination node.

    Usage:
        router = DynamicRouter(strategy="modality_aware")
        router.route(Path("scan.dcm"))
    """

    def __init__(
        self,
        nodes: list[DicomEndpoint] | None = None,
        strategy: str = "least_queue",
    ) -> None:
        self.nodes = nodes or DEFAULT_NODES
        self._strategy: RoutingStrategy = get_strategy(strategy)

    def route(self, dicom_path: Path) -> DicomEndpoint:
        """
        Select the best destination for the given DICOM file and send it.
        Returns the chosen endpoint. Raises SendError if sending fails.
        """
        dataset = pydicom.dcmread(str(dicom_path))
        destination = self._strategy.select(dataset, self.nodes)

        if destination is None:
            raise SendError("No reachable nodes available for routing.")

        logger.info(
            "Routing %s → %s [modality=%s]",
            dicom_path.name,
            destination.name,
            getattr(dataset, "Modality", "unknown"),
        )

        send_file(dicom_path, destination)
        return destination

    def route_directory(self, directory: Path) -> dict[str, str]:
        """
        Route every .dcm file in a directory.
        Returns a mapping of filename → destination node name.
        """
        results: dict[str, str] = {}
        dcm_files = list(directory.glob("*.dcm"))

        if not dcm_files:
            logger.warning("No .dcm files found in %s", directory)
            return results

        for dcm_file in dcm_files:
            try:
                destination = self.route(dcm_file)
                results[dcm_file.name] = destination.name
            except SendError as exc:
                logger.error("Failed to route %s: %s", dcm_file.name, exc)
                results[dcm_file.name] = f"ERROR: {exc}"

        return results
