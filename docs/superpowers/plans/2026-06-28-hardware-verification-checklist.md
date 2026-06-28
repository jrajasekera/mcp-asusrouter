# Hardware verification checklist (requires the live router)

Set real `ROUTER_HOSTNAME`/`ROUTER_PASSWORD` (and optionally `.env`), then:

- [ ] `get_ddns_status` returns real status (active/inactive, hostname, hint).
- [ ] `block_device(mac)` then `list_parental_control_rules` shows the new BLOCK
      rule AND every previously-existing rule (confirms no wipe).
- [ ] `unblock_device(mac)` removes only that rule; others remain.
- [ ] Decode the timemap format: in the router web UI create a parental-control
      schedule (e.g. Mon+Tue 21:00–07:00), then `list_parental_control_rules`
      and record the `timemap` string. Repeat for 2–3 schedules to derive the
      encoding, then implement it in `build_timemap` (replace the raise) and add
      exact-string unit tests.
- [ ] `schedule_device_block(mac, timemap="<captured string>")` applies and
      reads back correctly.
