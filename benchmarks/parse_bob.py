from typing import Optional
from datetime import datetime
from dataclasses import dataclass
import xmlstruct


@dataclass(slots=True)
class MessageHeader:
    nachrichtID: str
    erstellungszeitpunkt: datetime


@dataclass
class AllgemeineAngaben:
    name: str
    beschreibung: Optional[str]
    definition: Optional[str]
    fachlicherErsteller: Optional[str]


@dataclass
class Schema(AllgemeineAngaben):
    hilfetext: Optional[str]


@dataclass(slots=True)
class SchemaMessage:
    header: MessageHeader
    stammdatenschema: Schema


XDF3_NS = "urn:xoev-de:fim:standard:xdatenfelder_2"
XDF3_SCHEMA_MESSAGE = "xdatenfelder.stammdatenschema.0102"

SchemaMessageEncoding = xmlstruct.derive(
    SchemaMessage, local_name=XDF3_SCHEMA_MESSAGE, namespace=XDF3_NS
)


with open("./benchmarks/S60000011V2.1_xdf2.xml", "rb") as file:
    SchemaMessageEncoding.parse(file)
