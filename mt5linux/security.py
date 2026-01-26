"""Security utilities for download verification (GPG signatures and SHA256 checksums)."""

import hashlib
import re
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

try:
    import gnupg
except ImportError:
    gnupg = None  # type: ignore

try:
    from loguru import logger
except ImportError:
    import logging

    logger = logging.getLogger(__name__)

try:
    from rich.console import Console
except ImportError:
    Console = None  # type: ignore

# Initialize rich console if available
_console = Console() if Console else None

# Fallback echo function
def echo(message: str) -> None:
    """Echo function that uses rich if available, otherwise print."""
    if _console:
        _console.print(message)
    else:
        print(message)


@dataclass
class VerificationResult:
    """Result of file verification (GPG and/or SHA256)."""

    success: bool
    gpg_verified: bool
    sha256_verified: bool
    error: Optional[str] = None
    recovery_suggestion: Optional[str] = None


@dataclass
class DownloadResult:
    """Result of secure download operation."""

    success: bool
    file_path: Optional[str] = None
    signature_path: Optional[str] = None
    checksum_path: Optional[str] = None
    error: Optional[str] = None
    recovery_suggestion: Optional[str] = None


def _get_signature_url(file_url: str, try_sig: bool = False) -> str:
    """
    Get GPG signature file URL from main file URL.

    Args:
        file_url: URL of the main file
        try_sig: If True, try .sig extension instead of .asc

    Returns:
        URL of GPG signature file (.asc or .sig extension)
    """
    ext = ".sig" if try_sig else ".asc"
    # Try replacing extension if file has one, otherwise append
    if "." in file_url.split("/")[-1]:
        base_url = file_url.rsplit(".", 1)[0]
        return base_url + ext
    return file_url + ext


def _get_checksum_url(file_url: str, try_sha256sum: bool = False) -> str:
    """
    Get SHA256 checksum file URL from main file URL.

    Args:
        file_url: URL of the main file
        try_sha256sum: If True, try .sha256sum extension instead of .sha256

    Returns:
        URL of SHA256 checksum file (.sha256 or .sha256sum extension)
    """
    ext = ".sha256sum" if try_sha256sum else ".sha256"
    # Try replacing extension if file has one, otherwise append
    if "." in file_url.split("/")[-1]:
        base_url = file_url.rsplit(".", 1)[0]
        return base_url + ext
    return file_url + ext


