/**
 * Heltec V3 radio endpoint: RX evidence, serial protocol and one-shot TX.
 * Current community build: heltec_v87, empty native command table.
 * Only the learned-command continuous-burst path is included.
 * See docs/ARCHITECTURE.md and docs/MODULATION.md.
 */
#include <Arduino.h>
#include <RadioLib.h>
#include <U8g2lib.h>
#include <Wire.h>

#include <cctype>
#include <cstring>
#include <array>
#include <Preferences.h>
#include "easywave_learned_tx.h"

#include "easywave_tx_continuous_generated.h"

namespace pins {
constexpr uint8_t oledSda = 17, oledScl = 18, oledReset = 21, vext = 36;
constexpr uint8_t radioNss = 8, radioDio1 = 14, radioReset = 12, radioBusy = 13;
constexpr uint8_t userButton = 0;  // Heltec V3 PRG, active low
}

U8G2_SSD1306_128X64_NONAME_F_HW_I2C display(
    U8G2_R0, pins::oledReset, pins::oledScl, pins::oledSda);
SX1262 radio = new Module(
    pins::radioNss, pins::radioDio1, pins::radioReset, pins::radioBusy);

namespace gateway {
// Radio configuration, candidate cache and timing state live together here.
// Generated TX constants come from the offline encoder, not from the HA card.
constexpr float frequencyMHz = 868.314F, bitRateKbps = 2.0015F;
constexpr float deviationKHz = 43.8F, bandwidthKHz = 117.3F;
constexpr uint8_t dataShaping = RADIOLIB_SHAPING_NONE;
constexpr const char* shapingName = "none";
constexpr const char* firmwareIdentity = "NIKOBUS_HELTEC_EASYWAVE_GATEWAY_V8_7_LEARNED";
// Legacy build setting. It does not establish adequate power at the receiver;
// review the antenna and test power before the next observed RF campaign.
constexpr int8_t outputPowerDbm = easywave4x::powerDbm;
constexpr uint8_t syncProfiles[] = {0x55, 0x56, 0x59, 0x5A};
constexpr size_t profileCount = sizeof(syncProfiles);
constexpr size_t physicalLength = 9, fifoLength = 8;
constexpr uint32_t profileWindowMs = 1000, statusIntervalMs = 3600000;
constexpr uint32_t displayIntervalMs = 500, burstGapMs = 250;
constexpr uint32_t cadenceMs = 37, cadenceMinMs = 25, cadenceMaxMs = 200;
constexpr uint32_t cadenceToleranceMs = 15;
constexpr size_t candidateCapacity = 64;
constexpr uint32_t txArmLifetimeMs = 5000;
constexpr uint32_t minimumTxIntervalMs = 1000;
constexpr uint32_t txBudgetWindowMs = 3600000;
// 35 s/hour leaves margin below the 1% (36 s/hour) duty-cycle ceiling.
constexpr uint32_t maxTxAirtimePerWindowUs = 35000000;
constexpr uint32_t framePeriodUs = easywave4x::framePeriodUs;
constexpr uint8_t txChipsPerRepeat = easywave4x::physicalChips;
constexpr uint32_t frameAirtimeUs = easywave4x::nominalFrameAirtimeUs;
constexpr size_t txPayloadLength = easywave4x::payloadBytes;
constexpr float txBitRateKbps = easywave4x::bitRateKbps;
constexpr uint8_t txRepeats = easywave4x::repeats;
constexpr uint32_t interFrameGapUs = framePeriodUs - frameAirtimeUs;
constexpr uint32_t burstAirtimeUs = easywave4x::nominalBurstAirtimeUs;
constexpr uint8_t txRadioCalls = 1;
constexpr size_t txHistoryCapacity = 360;
constexpr RadioLibIrqFlags_t irqFlags =
    RADIOLIB_IRQ_RX_DEFAULT_FLAGS | (1UL << RADIOLIB_IRQ_SYNC_WORD_VALID);
constexpr RadioLibIrqFlags_t irqMask = (1UL << RADIOLIB_IRQ_RX_DONE);

struct KnownButton {
  const char* alias;
  const char* action;
  uint32_t word;
  bool inverted;
  int8_t capturedTail;
  constexpr KnownButton(const char* a = nullptr, const char* act = nullptr, uint32_t w = 0, bool inv = false, int8_t tail = -1)
      : alias(a), action(act), word{w}, inverted(inv), capturedTail(tail) {}
};

// No arbitrary RF word is accepted over serial or MQTT. Multiple physical
// buttons may intentionally map to the same Nikobus action.
constexpr std::array<KnownButton, 0> knownButtons{};

struct Candidate {
  bool used = false;
  bool learned = false;
  uint32_t word = 0;
  uint32_t firstSeenMs = 0;
  uint32_t lastSeenMs = 0;
  uint32_t observations = 0;
  uint32_t cadenceHits = 0;
  uint32_t burstCount = 0;
  float peakRssiDbm = -130.0F;
  uint8_t sync = 0;
  int8_t sideVariant = -1;
  int8_t capturedTail = -1;
  uint8_t tailCount = 0;
};

volatile bool irq = false;
bool ready = false;
bool transmitting = false;
size_t profile = 0;
uint32_t profileStartedMs = 0, fifoPackets = 0;
uint32_t rejectedManchester = 0, manchesterWords = 0;
uint32_t integrityKnown = 0, integrityUnknown = 0;
uint32_t learnedCount = 0, learnedEvents = 0;
uint32_t txCount = 0, txRejected = 0, lastTxMs = 0;
uint32_t txHistoryMs[txHistoryCapacity] = {};
size_t txHistoryCount = 0;
uint32_t armedNonce = 0, armedUntilMs = 0, lastUsedNonce = 0;
bool nonceArmed = false;
Candidate candidates[candidateCapacity];
char serialLine[96] = {};
size_t serialLength = 0;
}

