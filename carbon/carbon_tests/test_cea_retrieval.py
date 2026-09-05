from pathlib import Path
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from carbon.services.emission_import.retrieval import (
    CEASourceRetriever,
)


class CEASourceRetrieverTests(SimpleTestCase):
    """
    Tests for CEA source discovery and file retrieval.
    """

    def test_discover_latest_cea_version(self):
        html = """
        <html>
            <body>
                <a href="/old.xlsx">
                    Baseline Carbon Dioxide Emission Database
                    Version 20.0 OUTDATED
                </a>

                <a href="/v21.xlsx">
                    Baseline Carbon Dioxide Emission Database
                    Version 21.0
                </a>
            </body>
        </html>
        """

        mock_response = Mock()
        mock_response.text = html
        mock_response.url = (
            "https://cea.nic.in/cdm-co2-baseline-database/"
        )
        mock_response.raise_for_status.return_value = None

        with patch(
            "carbon.services.emission_import.retrieval.requests.get",
            return_value=mock_response,
        ):
            result = CEASourceRetriever.discover_latest()

        self.assertEqual(
            result.version,
            "Version 21.0",
        )

        self.assertEqual(
            result.source_url,
            "https://cea.nic.in/v21.xlsx",
        )

    @patch(
        "carbon.services.emission_import.retrieval.CEASourceRetriever"
        ".discover_latest"
    )
    @patch(
        "carbon.services.emission_import.retrieval.requests.get"
    )
    def test_download_latest(
        self,
        mock_get,
        mock_discover,
    ):
        mock_discover.return_value = Mock(
            version="Version 21.0",
            source_url="https://cea.nic.in/v21.xlsx",
        )

        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.iter_content.return_value = [
            b"test",
            b"workbook",
        ]

        mock_get.return_value.__enter__.return_value = (
            mock_response
        )

        with self.subTest("download succeeds"):
            metadata, file_path = (
                CEASourceRetriever.download_latest()
            )

            try:
                self.assertEqual(
                    metadata.version,
                    "Version 21.0",
                )

                self.assertTrue(
                    isinstance(file_path, Path)
                )

                self.assertTrue(
                    file_path.exists()
                )

                self.assertEqual(
                    file_path.read_bytes(),
                    b"testworkbook",
                )

            finally:
                if file_path.exists():
                    file_path.unlink()

    def test_discover_latest_fails_when_no_valid_version_exists(self):
        html = """
        <html>
            <body>
                <a href="/v20.xlsx">
                    Baseline Carbon Dioxide Emission Database
                    Version 20.0 OUTDATED
                </a>
            </body>
        </html>
        """

        mock_response = Mock()
        mock_response.text = html
        mock_response.url = (
            "https://cea.nic.in/cdm-co2-baseline-database/"
        )
        mock_response.raise_for_status.return_value = None

        with patch(
            "carbon.services.emission_import.retrieval.requests.get",
            return_value=mock_response,
        ):
            with self.assertRaises(RuntimeError):
                CEASourceRetriever.discover_latest()

    def test_discover_latest_handles_request_failure(self):
        import requests

        with patch(
            "carbon.services.emission_import.retrieval.requests.get",
            side_effect=requests.RequestException(
                "Network failure"
            ),
        ):
            with self.assertRaises(RuntimeError):
                CEASourceRetriever.discover_latest()