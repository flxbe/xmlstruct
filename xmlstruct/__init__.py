from __future__ import annotations

import dataclasses
import types
import typing
from datetime import datetime
from enum import Enum, IntEnum
from inspect import isclass
from typing import Any, Callable, Generic, Literal, Optional, TypeVar, Union

from .xml import (
    MissingAttribute,
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


@dataclasses.dataclass(frozen=True)
class Variant:
    """
    Annotate a Unino variant.
    Additional configuration of the behaviour is possible.

    ### `namespace`

    Set the namespace of the variant.
    This is `DefaultNamespace` by default, meaning that the optional global
    namespace will be used.

    Alternatively, either a `str` containing the actual namespace or
    `None` can be used to overwrite the global namespace.
    """

    name: str
    namespace: Optional[Namespace] = DefaultNamespace


@dataclasses.dataclass
class TextValue:
    """
    Annotate a dataclass member as the text value of the node.
    """

    pass


# The ValueDecoder must return an optional result to correctly deal with
# self-closing tags. When a tag is encountered, the decode function for that tag
# is called. To deal with optional content in a tag, the actually decoded value
# can therefore be empty.
# Required content is checked in the RequiredValueContainer whether it actually exists.
ValueDecoder = Callable[[XmlElement], T | None]

AttributeDecoder = Callable[[str], T]


def _none_decoder(_node: XmlElement) -> Any:
    raise NotImplementedError()


ENUM = TypeVar("ENUM", bound=Enum)
INT_ENUM = TypeVar("INT_ENUM", bound=IntEnum)


class _NoValue:
    pass


NoValue = _NoValue()


class RequiredValueEncoding(Generic[T]):
    def __init__(self, decode: ValueDecoder[T]):
        self.decode = decode

    @staticmethod
    def for_enum(enum_type: type[ENUM]) -> RequiredValueEncoding[ENUM]:
        def _decode(node: XmlElement) -> ENUM | None:
            value = node.text
            if value is None:
                return None

            raw = parse_token(value)
            return enum_type(raw)

        return RequiredValueEncoding(_decode)

    @staticmethod
    def for_int_enum(enum_type: type[INT_ENUM]) -> RequiredValueEncoding[INT_ENUM]:
        def _decode(node: XmlElement) -> INT_ENUM | None:
            value = node.text
            if value is None:
                return None

            raw = parse_token(value)
            return enum_type(int(raw))

        return RequiredValueEncoding(_decode)

    def create_empty_value(self) -> None:
        return None

    def parse(self, current_value: T | None, node: XmlElement) -> T:
        if current_value is not None:
            raise Exception(f"Duplicate value {node.tag}")

        current_value = self.decode(node)
        if current_value is None:
            raise Exception(f"Missing value {node.tag}")

        return current_value

    def unwrap(self, current_value: T | None, tag_name: str) -> T:
        if current_value is None:
            raise Exception(f"Missing value {tag_name}")

        return current_value


class OptionalValueEncoding(Generic[T]):
    def __init__(self, inner_encoding: Encoding[T]):
        self._inner_encoding = inner_encoding

    @property
    def decode(self):
        return self._inner_encoding.decode

    def create_empty_value(self) -> _NoValue:
        return NoValue

    def parse(self, current_value: T | None | _NoValue, node: XmlElement) -> T | None:
        if current_value is not NoValue:
            raise Exception(f"Duplicate value {node.tag}")

        return self.decode(node)

    def unwrap(self, current_value: T | None | _NoValue, tag_name: str) -> T | None:
        if current_value is NoValue:
            return None

        return current_value  # type: ignore


class ListEncoding(Generic[T]):
    def __init__(self, inner_encoding: Encoding[T]):
        self._inner_encoding = inner_encoding

    @property
    def decode(self):
        return self._inner_encoding.decode

    def create_empty_value(self) -> list[T]:
        return []

    def parse(self, current_value: list[T], node: XmlElement) -> list[T]:
        inner_value: Any = self._inner_encoding.create_empty_value()
        inner_value = self._inner_encoding.parse(inner_value, node)
        inner_value = self._inner_encoding.unwrap(inner_value, node.tag)

        current_value.append(inner_value)
        return current_value

    def unwrap(self, current_value: list[T], tag_name: str) -> list[T]:
        return current_value


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


def _parse_string(node: XmlElement) -> str | None:
    return node.text


def _parse_int(node: XmlElement) -> int | None:
    value = node.text
    if value is None:
        return None

    return int(parse_token(value))


def _parse_float(node: XmlElement) -> float | None:
    value = node.text
    if value is None:
        return None

    return float(parse_token(value))


def _parse_datetime(node: XmlElement) -> datetime | None:
    value = node.text
    if value is None:
        return None

    return datetime.fromisoformat(parse_token(value))


class Encodings:
    String = RequiredValueEncoding(_parse_string)
    Integer = RequiredValueEncoding(_parse_int)
    Float = RequiredValueEncoding(_parse_float)
    Datetime = RequiredValueEncoding(_parse_datetime)


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
    attribute_type: type | typing.ForwardRef,
    localns: Optional[dict[str, Any]],
    default_namespace: Optional[str],
) -> AttributeEncoding[Any]:
    if isinstance(attribute_type, str):
        raise Exception(
            "Do not use 'from __future__ import annotations' in the same file in which 'binary.derive()' is used."
        )

    if typing.get_origin(attribute_type) is typing.Annotated:
        attribute_type = typing.get_args(attribute_type)[0]

    if type(attribute_type) is typing.ForwardRef:
        raise Exception(f"Unresolved forward ref: {attribute_type}")

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
    elif _is_union(attribute_type):
        inner_types = typing.get_args(attribute_type)

        optional_type = _get_optional_type(inner_types)
        if optional_type is not None:
            return OptionalAttributeEncoding(
                _derive_attribute(optional_type, localns, default_namespace)
            )

        raise TypeError(f"Unknown Union {attribute_type}")
    else:
        raise TypeError(f"Missing annotation for type {attribute_type.__name__}")


