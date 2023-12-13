from __future__ import annotations

from datetime import datetime
import dataclasses
from inspect import isclass
import typing
from typing import Any, Callable, Generic, Optional, TypeVar, Union
from enum import Enum, IntEnum

from .xml import XmlElement, XmlParser


class XmlStructError(Exception):
    pass


if typing.TYPE_CHECKING:
    from _typeshed import DataclassInstance

    D = TypeVar("D", bound=DataclassInstance)
else:
    D = TypeVar("D")


T = TypeVar("T")


class _DefaultNamespace:
    pass


DefaultNamespace = _DefaultNamespace()

Namespace = Union[str, _DefaultNamespace]


@dataclasses.dataclass
class Value:
    """
    Annotate a dataclass member as a direct child value.
    Additional configuration of the behaviour is possible.

    ### `namespace`

    Set the namespace of the child element.
    This is `DefaultNamespace` by default, meaning that the optional global
    namespace will be used.

    Alternatively, either a `str` containing the actual namespace or
    `None` can be used to overwrite theglobal namespace.
    """

    name: Union[str, None] = None
    namespace: Optional[Namespace] = DefaultNamespace


# Make the decoder always return an optional field, so
# that empty of self-closing tags can be interpreted as
# empty values from the decoder.
# Values not wrapped in `Optional` are then handled with an
# extra test for `None` to ensure the value was actually there.
Decoder = Callable[[XmlElement, XmlParser], T]
# Encoder = Callable[[T, ValueList, ByteOrder], None]


class ValueContainer(Generic[T]):
    """
    Container to temporarily store a parsed value.
    """

    _value: Optional[T] = None
    _filled: bool = False

    def __init__(self, decode: Decoder[T], is_optional: bool):
        self._decode = decode
        self._is_optional = is_optional

    def unwrap(self, tag_name: str) -> Optional[T]:
        if not self._is_optional and self._value is None:
            raise Exception(f"Missing node {tag_name}")

        return self._value

    def parse(self, node: XmlElement, parser: XmlParser):
        if self._filled:
            raise Exception("Duplicate Value")

        self._value = self._decode(node, parser)
        assert self._value is not None

        self._filled = True


class ListContainer(Generic[T]):
    def __init__(self, inner_encoding: Encoding[T]):
        self._inner_encoding = inner_encoding
        self.values: list[Any] = []

    def unwrap(self, _tag_name: str) -> list[T]:
        return self.values

    def parse(self, node: XmlElement, parser: XmlParser):
        inner_container = self._inner_encoding.create_value_container()
        inner_container.parse(node, parser)

        self.values.append(inner_container.unwrap(node.tag))


def _none_decoder(_node: XmlElement, _parser: XmlParser) -> Any:
    raise NotImplementedError()


ENUM = TypeVar("ENUM", bound=Enum)
INT_ENUM = TypeVar("INT_ENUM", bound=IntEnum)


class ValueEncoding(Generic[T]):
    def __init__(self, target: type[T], decode: Decoder[T]):
        self.target = target
        self.decode = decode

    @staticmethod
    def for_enum(enum_type: type[ENUM]) -> ValueEncoding[ENUM]:
        def _decode(_node: XmlElement, parser: XmlParser) -> ENUM:
            raw = parser.parse_token()
            return enum_type(raw)

        return ValueEncoding(enum_type, _decode)

    @staticmethod
    def for_int_enum(enum_type: type[INT_ENUM]) -> ValueEncoding[INT_ENUM]:
        def _decode(_node: XmlElement, parser: XmlParser) -> INT_ENUM:
            raw = parser.parse_token()
            return enum_type(int(raw))

        return ValueEncoding(enum_type, _decode)

    def create_value_container(self) -> ValueContainer[T]:
        return ValueContainer(self.decode, is_optional=False)


