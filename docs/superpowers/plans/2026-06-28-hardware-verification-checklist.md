# Hardware verification checklist (requires the live router)

All items verified 2026-06-28 against an ASUS RT-AX55 (router `192.168.50.1`).

- [x] `get_ddns_status` returns real status (showed DDNS disabled, with hint).
- [x] `block_device(mac)` then `list_parental_control_rules` shows the new BLOCK
      rule AND every previously-existing rule — confirmed no wipe (blocked two
      placeholder MACs, both survived).
- [x] `unblock_device(mac)` removes only that rule; others remain. The no-op
      message for an unknown MAC was also confirmed.
- [x] Decoded the timemap format from the router's own
      `js/weekSchedule/weekSchedule.js` (`PC_transform_offtime_json_to_string`):
      each segment is `W` + `1` (enabled) + weekday (2 digits, Sunday=0 …
      Saturday=6) + start `HHMM` + end `HHMM`, segments joined by `<`. Overnight
      = end < start; `24:00` = end-of-day. Implemented in `build_timemap` with
      ground-truth unit tests.
- [x] `schedule_device_block(mac, timemap="W10121000700")` applied and read back
      byte-identical, then cleaned up.
