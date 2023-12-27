from __future__ import annotations
from dataclasses import dataclass
import re

from typing import Union

UTF_8_BOM = bytes.fromhex("efbbbf").decode("utf-8")


class XmlException(Exception):
    pass


@dataclass(slots=True, frozen=True)
class StartOpenTag:
    prefix: str | None
    tag: str


@dataclass(slots=True, frozen=True)
class Attribute:
    prefix: str | None
    tag: str
    value: str


@dataclass(slots=True, frozen=True)
class FinishOpenTag:
    empty: bool


@dataclass(slots=True, frozen=True)
class Text:
    content: str


@dataclass(slots=True, frozen=True)
class CloseTag:
    prefix: str | None
    tag: str


XmlEvent = Union[StartOpenTag, Attribute, FinishOpenTag, Text, CloseTag]


def parse(data: Union[str, bytes, memoryview]) -> list[XmlEvent]:
    events: list[XmlEvent] = []
    stream = Stream(data)

    # Skip UTF-8 BOM
    if stream.starts_with(UTF_8_BOM):
        stream.skip(3)

    if stream.starts_with("<?xml "):
        _parse_declaration(stream)

    parse_misc(stream)
    stream.skip_spaces()

    if stream.current_char() == "<":
        parse_element(stream, events)

    parse_misc(stream)

    # TODO: make this faster
    if not stream.at_end():
        raise XmlException(f"Expected EOF, got: {stream.rest()}")

    return events


def _parse_declaration(stream: Stream):
    """
    XMLDecl ::= '<?xml' VersionInfo EncodingDecl? SDDecl? S? '?>'
    """

    # Skip '<?xml '
    stream.skip(6)
    stream.skip_spaces()

    # Skip version
    if not stream.starts_with("version"):
        raise XmlException("Missing 'version' attribute in xml declaration")
    _ = parse_attribute(stream)
    stream.consume_declaration_spaces()

    # Skip encoding
    if stream.starts_with("encoding"):
        _ = parse_attribute(stream)
        stream.consume_declaration_spaces()

    # Skip standalone
    if stream.starts_with("standalone"):
        _ = parse_attribute(stream)

    stream.skip_spaces()
    stream.consume_str("?>")


def parse_misc(stream: Stream):
    while not stream.at_end():
        stream.skip_spaces()

        if stream.starts_with("<!--"):
            parse_comment(stream)
        elif stream.starts_with("<?"):
            raise XmlException("Processing instructions not supported")
        else:
            return



def parse_attribute(
    stream: Stream,
) -> tuple[str | None, str, str]:
    """
    Attribute ::= Name Eq AttValue
    """
    prefix, local = stream.consume_qname()
    stream.consume_eq()

    # Safe the exact type of quote to validate it at then end of the value
    quote = stream.consume_quote()
    value = stream.consume_until([quote, LESS_THAN])
    stream.consume_char(quote)

    return prefix, local, value


def parse_element(stream: Stream, events: list[XmlEvent]):
    stream.skip(1)  # <

    prefix, local_name = stream.consume_qname()
    events.append(StartOpenTag(prefix, local_name))

    while not stream.at_end():
        has_space = stream.starts_with_space()
        stream.skip_spaces()

        match stream.current_char():
            case "/":
                stream.skip(1)
                stream.consume_char(">")
                events.append(FinishOpenTag(empty=True))
                return
            case ">":
                stream.skip(1)
                events.append(FinishOpenTag(empty=False))
                parse_content(stream, events)
                return
            case _:
                # an attribute must always be preceded by a whitespace
                if not has_space:
                    raise XmlException(
                        f"Expected whitespace, got {stream.current_char()}"
                    )

                prefix, attribute_name, attribute_value = parse_attribute(stream)
                events.append(Attribute(prefix, attribute_name, attribute_value))


def parse_content(stream: Stream, events: list[XmlEvent]):
    while not stream.at_end():
        if stream.current_char() == "<":
            match stream.next_char():
                case "!":
                    parse_comment(stream)
                case "?":
                    raise XmlException("Processing instructions not supported")
                case "/":
                    return parse_close_element(stream, events)
                case _:
                    parse_element(stream, events)
        else:
            parse_text(stream, events)


def parse_close_element(stream: Stream, events: list[XmlEvent]):
    stream.skip(2)  # </

    prefix, tag = stream.consume_qname()
    stream.skip_spaces()
    stream.consume_char(">")

    events.append(CloseTag(prefix, tag))


def parse_text(stream: Stream, events: list[XmlEvent]):
    text = stream.consume_until(["<"])

    # Must not appear in text blocks
    # See: https://www.w3.org/TR/xml/#syntax
    if "||>" in text:
        raise XmlException("Got unexpected '||>' in text data")

    events.append(Text(text))

