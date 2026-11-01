<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/unseenet/unseenet/main/assets/logo-dark.svg">
    <img src="https://raw.githubusercontent.com/unseenet/unseenet/main/assets/logo-light.svg" alt="Unseenet" width="360">
  </picture>
</p>

<h1 align="center">unseenet-homeassistant</h1>

<p align="center"><b>See how your Unseenet node is doing, right in Home Assistant.</b><br>
Tor, traffic, peers, storage and warnings - and a council replica's role and alarms.</p>

<p align="center">
  <a href="https://github.com/unseenet/unseenet-homeassistant/releases"><img src="https://img.shields.io/github/v/release/unseenet/unseenet-homeassistant?include_prereleases&label=release" alt="Release"></a>
  <a href="https://github.com/unseenet/unseenet-homeassistant/actions/workflows/ci.yml"><img src="https://github.com/unseenet/unseenet-homeassistant/actions/workflows/ci.yml/badge.svg" alt="ci"></a>
  <a href="https://hacs.xyz"><img src="https://img.shields.io/badge/HACS-custom-orange" alt="HACS custom"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-blue" alt="Apache-2.0"></a>
</p>

> **Pre-alpha, and not usable yet.** The integration is written and tested, but
> nodes and replicas do not offer their stats to Home Assistant until
> [unseenet/unseenet#873](https://github.com/unseenet/unseenet/issues/873) and
> [unseenet/unseenet-haos-addons#3](https://github.com/unseenet/unseenet-haos-addons/issues/3)
> are done. Unseenet has not had a security review.

## What it is

[Unseenet](https://unseenet.org) is a discussion network in the spirit of old
Usenet, carried over Tor onion services, on nodes anyone can run. With the
[Unseenet add-ons](https://github.com/unseenet/unseenet-haos-addons), your Home
Assistant machine is one of those nodes - one more node of the shared network.

This integration shows how that node is doing. It only **reads** the node's
stats - the same ones `unseenet-monitor` shows - and changes nothing on the
node. It sees nothing about readers or what they read: the node does not record
that.

## What you get

Each node or replica is a device.

**A node**
- Tor: running, off or down, and how far it has started
- Posts taken in, sent to peers, served and refused in the last hour; posts
  taken in all told
- Open connections, peers connected, connections turned away
- Groups and posts stored, their size, free disk
- New messages in your operator contact inbox
- One connectivity sensor per peer - on when the exchange works, with its last
  error as an attribute; peers added later show up by themselves
- **Needs attention**, and the node's warnings as a Home Assistant repair

**A council replica**
- Role: waiting, shadow, member on probation, full member
- Ripening level, council members and full members, reports and agreeing days
  in the last 60, when it becomes a full member
- **Waiting for you**: council changes held for your agreement, also as a repair
- **Twin alarm**: another copy of the replica uses its key, as a critical
  repair telling what to do

## Install

1. In HACS: **⋮ → Custom repositories**, add
   `https://github.com/unseenet/unseenet-homeassistant` as an *Integration*,
   and download **Unseenet**. Restart Home Assistant.
2. With the Unseenet add-ons, Home Assistant offers *"Unseenet found"* by
   itself. Otherwise: **Settings → Devices & services → Add integration →
   Unseenet**, and give the host, port (1120 for the add-ons) and the token from
   the add-on's log.

If the add-on makes a new token, Home Assistant asks for it (re-authentication).
English and Danish.

## How it talks to the node

One TCP connection on Home Assistant's internal add-on network, never over Tor
and never on your LAN: first `token <token>`, then `stats`, one JSON line back
- the node's snapshot (`"v": 1`, documented in the core's
[`stats.py`](https://github.com/unseenet/unseenet/blob/main/src/unseenet/node/stats.py)),
or a replica's `status.json`. Polled every 30 seconds. See
[`api.py`](custom_components/unseenet/api.py).

## Development

```
pip install -r requirements_test.txt
python -m pytest
```

The tests start a fake stats interface (`tests/conftest.py`) with a node's and
a replica's snapshot (`tests/fixtures/`). The CI also runs ruff, Home
Assistant's hassfest and HACS's checks.

## More

- The add-ons: <https://github.com/unseenet/unseenet-haos-addons>
- How Unseenet works: <https://unseenet.org/guide/>
- The core: <https://github.com/unseenet/unseenet>

Apache-2.0. The Unseenet logo is CC BY 4.0.