namespace learnedTx {
Preferences storage;
Frame saved[capacity] = {};
char aliases[capacity][12] = {};
gateway::KnownButton buttons[capacity];
void refresh(size_t i) {
  snprintf(aliases[i], sizeof(aliases[i]), "rx_%08lX", static_cast<unsigned long>(saved[i].word));
  buttons[i] = {aliases[i], "user_assigned", saved[i].word, false, static_cast<int8_t>(saved[i].tail)};
}
void load() {
  storage.begin("easywave_tx", false);
  if (storage.getBytesLength("frames") == sizeof(saved)) storage.getBytes("frames", saved, sizeof(saved));
  for (size_t i = 0; i < capacity; ++i) refresh(i);
}
bool selfTest() {
  uint8_t bytes[111];
  for (const auto& button : gateway::knownButtons) {
    if (button.inverted) continue;
    encode({button.word, 1}, bytes);
    const uint8_t* legacy = easywave4x::payloadFor(button.word, false);
    if (!legacy || memcmp(bytes, legacy, sizeof(bytes)) != 0) return false;
  }
  // Independent received Manchester prefixes for the two complete HD references.
  const uint8_t reference[8] = {0x59,0x59,0x99,0x5A,0x9A,0xAA,0x5A,0x95};
  encode({0x0C400707UL, 1}, bytes);
  for (size_t chip = 0; chip < 64; ++chip) {
    const uint8_t actual = (bytes[chip / 2] >> (chip % 2 ? 0 : 4)) & 15;
    const bool expected = (reference[chip / 8] >> (7 - chip % 8)) & 1;
    if (actual != (expected ? 15 : 0)) return false;
  }
  if (bytes[32] != 0xF0) return false;
  encode({0x0C400707UL, 0}, bytes);
  for (size_t repeat = 0; repeat < 3; ++repeat) {
    if (bytes[repeat * 37 + 32] != 0x0F) return false;
    for (size_t i = 33; i < 37; ++i) if (bytes[repeat * 37 + i] != 0) return false;
  }
  return true;
}
bool install(Frame f) {
  if (!valid(f)) return false;
  size_t slot = capacity;
  for (size_t i = 0; i < capacity; ++i) {
    if (saved[i].word == f.word) return saved[i].tail == f.tail;
    if (!valid(saved[i]) && slot == capacity) slot = i;
  }
  bool observed = false;
  for (const auto& c : gateway::candidates)
    if (c.used && c.word == f.word && c.sideVariant >= 0 && c.capturedTail == f.tail && c.tailCount >= 2) observed = true;
  if (!observed || slot == capacity) return false;
  saved[slot] = f;
  if (storage.putBytes("frames", saved, sizeof(saved)) != sizeof(saved)) { saved[slot] = {}; return false; }
  refresh(slot);
  return true;
}
}


void IRAM_ATTR onRadioIrq() { gateway::irq = true; }

bool ok(const char* operation, int16_t state) {
  if (state == RADIOLIB_ERR_NONE) return true;
  Serial.printf("CONFIG_ERROR operation=%s code=%d\n", operation, state);
  return false;
}

uint8_t crc8(const uint8_t* data, size_t length) {
  uint8_t crc = 0;
  for (size_t i = 0; i < length; ++i) {
    crc ^= data[i];
    for (uint8_t bit = 0; bit < 8; ++bit) {
      crc = (crc & 0x80U) ? static_cast<uint8_t>((crc << 1U) ^ 0x1DU)
                          : static_cast<uint8_t>(crc << 1U);
    }
  }
  return crc;
}

void wordBytes(uint32_t word, uint8_t* bytes) {
  bytes[0] = word >> 24U;
  bytes[1] = word >> 16U;
  bytes[2] = word >> 8U;
  bytes[3] = word;
}

bool decodeManchester(const uint8_t* physical, uint32_t& word) {
  word = 0;
  for (size_t bit = 0; bit < 32; ++bit) {
    const size_t first = bit * 2U, second = first + 1U;
    const uint8_t a = (physical[first / 8U] >> (7U - first % 8U)) & 1U;
    const uint8_t b = (physical[second / 8U] >> (7U - second % 8U)) & 1U;
    if (a == 0U && b == 1U) word <<= 1U;
    else if (a == 1U && b == 0U) word = (word << 1U) | 1U;
    else return false;
  }
  return true;
}

uint8_t currentSync() { return gateway::syncProfiles[gateway::profile]; }

void showStatus() {
  char line2[24], line3[24], line4[24];
  snprintf(line2, sizeof(line2), "RX sync %02X scan", currentSync());
  snprintf(line3, sizeof(line3), "learn %lu event %lu",
           static_cast<unsigned long>(gateway::learnedCount),
           static_cast<unsigned long>(gateway::learnedEvents));
  snprintf(line4, sizeof(line4), "TX %lu reject %lu",
           static_cast<unsigned long>(gateway::txCount),
           static_cast<unsigned long>(gateway::txRejected));
  display.clearBuffer();
  display.setFont(u8g2_font_6x12_tf);
  display.drawStr(0, 12, "Easywave gateway V8");
  display.drawStr(0, 29, line2);
  display.drawStr(0, 45, line3);
  display.drawStr(0, 61, line4);
  display.sendBuffer();
}