def download_file_secure(
    file_url: str,
    output_path: str,
    download_signature: bool = True,
    download_checksum: bool = True,
) -> DownloadResult:
    """
    Download a file securely with signature and checksum files.

    Args:
        file_url: URL of the file to download
        output_path: Local path where file should be saved
        download_signature: Whether to download GPG signature file
        download_checksum: Whether to download SHA256 checksum file

    Returns:
        DownloadResult with download status and file paths
    """
    logger.info(f"Starting secure download: {file_url}")
    echo(f"  Downloading file from {file_url}...")

    file_path = Path(output_path)
    signature_path = None
    checksum_path = None

    try:
        # Download main file
        try:
            urllib.request.urlretrieve(file_url, str(file_path))
            logger.info(f"Downloaded main file to: {file_path}")
            echo(f"  [bold green]Downloaded:[/bold green] {file_path.name}")
        except urllib.error.URLError as e:
            error_msg = f"Failed to download file from {file_url}: {e}"
            logger.error(error_msg)
            return DownloadResult(
                success=False,
                error=error_msg,
                recovery_suggestion="Check internet connection and try again",
            )
        except OSError as e:
            error_msg = f"Failed to save file to {file_path}: {e}"
            logger.error(error_msg)
            return DownloadResult(
                success=False,
                error=error_msg,
                recovery_suggestion="Check file permissions and disk space",
            )

        # Download signature file if requested (try .asc first, then .sig)
        if download_signature:
            sig_path = file_path.with_suffix(file_path.suffix + ".asc")
            signature_downloaded = False
            for try_sig in [False, True]:  # Try .asc, then .sig
                sig_url = _get_signature_url(file_url, try_sig=try_sig)
                if try_sig:
                    sig_path = file_path.with_suffix(file_path.suffix + ".sig")
                try:
                    urllib.request.urlretrieve(sig_url, str(sig_path))
                    signature_path = str(sig_path)
                    signature_downloaded = True
                    logger.info(f"Downloaded signature file to: {sig_path}")
                    echo(f"  [bold green]Downloaded signature:[/bold green] {sig_path.name}")
                    break
                except urllib.error.HTTPError as e:
                    if e.code == 404:
                        if try_sig:  # Last attempt failed
                            logger.warning(f"Signature file not found at {sig_url} (tried .asc and .sig), continuing without GPG verification")
                        # Continue to try .sig if .asc failed
                    else:
                        if try_sig:  # Last attempt failed
                            logger.warning(f"Failed to download signature file: {e}")
                        # Continue to try .sig if .asc failed
                except urllib.error.URLError as e:
                    if try_sig:  # Last attempt failed
                        logger.warning(f"Failed to download signature file: {e}")
                    # Continue to try .sig if .asc failed
                except Exception as e:
                    if try_sig:  # Last attempt failed
                        logger.warning(f"Unexpected error downloading signature: {e}")
                    # Continue to try .sig if .asc failed

        # Download checksum file if requested (try .sha256 first, then .sha256sum)
        if download_checksum:
            checksum_file_path = file_path.with_suffix(file_path.suffix + ".sha256")
            checksum_downloaded = False
            for try_sha256sum in [False, True]:  # Try .sha256, then .sha256sum
                checksum_url = _get_checksum_url(file_url, try_sha256sum=try_sha256sum)
                if try_sha256sum:
                    checksum_file_path = file_path.with_suffix(file_path.suffix + ".sha256sum")
                try:
                    urllib.request.urlretrieve(checksum_url, str(checksum_file_path))
                    checksum_path = str(checksum_file_path)
                    checksum_downloaded = True
                    logger.info(f"Downloaded checksum file to: {checksum_file_path}")
                    echo(f"  [bold green]Downloaded checksum:[/bold green] {checksum_file_path.name}")
                    break
                except urllib.error.HTTPError as e:
                    if e.code == 404:
                        if try_sha256sum:  # Last attempt failed
                            logger.warning(f"Checksum file not found at {checksum_url} (tried .sha256 and .sha256sum), continuing without SHA256 verification")
                        # Continue to try .sha256sum if .sha256 failed
                    else:
                        if try_sha256sum:  # Last attempt failed
                            logger.warning(f"Failed to download checksum file: {e}")
                        # Continue to try .sha256sum if .sha256 failed
                except urllib.error.URLError as e:
                    if try_sha256sum:  # Last attempt failed
                        logger.warning(f"Failed to download checksum file: {e}")
                    # Continue to try .sha256sum if .sha256 failed
                except Exception as e:
                    if try_sha256sum:  # Last attempt failed
                        logger.warning(f"Unexpected error downloading checksum: {e}")
                    # Continue to try .sha256sum if .sha256 failed

        # Security check: At least one verification file must be downloaded if requested
        if download_signature and download_checksum:
            if signature_path is None and checksum_path is None:
                error_msg = "Failed to download both signature and checksum files - cannot verify file integrity"
                logger.error(error_msg)
                return DownloadResult(
                    success=False,
                    error=error_msg,
                    recovery_suggestion="Check internet connection and verify signature/checksum files are available at the download location",
                )
        elif download_signature and signature_path is None:
            error_msg = "Failed to download signature file - cannot verify file integrity"
            logger.error(error_msg)
            return DownloadResult(
                success=False,
                error=error_msg,
                recovery_suggestion="Check internet connection and verify signature file is available at the download location",
            )
        elif download_checksum and checksum_path is None:
            error_msg = "Failed to download checksum file - cannot verify file integrity"
            logger.error(error_msg)
            return DownloadResult(
                success=False,
                error=error_msg,
                recovery_suggestion="Check internet connection and verify checksum file is available at the download location",
            )

        return DownloadResult(
            success=True,
            file_path=str(file_path),
            signature_path=signature_path,
            checksum_path=checksum_path,
        )

    except Exception as e:
        error_msg = f"Unexpected error during secure download: {e}"
        logger.error(error_msg, exc_info=True)
        return DownloadResult(
            success=False,
            error=error_msg,
            recovery_suggestion="Retry the download or contact support if issue persists",
        )


