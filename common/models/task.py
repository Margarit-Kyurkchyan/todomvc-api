from dataclasses import dataclass
from rococo.models.versioned_model import VersionedModel


@dataclass
class Task(VersionedModel):
    person_id: str = None
    title: str = None
    completed: bool = False

