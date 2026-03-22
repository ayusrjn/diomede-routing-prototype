from __future__ import annotations

import logging
import time
from pathlib import Path

import pydicom
from pynetdicom import AE

from diomede.endpoints import DicomEndpoint

logger = logging.getLogger(__name__)

MAX_SEND_RETRIES = 2


class SendError(Exception):
    """Raised when a DICOM C-STORE fails after all retries."""


def send_file(dicom_path: Path, destination: DicomEndpoint) -> None:
    """
    Send a single DICOM file to a destination node via C-STORE.
    Retries up to MAX_SEND_RETRIES times before raising SendError.
    """
    dataset = pydicom.dcmread(str(dicom_path))

    for attempt in range(1, MAX_SEND_RETRIES + 2):
        try:
            _store(dataset, destination)
            logger.info(
                "Sent %s → %s (attempt %d)",
                dicom_path.name,
                destination.name,
                attempt,
            )
            return
        except SendError:
            if attempt > MAX_SEND_RETRIES:
                raise
            logger.warning(
                "Send attempt %d failed for %s → %s, retrying...",
                attempt,
                dicom_path.name,
                destination.name,
            )
            time.sleep(1)


def _store(dataset: pydicom.Dataset, destination: DicomEndpoint) -> None:
    ae = AE(ae_title="ROUTER")
    ae.add_requested_context(str(dataset.SOPClassUID))

    assoc = ae.associate(
        destination.host,
        destination.dicom_port,
        ae_title=destination.ae_title,
    )

    if not assoc.is_established:
        raise SendError(
            f"Could not associate with {destination.name} "
            f"({destination.host}:{destination.dicom_port})"
        )

    try:
        status = assoc.send_c_store(dataset)
        if not status or status.Status != 0x0000:
            raise SendError(
                f"C-STORE to {destination.name} returned status {getattr(status, 'Status', 'none'):#06x}"
            )
    finally:
        assoc.release()