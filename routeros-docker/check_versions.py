#!/usr/bin/env python3
"""Is the RouterOS lab running the newest RouterOS?

usage: python routeros-docker/check_versions.py [container ...]      (default: routeros-a routeros-b)

Prints the RouterOS version baked into each lab container's image, the newest release of every MikroTik channel
(https://upgrade.mikrotik.com), and what Docker Hub has for evilfreelancer/docker-routeros, then says what to do when the lab
is behind. Needs only Python and the docker CLI. Exit code: 0 the lab is on the newest long-term release or later, 1 it is
behind, 2 nothing could be checked.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import urllib.request

IMAGE = "evilfreelancer/docker-routeros"
CHANNELS = ("long-term", "stable", "testing", "development")


def parse(version: str) -> tuple:
    """7.23.8 -> (7, 23, 8, 3, 0); 7.25 -> (7, 25, 0, 3, 0); 7.26beta4 -> (7, 26, 0, 1, 4): a release sorts after its betas."""
    m = re.fullmatch(r"(\d+)\.(\d+)(?:\.(\d+))?(?:(beta|rc)(\d+))?", version.split()[0])
    if not m:
        return (0,)
    rank = {None: 3, "rc": 2, "beta": 1}[m.group(4)]
    return (int(m.group(1)), int(m.group(2)), int(m.group(3) or 0), rank, int(m.group(5) or 0))


def fetch(url: str) -> str:
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "mikrotik-mcp-lab-check"}), timeout=30) as response:
        return response.read().decode("utf-8", "replace").strip()


def docker(*args: str) -> str:
    result = subprocess.run(["docker", *args], capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else ""


def image_version(reference: str) -> str:
    env = docker("inspect", reference, "--format", "{{range .Config.Env}}{{println .}}{{end}}")
    found = re.search(r"^ROUTEROS_VERSION=(\S+)", env, re.M)
    return found.group(1) if found else ""


def main() -> int:
    containers = sys.argv[1:] or ["routeros-a", "routeros-b"]
    newest: dict[str, str] = {}
    for channel in CHANNELS:
        try:
            newest[channel] = fetch(f"https://upgrade.mikrotik.com/routeros/NEWESTa7.{channel}").split()[0]
        except Exception as error:  # noqa: BLE001
            print(f"  could not read the {channel} channel: {error}")
    if not newest:
        print("Could not reach upgrade.mikrotik.com.")
        return 2
    print("Newest RouterOS 7 per channel: " + " | ".join(f"{channel} {version}" for channel, version in newest.items()))

    hub_tags: dict[str, str] = {}
    try:
        page = json.loads(fetch(f"https://hub.docker.com/v2/repositories/{IMAGE}/tags?page_size=100&ordering=last_updated"))
        hub_tags = {tag["name"]: tag.get("digest", "") for tag in page.get("results", [])}
    except Exception as error:  # noqa: BLE001
        print(f"  could not read Docker Hub: {error}")
    published = sorted((t for t in hub_tags if re.fullmatch(r"7\.\d+(\.\d+)?", t)), key=parse)
    latest_is = next((t for t in reversed(published) if hub_tags[t] and hub_tags[t] == hub_tags.get("latest")), "?")
    if hub_tags:
        print(f"Docker Hub {IMAGE}: newest 7.x tag {published[-1] if published else '?'}, `latest` is {latest_is}")

    local_latest = image_version(f"{IMAGE}:latest")
    behind = False
    if local_latest:
        stale = latest_is != "?" and parse(local_latest) < parse(latest_is)
        behind |= stale
        print(f"Local image {IMAGE}:latest: {local_latest}" + (f"   <- older than Docker Hub's {latest_is}" if stale else ""))

    long_term, stable = newest.get("long-term"), newest.get("stable")
    checked = 0
    for name in containers:
        reference = docker("inspect", name, "--format", "{{.Config.Image}}")
        version = image_version(name)
        if not version:
            print(f"{name}: not found (is the lab running?)")
            continue
        checked += 1
        notes = []
        if long_term and parse(version) < parse(long_term):
            notes.append(f"older than the newest long-term {long_term}")
        if stable and parse(version) < parse(stable):
            notes.append(f"older than the newest stable {stable}")
        print(f"{name}: RouterOS {version} (image {reference})" + (f"   <- {'; '.join(notes)}" if notes else "   up to date"))
        behind |= bool(long_term and parse(version) < parse(long_term))
    if not checked and not local_latest:
        return 2

    if behind:
        print("\nTo move the lab to a newer RouterOS (the data volumes keep the disk of the image that created them, so they must go):")
        print("  docker compose -f routeros-docker/docker-compose.yml pull")
        print("  docker compose -f routeros-docker/docker-compose.yml down -v")
        print("  docker compose -f routeros-docker/docker-compose.yml up -d")
    if stable and published and parse(stable) > parse(published[-1]):
        print(f"\nThe newest stable release, {stable}, is not on Docker Hub yet. Build it from the upstream Dockerfile and point a router at it:")
        print(f"  docker build --build-arg ROUTEROS_VERSION={stable} -t local/docker-routeros:{stable} https://github.com/EvilFreelancer/docker-routeros.git#master")
        print(f"  ROUTEROS_IMAGE_A=local/docker-routeros:{stable} docker compose -f routeros-docker/docker-compose.yml up -d")
    return 1 if behind else 0


if __name__ == "__main__":
    sys.exit(main())