int16_t startReceive() {
  gateway::irq = false;
  return radio.startReceive(RADIOLIB_SX126X_RX_TIMEOUT_INF,
                            gateway::irqFlags, gateway::irqMask, 0);
}

bool applyRxProfile(size_t profile, bool announce) {
  gateway::ready = false;
  if (!ok("standby_before_profile", radio.standby())) return false;
  // TX uses 8.006 kbps; physical Easywave RX must return to 2.0015 kbps.
  if (!ok("setBitRate_rx", radio.setBitRate(gateway::bitRateKbps))) return false;
  gateway::profile = profile % gateway::profileCount;
  uint8_t sync = currentSync();
  if (!ok("setSyncWord_rx_8_bits", radio.setSyncWord(&sync, 1))) return false;
  if (!ok("setPreambleLength_rx_0", radio.setPreambleLength(0))) return false;
  if (!ok("fixedPacketLengthMode_rx_7",
          radio.fixedPacketLengthMode(gateway::fifoLength))) return false;
  if (!ok("startReceive_profile", startReceive())) return false;
  gateway::profileStartedMs = millis();
  gateway::ready = true;
  if (announce) {
    Serial.printf(
        "DISCOVERY_READY sync=%02X profile=%u/%u mode=continuous_gateway "
        "sparse_logging=true tx_allowlist=%u\n",
        currentSync(), static_cast<unsigned>(gateway::profile + 1),
        static_cast<unsigned>(gateway::profileCount),
        static_cast<unsigned>(gateway::knownButtons.size()));
    showStatus();
  }
  return true;
}

bool configureRadio() {
  // The modem exposes raw NRZ levels; software validates Easywave Manchester/CRC.
  const int16_t state = radio.beginFSK(
      gateway::frequencyMHz, gateway::bitRateKbps, gateway::deviationKHz,
      gateway::bandwidthKHz, gateway::outputPowerDbm, 0, 1.6F, false);
  if (!ok("beginFSK", state)) return false;
  if (!ok("setDataShaping", radio.setDataShaping(gateway::dataShaping)))
    return false;
  if (!ok("setCRC(0)", radio.setCRC(0))) return false;
  if (!ok("setEncoding(NRZ)", radio.setEncoding(RADIOLIB_ENCODING_NRZ)))
    return false;
  radio.setPacketReceivedAction(onRadioIrq);
  return applyRxProfile(0, true);
}

bool cadencePlausible(uint32_t gapMs) {
  if (gapMs < gateway::cadenceMinMs || gapMs > gateway::cadenceMaxMs)
    return false;
  const uint32_t multiple =
      (gapMs + gateway::cadenceMs / 2U) / gateway::cadenceMs;
  if (multiple == 0) return false;
  const uint32_t expected = multiple * gateway::cadenceMs;
  const uint32_t error =
      gapMs > expected ? gapMs - expected : expected - gapMs;
  return error <= gateway::cadenceToleranceMs;
}

gateway::Candidate& candidateFor(uint32_t word, uint32_t now) {
  gateway::Candidate* freeSlot = nullptr;
  gateway::Candidate* oldest = &gateway::candidates[0];
  for (size_t index = 0; index < gateway::candidateCapacity; ++index) {
    gateway::Candidate& candidate = gateway::candidates[index];
    if (candidate.used && candidate.word == word) return candidate;
    if (!candidate.used && freeSlot == nullptr) freeSlot = &candidate;
    if (candidate.lastSeenMs < oldest->lastSeenMs) oldest = &candidate;
  }
  gateway::Candidate* selected = freeSlot != nullptr ? freeSlot : oldest;
  *selected = gateway::Candidate{};
  selected->used = true;
  selected->word = word;
  selected->firstSeenMs = now;
  return *selected;
}

const char* integrityName(int8_t sideVariant) {
  if (sideVariant == 0) return "base_residue_18";
  if (sideVariant == 1) return "side_mask_8E_residue_98";
  return "unknown_repeated_structure";
}

