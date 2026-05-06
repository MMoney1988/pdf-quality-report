from __future__ import annotations

import json
from pathlib import Path

from pdf_quality_report.convert import convert_docling_document, main


def test_convert_page6_heading_keeps_runtime_compatible_bbox() -> None:
    docling_document = {
        "schema_name": "DoclingDocument",
        "version": "1.10.0",
        "origin": {"filename": "sample_article.pdf", "binary_hash": 123},
        "texts": [
            {
                "self_ref": "#/texts/46",
                "label": "section_header",
                "text": "2.  Document Element Recognition",
                "prov": [
                    {
                        "page_no": 6,
                        "bbox": {
                            "l": 70.8661,
                            "t": 694.1634146484375,
                            "r": 340.7660999999999,
                            "b": 642.1634146484375,
                            "coord_origin": "BOTTOMLEFT",
                        },
                        "charspan": [0, 41],
                    }
                ],
            }
        ],
        "tables": [],
        "pictures": [],
    }

    uif_document = convert_docling_document(docling_document, pages={6})

    block = uif_document["blocks"][0]
    assert block["id"] == "p6-texts-46"
    assert block["type"] == "heading"
    assert block["level"] == 1
    assert block["bbox"] == [70.8661, 642.1634146484375, 340.7660999999999, 694.1634146484375]
    assert block["relationships"] == []
    assert block["provenance"]["raw_docling_ref"] == "#/texts/46"
    assert block["provenance"]["source_pdf_hash"] == "pending"

    assert block["content"]["text"] == "2.  Document Element Recognition"


def test_convert_filters_pages_and_maps_picture_to_image() -> None:
    docling_document = {
        "schema_name": "DoclingDocument",
        "version": "1.10.0",
        "origin": {"filename": "sample.pdf"},
        "texts": [
            {
                "self_ref": "#/texts/1",
                "label": "text",
                "text": "Page five",
                "prov": [{"page_no": 5, "bbox": {"l": 1, "t": 4, "r": 3, "b": 2, "coord_origin": "BOTTOMLEFT"}}],
            }
        ],
        "tables": [],
        "pictures": [
            {
                "self_ref": "#/pictures/4",
                "label": "picture",
                "prov": [{"page_no": 6, "bbox": {"l": 10, "t": 40, "r": 30, "b": 20, "coord_origin": "BOTTOMLEFT"}}],
            }
        ],
    }

    uif_document = convert_docling_document(docling_document, pages={6})

    assert [block["id"] for block in uif_document["blocks"]] == ["p6-pictures-4"]
    block = uif_document["blocks"][0]
    assert block["type"] == "image"
    assert block["content"] is None
    assert block["base64"] is None

    assert block["provenance"]["raw_docling_ref"] == "#/pictures/4"


def test_cli_writes_page_filtered_uif_json(tmp_path: Path) -> None:
    docling_document = {
        "schema_name": "DoclingDocument",
        "version": "1.10.0",
        "origin": {"filename": "sample.pdf"},
        "texts": [
            {
                "self_ref": "#/texts/2",
                "label": "text",
                "text": "Visible text",
                "prov": [{"page_no": 6, "bbox": {"l": 1, "t": 4, "r": 3, "b": 2, "coord_origin": "BOTTOMLEFT"}}],
            }
        ],
        "tables": [],
        "pictures": [],
    }
    input_path = tmp_path / "docling.json"
    output_path = tmp_path / "uif.json"
    input_path.write_text(json.dumps(docling_document), encoding="utf-8")

    assert main(["--input", str(input_path), "--output", str(output_path), "--pages", "6"]) == 0

    uif_document = json.loads(output_path.read_text(encoding="utf-8"))
    assert uif_document["metadata"]["page_filter"] == [6]
    assert uif_document["blocks"][0]["type"] == "paragraph"