def verify_gpg_signature(file_path: str, signature_path: str) -> VerificationResult:
    """
    Verify GPG signature of a file.

    Args:
        file_path: Path to the file to verify
        signature_path: Path to the GPG signature file

    Returns:
        VerificationResult with verification status
    """
    logger.info(f"Verifying GPG signature: {file_path}")

    if gnupg is None:
        error_msg = "python-gnupg library not available, cannot verify GPG signature"
        logger.error(error_msg)
        return VerificationResult(
            success=False,
            gpg_verified=False,
            sha256_verified=False,
            error=error_msg,
            recovery_suggestion="Install python-gnupg library: pip install python-gnupg",
        )

    file_path_obj = Path(file_path)
    signature_path_obj = Path(signature_path)

    # Check if files exist
    if not file_path_obj.exists():
        error_msg = f"File not found: {file_path}"
        logger.error(error_msg)
        return VerificationResult(
            success=False,
            gpg_verified=False,
            sha256_verified=False,
            error=error_msg,
            recovery_suggestion="Ensure file was downloaded successfully",
        )

    if not signature_path_obj.exists():
        error_msg = f"Signature file not found: {signature_path}"
        logger.error(error_msg)
        return VerificationResult(
            success=False,
            gpg_verified=False,
            sha256_verified=False,
            error=error_msg,
            recovery_suggestion="Download signature file or disable GPG verification",
        )

    try:
        # Initialize GPG
        gpg = gnupg.GPG()

        # Check signature file is not empty
        sig_size = signature_path_obj.stat().st_size
        if sig_size < 100:
            error_msg = f"Signature file appears to be empty or invalid: {signature_path} (size: {sig_size} bytes)"
            logger.error(error_msg)
            return VerificationResult(
                success=False,
                gpg_verified=False,
                sha256_verified=False,
                error=error_msg,
                recovery_suggestion="Re-download the signature file from Python.org",
            )

        # Verify signature using python-gnupg
        # First, try reading the signature file to ensure it's valid
        try:
            with open(signature_path, "rb") as sig_file:
                signature_data = sig_file.read()
            if not signature_data:
                error_msg = f"Signature file is empty: {signature_path}"
                logger.error(error_msg)
                return VerificationResult(
                    success=False,
                    gpg_verified=False,
                    sha256_verified=False,
                    error=error_msg,
                    recovery_suggestion="Re-download the signature file from Python.org",
                )
            logger.debug(f"Signature file size: {len(signature_data)} bytes")
            # Check if it looks like a GPG signature (should start with -----BEGIN PGP)
            if not signature_data.startswith(b"-----BEGIN PGP"):
                logger.warning("Signature file doesn't start with PGP header, but continuing...")
        except Exception as e:
            error_msg = f"Could not read signature file: {e}"
            logger.error(error_msg)
            return VerificationResult(
                success=False,
                gpg_verified=False,
                sha256_verified=False,
                error=error_msg,
                recovery_suggestion="Re-download the signature file from Python.org",
            )
        
        # Use command-line gpg as primary method (more reliable for detached signatures)
        # python-gnupg can be unreliable with detached signatures
        try:
            logger.debug("Verifying GPG signature using command-line gpg...")
            result = subprocess.run(
                ["gpg", "--verify", str(signature_path), file_path],
                capture_output=True,
                text=True,
                timeout=30,
            )
            
            # GPG returns 0 on success, but also returns 0 if signature is good but key is untrusted
            # We need to check both return code and stderr/stdout
            if result.returncode == 0:
                # Check if verification was actually successful
                output = result.stdout + result.stderr
                if "Good signature" in output or "gpg: Good signature" in output:
                    logger.info("GPG signature verified successfully using command-line gpg")
                    if _console:
                        _console.print("  [bold green]GPG signature verified[/bold green]")
                    return VerificationResult(
                        success=True,
                        gpg_verified=True,
                        sha256_verified=False,
                    )
                elif "BAD signature" in output or "gpg: BAD signature" in output:
                    error_msg = "GPG signature verification failed: BAD signature"
                    logger.error(error_msg)
                    return VerificationResult(
                        success=False,
                        gpg_verified=False,
                        sha256_verified=False,
                        error=error_msg,
                        recovery_suggestion="The signature does not match the file. File may be corrupted or tampered with.",
                    )
                else:
                    # Return code 0 but unclear status - log and check
                    logger.warning(f"GPG returned 0 but unclear status: {output[:200]}")
            
            # Non-zero return code or no "Good signature" - verification failed
            error_output = result.stderr if result.stderr else result.stdout
            error_msg = f"GPG verification failed: {error_output[:500]}"
            logger.error(error_msg)
            
            # Try to extract key ID from error message
            key_match = re.search(r'([0-9A-F]{16,40})', error_output, re.IGNORECASE)
            recovery = "Import the GPG public key for the signer"
            if key_match:
                key_id = key_match.group(1)
                recovery = f"Import the GPG key: gpg --keyserver keyserver.ubuntu.com --recv-keys {key_id}"
            elif "No public key" in error_output or "no public key" in error_output:
                recovery = "The GPG key used to sign this file is not in your keyring. Import it from a keyserver."
            elif "signature expected but not found" in error_output.lower():
                recovery = "The signature file format may be incorrect. Try re-downloading the signature file."
            
            return VerificationResult(
                success=False,
                gpg_verified=False,
                sha256_verified=False,
                error=error_msg,
                recovery_suggestion=recovery,
            )
        except FileNotFoundError:
            error_msg = "gpg command not found. Install GPG to verify signatures."
            logger.error(error_msg)
            return VerificationResult(
                success=False,
                gpg_verified=False,
                sha256_verified=False,
                error=error_msg,
                recovery_suggestion="Install GPG: sudo apt install gnupg (or equivalent for your system)",
            )
        except subprocess.TimeoutExpired:
            error_msg = "GPG verification timed out"
            logger.error(error_msg)
            return VerificationResult(
                success=False,
                gpg_verified=False,
                sha256_verified=False,
                error=error_msg,
                recovery_suggestion="GPG verification took too long. Check your GPG keyring.",
            )
        except Exception as e:
            logger.warning(f"Command-line gpg verification failed: {e}, trying python-gnupg as fallback...")
            # Fallback to python-gnupg if command-line gpg fails
            if gnupg:
                try:
                    gpg_instance = gnupg.GPG()
                    with open(file_path, "rb") as f:
                        verified = gpg_instance.verify_file(f, str(signature_path))
                    logger.debug(f"python-gnupg verification status: {verified.status if verified else 'None'}")
                    
                    if verified and verified.valid:
                        logger.info("GPG signature verified successfully using python-gnupg")
                        if _console:
                            _console.print("  [bold green]GPG signature verified[/bold green]")
                        return VerificationResult(
                            success=True,
                            gpg_verified=True,
                            sha256_verified=False,
                        )
                    else:
                        error_msg = f"python-gnupg verification failed: {verified.status if verified else 'No status'}"
                        logger.error(error_msg)
                        recovery = "Verify GPG key is imported or contact support if issue persists"
                        if verified and verified.status:
                            status_lower = verified.status.lower()
                            if "no public key" in status_lower or "key not found" in status_lower:
                                key_match = re.search(r'([0-9A-F]{16,40})', verified.status, re.IGNORECASE)
                                if key_match:
                                    key_id = key_match.group(1)
                                    recovery = f"Import the GPG key: gpg --keyserver keyserver.ubuntu.com --recv-keys {key_id}"
                        return VerificationResult(
                            success=False,
                            gpg_verified=False,
                            sha256_verified=False,
                            error=error_msg,
                            recovery_suggestion=recovery,
                        )
                except Exception as e2:
                    logger.error(f"python-gnupg fallback also failed: {e2}")
                    return VerificationResult(
                        success=False,
                        gpg_verified=False,
                        sha256_verified=False,
                        error=f"Both command-line gpg and python-gnupg failed: {e}, {e2}",
                        recovery_suggestion="Check GPG installation and keyring",
                    )
            else:
                return VerificationResult(
                    success=False,
                    gpg_verified=False,
                    sha256_verified=False,
                    error=f"Command-line gpg failed and python-gnupg not available: {e}",
                    recovery_suggestion="Install GPG or python-gnupg library",
                )
        
        # This should never be reached - all code paths above return
        error_msg = "GPG verification reached unexpected code path"
        logger.error(error_msg)
        return VerificationResult(
            success=False,
            gpg_verified=False,
            sha256_verified=False,
            error=error_msg,
            recovery_suggestion="Check GPG installation and signature file",
        )

    except Exception as e:
        error_msg = f"Error during GPG verification: {e}"
        logger.error(error_msg, exc_info=True)
        return VerificationResult(
            success=False,
            gpg_verified=False,
            sha256_verified=False,
            error=error_msg,
            recovery_suggestion="Check GPG installation and keyring, or contact support",
        )