void observeWord(uint32_t word, float rssi, uint32_t now, int8_t tail = -1) {
  // Recognition has two layers: a 32-bit identity/integrity model and the actually
  // observed final data bit. Reproducing a new command needs both layers.
  uint8_t bytes[4];
  wordBytes(word, bytes);
  const uint8_t residue = crc8(bytes, sizeof(bytes));
  const uint32_t serial22 = word >> 10U;
  const uint8_t key2 = (word >> 8U) & 0x03U;
  const uint8_t check8 = word;
  const uint8_t predicted = crc8(bytes, 3) ^ 0xB4U;
  const bool primary = check8 == predicted && residue == 0x18U;
  const bool alternate =
      check8 == static_cast<uint8_t>(predicted ^ 0x8EU) && residue == 0x98U;
  const int8_t sideVariant = primary ? 0 : (alternate ? 1 : -1);
  if (sideVariant >= 0) ++gateway::integrityKnown;
  else ++gateway::integrityUnknown;
  ++gateway::manchesterWords;

  gateway::Candidate& candidate = candidateFor(word, now);
  const uint32_t gapMs =
      candidate.observations == 0 ? 0 : now - candidate.lastSeenMs;
  const bool newBurst = candidate.observations == 0 || gapMs > gateway::burstGapMs;
  if (newBurst) ++candidate.burstCount;
  else if (cadencePlausible(gapMs)) ++candidate.cadenceHits;
  ++candidate.observations;
  candidate.lastSeenMs = now;
  candidate.sync = currentSync();
  candidate.sideVariant = sideVariant;
  if (tail >= 0 && sideVariant >= 0 && serial22 != 0) {
    candidate.tailCount = candidate.capturedTail == tail ? (candidate.tailCount < 255 ? candidate.tailCount + 1 : 255) : 1;
    candidate.capturedTail = tail;
    if (candidate.tailCount == 2 || newBurst)
      Serial.printf("EASYWAVE_FRAME word=%08lX tail=%d confirmations=%u source=rf\n", static_cast<unsigned long>(word), tail, candidate.tailCount);
  } else { candidate.capturedTail = -1; candidate.tailCount = 0; }
  if (candidate.observations == 1 || rssi > candidate.peakRssiDbm)
    candidate.peakRssiDbm = rssi;
  gateway::profileStartedMs = now;

  const bool structuralLearning =
      (candidate.observations >= 3 && candidate.cadenceHits >= 2) ||
      (candidate.observations >= 3 && candidate.burstCount >= 3);
  const bool newlyLearned =
      !candidate.learned && (sideVariant >= 0 || structuralLearning);
  if (newlyLearned) {
    candidate.learned = true;
    ++gateway::learnedCount;
    Serial.printf(
        "EASYWAVE_LEARNED timestamp_ms=%lu reason=%s sync=%02X "
        "word=%08lX serial22=%06lX key2=%u side_variant=%d check8=%02X "
        "check8_base=%02X check8_mask=%02X crc_residue=%02X "
        "integrity_class=%s observations=%lu cadence_hits=%lu bursts=%lu "
        "peak_rssi_dbm=%.1f plausibility_valid=true\n",
        static_cast<unsigned long>(now),
        sideVariant >= 0 ? "known_integrity" : "repeated_cadence", currentSync(),
        static_cast<unsigned long>(word), static_cast<unsigned long>(serial22),
        static_cast<unsigned>(key2), static_cast<int>(sideVariant), check8,
        predicted, static_cast<unsigned>(check8 ^ predicted), residue,
        integrityName(sideVariant),
        static_cast<unsigned long>(candidate.observations),
        static_cast<unsigned long>(candidate.cadenceHits),
        static_cast<unsigned long>(candidate.burstCount), candidate.peakRssiDbm);
  }
  if (candidate.learned && (newBurst || newlyLearned)) {
    ++gateway::learnedEvents;
    Serial.printf(
        "EASYWAVE_EVENT timestamp_ms=%lu rssi_dbm=%.1f sync=%02X "
        "word=%08lX serial22=%06lX key2=%u side_variant=%d check8=%02X "
        "crc_residue=%02X integrity_class=%s candidate_observations=%lu "
        "candidate_bursts=%lu cadence_hits=%lu plausibility_valid=true "
        "event=%lu source=rf\n",
        static_cast<unsigned long>(now), rssi, currentSync(),
        static_cast<unsigned long>(word), static_cast<unsigned long>(serial22),
        static_cast<unsigned>(key2), static_cast<int>(sideVariant), check8,
        residue, integrityName(sideVariant),
        static_cast<unsigned long>(candidate.observations),
        static_cast<unsigned long>(candidate.burstCount),
        static_cast<unsigned long>(candidate.cadenceHits),
        static_cast<unsigned long>(gateway::learnedEvents));
  }
}

void handleRadioIrq() {
  // The ISR only signals work; packet decoding and serial reporting happen here.
  if (!gateway::ready || gateway::transmitting || !gateway::irq) return;
  gateway::irq = false;
  const uint32_t flags = radio.getIrqFlags();
  if ((flags & RADIOLIB_SX126X_IRQ_RX_DONE) == 0) {
    radio.clearIrqFlags(flags);
    if (!ok("startReceive_after_non_rx_irq", startReceive()))
      gateway::ready = false;
    return;
  }
  uint8_t fifo[gateway::fifoLength] = {};
  const int16_t state = radio.readData(fifo, sizeof(fifo));
  const float rssi = radio.getRSSI(true);
  const uint32_t now = millis();
  if (state == RADIOLIB_ERR_NONE) {
    ++gateway::fifoPackets;
    uint8_t physical[gateway::physicalLength] = {};
    physical[0] = currentSync();
    memcpy(physical + 1, fifo, sizeof(fifo));
    uint32_t word = 0;
    if (!decodeManchester(physical, word)) ++gateway::rejectedManchester;
    else {
      int8_t tail = -1;
      const uint8_t pair = physical[8] >> 6;
      if (pair == 1) tail = 0;
      if (pair == 2) tail = 1;
      observeWord(word, rssi, now, tail);
    }
  } else {
    Serial.printf("PACKET_ERROR timestamp_ms=%lu code=%d rssi_dbm=%.1f\n",
                  static_cast<unsigned long>(now), state, rssi);
  }
  if (!ok("startReceive_after_packet", startReceive())) gateway::ready = false;
}

