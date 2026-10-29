#!/usr/bin/env python3
"""Persistent Home Assistant MQTT bridge for the Heltec Easywave gateway."""

from __future__ import annotations

import argparse
import json
import logging
import os
import queue
import re
import secrets
import shutil
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Runtime boundary: this process owns the serial port, MQTT transport and durable
# discovery state. I keep UI drafts in the browser and RF waveform logic in firmware.


APP_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(APP_DIR))
from identification import Identification
from catalogue import Catalogue
DATA_DIR = Path(os.environ.get("EASYWAVE_DATA_DIR", "/data"))
DISCOVERY_FILE = DATA_DIR / "discovery.json"
TX_HISTORY_FILE = DATA_DIR / "tx_history.json"
EVENT_LOG_FILE = DATA_DIR / "events.jsonl"
EXPORT_DIR = Path(os.environ.get("EASYWAVE_EXPORT_DIR", "/share/heltec_easywave"))
EXPORT_DISCOVERY_FILE = EXPORT_DIR / "discovery.json"
EXPORT_EVENT_LOG_FILE = EXPORT_DIR / "events.jsonl"
REGISTRY_FILE = APP_DIR / "registry.json"

BASE_TOPIC = "nikobus/easywave"
RETIRED_TX_ALIASES = ('example_demo_a', 'example_demo_b')
DISCOVERY_PREFIX = "homeassistant"
MIN_TX_INTERVAL_SECONDS = 1.0
STATUS_POLL_SECONDS = 60.0
TX_WINDOW_SECONDS = 3600.0
BURST_AIRTIME_US = int(json.loads((APP_DIR / 'tx_timing.json').read_text())['burst_airtime_us'])
MAX_WINDOW_AIRTIME_US = 35_000_000
MAX_EVENT_LOG_BYTES = 5_000_000

LINE_RE = re.compile(r"^(?P<kind>[A-Z_]+)(?:\s+(?P<fields>.*))?$")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def read_json(path: Path, default: Any) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size >= MAX_EVENT_LOG_BYTES:
        rotated = path.with_suffix(".jsonl.1")
        if rotated.exists():
            rotated.unlink()
        path.replace(rotated)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def parse_line(line: str) -> tuple[str, dict[str, str]]:
    match = LINE_RE.match(line.strip())
    if not match:
        return "", {}
    fields: dict[str, str] = {}
    for token in (match.group("fields") or "").split():
        if "=" in token:
            key, value = token.split("=", 1)
            fields[key] = value
    return match.group("kind"), fields


def event_identity(fields: dict[str, str]) -> str:
    return f"{fields['serial22'].upper()}_{int(fields['key2'])}_{int(fields['side_variant'])}"


class TxBudget:
    """Persistent one-second cadence plus conservative rolling RF budget."""

    def __init__(self, path: Path):
        self.path = path
        raw = read_json(path, {"reservations": []})
        self.reservations = [float(value) for value in raw.get("reservations", [])]

    def _purge(self, now: float) -> None:
        self.reservations = [
            stamp for stamp in self.reservations if 0 <= now - stamp < TX_WINDOW_SECONDS
        ]

    def check(self, now: float) -> tuple[bool, str, float]:
        self._purge(now)
        if self.reservations and now - self.reservations[-1] < MIN_TX_INTERVAL_SECONDS:
            retry = MIN_TX_INTERVAL_SECONDS - (now - self.reservations[-1])
            return False, "minimum_interval", max(0.0, retry)
        used = len(self.reservations) * BURST_AIRTIME_US
        if used + BURST_AIRTIME_US > MAX_WINDOW_AIRTIME_US:
            retry = TX_WINDOW_SECONDS - (now - self.reservations[0])
            return False, "hourly_airtime_budget", max(0.0, retry)
        return True, "ok", 0.0

    def reserve(self, now: float) -> tuple[bool, str, float]:
        # Reserve before attempting RF. Failed/ambiguous sends still consume the
        # conservative budget; restarting the bridge does not reset its history.
        allowed, reason, retry = self.check(now)
        if not allowed:
            return allowed, reason, retry
        self.reservations.append(now)
        atomic_json(self.path, {"reservations": self.reservations})
        return True, "reserved", 0.0