def verify_sha256_checksum(file_path: str, checksum_path: str) -> VerificationResult:
    """
    Verify SHA256 checksum of a file.

    Args:
        file_path: Path to the file to verify
        checksum_path: Path to the SHA256 checksum file

    Returns:
        VerificationResult with verification status
    """
    logger.info(f"Verifying SHA256 checksum: {file_path}")

    file_path_obj = Path(file_path)
    checksum_path_obj = Path(checksum_path)

    # Check if files exist
    if not file_path_obj.exists():
        error_msg = f"File not found: {file_path}"
        logger.error(error_msg)
        return VerificationResult(
            success=False,
            gpg_verified=False,
            sha256_verified=False,
            error=error_msg,
            recovery_suggestion="Ensure file was downloaded successfully",
        )

    if not checksum_path_obj.exists():
        error_msg = f"Checksum file not found: {checksum_path}"
        logger.error(error_msg)
        return VerificationResult(
            success=False,
            gpg_verified=False,
            sha256_verified=False,
            error=error_msg,
            recovery_suggestion="Download checksum file or disable SHA256 verification",
        )

    try:
        # Calculate SHA256 hash of file
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
        calculated_hash = sha256_hash.hexdigest()

        # Read and parse checksum file
        checksum_content = checksum_path_obj.read_text().strip()
        checksum_lines = checksum_content.split("\n")

        # Try to find matching hash in checksum file
        # Format can be: "hash  filename" or just "hash"
        provided_hash = None
        candidate_hashes = []  # Store all valid hashes for fallback
        
        for line in checksum_lines:
            line = line.strip()
            if not line:
                continue
            # Try to extract hash (first 64 hex characters)
            parts = line.split()
            if parts:
                candidate_hash = parts[0]
                # Check if it looks like a SHA256 hash (64 hex characters)
                if len(candidate_hash) == 64 and all(c in "0123456789abcdefABCDEF" for c in candidate_hash):
                    # Check if filename matches (if provided)
                    if len(parts) > 1:
                        filename = parts[1]
                        if filename == file_path_obj.name or filename.endswith(file_path_obj.name):
                            provided_hash = candidate_hash.lower()
                            break  # Found exact match, use it
                    else:
                        # Just hash, no filename - store for potential fallback
                        candidate_hashes.append(candidate_hash.lower())
        
        # If no exact filename match found, use first valid hash only if single hash in file
        if provided_hash is None and len(candidate_hashes) == 1:
            provided_hash = candidate_hashes[0]
            logger.info(f"Using single hash from checksum file (no filename match): {file_path}")

        if provided_hash is None:
            error_msg = f"Could not parse checksum from file: {checksum_path}"
            logger.error(error_msg)
            return VerificationResult(
                success=False,
                gpg_verified=False,
                sha256_verified=False,
                error=error_msg,
                recovery_suggestion="Verify checksum file format is correct",
            )

        # Compare hashes (case-insensitive)
        if calculated_hash.lower() == provided_hash.lower():
            logger.info(f"SHA256 checksum verified successfully: {file_path} (calculated={calculated_hash}, provided={provided_hash})")
            echo(f"  [bold green]SHA256 checksum verified[/bold green]")
            return VerificationResult(
                success=True,
                gpg_verified=False,
                sha256_verified=True,
            )
        else:
            error_msg = f"SHA256 checksum mismatch: calculated={calculated_hash[:16]}..., provided={provided_hash[:16]}..."
            logger.error(f"{error_msg} (full calculated={calculated_hash}, full provided={provided_hash})")
            return VerificationResult(
                success=False,
                gpg_verified=False,
                sha256_verified=False,
                error=error_msg,
                recovery_suggestion="File may be corrupted or tampered with. Re-download the file or contact support",
            )

    except Exception as e:
        error_msg = f"Error during SHA256 verification: {e}"
        logger.error(error_msg, exc_info=True)
        return VerificationResult(
            success=False,
            gpg_verified=False,
            sha256_verified=False,
            error=error_msg,
            recovery_suggestion="Check file permissions and checksum file format, or contact support",
        )