const gateway::KnownButton* findButton(const char* alias) {
  for (size_t i = 0; i < learnedTx::capacity; ++i)
    if (learnedTx::valid(learnedTx::saved[i]) && strcmp(learnedTx::aliases[i], alias) == 0) return &learnedTx::buttons[i];
  for (const auto& button : gateway::knownButtons) {
    if (strcmp(button.alias, alias) == 0) return &button;
  }
  return nullptr;
}

bool parseNonce(const char* text, uint32_t& nonce) {
  if (text == nullptr || strlen(text) != 8) return false;
  nonce = 0;
  for (size_t index = 0; index < 8; ++index) {
    const char c = text[index];
    if (!isxdigit(static_cast<unsigned char>(c))) return false;
    nonce = (nonce << 4U) | static_cast<uint32_t>(
        c >= '0' && c <= '9' ? c - '0' : 10 + (toupper(c) - 'A'));
  }
  return nonce != 0;
}

void setPackedBit(uint8_t* bytes, size_t index, uint8_t value) {
  if (value) bytes[index / 8U] |= static_cast<uint8_t>(1U << (7U - index % 8U));
}

uint8_t manchesterChip(uint32_t word, size_t chipIndex) {
  if (chipIndex >= 64) return chipIndex == 64 ? 1U : 0U;  // final bit 1 -> 10
  const size_t bitIndex = chipIndex / 2U;
  const uint8_t bit = (word >> (31U - bitIndex)) & 1U;
  return chipIndex % 2U == 0 ? (bit ? 1U : 0U) : (bit ? 0U : 1U);
}

void buildTxFrame(uint32_t word, uint8_t& syncRegister, uint8_t* payload) {
  memset(payload, 0, 8);
  const uint8_t first = manchesterChip(word, 0);
  const uint8_t second = manchesterChip(word, 1);
  syncRegister = static_cast<uint8_t>((first << 7U) | (second << 6U));
  for (size_t index = 0; index < 64; ++index)
    setPackedBit(payload, index, manchesterChip(word, index + 2U));
}

void buildTxPayload64(uint32_t word, uint8_t* payload) {
  memset(payload, 0, 8);
  for (size_t index = 0; index < 64; ++index)
    setPackedBit(payload, index, manchesterChip(word, index));
}

const uint8_t* payloadForButton(const gateway::KnownButton& button) {
  if (button.capturedTail >= 0) {
    static uint8_t bytes[111];
    learnedTx::encode({button.word, static_cast<uint8_t>(button.capturedTail)}, bytes);
    return bytes;
  }
  return easywave4x::payloadFor(button.word, button.inverted);
}

void printTxPlan(const gateway::KnownButton& button) {
  const uint8_t* payload = payloadForButton(button);
  if (payload == nullptr) {
    Serial.println("TX_PLAN_ERROR reason=missing_generated_payload");
    return;
  }
  Serial.printf(
      "TX_PLAN alias=%s action=%s word=%08lX sync_bits=0 preamble_bits=0 "
      "polarity=%s transport_bits=%u transport_bitrate_bps=%.0f tx_shaping=none payload=",
      button.alias, button.action, static_cast<unsigned long>(button.word),
      button.inverted ? "inverted" : "normal",
      static_cast<unsigned>(gateway::txPayloadLength * 8),
      gateway::txBitRateKbps * 1000.0F);
  for (size_t index = 0; index < gateway::txPayloadLength; ++index)
    Serial.printf("%02X", payload[index]);
  Serial.printf(
      " chips=%u repeats=%u frame_airtime_us=%lu gap_us=%lu "
      "burst_airtime_us=%lu min_interval_ms=%lu budget_window_ms=%lu "
      "max_window_airtime_us=%lu max_bursts_per_window=%lu "
      "power_dbm=%d dry_run=true\n",
      static_cast<unsigned>(gateway::txChipsPerRepeat),
      static_cast<unsigned>(gateway::txRepeats),
      static_cast<unsigned long>(gateway::frameAirtimeUs),
      static_cast<unsigned long>(gateway::interFrameGapUs),
      static_cast<unsigned long>(gateway::burstAirtimeUs),
      static_cast<unsigned long>(gateway::minimumTxIntervalMs),
      static_cast<unsigned long>(gateway::txBudgetWindowMs),
      static_cast<unsigned long>(gateway::maxTxAirtimePerWindowUs),
      static_cast<unsigned long>(gateway::maxTxAirtimePerWindowUs /
                                 gateway::burstAirtimeUs),
      static_cast<int>(gateway::outputPowerDbm));
}

void purgeTxHistory(uint32_t now) {
  size_t kept = 0;
  for (size_t index = 0; index < gateway::txHistoryCount; ++index) {
    if (now - gateway::txHistoryMs[index] < gateway::txBudgetWindowMs)
      gateway::txHistoryMs[kept++] = gateway::txHistoryMs[index];
  }
  gateway::txHistoryCount = kept;
}

uint32_t txWindowAirtimeUs(uint32_t now) {
  purgeTxHistory(now);
  return static_cast<uint32_t>(gateway::txHistoryCount) *
         gateway::burstAirtimeUs;
}

