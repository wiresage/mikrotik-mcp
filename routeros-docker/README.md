# RouterOS lab

Two RouterOS CHR containers for live testing: `routeros-a` (SSH on host port 2222) and `routeros-b` (2223), user `admin` with an
empty password. They run [evilfreelancer/docker-routeros](https://hub.docker.com/r/evilfreelancer/docker-routeros), a QEMU wrapper
around one MikroTik CHR disk per image, so **the image tag is the RouterOS version**.

```bash
docker compose -f routeros-docker/docker-compose.yml up -d    # about two minutes to boot
python routeros-docker/check_versions.py                       # which RouterOS runs, and is there a newer one?
```

## Test on the newest RouterOS

The tools are written against RouterOS 7 and its command output changes between releases, so a lab that quietly stays on an old
release stops saying anything about what users run today. Two things keep it behind:

* `docker compose up` never pulls a newer `latest`. An image that is already on the machine is used as it is.
* The data volumes (`routeros-data-a`, `routeros-data-b`) keep the RouterOS disk of the image that first started in them. A newer
  image cannot boot from an old volume: QEMU stops with `Could not open '/routeros/chr-<new version>.vdi'`.

To move to a newer RouterOS, pull and recreate the lab, volumes included (the routers are throwaway; export what you need first):

```bash
docker compose -f routeros-docker/docker-compose.yml pull
docker compose -f routeros-docker/docker-compose.yml down -v
docker compose -f routeros-docker/docker-compose.yml up -d
```

`check_versions.py` prints the newest release of every MikroTik channel, what Docker Hub has, and the version each router runs.
It exits with 1 when a router is older than the newest long-term release.

## Which version is on Docker Hub

Tags are RouterOS versions (`7.23.8`, `6.49.23`, ...) and `latest` is the newest one the image's maintainers have built. It can be
older than MikroTik's newest stable release: on 2026-11-01 `latest` was 7.23.8 while stable was 7.25, and there was no 7.25 tag.
`check_versions.py` says so when that happens. A version Docker Hub lacks can be built from the upstream Dockerfile:

```bash
docker build --build-arg ROUTEROS_VERSION=7.25 -t local/docker-routeros:7.25 https://github.com/EvilFreelancer/docker-routeros.git#master
```

## Two versions side by side

`ROUTEROS_IMAGE` picks the image for both routers; `ROUTEROS_IMAGE_A` and `ROUTEROS_IMAGE_B` pick one router. A mixed lab also
shows how the server copes with a fleet whose devices run different releases:

```bash
ROUTEROS_IMAGE_A=local/docker-routeros:7.25 docker compose -f routeros-docker/docker-compose.yml up -d
```

(`tests/integration/` starts its own container from `evilfreelancer/docker-routeros:latest` through testcontainers, which also uses
a `latest` that is already on the machine; run `docker pull evilfreelancer/docker-routeros:latest` first.)