def verify_download(
    file_path: str,
    signature_path: Optional[str] = None,
    checksum_path: Optional[str] = None,
    require_gpg: bool = False,
    require_sha256: bool = True,
) -> VerificationResult:
    """
    Verify a downloaded file using GPG signature and/or SHA256 checksum.

    Args:
        file_path: Path to the downloaded file
        signature_path: Optional path to GPG signature file
        checksum_path: Optional path to SHA256 checksum file
        require_gpg: If True, GPG verification must pass (default: False, GPG is optional)
        require_sha256: If True, SHA256 verification must pass (default: True, SHA256 is required)

    Returns:
        VerificationResult with combined verification status
    """
    logger.info(f"Verifying downloaded file: {file_path}")
    echo("  Verifying file integrity...")

    gpg_verified = False
    sha256_verified = False
    errors = []
    recovery_suggestions = []

    # Verify GPG signature if provided
    if signature_path:
        gpg_result = verify_gpg_signature(file_path, signature_path)
        gpg_verified = gpg_result.gpg_verified
        if not gpg_verified:
            errors.append(f"GPG: {gpg_result.error}")
            if gpg_result.recovery_suggestion:
                recovery_suggestions.append(gpg_result.recovery_suggestion)
        if require_gpg and not gpg_verified:
            # GPG required but failed
            return VerificationResult(
                success=False,
                gpg_verified=False,
                sha256_verified=sha256_verified,
                error="; ".join(errors),
                recovery_suggestion="; ".join(recovery_suggestions) if recovery_suggestions else None,
            )

    # Verify SHA256 checksum if provided
    if checksum_path:
        sha256_result = verify_sha256_checksum(file_path, checksum_path)
        sha256_verified = sha256_result.sha256_verified
        if not sha256_verified:
            errors.append(f"SHA256: {sha256_result.error}")
            if sha256_result.recovery_suggestion:
                recovery_suggestions.append(sha256_result.recovery_suggestion)
        if require_sha256 and not sha256_verified:
            # SHA256 required but failed
            return VerificationResult(
                success=False,
                gpg_verified=gpg_verified,
                sha256_verified=False,
                error="; ".join(errors),
                recovery_suggestion="; ".join(recovery_suggestions) if recovery_suggestions else None,
            )

    # Determine overall success
    # At least one verification must pass, or both must pass if both are required
    if require_gpg and require_sha256:
        success = gpg_verified and sha256_verified
    elif require_gpg:
        success = gpg_verified
    elif require_sha256:
        success = sha256_verified
    else:
        # At least one must pass
        success = gpg_verified or sha256_verified

    if success:
        logger.info(f"File verification successful: {file_path}")
        echo("  [bold green]File verification successful[/bold green]")
        return VerificationResult(
            success=True,
            gpg_verified=gpg_verified,
            sha256_verified=sha256_verified,
        )
    else:
        error_msg = "File verification failed: " + "; ".join(errors) if errors else "Verification failed"
        logger.error(f"File verification failed: {file_path} - {error_msg}")
        echo(f"  [bold red]File verification failed:[/bold red] {error_msg}")
        return VerificationResult(
            success=False,
            gpg_verified=gpg_verified,
            sha256_verified=sha256_verified,
            error=error_msg,
            recovery_suggestion="; ".join(recovery_suggestions) if recovery_suggestions else "Contact support if issue persists",
        )