bool reserveTxBudget(uint32_t now, uint32_t nonce) {
  // Firmware enforces its own budget even when the host bridge misbehaves.
  const uint32_t usedUs = txWindowAirtimeUs(now);
  if (usedUs + gateway::burstAirtimeUs >
      gateway::maxTxAirtimePerWindowUs) {
    ++gateway::txRejected;
    const uint32_t retryAfterMs = gateway::txHistoryCount == 0
                                      ? gateway::txBudgetWindowMs
                                      : gateway::txBudgetWindowMs -
                                            (now - gateway::txHistoryMs[0]);
    Serial.printf(
        "TX_REJECT reason=hourly_airtime_budget request=%08lX "
        "window_airtime_us=%lu limit_us=%lu retry_after_ms=%lu\n",
        static_cast<unsigned long>(nonce), static_cast<unsigned long>(usedUs),
        static_cast<unsigned long>(gateway::maxTxAirtimePerWindowUs),
        static_cast<unsigned long>(retryAfterMs));
    return false;
  }
  if (gateway::txHistoryCount >= gateway::txHistoryCapacity) {
    ++gateway::txRejected;
    Serial.printf("TX_REJECT reason=tx_history_capacity request=%08lX\n",
                  static_cast<unsigned long>(nonce));
    return false;
  }
  // Reserve the complete burst before RF starts. Even a partial radio failure
  // therefore cannot make the airtime accounting optimistic.
  gateway::txHistoryMs[gateway::txHistoryCount++] = now;
  gateway::lastTxMs = now;
  return true;
}

bool restoreRx(size_t savedProfile) {
  gateway::transmitting = false;
  gateway::irq = false;
  const bool restored = applyRxProfile(savedProfile, false);
  Serial.printf("RX_RESUMED success=%s profile=%u sync=%02X\n",
                restored ? "true" : "false",
                static_cast<unsigned>(gateway::profile + 1), currentSync());
  return restored;
}

void transmitOnce(const gateway::KnownButton& button, uint32_t nonce) {
  // One radio call sends the continuous three-repeat payload. Held levels remain
  // inside that payload; they do not create an inter-frame radio-off interval.
  const uint32_t now = millis();
  gateway::nonceArmed = false;  // one-shot before touching the radio
  if (nonce == gateway::lastUsedNonce) {
    ++gateway::txRejected;
    Serial.printf("TX_REJECT reason=duplicate_nonce request=%08lX\n",
                  static_cast<unsigned long>(nonce));
    return;
  }
  if (gateway::txHistoryCount > 0 &&
      now - gateway::lastTxMs < gateway::minimumTxIntervalMs) {
    ++gateway::txRejected;
    Serial.printf(
        "TX_REJECT reason=duty_cycle_guard request=%08lX retry_after_ms=%lu\n",
        static_cast<unsigned long>(nonce),
        static_cast<unsigned long>(gateway::minimumTxIntervalMs -
                                   (now - gateway::lastTxMs)));
    return;
  }
  if (!reserveTxBudget(now, nonce)) return;

  gateway::lastUsedNonce = nonce;
  gateway::ready = false;
  gateway::transmitting = true;
  const size_t savedProfile = gateway::profile;
  if (!ok("standby_before_tx", radio.standby())) {
    ++gateway::txRejected;
    restoreRx(savedProfile);
    return;
  }

  uint8_t payload[gateway::txPayloadLength];
  const uint8_t* generated = payloadForButton(button);
  if (generated == nullptr) {
    ++gateway::txRejected;
    Serial.printf("TX_REJECT reason=missing_generated_payload request=%08lX\n",
                  static_cast<unsigned long>(nonce));
    restoreRx(savedProfile);
    return;
  }
  memcpy(payload, generated, sizeof(payload));
  uint8_t unusedSync = 0;
  // Public RadioLib API, zero sync bytes. No private syncWordLength override.
  if (!ok("setBitRate_tx_4x", radio.setBitRate(gateway::txBitRateKbps)) ||
      !ok("setSyncWord_tx_disabled", radio.setSyncWord(&unusedSync, size_t(0)))) {
    ++gateway::txRejected;
    restoreRx(savedProfile);
    return;
  }
  if (!ok("setPreambleLength_tx_0", radio.setPreambleLength(0)) ||
      !ok("fixedPacketLengthMode_tx", radio.fixedPacketLengthMode(sizeof(payload)))) {
    ++gateway::txRejected;
    restoreRx(savedProfile);
    return;
  }

  Serial.printf(
      "TX_STARTED request=%08lX alias=%s action=%s word=%08lX repeats=%u "
      "power_dbm=%d\n", static_cast<unsigned long>(nonce), button.alias,
      button.action, static_cast<unsigned long>(button.word),
      static_cast<unsigned>(gateway::txRepeats),
      static_cast<int>(gateway::outputPowerDbm));
  bool success = true;
  for (uint8_t repeat = 0; repeat < gateway::txRadioCalls; ++repeat) {
    const int16_t state = radio.transmit(payload, sizeof(payload));
    if (state != RADIOLIB_ERR_NONE) {
      Serial.printf("TX_RADIO_ERROR request=%08lX repeat=%u code=%d\n",
                    static_cast<unsigned long>(nonce),
                    static_cast<unsigned>(repeat + 1), state);
      success = false;
      break;
    }
    if (repeat + 1U < gateway::txRadioCalls)
      delayMicroseconds(gateway::interFrameGapUs);
  }
  if (success) {
    ++gateway::txCount;
  } else {
    ++gateway::txRejected;
  }
  const bool rxRestored = restoreRx(savedProfile);
  Serial.printf(
      "TX_COMPLETE request=%08lX alias=%s success=%s repeats=%u "
      "airtime_us=%lu rx_resumed=%s polarity=%s no_hold_repeat=true\n",
      static_cast<unsigned long>(nonce), button.alias,
      success ? "true" : "false", static_cast<unsigned>(gateway::txRepeats),
      static_cast<unsigned long>(gateway::burstAirtimeUs),
      rxRestored ? "true" : "false", button.inverted ? "inverted" : "normal");
}