class EasywaveGateway:
    # MQTT callbacks enqueue work. The main run() loop is the only serial owner,
    # including INSTALL_TX, nonce arm/ack exchanges and reception while waiting.
    def __init__(self) -> None:
        import paho.mqtt.client as mqtt
        import serial

        self.mqtt_module = mqtt
        self.serial_module = serial
        self.serial_port = os.environ.get("EASYWAVE_SERIAL_PORT", "/dev/ttyUSB0")
        self.baud = int(os.environ.get("EASYWAVE_BAUD", "115200"))
        self.tx_enabled = os.environ.get("EASYWAVE_TX_ENABLED", "false").lower() == "true"
        self.unknown_limit = int(os.environ.get("EASYWAVE_UNKNOWN_LIMIT", "25"))
        self.registry = read_json(REGISTRY_FILE, {})
        self.by_identity = {
            item["identity"]: item for item in self.registry.get("physical_buttons", [])
        }
        self.by_alias = {
            item["tx_alias"]: item
            for item in self.by_identity.values()
            if item.get("tx_alias")
        }
        self.mirror_private_state()
        self.discovery = read_json(DISCOVERY_FILE, {"devices": {}})
        self.discovery.setdefault("devices", {})
        self.identification = Identification(DATA_DIR / 'labels.json', self.registry, self.discovery)
        self.catalogue = Catalogue(self.identification)
        self.catalogue.install_tx = self.install_tx
        self.frames = {}
        self.by_identity = self.identification.items()
        self.refresh_aliases()
        self.identify_commands = queue.Queue(maxsize=32)
        self.reconcile_registry()
        self.persist_discovery()
        self.budget = TxBudget(TX_HISTORY_FILE)
        self.commands: queue.Queue[str] = queue.Queue(maxsize=1)
        self.serial = serial.Serial(self.serial_port, self.baud, timeout=0.2)
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="easywave_gateway")
        self.client.username_pw_set(
            os.environ["EASYWAVE_MQTT_USERNAME"], os.environ["EASYWAVE_MQTT_PASSWORD"]
        )
        self.client.will_set(f"{BASE_TOPIC}/status", "offline", qos=1, retain=True)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

    def mirror_private_state(self) -> None:
        """Seed the user-accessible mirror once without duplicating records."""
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        if EVENT_LOG_FILE.exists() and not EXPORT_EVENT_LOG_FILE.exists():
            shutil.copy2(EVENT_LOG_FILE, EXPORT_EVENT_LOG_FILE)
        if DISCOVERY_FILE.exists():
            atomic_json(EXPORT_DISCOVERY_FILE, read_json(DISCOVERY_FILE, {"devices": {}}))

    def refresh_aliases(self):
        # Complete RF evidence supplies capability, independently of labels/groups.
        radio = self.identification.radio_items(self.catalogue.firmware_ready)
        self.by_alias = {item['tx_alias']: item for item in radio.values() if item.get('tx_alias')}

    def install_tx(self, event):
        nonce = secrets.token_hex(4).upper()
        self.serial.write(f"INSTALL_TX {event['word']} {event['tail']} {nonce}\n".encode())
        kind, fields = self.wait_serial(nonce, {'TX_INSTALLED', 'COMMAND_REJECT'}, 3.0)
        self.last_install_reason = fields.get('reason', 'learning_required' if kind != 'TX_INSTALLED' else '')
        return kind == 'TX_INSTALLED' and fields.get('success') == 'true' and fields.get('word') == event['word']

    def persist_discovery(self) -> None:
        atomic_json(DISCOVERY_FILE, self.discovery)
        atomic_json(EXPORT_DISCOVERY_FILE, self.discovery)

    def reconcile_registry(self) -> None:
        """Apply registry renames without losing first/last-seen history."""
        changed = False
        for identity, event in self.discovery["devices"].items():
            known = self.by_identity.get(identity)
            expected_known = known is not None
            label = (
                f"{known['source']} · {known['button']}"
                if known
                else f"Inconnu {identity}"
            )
            action_id = known.get("action_id") if known else None
            if (
                event.get("known") != expected_known
                or event.get("label") != label
                or event.get("action_id") != action_id
            ):
                event.update(known=expected_known, label=label, action_id=action_id)
                changed = True
        if changed:
            self.persist_discovery()

    @staticmethod
    def device() -> dict[str, Any]:
        return {
            "identifiers": ["heltec_easywave_gateway"],
            "name": "Passerelle Easywave",
            "manufacturer": "Heltec / local reverse engineering",
            "model": "WiFi LoRa 32 V3 (SX1262)",
            "sw_version": "gateway-v8.7 / add-on-0.4.0",
        }

    def publish_config(self, component: str, object_id: str, payload: dict[str, Any]) -> None:
        topic = f"{DISCOVERY_PREFIX}/{component}/easywave/{object_id}/config"
        self.client.publish(topic, json.dumps(payload, ensure_ascii=False), qos=1, retain=True)

    def publish_static_discovery(self) -> None:
        availability = {"topic": f"{BASE_TOPIC}/status", "payload_available": "online", "payload_not_available": "offline"}
        for item in self.by_identity.values():
            identity = item["identity"].lower()
            state_topic = f"{BASE_TOPIC}/rx/{identity}"
            self.publish_config("sensor", f"last_seen_{identity}", {
                "name": f"Dernière détection · {item['source']} · {item['button']}",
                "unique_id": f"easywave_last_seen_{identity}",
                "icon": item.get('icon', 'mdi:gesture-tap-button'),
                "state_topic": state_topic,
                "value_template": "{{ value_json.last_seen }}",
                "json_attributes_topic": state_topic,
                "device_class": "timestamp",
                "availability": availability,
                "device": self.device(),
            })
            if item.get("tx_alias"):
                alias = item["tx_alias"]
                self.publish_config("button", f"tx_{alias}", {
                    "name": f"Émettre · {item['source']} · {item['button']}",
                    "unique_id": f"easywave_tx_{alias}",
                    "icon": item.get('icon', 'mdi:gesture-tap-button'),
                    "command_topic": f"{BASE_TOPIC}/tx/{alias}/set",
                    "payload_press": "PRESS",
                    "qos": 0,
                    "retain": False,
                    "availability": availability,
                    "device": self.device(),
                })
        for alias in RETIRED_TX_ALIASES:
            self.client.publish(f'{DISCOVERY_PREFIX}/button/easywave/tx_{alias}/config', '', qos=1, retain=True)
        for object_id, name, template in (
            ("latest", "Dernière commande Easywave", "{{ value_json.label }}"),
            ("unknowns", "Interrupteurs Easywave inconnus", "{{ value_json.count }}"),
            ("tx_result", "Dernier résultat TX Easywave", "{{ value_json.result }}"),
            ("gateway_status", "État passerelle Easywave", "{{ value_json.state }}"),
            ("catalogue", "Catalogue des touches", "{{ value_json.revision }}"),
        ):
            topic = f"{BASE_TOPIC}/{object_id}"
            self.publish_config("sensor", object_id, {
                "name": name,
                "unique_id": f"easywave_{object_id}",
                "state_topic": topic,
                "value_template": template,
                "json_attributes_topic": topic,
                "availability": availability,
                "device": self.device(),
            })

    def publish_dynamic_sensor(self, identity: str) -> None:
        object_id = identity.lower()
        topic = f"{BASE_TOPIC}/rx/{object_id}"
        self.publish_config("sensor", f"last_seen_{object_id}", {
            "name": f"Dernière détection · Inconnu {identity}",
            "unique_id": f"easywave_last_seen_{object_id}",
            "state_topic": topic,
            "value_template": "{{ value_json.last_seen }}",
            "json_attributes_topic": topic,
            "device_class": "timestamp",
            "availability": {"topic": f"{BASE_TOPIC}/status"},
            "device": self.device(),
        })

    def on_connect(self, client: Any, userdata: Any, flags: Any, reason_code: Any, properties: Any) -> None:
        if reason_code != 0:
            logging.error("MQTT connection refused: %s", reason_code)
            return
        client.publish(f"{BASE_TOPIC}/status", "online", qos=1, retain=True)
        client.subscribe(f"{BASE_TOPIC}/tx/+/set", qos=0)
        client.subscribe(f"{BASE_TOPIC}/identify/+/set", qos=0)
        self.publish_static_discovery()
        self.publish_unknowns()
        self.publish_identification()
        logging.info("MQTT connected; TX enabled=%s", self.tx_enabled)

    def on_message(self, client: Any, userdata: Any, message: Any) -> None:
        # Metadata and manual presses use different topics and queues. Retained
        # commands never become a new physical action after reconnecting MQTT.
        if message.topic.startswith(f'{BASE_TOPIC}/identify/'):
            if message.retain or len(message.payload) > 8192:
                return
            try:
                field = message.topic.removeprefix(f'{BASE_TOPIC}/identify/').removesuffix('/set')
                self.identify_commands.put_nowait((field, message.payload.decode('utf-8')))
            except (queue.Full, UnicodeError):
                logging.warning('Identification command rejected: busy or invalid text')
            return
        alias = message.topic.removeprefix(f"{BASE_TOPIC}/tx/").removesuffix("/set")
        client_request = None
        valid = message.payload == b'PRESS'
        if not valid and len(message.payload) <= 256:
            try:
                command = json.loads(message.payload)
                client_request = command.get('request_id') if isinstance(command, dict) else None
                valid = (isinstance(command, dict) and command.get('action') == 'PRESS'
                         and isinstance(client_request, str)
                         and re.fullmatch(r'[A-Za-z0-9_-]{8,80}', client_request) is not None)
            except (ValueError, UnicodeError):
                pass
        if message.retain or not valid or alias not in self.by_alias:
            self.publish_tx_result(alias, "rejected_invalid_command", client_request=client_request)
            return
        if not self.tx_enabled:
            self.publish_tx_result(alias, "rejected_tx_disabled", client_request=client_request)
            return
        try:
            if client_request:
                recent = getattr(self, 'recent_requests', [])
                if client_request in recent:
                    return
                self.commands.put_nowait((alias, client_request))
                self.recent_requests = (recent + [client_request])[-64:]
            else:
                self.commands.put_nowait(alias)
            self.catalogue.record_tx(alias, None, False)
        except queue.Full:
            self.publish_tx_result(alias, "rejected_busy", client_request=client_request)

    def append_event_log(self, event: dict[str, Any]) -> None:
        append_jsonl(EVENT_LOG_FILE, event)
        append_jsonl(EXPORT_EVENT_LOG_FILE, event)

    def process_event(self, fields: dict[str, str]) -> None:
        # A firmware event updates observations; it never queues a transmission.
        required = {"word", "serial22", "key2", "side_variant", "rssi_dbm"}
        if not required.issubset(fields) or fields.get("plausibility_valid") != "true":
            return
        identity = event_identity(fields)
        known = self.by_identity.get(identity)
        now = utc_now()
        previous = self.discovery["devices"].get(identity, {})
        count = int(previous.get("count", 0)) + 1
        label = (
            f"{known['source']} · {known['button']}" if known else f"Inconnu {identity}"
        )
        event = {
            "record_type": "easywave_event",
            "identity": identity,
            "word": fields["word"].upper(),
            "serial22": fields["serial22"].upper(),
            "key2": int(fields["key2"]),
            "side_variant": int(fields["side_variant"]),
            "rssi_dbm": float(fields["rssi_dbm"]),
            "sync": fields.get("sync"),
            "known": known is not None,
            "action_id": known.get("action_id") if known else None,
            "label": label,
            "first_seen": previous.get("first_seen", now),
            "last_seen": now,
            "count": count,
        }
        if previous.get('word') == event['word']:
            for key in ('tail', 'frame_confirmations'):
                if key in previous:
                    event[key] = previous[key]
        frame = self.frames.get(event['word'])
        if frame:
            event.update(frame)
        self.discovery["devices"][identity] = event
        self.refresh_aliases()
        self.persist_discovery()
        self.append_event_log(event)
        if not known:
            self.publish_dynamic_sensor(identity)
        topic = f"{BASE_TOPIC}/rx/{identity.lower()}"
        payload = json.dumps(event, ensure_ascii=False)
        self.client.publish(topic, payload, qos=1, retain=True)
        self.client.publish(f"{BASE_TOPIC}/latest", payload, qos=1, retain=True)
        self.client.publish(f"{BASE_TOPIC}/rx/event", payload, qos=0, retain=False)
        self.publish_unknowns()
        self.publish_identification()

    def publish_identification(self) -> None:
        availability = {'topic': f'{BASE_TOPIC}/status'}
        for component, obj, payload in self.identification.configs(self.device(), availability, BASE_TOPIC):
            self.publish_config(component, obj, payload)
        for field, value in self.identification.states().items():
            if isinstance(value, dict):
                value = json.dumps(value, ensure_ascii=False)
            self.client.publish(f'{BASE_TOPIC}/identify/{field}', value, qos=1, retain=True)
        self.client.publish(f'{BASE_TOPIC}/catalogue', json.dumps(self.catalogue.view(), ensure_ascii=False),
                            qos=1, retain=True)

    def process_identification(self) -> None:
        # A successful metadata transaction republishes discovery and the catalogue.
        # It may rename an entity, but must not change its stable radio identity.
        try:
            field, value = self.identify_commands.get_nowait()
        except queue.Empty:
            return
        try:
            identity = self.identification.selected
            if field == 'catalogue':
                request = json.loads(value)
                changed = self.catalogue.apply(request)
                identity = request.get('identity') if isinstance(request, dict) else None
            else:
                changed = self.identification.handle(field, value)
                identity = self.identification.selected
            if changed:
                self.by_identity = self.identification.items()
                self.refresh_aliases()
                self.reconcile_registry()
                atomic_json(EXPORT_DIR / 'labels.json', self.identification.labels)
                self.publish_static_discovery()
                self.publish_unknowns()
                event = self.discovery['devices'].get(identity)
                if event:
                    self.client.publish(f'{BASE_TOPIC}/rx/{identity.lower()}', json.dumps(event, ensure_ascii=False), qos=1, retain=True)
        except (ValueError, OSError, TypeError, KeyError) as error:
            self.identification.result = f'Attribution non enregistrée : {error}'
        self.publish_identification()

    def publish_unknowns(self) -> None:
        unknowns = [item for item in self.discovery["devices"].values() if not item.get("known")
                    and not self.identification.labels.get(item['identity'], {}).get('ignored')]
        unknowns.sort(key=lambda item: item.get("last_seen", ""), reverse=True)
        recent = unknowns[: self.unknown_limit]
        payload = {
            "count": len(unknowns),
            "last_seen": recent[0]["last_seen"] if recent else None,
            "recent": recent,
        }
        self.client.publish(
            f"{BASE_TOPIC}/unknowns", json.dumps(payload, ensure_ascii=False), qos=1, retain=True
        )

    def publish_tx_result(self, alias: str, result: str, **extra: Any) -> None:
        payload = {"result": result, "alias": alias, "timestamp": utc_now(), **extra}
        self.append_event_log({"record_type": "tx_result", **payload})
        self.client.publish(
            f"{BASE_TOPIC}/tx_result", json.dumps(payload, ensure_ascii=False), qos=1, retain=True
        )

    def process_serial_line(self, line: str) -> tuple[str, dict[str, str]]:
        kind, fields = parse_line(line)
        if kind == 'EASYWAVE_FRAME' and fields.get('source') == 'rf':
            word, tail, confirmations = fields.get('word', ''), fields.get('tail'), fields.get('confirmations', '')
            if re.fullmatch('[0-9A-F]{8}', word) and tail in ('0', '1') and confirmations.isdigit():
                frame = dict(tail=int(tail), frame_confirmations=int(confirmations))
                self.frames[word] = frame
                for event in self.discovery['devices'].values():
                    if event.get('word') == word:
                        event.update(frame)
                self.persist_discovery()
                self.refresh_aliases()
                self.publish_identification()
        elif kind == "EASYWAVE_EVENT":
            self.process_event(fields)
        elif kind == "GATEWAY_STATUS":
            observed_at = utc_now()
            payload: dict[str, Any] = {
                "state": "rx_active",
                "firmware": "gateway_v8",
                "last_seen": observed_at,
                "tx_enabled": self.tx_enabled,
            }
            payload.update(fields)
            self.catalogue.firmware_ready = fields.get('firmware') == 'NIKOBUS_HELTEC_EASYWAVE_GATEWAY_V8_7_LEARNED'
            self.refresh_aliases()
            self.publish_identification()
            self.append_event_log({
                "record_type": "gateway_status",
                "observed_at": observed_at,
                "firmware": "gateway_v8",
                "tx_enabled": self.tx_enabled,
                **fields,
            })
            self.client.publish(
                f"{BASE_TOPIC}/gateway_status",
                json.dumps(payload, ensure_ascii=False), qos=1, retain=True,
            )
            logging.info(
                "Heltec V8 responding; RX sync=%s, TX window=%s/%s us",
                fields.get("sync"), fields.get("tx_window_airtime_us"),
                fields.get("tx_window_limit_us"),
            )
        return kind, fields

    def wait_serial(self, nonce: str, terminal: set[str], timeout: float) -> tuple[str, dict[str, str]]:
        # RX/status lines can interleave with a reply. I continue processing them
        # and accept a positive result only when its nonce matches this request.
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            line = self.serial.readline().decode("utf-8", errors="replace").strip()
            if not line:
                continue
            kind, fields = self.process_serial_line(line)
            # An uncorrelated line must never acknowledge this transmission.
            # The legacy firmware omits request only on COMMAND_REJECT (failure).
            matches = fields.get("request", "").upper() == nonce
            if kind in terminal and (matches or kind == "COMMAND_REJECT"):
                return kind, fields
        return "TIMEOUT", {}

    def transmit(self, alias: str, client_request=None) -> None:
        # client_request correlates the browser click; the serial nonce correlates
        # the firmware exchange. Neither value represents the real lamp state.
        def emit_result(state, **extra):
            self.publish_tx_result(alias, state, client_request=client_request, **extra)

        # Only a manual PRESS reaches here. Naming and recognition never transmit.
        if alias not in self.by_alias or not self.tx_enabled:
            emit_result('rejected_invalid_command')
            return
        if alias.startswith('rx_'):
            item = self.by_alias[alias]
            frame = self.identification.command_frame(item['identity'])
            if not self.catalogue.firmware_ready or not frame or alias != 'rx_' + frame['word']:
                emit_result('rejected_incomplete_frame')
                return
            # Idempotent installation from received bits, on the serial owner thread.
            # It does not arm or emit, and avoids filling NVS with every nearby signal.
            if not self.install_tx(frame):
                emit_result('rejected_learning', reason=getattr(self, 'last_install_reason', 'learning_required'))
                return
        self.catalogue.record_tx(alias, None, False)
        self.publish_identification()
        now = time.time()
        allowed, reason, retry = self.budget.reserve(now)
        if not allowed:
            emit_result(f"rejected_{reason}", retry_after_seconds=round(retry, 1))
            return
        nonce = secrets.token_hex(4).upper()
        self.serial.write(f"ARM_TX {nonce}\n".encode())
        kind, fields = self.wait_serial(nonce, {"TX_ARMED", "COMMAND_REJECT"}, 2.0)
        if kind != "TX_ARMED":
            emit_result("failed_arm", firmware=kind)
            return
        self.serial.write(f"TX {alias} {nonce}\n".encode())
        kind, fields = self.wait_serial(
            nonce, {"TX_COMPLETE", "TX_REJECT", "COMMAND_REJECT"}, 3.0
        )
        success = kind == "TX_COMPLETE" and fields.get("success") == "true"
        result = "transmitted_unconfirmed" if success else "failed_firmware"
        if success and fields.get("rx_resumed") != "true":
            result = "transmitted_rx_failed"
        reported_airtime = fields.get("airtime_us", "")
        self.publish_tx_result(
            alias, result, firmware=kind, request=nonce, polarity=fields.get("polarity"),
            client_request=client_request,
            physical_state_confirmed=False,
            rx_resumed=fields.get("rx_resumed"),
            airtime_us=int(reported_airtime) if reported_airtime.isdigit() else None,
            reserved_airtime_us=BURST_AIRTIME_US,
            reason=fields.get("reason"),
        )
        self.catalogue.record_tx(alias, nonce, result == 'transmitted_unconfirmed')
        self.publish_identification()

    def refresh_status(self, force: bool = False) -> None:
        now = time.monotonic()
        if force or now >= getattr(self, "next_status_at", 0.0):
            self.serial.write(b"STATUS\n")
            self.next_status_at = now + STATUS_POLL_SECONDS

    def run(self) -> None:
        host = os.environ["EASYWAVE_MQTT_HOST"]
        port = int(os.environ.get("EASYWAVE_MQTT_PORT", "1883"))
        self.client.connect(host, port, keepalive=60)
        self.client.loop_start()
        self.append_event_log({
            "record_type": "session_start",
            "observed_at": utc_now(),
            "firmware": "gateway_v8",
            "addon_version": "0.4.0",
            "tx_enabled": self.tx_enabled,
        })
        self.refresh_status(force=True)
        try:
            while True:
                self.process_identification()
                try:
                    alias = self.commands.get_nowait()
                except queue.Empty:
                    alias = None
                if alias:
                    if isinstance(alias, tuple):
                        self.transmit(*alias)
                    else:
                        self.transmit(alias)
                self.refresh_status(force=bool(alias))
                line = self.serial.readline().decode("utf-8", errors="replace").strip()
                if line:
                    self.process_serial_line(line)
        finally:
            self.append_event_log({
                "record_type": "session_stop",
                "observed_at": utc_now(),
                "firmware": "gateway_v8",
                "addon_version": "0.4.0",
            })
            self.client.publish(f"{BASE_TOPIC}/status", "offline", qos=1, retain=True)
            self.client.disconnect()


