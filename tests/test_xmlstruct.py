from dataclasses import dataclass
from datetime import datetime, timezone, date
from enum import Enum, IntEnum
from typing import Annotated, Optional, Union

from xmlstruct import (
    Attribute,
    RequiredAttributeEncoding,
    RequiredValueEncoding,
    TextValue,
    Value,
    derive,
    Variant,
)
from xmlstruct.xml import XmlElement, parse_token


def test_should_parse_primitive_types():
    DATA = b"""
    <data>
        <a>A</a>
        <b>1</b>
        <c>1.1</c>
        <d>2020-09-01T00:00:00.000000Z</d>
        <e>2020-09-01</e>
    </data>
    """

    @dataclass
    class Data:
        a: str
        b: int
        c: float
        d: datetime
        e: date

    DataEncoding = derive(Data, local_name="data")

    instance = DataEncoding.parse(DATA)

    assert instance == Data(
        a="A",
        b=1,
        c=1.1,
        d=datetime(
            2020,
            9,
            1,
            hour=0,
            minute=0,
            second=0,
            tzinfo=timezone.utc,
        ),
        e=date(2020, 9, 1),
    )


def test_should_parse_nested_structs():
    DATA = b"""
    <outer>
        <inner>
            <a>A</a>
            <b>B</b>
        </inner>
    </outer>
    """

    @dataclass
    class Inner:
        a: str
        b: str

    @dataclass
    class Outer:
        inner: Inner

    OuterEncoding = derive(Outer, local_name="outer")

    instance = OuterEncoding.parse(DATA)

    assert instance == Outer(
        inner=Inner(
            a="A",
            b="B",
        )
    )


def test_should_parse_optional_fields():
    DATA = b"""
    <wrapper>
        <a>A</a>
        <b></b>
        <c/>
    </wrapper>
    """

    @dataclass
    class Wrapper:
        a: str | None
        b: None | str
        c: Optional[str]
        d: Optional[str]

    WrapperEncoding = derive(Wrapper, local_name="wrapper")

    instance = WrapperEncoding.parse(DATA)

    assert instance == Wrapper(
        a="A",
        b=None,
        c=None,
        d=None,
    )


def test_should_parse_unions():
    DATA = b"""
    <wrapper>
        <implicit>
            <a>a</a>
        </implicit>
        <explicit>
            <b>b</b>
        </explicit>
    </wrapper>
    """

    @dataclass
    class A:
        value: Annotated[str, TextValue()]

    @dataclass
    class B:
        value: Annotated[str, TextValue()]

    @dataclass
    class Wrapper:
        implicit: Annotated[A, Variant("a")] | Annotated[B, Variant("b")]
        explicit: Union[
            Annotated[A, Variant("a")],
            Annotated[B, Variant("b")],
        ]

    WrapperEncoding = derive(Wrapper, local_name="wrapper")

    instance = WrapperEncoding.parse(DATA)

    assert instance == Wrapper(
        implicit=A("a"),
        explicit=B("b"),
    )


def test_should_parse_recursive_structs():
    DATA = b"""
    <schema>
        <group>
            <name>Group 1</name>
            <group>
                <name>Group 1.1</name>
            </group>
        </group>
    </schema>
    """

    @dataclass
    class Group:
        name: str
        group: Optional["Group"]

    @dataclass
    class Schema:
        group: Group

    SchemaEncoding = derive(Schema, local_name="schema", localns=locals())

    instance = SchemaEncoding.parse(DATA)

    assert instance == Schema(
        group=Group(
            name="Group 1",
            group=Group(
                name="Group 1.1",
                group=None,
            ),
        )
    )


def test_should_parse_lists():
    DATA = b"""
    <list>
        <item>A</item>
        <item>B</item>
        <item>C</item>
    </list>
    """

    @dataclass
    class List:
        items: Annotated[list[str], Value(name="item")]

    ListEncoding = derive(
        List,
        local_name="list",
    )

    instance = ListEncoding.parse(DATA)

    assert instance == List(items=["A", "B", "C"])


def test_should_parse_list_with_custom_item_encoding():
    DATA = b"""
    <list>
        <item>1</item>
    </list>
    """

    def _decode(node: XmlElement) -> int | None:
        value = node.text
        if value is None:
            return None

        return int(parse_token(value)) + 1

    IncEncoding = RequiredValueEncoding(decode=_decode)

    @dataclass
    class List:
        item: list[Annotated[int, IncEncoding]]

    ListEncoding = derive(
        List,
        local_name="list",
    )

    instance = ListEncoding.parse(DATA)

    assert instance == List(item=[2])