def parse_comment(stream):
    raise NotImplementedError()


WHITESPACE = " \r\n\t"
LESS_THAN = "<"
EQ = "="
QUOTES = "'\""


NAME_START_CHARS = "[:]|[A-Z]|[_]|[a-z]|[\u00C0-\u00D6]|[\u00D8-\u00F6]|[\u00F8-\u02FF]|[\u0370-\u037D]|[\u037F-\u1FFF]|[\u200C-\u200D]|[\u2070-\u218F]|[\u2C00-\u2FEF]|[\u3001-\uD7FF]|[\uF900-\uFDCF]|[\uFDF0-\uFFFD]|[\U00010000-\U000EFFFF]"
ALL_NAME_CHARS = (
    NAME_START_CHARS + "|[-]|[.]|[0-9]|\u00B7|[\u0300-\u036F]|[\u203F-\u2040]"
)

XML_NAME_START_REGEXP = re.compile(f"^({NAME_START_CHARS})$")
XML_NAME_REGEXP = re.compile(f"^({ALL_NAME_CHARS})$")


class Stream:
    def __init__(self, data: Union[str, bytes, memoryview]):
        if isinstance(data, memoryview):
            self._data = data.tobytes().decode("utf-8")
        elif not isinstance(data, str):
            self._data = data.decode("utf-8")
        else:
            self._data = data

        self._position = 0
        self._end = len(data)

    def starts_with_space(self) -> bool:
        return self._data[self._position] in WHITESPACE

    def skip_spaces(self):
        while self._position != self._end:
            if self._data[self._position] in WHITESPACE:
                self._position = self._position + 1
            else:
                return

    def consume_spaces(self):
        """
        Like `skip_spaces', but checks that the first character is actually a space.
        """

        if self._data[self._position] in WHITESPACE:
            self.skip_spaces()
        else:
            raise Exception("Expected at least one whitespace character")

    def consume_declaration_spaces(self):
        """
        Like `consume_spaces', but exits without an error when the declaration ends
        """

        if self._data[self._position] in WHITESPACE:
            self.skip_spaces()
        elif self.starts_with("?>"):
            return
        else:
            raise Exception("Expected at least one whitespace character")

    def skip(self, num_bytes: int):
        self._position = self._position + num_bytes

    def starts_with(self, data: str) -> bool:
        return self._data[self._position : self._position + len(data)] == data

    def consume_qname(self) -> tuple[str | None, str]:
        """
        https://www.w3.org/TR/xml-names/#ns-qualnames
        """
        start = self._position
        split: int | None = None

        while self._position != self._end:
            char = self._data[self._position]

            if char == ":":
                if split is None:
                    split = self._position
                    self._position = self._position + 1
                else:
                    # Multiple `:` is an error
                    raise Exception("multiple `:`")
            else:
                if XML_NAME_REGEXP.match(char) is not None:
                    self._position = self._position + 1
                else:
                    break

        if split is None:
            prefix = None
            local = self._data[start : self._position]
        else:
            prefix = self._data[start:split]
            local = self._data[split + 1 : self._position]

            # prefix must start with `NameStartChar`
            if XML_NAME_START_REGEXP.match(prefix[0]) is None:
                raise Exception("Invalid starting string in prefix")

        if len(local) == 0:
            raise Exception("Local name must not be empty")

        # local must start with `NameStartChar`
        if XML_NAME_START_REGEXP.match(local[0]) is None:
            raise Exception("Invalid starting string in local")

        return prefix, local

    def consume_eq(self):
        self.consume_char(EQ)

    def consume_quote(self) -> str:
        char = self._data[self._position]

        if char not in QUOTES:
            raise XmlException(f"Expected quote, got: {char}")

        self._position = self._position + 1
        return char

    def consume_char(self, expected_char: str):
        char = self._data[self._position]
        if char != expected_char:
            raise XmlException(f"Expected '=', got: {char}")

        self._position = self._position + 1

    def consume_str(self, expected_str: str):
        length = len(expected_str)
        end = self._position + length
        part = self._data[self._position : end]

        if part != expected_str:
            raise XmlException(f"Expected '{expected_str}', got '{part}'")

        self._position = end

    def consume_until(self, read_until_char: list[str]) -> str:
        start = self._position

        while self._data[self._position] not in read_until_char:
            self._position = self._position + 1

        return self._data[start : self._position]

    def current_char(self) -> str | None:
        if self._position >= self._end:
            return None
        else:
            return self._data[self._position]

    def next_char(self) -> str | None:
        if self._position + 1 >= self._end:
            return None
        else:
            return self._data[self._position + 1]

    def at_end(self) -> bool:
        return self._position >= self._end

    def rest(self) -> str:
        return self._data[self._position :]
