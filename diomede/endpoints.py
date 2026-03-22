from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DicomEndpoint:
    """A single DICOM destination node."""
    name: str
    ae_title: str
    host: str
    dicom_port: int
    rest_port: int

    @property
    def rest_base_url(self) -> str:
        return f"http://{self.host}:{self.rest_port}"


DEFAULT_NODES: list[DicomEndpoint] = [
    DicomEndpoint(
        name="Node1",
        ae_title="NODE1",
        host="localhost",
        dicom_port=4242,
        rest_port=8042,
    ),
    DicomEndpoint(
        name="Node2",
        ae_title="NODE2",
        host="localhost",
        dicom_port=4243,
        rest_port=8043,
    ),
    DicomEndpoint(
        name="Node3",
        ae_title="NODE3",
        host="localhost",
        dicom_port=4244,
        rest_port=8044,
    ),
]
