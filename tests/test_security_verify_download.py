"""Additional tests for verify_download function."""

import hashlib
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mt5linux.security import verify_download


class TestVerifyDownload:
    """Tests for combined verification function."""

    def test_verify_download_sha256_only(self) -> None:
        """Test verify_download with SHA256 checksum only."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("Hello, World!")
            
            actual_hash = hashlib.sha256(test_file.read_bytes()).hexdigest()
            checksum_file = Path(tmpdir) / "test.txt.sha256"
            checksum_file.write_text(f"{actual_hash}  test.txt\n")
            
            result = verify_download(
                str(test_file),
                checksum_path=str(checksum_file),
                require_sha256=True,
            )
            assert result.success is True
            assert result.sha256_verified is True

    @patch("mt5linux.security.gnupg")
    def test_verify_download_both_gpg_and_sha256(self, mock_gnupg_module: MagicMock) -> None:
        """Test verify_download with both GPG and SHA256."""
        mock_gpg = MagicMock()
        mock_gnupg_module.GPG.return_value = mock_gpg
        
        mock_verified = MagicMock()
        mock_verified.valid = True
        mock_gpg.verify_file.return_value = mock_verified
        
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("Hello, World!")
            
            actual_hash = hashlib.sha256(test_file.read_bytes()).hexdigest()
            checksum_file = Path(tmpdir) / "test.txt.sha256"
            checksum_file.write_text(f"{actual_hash}  test.txt\n")
            
            sig_file = Path(tmpdir) / "test.txt.asc"
            sig_file.write_text("fake signature")
            
            result = verify_download(
                str(test_file),
                signature_path=str(sig_file),
                checksum_path=str(checksum_file),
                require_gpg=False,
                require_sha256=True,
            )
            assert result.success is True
            assert result.gpg_verified is True
            assert result.sha256_verified is True

    def test_verify_download_verification_failure(self) -> None:
        """Test verify_download when verification fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("Hello, World!")
            
            checksum_file = Path(tmpdir) / "test.txt.sha256"
            checksum_file.write_text("invalid_hash  test.txt\n")
            
            result = verify_download(
                str(test_file),
                checksum_path=str(checksum_file),
                require_sha256=True,
            )
            assert result.success is False
            assert result.sha256_verified is False
            assert result.error is not None

    def test_verify_download_neither_signature_nor_checksum(self) -> None:
        """Test verify_download when neither signature nor checksum is provided."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("Hello, World!")
            
            # No signature or checksum provided
            result = verify_download(
                str(test_file),
                require_sha256=False,
            )
            # Should fail because no verification can be performed
            assert result.success is False
            assert result.error is not None

    def test_verify_download_checksum_multiple_hashes_no_match(self) -> None:
        """Test verify_download with checksum file containing multiple hashes, none matching filename."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("Hello, World!")
            
            # Create checksum file with multiple hashes, none matching our filename
            actual_hash = hashlib.sha256(test_file.read_bytes()).hexdigest()
            checksum_file = Path(tmpdir) / "checksums.sha256"
            checksum_file.write_text(f"other_hash_1  other_file1.txt\n{actual_hash}\nother_hash_2  other_file2.txt\n")
            
            # Should use the single hash without filename (middle line)
            result = verify_download(
                str(test_file),
                checksum_path=str(checksum_file),
                require_sha256=True,
            )
            assert result.success is True
            assert result.sha256_verified is True
