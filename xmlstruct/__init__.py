from __future__ import annotations

from datetime import datetime
import dataclasses
from inspect import isclass
import typing
from typing import Any, Callable, Generic, Optional, TypeVar, Union
from enum import Enum, IntEnum

from .xml import (
    MissingAttribute,
    MissingValue,
    UnexpectedChildNodeException,
    XmlDataSource,
    XmlElement,
    parse_token,
    parse_xml,
)


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
class Attribute:
    """
    Annotate a dataclass member as an attribute value.
    Additional configuration of the behaviour is possible.

    ### `namespace`

    Set the namespace of the child element.
    This is `DefaultNamespace` by default, meaning that the optional global
    namespace will be used.

    Alternatively, either a `str` containing the actual namespace or
    `None` can be used to overwrite the global namespace.
    """

    name: Union[str, None] = None
    namespace: Optional[Namespace] = DefaultNamespace


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
    `None` can be used to overwrite the global namespace.
    """

    name: Union[str, None] = None
    namespace: Optional[Namespace] = DefaultNamespace


# Make the decoder always return an optional field, so
# that empty of self-closing tags can be interpreted as
# empty values from the decoder.
# Values not wrapped in `Optional` are then handled with an
# extra test for `None` to ensure the value was actually there.
ValueDecoder = Callable[[XmlElement], T]
# Encoder = Callable[[T, ValueList, ByteOrder], None]

AttributeDecoder = Callable[[str], T]


class ValueContainer(Generic[T]):
    """
    Container to temporarily store a parsed value.
    """

    __slots__ = ["_value", "_decode"]

    def __init__(self, decode: ValueDecoder[T]):
        self._value: Optional[T] = None
        self._decode = decode

    def unwrap(self, tag_name: str) -> T:
        if self._value is None:
            raise Exception(f"Missing node {tag_name}")

        return self._value

    def parse(self, node: XmlElement):
        if self._value is not None:
            raise Exception("Duplicate Value")

        self._value = self._decode(node)
        assert self._value is not None


class OptionalValueContainer(Generic[T]):
    """
    Container to temporarily store an optional parsed value.
    """

    __slots__ = ["_value", "_filled", "_decode"]

    def __init__(self, decode: ValueDecoder[T]):
        self._value: Optional[T] = None
        self._filled = False
        self._decode = decode

    def unwrap(self, _tag_name: str) -> Optional[T]:
        return self._value

    def parse(self, node: XmlElement):
        if self._filled:
            raise Exception("Duplicate Value")

        self._value = self._decode(node)
        assert self._value is not None

        self._filled = True


class ListContainer(Generic[T]):
    __slots__ = ["_inner_encoding", "_values"]

    def __init__(self, inner_encoding: Encoding[T]):
        self._inner_encoding = inner_encoding
        self._values: list[Any] = []

    def unwrap(self, _tag_name: str) -> list[T]:
        return self._values

    def parse(self, node: XmlElement):
        inner_container = self._inner_encoding.create_value_container()
        inner_container.parse(node)

        self._values.append(inner_container.unwrap(node.tag))


def _none_decoder(_node: XmlElement) -> Any:
    raise NotImplementedError()


ENUM = TypeVar("ENUM", bound=Enum)
INT_ENUM = TypeVar("INT_ENUM", bound=IntEnum)


class RequiredValueEncoding(Generic[T]):
    def __init__(self, target: type[T], decode: ValueDecoder[T]):
        self.target = target
        self.decode = decode

    @staticmethod
    def for_enum(enum_type: type[ENUM]) -> RequiredValueEncoding[ENUM]:
        def _decode(node: XmlElement) -> ENUM:
            raw = parse_token(node)
            return enum_type(raw)

        return RequiredValueEncoding(enum_type, _decode)

    @staticmethod
    def for_int_enum(enum_type: type[INT_ENUM]) -> RequiredValueEncoding[INT_ENUM]:
        def _decode(node: XmlElement) -> INT_ENUM:
            raw = parse_token(node)
            return enum_type(int(raw))

        return RequiredValueEncoding(enum_type, _decode)

    def create_value_container(self) -> ValueContainer[T]:
        return ValueContainer(self.decode)


class OptionalValueEncoding(Generic[T]):
    def __init__(self, inner_encoding: Encoding[T]):
        self._inner_encoding = inner_encoding

    @property
    def decode(self):
        return self._inner_encoding.decode

    def create_value_container(self) -> OptionalValueContainer[T]:
        return OptionalValueContainer(self._inner_encoding.decode)


class ListEncoding(Generic[T]):
    def __init__(self, inner_encoding: Encoding[T]):
        self._inner_encoding = inner_encoding

    @property
    def decode(self):
        return self._inner_encoding.decode

    def create_value_container(self) -> ListContainer[T]:
        return ListContainer(self._inner_encoding)


Encoding = Union[RequiredValueEncoding[T], OptionalValueEncoding[T], ListEncoding[T]]


class RequiredAttributeEncoding(Generic[T]):
    def __init__(self, decode: AttributeDecoder[T]):
        self._decode = decode

    @staticmethod
    def for_enum(enum_type: type[ENUM]) -> RequiredAttributeEncoding[ENUM]:
        def _decode(value: str) -> ENUM:
            return enum_type(value)

        return RequiredAttributeEncoding(_decode)

    @staticmethod
    def for_int_enum(enum_type: type[INT_ENUM]) -> RequiredAttributeEncoding[INT_ENUM]:
        def _decode(value: str) -> INT_ENUM:
            return enum_type(int(value))

        return RequiredAttributeEncoding(_decode)

    def decode(self, tag_name: str, value: str | None) -> T:
        if value is None:
            # TODO: somehow insert name
            raise MissingAttribute(tag_name)

        return self._decode(value)


class OptionalAttributeEncoding(Generic[T]):
    def __init__(self, inner_encoding: AttributeEncoding[T]):
        self._inner_encoding = inner_encoding

    def decode(self, tag_name: str, value: str | None) -> T | None:
        if value is None:
            return None
        else:
            return self._inner_encoding.decode(tag_name, value)


AttributeEncoding = Union[RequiredAttributeEncoding[T], OptionalAttributeEncoding[T]]


def _parse_string(node: XmlElement) -> str:
    return node.text or ""


def _parse_int(node: XmlElement) -> int:
    return int(parse_token(node))


def _parse_float(node: XmlElement) -> float:
    return float(parse_token(node))


def _parse_datetime(node: XmlElement) -> datetime:
    return datetime.fromisoformat(parse_token(node))


class Encodings:
    String = RequiredValueEncoding(str, _parse_string)
    Integer = RequiredValueEncoding(int, _parse_int)
    Float = RequiredValueEncoding(float, _parse_float)
    Datetime = RequiredValueEncoding(datetime, _parse_datetime)


class AttributeEncodings:
    String = RequiredAttributeEncoding(lambda v: v)
    Integer = RequiredAttributeEncoding(lambda v: int(v))
    Float = RequiredAttributeEncoding(lambda v: float(v))
    Datetime = RequiredAttributeEncoding(lambda v: datetime.fromisoformat(v))


class DocumentEncoding(Generic[T]):
    def __init__(self, encoding: Encoding[T], xml_tag: str):
        self._encoding = encoding
        self._xml_tag = xml_tag

    def parse(self, data: XmlDataSource) -> T:
        node = parse_xml(data)

        if node.tag != self._xml_tag:
            raise UnexpectedChildNodeException(node.tag)

        value = self._encoding.decode(node)
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


def _derive_attribute(
    attribute_type: Any,
    localns: Optional[dict[str, Any]],
    default_namespace: Optional[str],
) -> AttributeEncoding[Any]:
    if isinstance(attribute_type, str):
        raise Exception(
            "Do not use 'from __future__ import annotations' in the same file in which 'binary.derive()' is used."
        )

    if attribute_type is str:
        return AttributeEncodings.String
    elif attribute_type is int:
        return AttributeEncodings.Integer
    elif attribute_type is float:
        return AttributeEncodings.Float
    elif attribute_type is datetime:
        return AttributeEncodings.Datetime
    elif isclass(attribute_type) and issubclass(attribute_type, IntEnum):
        # NOTE(Felix): Check `IntEnum` first, as it is also a subclass
        # of `Enum` and would therefore also fulfill the next condition.
        return RequiredAttributeEncoding.for_int_enum(attribute_type)
    elif isclass(attribute_type) and issubclass(attribute_type, Enum):
        return RequiredAttributeEncoding.for_enum(attribute_type)
    elif typing.get_origin(attribute_type) is typing.Union:
        inner_type, *rest = typing.get_args(attribute_type)

        if len(rest) == 1 and rest[0] is type(None):
            return OptionalAttributeEncoding(
                _derive_attribute(inner_type, localns, default_namespace)
            )
        else:
            raise TypeError(f"Unknown Union {attribute_type}")
    elif type(attribute_type) is typing.ForwardRef:
        raise Exception(f"Unresolved forward ref: {attribute_type}")
    else:
        raise TypeError(f"Missing annotation for type {attribute_type.__name__}")


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
        return RequiredValueEncoding.for_int_enum(attribute_type)
    elif isclass(attribute_type) and issubclass(attribute_type, Enum):
        return RequiredValueEncoding.for_enum(attribute_type)
    elif typing.get_origin(attribute_type) is typing.Union:
        inner_type, *rest = typing.get_args(attribute_type)

        if len(rest) == 1 and rest[0] is type(None):
            return OptionalValueEncoding(
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
    class_encoding = RequiredValueEncoding(cls, decode=_none_decoder)
    encoding_cache[cls] = class_encoding

    type_hints = typing.get_type_hints(cls, localns=localns)

    fields = dataclasses.fields(cls)

    # TODO: Somehow distinguish between attributes and values to allow name collisions
    # TODO: Detect duplicate names
    argument_names: list[str] = []
    value_encodings: dict[str, Encoding[Any]] = {}
    attribute_encodings: dict[str, AttributeEncoding[Any]] = {}
    for field in fields:
        # NOTE(Felix): First extract the optional config for the field.
        # This uses the `field.type` object, as here `Annotated` is not
        # resolved.
        metadata = _get_metadata(field)

        if isinstance(metadata, ValueMetadata):
            encoding = metadata.encoding
            if encoding is None:
                field_type = type_hints[field.name]
                encoding = _derive(
                    field_type, encoding_cache, localns, default_namespace
                )

            field_tag = _get_tag(metadata.value, field.name, default_namespace)
            value_encodings[field_tag] = encoding
            argument_names.append(field_tag)
        else:
            encoding = metadata.encoding
            if encoding is None:
                field_type = type_hints[field.name]
                encoding = _derive_attribute(field_type, localns, default_namespace)

            field_tag = _get_tag(metadata.attribute, field.name, default_namespace)
            attribute_encodings[field_tag] = encoding
            argument_names.append(field_tag)

    def _decode(node: XmlElement) -> D:
        value_containers = {
            xml_tag: encoding.create_value_container()
            for xml_tag, encoding in value_encodings.items()
        }

        for child in node:
            child_parser = value_containers.get(child.tag)
            if child_parser is None:
                continue

            child_parser.parse(child)

        arguments = {
            xml_tag: container.unwrap(xml_tag)
            for xml_tag, container in value_containers.items()
        }

        for attribute_name, encoding in attribute_encodings.items():
            value = node.get(attribute_name)
            arguments[attribute_name] = encoding.decode(attribute_name, value)

        return cls(*[arguments[xml_tag] for xml_tag in argument_names])

    class_encoding.decode = _decode
    return class_encoding


@dataclasses.dataclass
class AttributeMetadata(Generic[T]):
    attribute: Optional[Attribute]
    encoding: Optional[AttributeEncoding[T]]


@dataclasses.dataclass
class ValueMetadata(Generic[T]):
    value: Optional[Value]
    encoding: Optional[Encoding[T]]


def _get_metadata(
    field: dataclasses.Field[T],
) -> AttributeMetadata[T] | ValueMetadata[T]:
    config = _get_field_config(field)

    if isinstance(config, Value):
        encoding = _get_value_encoding(field)
        return ValueMetadata(value=config, encoding=encoding)
    elif isinstance(config, Attribute):
        encoding = _get_attribute_encoding(field)
        return AttributeMetadata(attribute=config, encoding=encoding)
    else:
        encoding = _get_attribute_encoding(field)
        if encoding is not None:
            return AttributeMetadata(attribute=None, encoding=encoding)
        else:
            return ValueMetadata(value=None, encoding=_get_value_encoding(field))


def _get_field_config(field: dataclasses.Field[Any]) -> Union[Value, Attribute, None]:
    if typing.get_origin(field.type) is typing.Annotated:
        _annotated_type, *annotation_args = typing.get_args(field.type)

        for arg in annotation_args:
            if isinstance(arg, Value):
                return arg
            elif isinstance(arg, Attribute):
                return arg


def _get_value_encoding(
    field: dataclasses.Field[T],
) -> Optional[Encoding[T]]:
    if typing.get_origin(field.type) is typing.Annotated:
        _annotated_type, *annotation_args = typing.get_args(field.type)

        for arg in annotation_args:
            if isinstance(
                arg,
                (RequiredValueEncoding, OptionalValueEncoding, ListEncoding),
            ):
                return arg


def _get_attribute_encoding(
    field: dataclasses.Field[T],
) -> Optional[AttributeEncoding[T]]:
    if typing.get_origin(field.type) is typing.Annotated:
        _annotated_type, *annotation_args = typing.get_args(field.type)

        for arg in annotation_args:
            if isinstance(
                arg,
                (RequiredAttributeEncoding, OptionalAttributeEncoding),
            ):
                return arg


def _get_tag(
    config: Union[Value, Attribute, None],
    member_name: str,
    default_namespace: Optional[str],
) -> str:
    if isinstance(config, (Value, Attribute)):
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
