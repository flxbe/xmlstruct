"""
Utilities for XML parsing.
"""

from __future__ import annotations
from typing import Iterator, Literal, Optional
from io import BytesIO

import lxml.etree


class ParserException(Exception):
    pass


class UnexpectedChildNodeException(ParserException):
    def __init__(self, tag: str):
        super().__init__(f"Unexpected child node [tag={tag}]")


class MissingValue(ParserException):
    def __init__(self, value_name: str):
        super().__init__(f"Missing value: {value_name}")


class EmptyNode(ParserException):
    pass


class DuplicateValue(ParserException):
    def __init__(self):
        super().__init__("Duplicate value")


XmlElement = lxml.etree._Element  # type: ignore reportPrivateUsage
XmlEventType = Literal["start", "end"]
XmlEvent = tuple[XmlEventType, XmlElement]


class XmlParser:
    """
    Custom wrapper around the raw lxml event stream.
    Provides a higher-level API supporting the xdf parsers.
    """

    __slots__ = ["_iter", "current_line"]

    def __init__(self, data: bytes):
        self._iter: Iterator[XmlEvent] = lxml.etree.iterparse(
            BytesIO(data),
            events=("start", "end"),
            dtd_validation=False,
            load_dtd=False,
            no_network=True,
            remove_comments=True,
            remove_pis=True,
        )

        self.current_line = 0

    def expect_child(self, tag: str) -> XmlElement:
        child = self.next_child()

        if child is None:
            raise MissingValue(tag)

        if child.tag != tag:
            raise UnexpectedChildNodeException(child.tag)

        return child

    def expect_close(self):
        event, data = self.next()

        if event != "end":
            raise UnexpectedChildNodeException(data.tag)

    def next_child(self) -> Optional[XmlElement]:
        event, data = self.next()

        if event == "start":
            return data
        else:
            return None

    def skip_node(self):
        depths = 1

        while True:
            event, _ = self.next()
            if event == "start":
                depths += 1
            elif event == "end":
                if depths == 1:
                    return
                else:
                    depths -= 1

    def parse_code(self) -> str | None:
        """
        Parse the content of the `code` child node.

        E.g., calling the function for the following xml data

        ```
        <outer_node>
            <!-- Function should be called at this point -->
            <code>
                RequestedValue
            </code>
        </outer_node>
        ```

        would return `"RequestedValue"`.
        """

        self.expect_child("code")
        value = self.parse_token()
        self.expect_close()

        return value

    def parse_token(self) -> str:
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
        value = self.parse_value()

        return " ".join(value.split())

    def parse_value(self) -> str:
        event, element = self.next()
        if event == "start":
            raise UnexpectedChildNodeException(element.tag)
        else:
            return element.text or ""

    def next(self) -> XmlEvent:
        try:
            event, data = next(self._iter)
        except lxml.etree.XMLSyntaxError as error:
            raise ParserException("Invalid xml document") from error

        self.current_line = data.sourceline

        return event, data


def get_local_name(tag: str) -> str:
    return lxml.etree.QName(tag).localname