def test_should_use_value_config():
    DATA = b"""
    <test:schema xmlns:test="urn:test">
        <test:a>A</test:a>
        <test:b>B</test:b>
        <c>C</c>
    </test:schema>
    """

    @dataclass
    class Schema:
        a: Annotated[str, Value(namespace="urn:test")]
        not_b: Annotated[str, Value(namespace="urn:test", name="b")]
        c: Annotated[str, Value(namespace=None)]

    SchemaEncoding = derive(
        Schema,
        local_name="schema",
        namespace="urn:test",
    )

    instance = SchemaEncoding.parse(DATA)

    assert instance == Schema(
        a="A",
        not_b="B",
        c="C",
    )


def test_should_use_default_namespace():
    DATA = b"""
    <test:schema xmlns:test="urn:test">
        <test:a>A</test:a>
        <test:b>B</test:b>
        <c>C</c>
    </test:schema>
    """

    @dataclass
    class Schema:
        a: Annotated[str, Value(namespace="urn:test")]
        b: str
        c: Annotated[str, Value(namespace=None)]

    SchemaEncoding = derive(
        Schema,
        local_name="schema",
        namespace="urn:test",
    )

    instance = SchemaEncoding.parse(DATA)

    assert instance == Schema(
        a="A",
        b="B",
        c="C",
    )


def test_should_parse_enums():
    DATA = b"""
    <data>
        <a>a</a>
        <b>b</b>
        <one>1</one>
        <two>2</two>
    </data>
    """

    class StringEnum(Enum):
        A = "a"
        B = "b"

    class NumericEnum(IntEnum):
        ONE = 1
        TWO = 2

    @dataclass
    class Data:
        a: StringEnum
        b: StringEnum
        one: NumericEnum
        two: NumericEnum

    DataEncoding = derive(Data, local_name="data")

    instance = DataEncoding.parse(DATA)

    assert instance == Data(
        a=StringEnum.A,
        b=StringEnum.B,
        one=NumericEnum.ONE,
        two=NumericEnum.TWO,
    )


def test_should_use_custom_encoding():
    DATA = b"""
    <data>
        <a>1</a>
    </data>
    """

    def _decode(node: XmlElement) -> int | None:
        value = node.text
        if value is None:
            return None

        return int(parse_token(value)) + 1

    IncEncoding = RequiredValueEncoding(decode=_decode)

    @dataclass
    class Data:
        a: Annotated[int, IncEncoding]

    DataEncoding = derive(Data, local_name="data")

    instance = DataEncoding.parse(DATA)

    assert instance == Data(a=2)


def test_should_parse_attributes():
    DATA = b"""
    <test:schema xmlns:test="urn:test" test:a="A" test:b="B" c="C" />
    """

    @dataclass
    class Schema:
        a: Annotated[str | None, Attribute()]
        not_b: Annotated[str, Attribute(name="b")]
        c: Annotated[str, Attribute(namespace=None)]

    SchemaEncoding = derive(
        Schema,
        local_name="schema",
        namespace="urn:test",
    )

    instance = SchemaEncoding.parse(DATA)

    assert instance == Schema(
        a="A",
        not_b="B",
        c="C",
    )


def test_should_use_custom_attribute_encoding():
    DATA = b'<data a="1" />'

    def _decode(str) -> int:
        return int(str) + 1

    IncEncoding = RequiredAttributeEncoding(decode=_decode)

    @dataclass
    class Data:
        a: Annotated[int, IncEncoding]

    DataEncoding = derive(Data, local_name="data")

    instance = DataEncoding.parse(DATA)

    assert instance == Data(a=2)


def test_should_parse_attributes_mixed_with_text_value():
    DATA = b"""
    <schema a="a">value</schema>
    """

    @dataclass
    class Schema:
        a: Annotated[str, Attribute()]
        value: Annotated[str, TextValue()]

    SchemaEncoding = derive(Schema, local_name="schema")

    instance = SchemaEncoding.parse(DATA)

    assert instance == Schema(a="a", value="value")


def test_should_parse_optional_text_value():
    DATA = b"<schema />"

    @dataclass
    class Schema:
        value: Annotated[str | None, TextValue()]

    SchemaEncoding = derive(Schema, local_name="schema")

    instance = SchemaEncoding.parse(DATA)

    assert instance == Schema(value=None)