void printStatus() {
  const uint32_t windowAirtimeUs = txWindowAirtimeUs(millis());
  Serial.printf(
      "GATEWAY_STATUS timestamp_ms=%lu sync=%02X fifo_packets=%lu "
      "rejected_manchester=%lu manchester_words=%lu integrity_known=%lu "
      "integrity_unknown=%lu learned_candidates=%lu learned_events=%lu "
      "tx_count=%lu tx_rejected=%lu tx_armed=%s tx_power_dbm=%d "
      "min_tx_interval_ms=%lu burst_airtime_us=%lu tx_window_bursts=%u "
      "tx_window_airtime_us=%lu tx_window_limit_us=%lu tx_shaping=%s "
      "logging=sparse firmware=%s tx_chips=%u tx_payload_bytes=%u "
      "tx_transport_bitrate_bps=%.1f\n",
      static_cast<unsigned long>(millis()), currentSync(),
      static_cast<unsigned long>(gateway::fifoPackets),
      static_cast<unsigned long>(gateway::rejectedManchester),
      static_cast<unsigned long>(gateway::manchesterWords),
      static_cast<unsigned long>(gateway::integrityKnown),
      static_cast<unsigned long>(gateway::integrityUnknown),
      static_cast<unsigned long>(gateway::learnedCount),
      static_cast<unsigned long>(gateway::learnedEvents),
      static_cast<unsigned long>(gateway::txCount),
      static_cast<unsigned long>(gateway::txRejected),
      gateway::nonceArmed ? "true" : "false",
      static_cast<int>(gateway::outputPowerDbm),
      static_cast<unsigned long>(gateway::minimumTxIntervalMs),
      static_cast<unsigned long>(gateway::burstAirtimeUs),
      static_cast<unsigned>(gateway::txHistoryCount),
      static_cast<unsigned long>(windowAirtimeUs),
      static_cast<unsigned long>(gateway::maxTxAirtimePerWindowUs),
      gateway::shapingName, gateway::firmwareIdentity,
      static_cast<unsigned>(gateway::txChipsPerRepeat),
      static_cast<unsigned>(gateway::txPayloadLength),
      gateway::txBitRateKbps * 1000.0F);
}

void rejectCommand(const char* reason) {
  ++gateway::txRejected;
  Serial.printf("COMMAND_REJECT reason=%s\n", reason);
}

void handleCommand(char* line) {
  // STATUS/PLAN inspect state. INSTALL_TX records observed evidence without RF.
  // Only a valid armed TX command enters transmitOnce().
  char* save = nullptr;
  char* command = strtok_r(line, " ", &save);
  if (command == nullptr) return;
  if (strcmp(command, "STATUS") == 0) {
    printStatus();
    return;
  }
  if (strcmp(command, "NEXT") == 0) {
    applyRxProfile(gateway::profile + 1, true);
    return;
  }
  if (strcmp(command, "RESET_DISCOVERY") == 0) {
    memset(gateway::candidates, 0, sizeof(gateway::candidates));
    gateway::learnedCount = 0;
    gateway::learnedEvents = 0;
    Serial.println("SELF_LEARNING_RESET requested=true candidates_cleared=true");
    applyRxProfile(0, true);
    return;
  }
  if (strcmp(command, "PLAN") == 0) {
    const char* alias = strtok_r(nullptr, " ", &save);
    const gateway::KnownButton* button = alias ? findButton(alias) : nullptr;
    if (button == nullptr) rejectCommand("unknown_alias");
    else printTxPlan(*button);
    return;
  }
  if (strcmp(command, "INSTALL_TX") == 0) {
    const char* wordText = strtok_r(nullptr, " ", &save);
    const char* tailText = strtok_r(nullptr, " ", &save);
    const char* request = strtok_r(nullptr, " ", &save);
    uint32_t word = 0, nonce = 0;
    if (!parseNonce(wordText, word) || !parseNonce(request, nonce) || !tailText ||
        strlen(tailText) != 1 || (tailText[0] != '0' && tailText[0] != '1') || strtok_r(nullptr, " ", &save)) {
      rejectCommand("invalid_install"); return;
    }
    const bool installed = learnedTx::install({word, static_cast<uint8_t>(tailText[0] - '0')});
    Serial.printf("TX_INSTALLED request=%08lX success=%s word=%08lX\n", static_cast<unsigned long>(nonce), installed ? "true" : "false", static_cast<unsigned long>(word));
    return;
  }
  if (strcmp(command, "ARM_TX") == 0) {
    const char* nonceText = strtok_r(nullptr, " ", &save);
    uint32_t nonce = 0;
    if (!parseNonce(nonceText, nonce) || nonce == gateway::lastUsedNonce) {
      rejectCommand("invalid_or_used_nonce");
      return;
    }
    gateway::armedNonce = nonce;
    gateway::armedUntilMs = millis() + gateway::txArmLifetimeMs;
    gateway::nonceArmed = true;
    Serial.printf("TX_ARMED request=%08lX lifetime_ms=%lu one_shot=true\n",
                  static_cast<unsigned long>(nonce),
                  static_cast<unsigned long>(gateway::txArmLifetimeMs));
    return;
  }
  if (strcmp(command, "TX") == 0) {
    const char* alias = strtok_r(nullptr, " ", &save);
    const char* nonceText = strtok_r(nullptr, " ", &save);
    uint32_t nonce = 0;
    const gateway::KnownButton* button = alias ? findButton(alias) : nullptr;
    if (button == nullptr || !parseNonce(nonceText, nonce)) {
      rejectCommand("invalid_tx_command");
      return;
    }
    if (!gateway::nonceArmed || nonce != gateway::armedNonce ||
        static_cast<int32_t>(millis() - gateway::armedUntilMs) > 0) {
      gateway::nonceArmed = false;
      rejectCommand("tx_not_armed_or_expired");
      return;
    }
    transmitOnce(*button, nonce);
    return;
  }
  rejectCommand("unknown_command");
}

