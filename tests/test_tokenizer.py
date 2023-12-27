import pytest

from xmlstruct.tokenizer import (
    Attribute,
    CloseTag,
    StartOpenTag,
    Text,
    FinishOpenTag,
    XmlEvent,
    parse,
)


@pytest.mark.parametrize(
    "data",
    [
        '<?xml version="1.0" ?>',
        '<?xml version="1.1" ?>',
        '<?xml version="1.1" encoding="utf-8" ?>',
    ],
)
def test_should_parse_valid_xml_declaration(data: str):
    assert parse(data) == []


@pytest.mark.parametrize(
    "data,events",
    [
        (
            "<root/>",
            [
                StartOpenTag(None, "root"),
                FinishOpenTag(empty=True),
            ],
        ),
        (
            "  <root/>",
            [
                StartOpenTag(None, "root"),
                FinishOpenTag(empty=True),
            ],
        ),
        (
            "<root/>  ",
            [
                StartOpenTag(None, "root"),
                FinishOpenTag(empty=True),
            ],
        ),
        (
            "<root />",
            [
                StartOpenTag(None, "root"),
                FinishOpenTag(empty=True),
            ],
        ),
        (
            "<test:root/>",
            [
                StartOpenTag("test", "root"),
                FinishOpenTag(empty=True),
            ],
        ),
        (
            "<root></root>",
            [
                StartOpenTag(None, "root"),
                FinishOpenTag(empty=False),
                CloseTag(None, "root"),
            ],
        ),
        (
            "<root attribute='value' />",
            [
                StartOpenTag(None, "root"),
                Attribute(None, "attribute", "value"),
                FinishOpenTag(empty=True),
            ],
        ),
        (
            "<root test:attribute='value' />",
            [
                StartOpenTag(None, "root"),
                Attribute("test", "attribute", "value"),
                FinishOpenTag(empty=True),
            ],
        ),
        (
            "<root><inner /></root>",
            [
                StartOpenTag(None, "root"),
                FinishOpenTag(empty=False),
                StartOpenTag(None, "inner"),
                FinishOpenTag(empty=True),
                CloseTag(None, "root"),
            ],
        ),
        (
            "<root> </root>",
            [
                StartOpenTag(None, "root"),
                FinishOpenTag(empty=False),
                Text(" "),
                CloseTag(None, "root"),
            ],
        ),
    ],
)
def test_should_parse_correctly(data: str, events: list[XmlEvent]):
    assert parse(data) == events
