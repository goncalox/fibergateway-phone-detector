"""Build an installable release from explicit integration and documentation paths."""
import argparse
import json
from pathlib import Path
import re
import zipfile

PROJECT = Path(__file__).resolve().parents[1]


def build(output: Path, tag: str | None = None) -> Path:
    manifest = json.loads((PROJECT / "custom_components/wifi_phone_detector/manifest.json").read_text())
    version = manifest["version"]
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("Manifest version must be a stable semantic version")
    if tag is not None and tag != f"v{version}":
        raise ValueError("Release tag must match the integration manifest version")
    output.mkdir(parents=True, exist_ok=True)
    destination = output / f"fibergateway-phone-detector-v{version}.zip"
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted((PROJECT / "custom_components/wifi_phone_detector").rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                archive.write(path, path.relative_to(PROJECT))
        for name in ("LICENSE", "README.md", "AUTOMATIONS.md", "DASHBOARD.md", "HACS.md", "CHANGELOG.md", "GR141DG-compatibility.md", "STANDALONE.md", "requirements-standalone.txt", "hacs.json", "tools/standalone.py"):
            archive.write(PROJECT / name, name)
    with zipfile.ZipFile(destination) as archive:
        if archive.testzip() is not None:
            raise ValueError("Release archive integrity check failed")
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=PROJECT / "dist")
    parser.add_argument("--tag")
    args = parser.parse_args()
    print(build(args.output, args.tag))