def _is_union(attribute_type: type) -> bool:
    origin = typing.get_origin(attribute_type)

    return (
        # Check explicit unions, like `Optional[str]`
        origin is typing.Union
        or
        # Check implicit unions, like `str | None`
        origin is types.UnionType
    )


def _derive(
    attribute_type: type | typing.ForwardRef,
    encoding_cache: dict[Any, Encoding[Any]],
    localns: Optional[dict[str, Any]],
    default_namespace: Optional[str],
) -> Encoding[Any]:
    if isinstance(attribute_type, str):
        raise Exception(
            "Do not use 'from __future__ import annotations' in the same file in which 'binary.derive()' is used."
        )

    if typing.get_origin(attribute_type) is typing.Annotated:
        attribute_type = typing.get_args(attribute_type)[0]

    if type(attribute_type) is typing.ForwardRef:
        raise Exception(f"Unresolved forward ref: {attribute_type}")

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
    elif _is_union(attribute_type):
        inner_types = typing.get_args(attribute_type)

        optional_type = _get_optional_type(inner_types)
        if optional_type is not None:
            return OptionalValueEncoding(
                _derive(optional_type, encoding_cache, localns, default_namespace)
            )

        return _derive_union(inner_types, encoding_cache, localns, default_namespace)
    elif typing.get_origin(attribute_type) is list:
        inner_type = typing.get_args(attribute_type)[0]
        return ListEncoding(
            _derive(inner_type, encoding_cache, localns, default_namespace)
        )
    else:
        raise TypeError(f"Missing annotation for type {attribute_type.__name__}")


def _get_optional_type(inner_types: tuple[Any, ...]) -> type | None:
    if len(inner_types) != 2:
        return None

    if inner_types[0] is type(None):
        return inner_types[1]
    elif inner_types[1] is type(None):
        return inner_types[0]

    return None


def _derive_union(
    variants: tuple[Any, ...],
    encoding_cache: dict[Any, Encoding[Any]],
    localns: Optional[dict[str, Any]],
    default_namespace: Optional[str],
) -> Encoding[T]:
    variant_encodings: dict[str, Encoding[T]] = {}

    for variant in variants:
        if typing.get_origin(variant) is not typing.Annotated:
            raise XmlStructError(f"Missing union variant annotation for {variant}")

        variant_type, *type_args = typing.get_args(variant)
        variant_tag = _get_variant_tag(type_args, default_namespace)
        if variant_tag is None:
            raise XmlStructError(f"Missing union variant annotation for {variant}")

        variant_encodings[variant_tag] = _derive(
            variant_type, encoding_cache, localns, default_namespace
        )

    def _decode(node: XmlElement):
        if len(node) != 1:
            raise XmlStructError(f"Expected only single child in union {node.tag}")

        child = node[0]
        variant_encoding = variant_encodings.get(child.tag)
        if variant_encoding is None:
            raise XmlStructError(f"Unknown variant {child.tag} in union {node.tag}")

        return variant_encoding.decode(child)

    return RequiredValueEncoding(decode=_decode)