class OptionalEncoding(Generic[T]):
    def __init__(self, inner_encoding: Encoding[T]):
        self._inner_encoding = inner_encoding

    @property
    def decode(self):
        return self._inner_encoding.decode

    def create_value_container(self) -> ValueContainer[T]:
        return ValueContainer(self._inner_encoding.decode, is_optional=True)


class ListEncoding(Generic[T]):
    def __init__(self, inner_encoding: Encoding[T]):
        self._inner_encoding = inner_encoding

    @property
    def decode(self):
        return self._inner_encoding.decode

    def create_value_container(self) -> ListContainer[T]:
        return ListContainer(self._inner_encoding)


Encoding = Union[ValueEncoding[T], OptionalEncoding[T], ListEncoding[T]]


def _parse_string(_node: XmlElement, parser: XmlParser) -> str:
    return parser.parse_value()


def _parse_int(_node: XmlElement, parser: XmlParser) -> int:
    return int(parser.parse_token())


def _parse_float(_node: XmlElement, parser: XmlParser) -> float:
    return float(parser.parse_token())


def _parse_datetime(_node: XmlElement, parser: XmlParser) -> datetime:
    return datetime.fromisoformat(parser.parse_token())


class Encodings:
    String = ValueEncoding(str, _parse_string)
    Integer = ValueEncoding(int, _parse_int)
    Float = ValueEncoding(float, _parse_float)
    Datetime = ValueEncoding(datetime, _parse_datetime)


class DocumentEncoding(Generic[T]):
    def __init__(self, encoding: Encoding[T], xml_tag: str):
        self._encoding = encoding
        self._xml_tag = xml_tag

    def parse(self, data: bytes) -> T:
        parser = XmlParser(data)

        node = parser.expect_child(self._xml_tag)

        value = self._encoding.decode(node, parser)
        if value is None:
            raise Exception(f"Empty node {self._xml_tag}")

        return value


def derive(
    attribute_type: type[T],
    local_name: str,
    namespace: Optional[str] = None,
    localns: Optional[dict[str, Any]] = None,
) -> DocumentEncoding[T]:
    encoding_cache: dict[Any, Encoding[Any]] = {}

    xml_tag = _resolve_full_tag(local_name, namespace)

    return DocumentEncoding(
        encoding=_derive(attribute_type, encoding_cache, localns, namespace),
        xml_tag=xml_tag,
    )


def _derive(
    attribute_type: Any,
    encoding_cache: dict[Any, Encoding[Any]],
    localns: Optional[dict[str, Any]],
    default_namespace: Optional[str],
) -> Encoding[Any]:
    if isinstance(attribute_type, str):
        raise Exception(
            "Do not use 'from __future__ import annotations' in the same file in which 'binary.derive()' is used."
        )

    if attribute_type in encoding_cache:
        return encoding_cache[attribute_type]
    elif dataclasses.is_dataclass(attribute_type):
        return _derive_dataclass(
            attribute_type, encoding_cache, localns, default_namespace
        )
    elif attribute_type is str:
        return Encodings.String
    elif attribute_type is int:
        return Encodings.Integer
    elif attribute_type is float:
        return Encodings.Float
    elif attribute_type is datetime:
        return Encodings.Datetime
    elif isclass(attribute_type) and issubclass(attribute_type, IntEnum):
        # NOTE(Felix): Check `IntEnum` first, as it is also a subclass
        # of `Enum` and would therefore also fulfill the next condition.
        return ValueEncoding.for_int_enum(attribute_type)
    elif isclass(attribute_type) and issubclass(attribute_type, Enum):
        return ValueEncoding.for_enum(attribute_type)
    elif typing.get_origin(attribute_type) is typing.Union:
        inner_type, *rest = typing.get_args(attribute_type)

        if len(rest) == 1 and rest[0] is type(None):
            return OptionalEncoding(
                _derive(inner_type, encoding_cache, localns, default_namespace)
            )
        else:
            raise TypeError(f"Unknown Union {attribute_type}")
    elif typing.get_origin(attribute_type) is list:
        inner_type = typing.get_args(attribute_type)[0]
        return ListEncoding(
            _derive(inner_type, encoding_cache, localns, default_namespace)
        )
    elif type(attribute_type) is typing.ForwardRef:
        raise Exception(f"Unresolved forward ref: {attribute_type}")
    else:
        raise TypeError(f"Missing annotation for type {attribute_type.__name__}")


