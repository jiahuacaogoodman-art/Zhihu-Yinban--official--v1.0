from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
UTF8_BOM = b"\xef\xbb\xbf"

WINDOWS_POWERSHELL_51_ENTRYPOINTS = [
    PROJECT_ROOT / "scripts" / "launch-local.ps1",
    PROJECT_ROOT / "scripts" / "setup-wizard.ps1",
    PROJECT_ROOT / "scripts" / "build-exe.ps1",
]


def test_windows_powershell_entrypoints_use_utf8_bom():
    missing = [
        path.relative_to(PROJECT_ROOT).as_posix()
        for path in WINDOWS_POWERSHELL_51_ENTRYPOINTS
        if not path.read_bytes().startswith(UTF8_BOM)
    ]

    assert not missing, (
        "Windows PowerShell 5.1 reads UTF-8 scripts without a BOM as the "
        f"system ANSI code page, which mojibakes Chinese startup text: {missing}"
    )