def self_test() -> None:
    kind, fields = parse_line(
        "EASYWAVE_EVENT timestamp_ms=42 rssi_dbm=-61.5 sync=55 word=0C400707 "
        "serial22=031001 key2=3 side_variant=0 plausibility_valid=true source=rf"
    )
    assert kind == "EASYWAVE_EVENT"
    assert event_identity(fields) == "031001_3_0"
    registry = read_json(REGISTRY_FILE, {})
    identities = [item["identity"] for item in registry["physical_buttons"]]
    aliases = [item["tx_alias"] for item in registry["physical_buttons"] if item["tx_alias"]]
    assert len(identities) == len(set(identities))
    assert len(aliases) == len(set(aliases))
    with tempfile.TemporaryDirectory() as directory:
        budget = TxBudget(Path(directory) / "budget.json")
        assert budget.reserve(0.0)[0]
        assert budget.reserve(0.5)[1] == "minimum_interval"
        capacity = MAX_WINDOW_AIRTIME_US // BURST_AIRTIME_US
        for second in range(1, capacity):
            assert budget.reserve(float(second))[0]
        assert len(budget.reservations) == capacity
        assert budget.reserve(float(capacity))[1] == "hourly_airtime_budget"
        assert budget.reserve(3600.1)[0]
        event_log = Path(directory) / "events.jsonl"
        append_jsonl(event_log, {"record_type": "gateway_status", "value": 1})
        append_jsonl(event_log, {"record_type": "easywave_event", "value": 2})
        records = [json.loads(line) for line in event_log.read_text(encoding="utf-8").splitlines()]
        assert [record["value"] for record in records] == [1, 2]
    print("EASYWAVE_GATEWAY_SELF_TEST_OK")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    EasywaveGateway().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
