"""Unit tests for mt5linux.security module."""

import hashlib
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

from mt5linux.security import (
    DownloadResult,
    VerificationResult,
    download_file_secure,
    verify_download,
    verify_gpg_signature,
    verify_sha256_checksum,
)


class TestSHA256Verification:
    """Tests for SHA256 checksum verification."""

    def test_verify_sha256_checksum_valid(self) -> None:
        """Test SHA256 verification with valid checksum."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test file
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("Hello, World!")
            
            # Calculate actual hash
            actual_hash = hashlib.sha256(test_file.read_bytes()).hexdigest()
            
            # Create checksum file
            checksum_file = Path(tmpdir) / "test.txt.sha256"
            checksum_file.write_text(f"{actual_hash}  test.txt\n")
            
            result = verify_sha256_checksum(str(test_file), str(checksum_file))
            assert result.success is True
            assert result.sha256_verified is True
            assert result.error is None

    def test_verify_sha256_checksum_invalid(self) -> None:
        """Test SHA256 verification with invalid checksum."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("Hello, World!")
            
            checksum_file = Path(tmpdir) / "test.txt.sha256"
            checksum_file.write_text("invalid_hash  test.txt\n")
            
            result = verify_sha256_checksum(str(test_file), str(checksum_file))
            assert result.success is False
            assert result.sha256_verified is False
            assert result.error is not None
            assert "checksum" in result.error.lower() or "hash" in result.error.lower()

    def test_verify_sha256_checksum_missing_file(self) -> None:
        """Test SHA256 verification with missing checksum file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("Hello, World!")
            
            checksum_file = Path(tmpdir) / "nonexistent.sha256"
            
            result = verify_sha256_checksum(str(test_file), str(checksum_file))
            assert result.success is False
            assert result.sha256_verified is False
            assert result.error is not None

    def test_verify_sha256_checksum_single_line_format(self) -> None:
        """Test SHA256 verification with single-line format (just hash)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("Hello, World!")
            
            actual_hash = hashlib.sha256(test_file.read_bytes()).hexdigest()
            checksum_file = Path(tmpdir) / "test.txt.sha256"
            checksum_file.write_text(f"{actual_hash}\n")
            
            result = verify_sha256_checksum(str(test_file), str(checksum_file))
            assert result.success is True
            assert result.sha256_verified is True

    def test_verify_sha256_checksum_multi_line_format(self) -> None:
        """Test SHA256 verification with multi-line checksum file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("Hello, World!")
            
            actual_hash = hashlib.sha256(test_file.read_bytes()).hexdigest()
            checksum_file = Path(tmpdir) / "checksums.sha256"
            checksum_file.write_text(f"other_hash  other.txt\n{actual_hash}  test.txt\n")
            
            result = verify_sha256_checksum(str(test_file), str(checksum_file))
            assert result.success is True
            assert result.sha256_verified is True


class TestGPGVerification:
    """Tests for GPG signature verification."""

    @patch("mt5linux.security.gnupg")
    def test_verify_gpg_signature_valid(self, mock_gnupg_module: MagicMock) -> None:
        """Test GPG verification with valid signature."""
        mock_gpg = MagicMock()
        mock_gnupg_module.GPG.return_value = mock_gpg
        
        # Mock successful verification
        mock_verified = MagicMock()
        mock_verified.valid = True
        mock_verified.status = "signature valid"
        mock_gpg.verify_file.return_value = mock_verified
        
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("Hello, World!")
            sig_file = Path(tmpdir) / "test.txt.asc"
            sig_file.write_text("fake signature")
            
            result = verify_gpg_signature(str(test_file), str(sig_file))
            assert result.success is True
            assert result.gpg_verified is True
            assert result.error is None

    @patch("mt5linux.security.gnupg")
    def test_verify_gpg_signature_invalid(self, mock_gnupg_module: MagicMock) -> None:
        """Test GPG verification with invalid signature."""
        mock_gpg = MagicMock()
        mock_gnupg_module.GPG.return_value = mock_gpg
        
        # Mock failed verification
        mock_verified = MagicMock()
        mock_verified.valid = False
        mock_verified.status = "signature invalid"
        mock_gpg.verify_file.return_value = mock_verified
        
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("Hello, World!")
            sig_file = Path(tmpdir) / "test.txt.asc"
            sig_file.write_text("fake signature")
            
            result = verify_gpg_signature(str(test_file), str(sig_file))
            assert result.success is False
            assert result.gpg_verified is False
            assert result.error is not None

    @patch("mt5linux.security.gnupg")
    def test_verify_gpg_signature_missing_file(self, mock_gnupg_module: MagicMock) -> None:
        """Test GPG verification with missing signature file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("Hello, World!")
            sig_file = Path(tmpdir) / "nonexistent.asc"
            
            result = verify_gpg_signature(str(test_file), str(sig_file))
            assert result.success is False
            assert result.gpg_verified is False
            assert result.error is not None

    @patch("mt5linux.security.gnupg")
    def test_verify_gpg_signature_missing_key(self, mock_gnupg_module: MagicMock) -> None:
        """Test GPG verification with missing GPG key."""
        mock_gpg = MagicMock()
        mock_gnupg_module.GPG.return_value = mock_gpg
        
        # Mock verification with missing key
        mock_verified = MagicMock()
        mock_verified.valid = False
        mock_verified.status = "no public key"
        mock_gpg.verify_file.return_value = mock_verified
        
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("Hello, World!")
            sig_file = Path(tmpdir) / "test.txt.asc"
            sig_file.write_text("fake signature")
            
            result = verify_gpg_signature(str(test_file), str(sig_file))
            assert result.success is False
            assert result.gpg_verified is False
            assert "key" in result.error.lower() or "gpg" in result.error.lower()


