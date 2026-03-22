"""
Generate dummy DICOM files for testing the router without real scanner data.
Run: python generate_samples.py
"""
from __future__ import annotations

import struct
from pathlib import Path

import pydicom
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.sequence import Sequence
from pydicom.uid import generate_uid, ExplicitVRLittleEndian

OUTPUT_DIR = Path(__file__).parent / "sample_dicoms"

SAMPLE_STUDIES = [
    {"modality": "CT",  "patient": "Smith^John",   "study_desc": "Chest CT"},
    {"modality": "MR",  "patient": "Doe^Jane",     "study_desc": "Brain MRI"},
    {"modality": "CR",  "patient": "Jones^Bob",    "study_desc": "Chest X-Ray"},
    {"modality": "PT",  "patient": "Brown^Alice",  "study_desc": "PET Scan"},
    {"modality": "DX",  "patient": "White^Eve",    "study_desc": "Knee X-Ray"},
]


def create_dicom_file(modality: str, patient_name: str, study_desc: str, output_path: Path) -> None:
    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.2"  # CT Storage
    file_meta.MediaStorageSOPInstanceUID = generate_uid()
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian

    ds = Dataset()
    ds.file_meta = file_meta
    ds.is_implicit_VR = False
    ds.is_little_endian = True

    ds.SOPClassUID = "1.2.840.10008.5.1.4.1.1.2"
    ds.SOPInstanceUID = generate_uid()
    ds.StudyInstanceUID = generate_uid()
    ds.SeriesInstanceUID = generate_uid()

    ds.PatientName = patient_name
    ds.PatientID = patient_name.split("^")[0].upper()[:8]
    ds.StudyDate = "20260101"
    ds.StudyTime = "120000"
    ds.Modality = modality
    ds.StudyDescription = study_desc
    ds.Rows = 64
    ds.Columns = 64
    ds.BitsAllocated = 16
    ds.BitsStored = 16
    ds.HighBit = 15
    ds.PixelRepresentation = 0
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.PixelData = bytes(64 * 64 * 2)

    pydicom.dcmwrite(str(output_path), ds)
    print(f"Created: {output_path.name}  (modality={modality})")


def main() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    for i, study in enumerate(SAMPLE_STUDIES):
        filename = f"sample_{i+1:02d}_{study['modality']}.dcm"
        create_dicom_file(
            modality=study["modality"],
            patient_name=study["patient"],
            study_desc=study["study_desc"],
            output_path=OUTPUT_DIR / filename,
        )
    print(f"\nGenerated {len(SAMPLE_STUDIES)} sample DICOM files in {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