void handleSerial() {
  while (Serial.available()) {
    const char c = Serial.read();
    if (c == '\r') continue;
    if (c == '\n') {
      gateway::serialLine[gateway::serialLength] = '\0';
      handleCommand(gateway::serialLine);
      gateway::serialLength = 0;
      continue;
    }
    if (gateway::serialLength + 1U >= sizeof(gateway::serialLine)) {
      gateway::serialLength = 0;
      rejectCommand("line_too_long");
      continue;
    }
    if (c >= 32 && c <= 126)
      gateway::serialLine[gateway::serialLength++] = c;
  }
}

void setup() {
  Serial.begin(115200);
  delay(1500);
  if (!learnedTx::selfTest()) { Serial.println("LEARNED_TX_SELF_TEST_FAILED"); return; }
  Serial.println("LEARNED_TX_SELF_TEST_OK legacy_payloads=unchanged tail=observed_only auto_tx=false");
  learnedTx::load();
  pinMode(pins::userButton, INPUT_PULLUP);
  pinMode(pins::vext, OUTPUT);
  digitalWrite(pins::vext, LOW);
  delay(100);
  display.begin();
  Serial.println();
  Serial.println(gateway::firmwareIdentity);
  Serial.println("Board: Heltec WiFi LoRa 32 V3");
  Serial.printf(
      "RADIO frequency_mhz=868.314 bitrate_kbps=2.0015 deviation_khz=43.8 "
      "bandwidth_khz=117.3 shaping=%s power_dbm=%d crc_hardware=off "
      "whitening=off\n",
      gateway::shapingName, static_cast<int>(gateway::outputPowerDbm));
  Serial.printf(
      "TX_POLICY allowlist_only=true arbitrary_words=false one_command_one_burst=true "
      "hold_repeat=false repeats_per_burst=%u chips_per_repeat=%u "
      "burst_airtime_us=%lu min_interval_ms=%lu budget_window_ms=%lu "
      "max_window_airtime_us=%lu max_bursts_per_window=%lu "
      "arm_one_shot=true arm_lifetime_ms=%lu\n",
      static_cast<unsigned>(gateway::txRepeats),
      static_cast<unsigned>(gateway::txChipsPerRepeat),
      static_cast<unsigned long>(gateway::burstAirtimeUs),
      static_cast<unsigned long>(gateway::minimumTxIntervalMs),
      static_cast<unsigned long>(gateway::txBudgetWindowMs),
      static_cast<unsigned long>(gateway::maxTxAirtimePerWindowUs),
      static_cast<unsigned long>(gateway::maxTxAirtimePerWindowUs /
                                 gateway::burstAirtimeUs),
      static_cast<unsigned long>(gateway::txArmLifetimeMs));
  Serial.println(
      "COMMANDS STATUS | NEXT | RESET_DISCOVERY | PLAN <alias> | "
      "ARM_TX <nonce8> | TX <alias> <nonce8>");
  for (const auto& button : gateway::knownButtons)
    Serial.printf("TX_ALLOW alias=%s action=%s word=%08lX\n", button.alias,
                  button.action, static_cast<unsigned long>(button.word));
  if (!configureRadio()) {
    Serial.println("GATEWAY_BOOT_READY false");
    return;
  }
  Serial.println("GATEWAY_BOOT_READY true");
}

void loop() {
  // Cooperative scheduling keeps serial handling, RX profile scanning and display
  // updates on the same firmware thread; there is no autonomous TX scheduler.
  handleSerial();
  if (!gateway::ready || gateway::transmitting) {
    delay(2);
    return;
  }
  handleRadioIrq();
  const uint32_t now = millis();
  static uint32_t lastStatus = 0, lastDisplay = 0;
  if (gateway::nonceArmed &&
      static_cast<int32_t>(now - gateway::armedUntilMs) > 0) {
    gateway::nonceArmed = false;
    Serial.println("TX_ARM_EXPIRED one_shot_cleared=true");
  }
  if (now - gateway::profileStartedMs >= gateway::profileWindowMs)
    if (!applyRxProfile(gateway::profile + 1, false)) gateway::ready = false;
  if (now - lastStatus >= gateway::statusIntervalMs) {
    lastStatus = now;
    printStatus();
  }
  if (now - lastDisplay >= gateway::displayIntervalMs) {
    lastDisplay = now;
    showStatus();
  }
  delay(2);
}
