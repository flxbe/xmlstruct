from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, TypeVar, Annotated
from enum import Enum, IntEnum

from xmlstruct import Encoding, RequiredValueEncoding, derive
from xmlstruct.xml import XmlElement

XDF3_NS = "urn:xoev-de:fim:standard:xdatenfelder_3.0.0"
XDF3_SCHEMA_MESSAGE = "xdatenfelder.stammdatenschema.0102"


E = TypeVar("E", bound=Enum)


def create_code_encoding(cls: type[E]) -> Encoding[E]:
    """
    Create a specialized encoding to parse nested code items of the form

    ```xml
    <outer>
        <code>Actual Value</code>
    </outer>
    ```

    directly into an Enum, without needing to parse the nested structure
    into a custom dataclass with only one member `code`.
    """

    if issubclass(cls, IntEnum):
        enum_encoding = RequiredValueEncoding.for_int_enum(cls)
    else:
        enum_encoding = RequiredValueEncoding.for_enum(cls)

    def _decode_code(node: XmlElement) -> E:
        container = enum_encoding.create_value_container()

        for child in node:
            if child.tag == "code":
                container.parse(child)

        value = container.unwrap(node.tag)
        assert value is not None

        return value

    return RequiredValueEncoding(decode=_decode_code)


class FreigabeStatus(IntEnum):
    """
    See: https://www.xrepository.de/details/urn:xoev-de:xprozess:codeliste:status
    """

    IN_PLANUNG = 1
    IN_BEARBEITUNG = 2
    ENTWURF = 3
    METHODISCH_FREIGEGEBEN = 4
    FACHLICH_FREIGEGEBEN_SILBER = 5
    FACHLICH_FREIGEGEBEN_GOLD = 6
    INAKTIV = 7
    VORGESEHEN_ZUM_LOESCHEN = 8


FreigabeStatusEncoding = create_code_encoding(FreigabeStatus)


@dataclass
class AllgemeineAngaben:
    # identifier: Identifier
    name: str
    beschreibung: Optional[str]
    definition: Optional[str]
    # bezug: list[Rechtsbezug]
    freigabestatus: Annotated[FreigabeStatus, FreigabeStatusEncoding]
    # status_gesetzt_am: date | None
    statusGesetztDurch: Optional[str]
    # gueltig_ab: date | None
    # gueltig_bis: date | None
    # versionshinweis: din91379.StringLatin | None
    # veroeffentlichungsdatum: date | None
    # letzte_aenderung: datetime
    # relation: list[Relation]
    # stichwort: list[Stichwort]


@dataclass
class Schema(AllgemeineAngaben):
    bezeichnung: str
    hilfetext: Optional[str]


@dataclass
class MessageHeader:
    nachrichtID: str
    erstellungszeitpunkt: datetime


@dataclass
class SchemaMessage:
    header: MessageHeader
    stammdatenschema: Schema


SchemaMessageEncoding = derive(
    SchemaMessage, local_name=XDF3_SCHEMA_MESSAGE, namespace=XDF3_NS
)


def test_xdf3():
    with open("./tests/xdf3.xml", "rb") as f:
        message = SchemaMessageEncoding.parse(f)

    assert message == SchemaMessage(
        header=MessageHeader(
            nachrichtID="abcd1234",
            erstellungszeitpunkt=datetime(
                2020,
                9,
                1,
                hour=0,
                minute=0,
                second=0,
                tzinfo=timezone.utc,
            ),
        ),
        stammdatenschema=Schema(
            name="Test",
            beschreibung="Eine Beschreibung",
            definition="Eine Definition",
            freigabestatus=FreigabeStatus.FACHLICH_FREIGEGEBEN_GOLD,
            statusGesetztDurch="Test",
            bezeichnung="Eine Bezeichnung",
            hilfetext="Ein Hilfetext",
        ),
    )
