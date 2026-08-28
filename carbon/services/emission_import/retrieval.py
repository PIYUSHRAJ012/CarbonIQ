from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import urljoin

import requests
from html.parser import HTMLParser
import re

class _CEALinkParser(HTMLParser):
    """
    Minimal HTML parser used to discover the latest CEA
    database resource from the official index page.
    """

    def __init__(self):
        super().__init__()
        self.matches = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "a":
            return

        attrs_dict = dict(attrs)
        href = attrs_dict.get("href")

        if not href:
            return

        self._current_href = href
        self._current_text = []

    def handle_data(self, data):
        if hasattr(self, "_current_href"):
            self._current_text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() != "a":
            return

        if not hasattr(self, "_current_href"):
            return

        text = " ".join(self._current_text).strip()

        self.matches.append(
            {
                "href": self._current_href,
                "text": text,
            }
        )

        del self._current_href
        del self._current_text


@dataclass(frozen=True)
class CEADownload:
    """
    Information about a CEA database resource discovered
    from the official CEA website.
    """

    version: str
    source_url: str


class CEASourceRetriever:
    """
    Retrieves the latest CEA CO2 Baseline Database resource
    from the official CEA website.

    This class is responsible only for source discovery and
    file retrieval. Workbook parsing belongs to CEASourceAdapter.
    """

    INDEX_URL = (
        "https://cea.nic.in/cdm-co2-baseline-database/"
        "?lang=en"
    )

    REQUEST_TIMEOUT = 30

    @classmethod
    def discover_latest(cls) -> CEADownload:
        """
        Discover the newest non-outdated CEA database link.

        Raises:
            RuntimeError: If the official CEA page cannot be
            reached or no suitable database link is found.
        """

        try:
            response = requests.get(
                cls.INDEX_URL,
                timeout=cls.REQUEST_TIMEOUT,
                headers={
                    "User-Agent": (
                        "CarbonIQ/1.0 "
                        "(Emission Factor Update Service)"
                    )
                },
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise RuntimeError(
                "Unable to retrieve the official CEA database page."
            ) from exc

        parser = _CEALinkParser()
        parser.feed(response.text)

        candidates = []

        for match in parser.matches:
            text = " ".join(match["text"].split())

            if not text:
                continue

            normalized_text = text.lower()

            if "baseline carbon dioxide emission database" not in normalized_text:
                continue

            if "version" not in normalized_text:
                continue

            if "outdated" in normalized_text:
                continue

            version_match = re.search(
                r"version\s+([0-9]+(?:\.[0-9]+)?)",
                text,
                flags=re.IGNORECASE,
            )

            if version_match is None:
                continue

            version_text = version_match.group(1)

            try:
                version_number = float(version_text)
            except ValueError:
                continue

            href = urljoin(
                response.url,
                match["href"],
            )

            candidates.append(
                (version_number, version_text, href)
            )

        if not candidates:
            raise RuntimeError(
                "No current CEA emission-factor database "
                "was discovered."
            )

        version_number, version_text, source_url = max(
            candidates,
            key=lambda item: item[0],
        )

        return CEADownload(
            version=f"Version {version_text}",
            source_url=source_url,
        )

    @classmethod
    def download_latest(
        cls,
        destination_dir: str | Path | None = None,
    ) -> tuple[CEADownload, Path]:
        """
        Discover and download the latest CEA resource.

        Returns:
            Tuple containing discovered metadata and local path.

        Raises:
            RuntimeError: If retrieval/download fails.
        """

        latest = cls.discover_latest()

        if destination_dir is None:
            temp_file = NamedTemporaryFile(
                suffix=".xlsx",
                delete=False,
            )
            destination = Path(temp_file.name)
            temp_file.close()
        else:
            destination_dir = Path(destination_dir)
            destination_dir.mkdir(
                parents=True,
                exist_ok=True,
            )

            destination = (
                destination_dir
                / "cea_latest.xlsx"
            )

        try:
            with requests.get(
                latest.source_url,
                timeout=cls.REQUEST_TIMEOUT,
                headers={
                    "User-Agent": (
                        "CarbonIQ/1.0 "
                        "(Emission Factor Update Service)"
                    )
                },
                stream=True,
            ) as response:
                response.raise_for_status()

                with destination.open("wb") as output:
                    for chunk in response.iter_content(
                        chunk_size=8192
                    ):
                        if chunk:
                            output.write(chunk)

        except requests.RequestException as exc:
            if destination.exists():
                destination.unlink()

            raise RuntimeError(
                "Unable to download the latest CEA "
                "emission-factor resource."
            ) from exc

        return latest, destination