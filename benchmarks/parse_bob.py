from dataclasses import dataclass
import xmlstruct


with open("./benchmarks/S60000011V2.1_xdf2.xml", "rb") as file:
    data = file.read()


@dataclass
class SchemaMessage:
    pass


XDF3_NS = "urn:xoev-de:fim:standard:xdatenfelder_2"
XDF3_SCHEMA_MESSAGE = "xdatenfelder.stammdatenschema.0102"

SchemaMessageEncoding = xmlstruct.derive(
    SchemaMessage, local_name=XDF3_SCHEMA_MESSAGE, namespace=XDF3_NS
)

SchemaMessageEncoding.parse(data)