def _derive_dataclass(
    cls: type[D],
    encoding_cache: dict[Any, Encoding[Any]],
    localns: Optional[dict[str, Any]],
    default_namespace: Optional[str],
) -> Encoding[D]:
    # Create a stub encoding and save it to the cache first.
    # This way, recursive usage of the same dataclass will reuse this
    # encoding, as it is already in the cache.
    # Later, update the decode function with the actual one.
    class_encoding = RequiredValueEncoding(decode=_none_decoder)
    encoding_cache[cls] = class_encoding

    type_hints = typing.get_type_hints(
        cls,
        localns=localns,
        include_extras=True,
    )

    fields = dataclasses.fields(cls)

    # TODO: Somehow distinguish between attributes and values to allow name collisions
    # TODO: Detect duplicate names
    argument_names: list[str] = []
    value_encodings: list[tuple[str, Encoding[Any]]] = []
    text_value_encoding: tuple[str, Encoding[Any]] | None = None
    attribute_encodings: list[tuple[str, AttributeEncoding[Any]]] = []
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
            value_encodings.append((field_tag, encoding))
            argument_names.append(field_tag)
        elif isinstance(metadata, TextValueMetadata):
            if text_value_encoding is not None:
                raise XmlStructError(f"TextValue can only be used once [{cls}]")

            encoding = metadata.encoding
            if encoding is None:
                field_type = type_hints[field.name]
                encoding = _derive(
                    field_type, encoding_cache, localns, default_namespace
                )

            text_value_encoding = (field.name, encoding)
            argument_names.append(field.name)
        else:
            encoding = metadata.encoding
            if encoding is None:
                field_type = type_hints[field.name]
                encoding = _derive_attribute(field_type, localns, default_namespace)

            field_tag = _get_tag(metadata.attribute, field.name, default_namespace)
            attribute_encodings.append((field_tag, encoding))
            argument_names.append(field_tag)

    def _decode(node: XmlElement) -> D:
        values = {
            xml_tag: (encoding, encoding.create_empty_value())
            for xml_tag, encoding in value_encodings
        }

        for child in node:
            value_state = values.get(child.tag)
            if value_state is not None:
                encoding, value = value_state
                value = encoding.parse(value, child)  # type: ignore
                values[child.tag] = (encoding, value)

        arguments = {
            xml_tag: encoding.unwrap(value, xml_tag)  # type: ignore
            for xml_tag, (encoding, value) in values.items()
        }

        if text_value_encoding is not None:
            arguments[text_value_encoding[0]] = text_value_encoding[1].decode(node)

        for attribute_name, encoding in attribute_encodings:
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


@dataclasses.dataclass
class TextValueMetadata(Generic[T]):
    encoding: Optional[Encoding[T]]


def _get_metadata(
    field: dataclasses.Field[T],
) -> AttributeMetadata[T] | ValueMetadata[T] | TextValueMetadata[T]:
    config = _get_field_config(field)

    if isinstance(config, Value):
        encoding = _get_value_encoding(field)
        return ValueMetadata(value=config, encoding=encoding)
    elif isinstance(config, TextValue):
        encoding = _get_value_encoding(field)
        return TextValueMetadata(encoding=encoding)
    elif isinstance(config, Attribute):
        encoding = _get_attribute_encoding(field)
        return AttributeMetadata(attribute=config, encoding=encoding)
    else:
        encoding = _get_attribute_encoding(field)
        if encoding is not None:
            return AttributeMetadata(attribute=None, encoding=encoding)
        else:
            return ValueMetadata(value=None, encoding=_get_value_encoding(field))


def _get_field_config(
    field: dataclasses.Field[Any],
) -> Union[Value, Attribute, TextValue, None]:
    if typing.get_origin(field.type) is typing.Annotated:
        _annotated_type, *annotation_args = typing.get_args(field.type)

        for arg in annotation_args:
            if isinstance(arg, Value):
                return arg
            elif isinstance(arg, Attribute):
                return arg
            elif isinstance(arg, TextValue):
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


def _get_variant_tag(
    type_args: list[Any],
    default_namespace: Optional[str],
) -> str | None:
    for arg in type_args:
        if isinstance(
            arg,
            Variant,
        ):
            if isinstance(arg.namespace, _DefaultNamespace):
                namespace = default_namespace
            else:
                namespace = arg.namespace

            return _resolve_full_tag(arg.name, namespace)

    return None


def _resolve_full_tag(local_name: str, namespace: Optional[str]) -> str:
    if namespace is None:
        return local_name
    else:
        return f"{{{namespace}}}{local_name}"
