"""The only subset of Django's Storage API that app code may use (SPEC.md §4.3)."""

from typing import Protocol

from django.core.files import File


class MediaStore(Protocol):
    def save(self, name: str, content: File) -> str: ...

    def url(self, name: str) -> str: ...

    def exists(self, name: str) -> bool: ...

    def delete(self, name: str) -> None: ...
