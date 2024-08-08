"""
Utilities for XML parsing.
"""

from __future__ import annotations
from typing import BinaryIO

import lxml.etree


class ParserException(Exception):
    pass


class UnexpectedChildNodeException(ParserException):
    def __init__(self, tag: str):
        super().__init__(f"Unexpected child node [tag={tag}]")


class MissingValue(ParserException):
    def __init__(self, value_name: str):
        super().__init__(f"Missing value: {value_name}")


class MissingAttribute(ParserException):
    def __init__(self, name: str):
        super().__init__(f"Missing attribute: {name}")


class EmptyNode(ParserException):
    pass


class DuplicateValue(ParserException):
    def __init__(self):
        super().__init__("Duplicate value")


XmlElement = lxml.etree._Element  # type: ignore reportPrivateUsage
XmlDataSource = bytes | BinaryIO


def parse_xml(data: XmlDataSource) -> XmlElement:
    parser = lxml.etree.XMLParser(
        dtd_validation=False,
        load_dtd=False,
        no_network=True,
        remove_pis=True,
        remove_comments=True,
        resolve_entities=False,
    )

    if isinstance(data, bytes):
        return lxml.etree.fromstring(data, parser=parser)
    else:
        return lxml.etree.parse(data, parser=parser).getroot()


def parse_token(node: XmlElement) -> str:
    """
    Parse a value as `xs:token`.
    This will remove whitespace at the edges of the string, and replace all internal
    whitespaces with a single space.

    e.g.:
        "    Some   \n Test "
    will become:
        "Some Test"

    See: https://www.w3schools.com/XML/schema_dtypes_string.asp
    """
    value = node.text or ""

    return " ".join(value.split())
