from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from enum import IntEnum

from xmlstruct import derive

XDF3_NS = "urn:xoev-de:fim:standard:xdatenfelder_3.0.0"
XDF3_SCHEMA_MESSAGE = "xdatenfelder.stammdatenschema.0102"


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


@dataclass(slots=True)
class AllgemeineAngaben:
    # identifier: Identifier
    name: str
    beschreibung: Optional[str]
    definition: Optional[str]
    # bezug: list[Rechtsbezug]
    freigabestatus: FreigabeStatus
    # status_gesetzt_am: date | None
    statusGesetztDurch: Optional[str]
    # gueltig_ab: date | None
    # gueltig_bis: date | None
    # versionshinweis: din91379.StringLatin | None
    # veroeffentlichungsdatum: date | None
    # letzte_aenderung: datetime
    # relation: list[Relation]
    # stichwort: list[Stichwort]


@dataclass(slots=True)
class Schema(AllgemeineAngaben):
    bezeichnung: str
    hilfetext: Optional[str]


@dataclass(slots=True)
class MessageHeader:
    nachrichtID: str
    erstellungszeitpunkt: datetime


@dataclass(slots=True)
class SchemaMessage:
    header: MessageHeader
    stammdatenschema: Schema


SchemaMessageEncoding = derive(
    SchemaMessage, local_name=XDF3_SCHEMA_MESSAGE, namespace=XDF3_NS
)

with open("./tests/xdf3.xml", "rb") as f:
    data = f.read()


def test_xdf3():
    message = SchemaMessageEncoding.parse(data)

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
