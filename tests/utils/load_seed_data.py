"""Utilities for loading seed data from the examples directory."""

import json
import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from xml.etree import ElementTree
from zipfile import ZipFile

WORKBOOK_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REPO_ROOT = Path(__file__).parents[2]
EXAMPLES_DIR = REPO_ROOT / "examples"
ANNOTATION_LABEL_COLUMN = 6
METADATA_VALUE_COLUMN = 2


@dataclass(frozen=True, slots=True)
class ExpectedSeedData:
    """Expected content loaded by the Compose seed jobs."""

    source_name: str
    image_set_uuid: str
    image_set_name: str
    image_filenames: set[str]
    image_filename_sample: set[str]
    annotation_set_name: str
    annotation_count: int
    label_names: set[str]
    search_label: str


@cache
def load_expected_seed_data(source_name: str) -> ExpectedSeedData:
    """Load expected seed content from the examples directory."""
    metadata = json.loads((EXAMPLES_DIR / f"sample_{source_name}.json").read_text(encoding="utf-8"))
    annotation_workbook = EXAMPLES_DIR / f"sample_{source_name}_annotations.xlsx"
    metadata_rows = read_workbook_sheet(annotation_workbook, "Annotation set metadata")
    annotation_rows = read_workbook_sheet(annotation_workbook, "Annotation data")
    label_rows = read_workbook_sheet(annotation_workbook, "Label set")

    label_names = [row[1] for row in label_rows[3:] if len(row) > 1 and row[1]]
    image_filenames = [item["image-filename"] for item in metadata["ifdo"]["image-set-items"]]

    return ExpectedSeedData(
        source_name=source_name,
        image_set_uuid=metadata["image_set_uuid"],
        image_set_name=metadata["ifdo"]["image-set-header"]["image-set-name"],
        image_filenames=set(image_filenames),
        image_filename_sample=set(image_filenames[:5]),
        annotation_set_name=cell_value(metadata_rows, "annotation-set-name"),
        annotation_count=sum(
            1 for row in annotation_rows[4:] if len(row) > ANNOTATION_LABEL_COLUMN and row[ANNOTATION_LABEL_COLUMN]
        ),
        label_names=set(label_names),
        search_label=label_names[0],
    )


def cell_value(rows: list[list[str | None]], field_name: str) -> str:
    """Return the value column for a metadata field."""
    for row in rows:
        if row and row[0] == field_name and len(row) > METADATA_VALUE_COLUMN and row[METADATA_VALUE_COLUMN]:
            return row[METADATA_VALUE_COLUMN]
    raise AssertionError(f"Missing {field_name} in seed workbook")


def read_workbook_sheet(path: Path, sheet_name: str) -> list[list[str | None]]:
    """Read an XLSX sheet with the standard library."""
    with ZipFile(path) as archive:
        shared_strings = read_shared_strings(archive)
        sheet_path = sheet_xml_path(archive, sheet_name)
        return read_sheet_rows(archive, sheet_path, shared_strings)


def read_shared_strings(archive: ZipFile) -> list[str]:
    """Read XLSX shared strings."""
    root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
    values: list[str] = []
    for item in root.findall(f"{{{WORKBOOK_NS}}}si"):
        values.append("".join(text.text or "" for text in item.iter(f"{{{WORKBOOK_NS}}}t")))
    return values


def sheet_xml_path(archive: ZipFile, sheet_name: str) -> str:
    """Return the XML path for a sheet name."""
    workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
    rels = ElementTree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    targets = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels}

    elem = workbook.find(f"{{{WORKBOOK_NS}}}sheets")
    if elem is None:
        raise AssertionError(f"Missing sheets in {archive.filename}")
    for sheet in elem:
        if sheet.attrib["name"] == sheet_name:
            relationship_id = sheet.attrib[f"{{{REL_NS}}}id"]
            return f"xl/{targets[relationship_id]}"
    raise AssertionError(f"Missing sheet {sheet_name} in {archive.filename}")


def read_sheet_rows(archive: ZipFile, sheet_path: str, shared_strings: list[str]) -> list[list[str | None]]:
    """Read rows from an XLSX worksheet XML file."""
    root = ElementTree.fromstring(archive.read(sheet_path))
    rows: list[list[str | None]] = []
    for row in root.findall(f".//{{{WORKBOOK_NS}}}row"):
        values: list[str | None] = []
        for cell in row.findall(f"{{{WORKBOOK_NS}}}c"):
            column_index = cell_column_index(cell.attrib["r"])
            while len(values) <= column_index:
                values.append(None)
            value = cell.find(f"{{{WORKBOOK_NS}}}v")
            if value is None:
                continue
            cell_value_text = value.text
            if cell.attrib.get("t") == "s" and cell_value_text is not None:
                cell_value_text = shared_strings[int(cell_value_text)]
            values[column_index] = cell_value_text
        rows.append(values)
    return rows


def cell_column_index(cell_reference: str) -> int:
    """Return zero-based column index from an Excel cell reference."""
    column = re.match(r"[A-Z]+", cell_reference)
    if column is None:
        raise AssertionError(f"Invalid Excel cell reference: {cell_reference}")

    index = 0
    for character in column.group(0):
        index = (index * 26) + ord(character) - ord("A") + 1
    return index - 1