def _derive_dataclass(
    cls: type[D],
    encoding_cache: dict[Any, Encoding[Any]],
    localns: Optional[dict[str, Any]],
    default_namespace: Optional[str],
) -> Encoding[D]:
    # Create a stub encoding and save it to the cache first.
    # This way, recursive uses of the same dataclass will reuse this
    # encoding, as it is already in the cache.
    # Later, update the decode function with the actual one.
    class_encoding = ValueEncoding(cls, decode=_none_decoder)
    encoding_cache[cls] = class_encoding

    type_hints = typing.get_type_hints(cls, localns=localns)

    fields = dataclasses.fields(cls)

    attribute_encodings: list[tuple[str, Encoding[Any]]] = []
    for field in fields:
        # NOTE(Felix): First extract the optional config for the field.
        # This uses the `field.type` object, as here `Annotated` is not
        # resolved.
        config, encoding = _get_metadata(field)

        if encoding is None:
            # NOTE(Felix): Use the fully resolve type here, to allow recursive
            # definitions.
            field_type = type_hints[field.name]
            encoding = _derive(field_type, encoding_cache, localns, default_namespace)

        field_tag = _get_tag(config, field.name, default_namespace)
        attribute_encodings.append((field_tag, encoding))

    def _decode(_node: XmlElement, parser: XmlParser) -> D:
        attributes = {
            xml_tag: encoding.create_value_container()
            for xml_tag, encoding in attribute_encodings
        }

        while (child := parser.next_child()) is not None:
            child_parser = attributes.get(child.tag)
            if child_parser is None:
                parser.skip_node()
                continue

            child_parser.parse(child, parser)

        return cls(
            *[attributes[xml_tag].unwrap(xml_tag) for xml_tag, _ in attribute_encodings]
        )

    class_encoding.decode = _decode
    return class_encoding


def _get_metadata(
    field: dataclasses.Field[T],
) -> tuple[Optional[Value], Optional[Encoding[T]]]:
    config = _get_field_config(field)
    encoding = _get_custom_encoding(field)

    return config, encoding


def _get_field_config(field: dataclasses.Field[Any]) -> Union[Value, None]:
    if typing.get_origin(field.type) is typing.Annotated:
        _annotated_type, *annotation_args = typing.get_args(field.type)

        for arg in annotation_args:
            if isinstance(arg, Value):
                return arg


def _get_custom_encoding(field: dataclasses.Field[T]) -> Optional[Encoding[T]]:
    if typing.get_origin(field.type) is typing.Annotated:
        _annotated_type, *annotation_args = typing.get_args(field.type)

        for arg in annotation_args:
            if isinstance(arg, (ValueEncoding, OptionalEncoding, ListEncoding)):
                return arg


def _get_tag(
    config: Union[Value, None],
    member_name: str,
    default_namespace: Optional[str],
) -> str:
    if isinstance(config, Value):
        if isinstance(config.namespace, _DefaultNamespace):
            namespace = default_namespace
        else:
            namespace = config.namespace

        return _resolve_full_tag(
            local_name=config.name or member_name,
            namespace=namespace,
        )
    else:
        return _resolve_full_tag(
            local_name=member_name,
            namespace=default_namespace,
        )


def _resolve_full_tag(local_name: str, namespace: Optional[str]) -> str:
    if namespace is None:
        return local_name
    else:
        return f"{{{namespace}}}{local_name}"