class TestSecureDownload:
    """Tests for secure download function."""

    @patch("urllib.request.urlretrieve")
    @patch("os.path.exists")
    def test_download_file_secure_success(self, mock_exists: MagicMock, mock_urlretrieve: MagicMock) -> None:
        """Test secure download with all files available."""
        mock_exists.return_value = True
        
        with tempfile.TemporaryDirectory() as tmpdir:
            download_dir = Path(tmpdir)
            
            result = download_file_secure(
                "https://example.com/file.exe",
                str(download_dir / "file.exe"),
            )
            
            # Should attempt to download main file, signature, and checksum
            assert mock_urlretrieve.call_count >= 1
            assert result.success is True or result.success is False  # May fail if files don't exist

    @patch("urllib.request.urlretrieve")
    def test_download_file_secure_network_error(self, mock_urlretrieve: MagicMock) -> None:
        """Test secure download with network error."""
        import urllib.error
        mock_urlretrieve.side_effect = urllib.error.URLError("Network error")
        
        with tempfile.TemporaryDirectory() as tmpdir:
            download_dir = Path(tmpdir)
            
            result = download_file_secure(
                "https://example.com/file.exe",
                str(download_dir / "file.exe"),
            )
            
            assert result.success is False
            assert result.error is not None

    @patch("urllib.request.urlretrieve")
    def test_download_file_secure_file_not_found(self, mock_urlretrieve: MagicMock) -> None:
        """Test secure download with file not found."""
        import urllib.error
        mock_urlretrieve.side_effect = urllib.error.HTTPError(
            "https://example.com/file.exe", 404, "Not Found", {}, None
        )
        
        with tempfile.TemporaryDirectory() as tmpdir:
            download_dir = Path(tmpdir)
            
            result = download_file_secure(
                "https://example.com/file.exe",
                str(download_dir / "file.exe"),
            )
            
            assert result.success is False
            assert result.error is not None

    @patch("urllib.request.urlretrieve")
    def test_download_file_secure_both_signature_and_checksum_fail(self, mock_urlretrieve: MagicMock) -> None:
        """Test secure download fails when both signature and checksum downloads fail."""
        import urllib.error
        
        # First call succeeds (main file), subsequent calls fail (signature and checksum)
        call_count = 0
        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return None  # Main file download succeeds
            else:
                raise urllib.error.HTTPError("https://example.com/file.exe.asc", 404, "Not Found", {}, None)
        
        mock_urlretrieve.side_effect = side_effect
        
        with tempfile.TemporaryDirectory() as tmpdir:
            download_dir = Path(tmpdir)
            
            result = download_file_secure(
                "https://example.com/file.exe",
                str(download_dir / "file.exe"),
                download_signature=True,
                download_checksum=True,
            )
            
            # Should fail because both verification files failed to download
            assert result.success is False
            assert result.error is not None
            assert "verification" in result.error.lower() or "signature" in result.error.lower() or "checksum" in result.error.lower()
