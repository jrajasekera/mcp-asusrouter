# ASUS Router MCP

An MCP server that exposes ASUS router monitoring and management as a suite of
tools for AI agents and MCP clients. It is a thin
[FastMCP](https://github.com/modelcontextprotocol/python-sdk) wrapper over the
[`asusrouter`](https://pypi.org/project/asusrouter/) Python library, which does
the actual talking to your router.

> ⚠️ **Some tools change router state** — reboot, firmware upgrade, blocking
> devices, restarting services, changing Wi-Fi settings. An MCP client may invoke
> these autonomously. See [Security Considerations](#security-considerations).

## Requirements

- **Python ≥ 3.11** and [uv](https://docs.astral.sh/uv/).
- An **ASUS router** running AsusWRT (stock or Asuswrt-Merlin) reachable on your
  network, with admin credentials.
- Individual tools depend on router/firmware support for the underlying feature
  (e.g. DSL, AiMesh, AURA, VPN). Unsupported features return an error or empty
  result rather than crashing the server.

Verified against an **RT-AX55**. Other AsusWRT models supported by the
`asusrouter` library should work, but tool behavior can vary by model and
firmware.

## Installation

This project is managed with [uv](https://docs.astral.sh/uv/). Install the
dependencies into a local virtual environment with:

```bash
uv sync
```

## Configuration

Router connection settings are read from environment variables (or a local
`.env` file) — no credentials live in the source. Copy `.env.example` to `.env`
and fill it in:

```bash
cp .env.example .env
# then edit .env
```

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ROUTER_HOSTNAME` | yes | — | Router IP / hostname (usually your LAN gateway, e.g. `192.168.50.1`) |
| `ROUTER_PASSWORD` | yes | — | Admin password |
| `ROUTER_USERNAME` | no | `admin` | Admin username |
| `ROUTER_USE_SSL` | no | `false` | Connect over HTTPS |

The variables may also be set directly in your MCP client config (e.g. an `env`
block) instead of a `.env` file. The server fails fast with a clear error if a
required value is missing.

## Running the server

The server speaks the MCP stdio transport, which is what MCP clients/agents
connect to:

```bash
uv run python server.py
```

It reads credentials from `.env` in the project directory (see
[Configuration](#configuration)).

### Use with Claude Code

```bash
claude mcp add asusrouter --scope user -- \
  uv run --directory /absolute/path/to/mcp-asusrouter python server.py
```

`--directory` makes the server run from the project directory so it finds
`.env`. Restart Claude Code (MCP servers load at session start), then the
`asusrouter` tools are available.

### Use with Claude Desktop (or any stdio MCP client)

Add an entry to the client's MCP config (for Claude Desktop:
`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "asusrouter": {
      "command": "uv",
      "args": ["run", "--directory", "/absolute/path/to/mcp-asusrouter", "python", "server.py"]
    }
  }
}
```

If you prefer not to use a `.env` file, supply the credentials inline instead:

```json
{
  "mcpServers": {
    "asusrouter": {
      "command": "uv",
      "args": ["run", "--directory", "/absolute/path/to/mcp-asusrouter", "python", "server.py"],
      "env": { "ROUTER_HOSTNAME": "192.168.50.1", "ROUTER_PASSWORD": "your-password" }
    }
  }
}
```

## Available Tools

Every tool returns a JSON object. On failure it returns `{"error": "<message>"}`
rather than raising, and a tool with nothing to report returns
`{"message": "..."}`. Argument and return schemas are exposed to your MCP client
at runtime (from each tool's signature and docstring).

> ⚠️ Tools in **System Maintenance**, **WiFi Management**, **Network Security &
> Management**, and **VPN Management** change router state and can interrupt your
> network. The rest are read-only.

### Device Information

1. **get_connected_devices**
   Retrieves information about all devices connected to your router.

   Example prompt:
   ```
   Show me all devices connected to my network right now
   ```

2. **get_aimesh_info**
   Gets information about your AiMesh setup and node status.

   Example prompt:
   ```
   What's the status of my AiMesh network? Are all nodes connected?
   ```

3. **get_boottime**
   Retrieves the router's boot time and calculates uptime.

   Example prompt:
   ```
   How long has my router been running since the last reboot?
   ```

### Network Status

4. **get_network_status**
   Retrieves traffic statistics for all network interfaces.

   Example prompt:
   ```
   What's my current network utilization across all interfaces?
   ```

5. **get_wan_status**
   Gets detailed WAN (internet) connection status and configuration.

   Example prompt:
   ```
   Show me my internet connection details and public IP address
   ```

6. **get_wlan_status**
   Retrieves detailed wireless network configuration.

   Example prompt:
   ```
   What are my current WiFi settings for all bands?
   ```

7. **get_guest_wifi_status**
   Gets guest WiFi network status and configuration.

   Example prompt:
   ```
   Are any guest networks currently enabled on my router?
   ```

8. **get_ports_status**
   Retrieves the status of physical network ports.

   Example prompt:
   ```
   Which physical ports on my router are currently active and what are their speeds?
   ```

9. **get_dsl_status**
   Retrieves DSL connection status and line information for DSL routers.

   Example prompt:
   ```
   What's my DSL connection quality and sync speed?
   ```

10. **run_speedtest**
    Initiates a speed test directly from the router.

    Example prompt:
    ```
    Run a speed test from my router to check my connection speed
    ```

11. **ping_host_from_router**
    Pings a specified host from the router itself.

    Example prompt:
    ```
    Ping google.com from my router to check connectivity
    ```

### Dynamic DNS

12. **get_ddns_status**
    Retrieves the router's Dynamic DNS configuration and current registration status.

    Example prompt:
    ```
    Show me my DDNS settings and whether my hostname is currently registered
    ```

### System Performance

13. **get_system_info**
    Retrieves comprehensive system information.

    Example prompt:
    ```
    Give me a complete system overview of my router
    ```

14. **get_cpu_ram_usage**
    Gets CPU and RAM utilization statistics.

    Example prompt:
    ```
    What's the current CPU and RAM usage on my router?
    ```

15. **get_temperature**
    Retrieves temperature readings from various sensors.

    Example prompt:
    ```
    Is my router running hot? Show me all temperature readings
    ```

16. **get_firmware_info**
    Gets firmware version and update availability information.

    Example prompt:
    ```
    Check if there's a firmware update available for my router
    ```

17. **check_firmware_updates**
    Triggers a check for new firmware updates.

    Example prompt:
    ```
    Force check for new firmware updates now
    ```

18. **start_firmware_upgrade**
    Initiates a firmware upgrade if an update is available.

    Example prompt:
    ```
    Upgrade my router to the latest firmware
    ```

### Network Security & Management

19. **get_parental_control**
    Retrieves parental control configuration and rule settings.

    Example prompt:
    ```
    Show me my current parental control settings and active rules
    ```

20. **set_parental_control_global_state**
    Enables or disables the Parental Controls feature globally.

    Example prompt:
    ```
    Enable parental controls on my router
    ```

21. **set_parental_control_block_all**
    Enables or disables the 'Block All Internet Access' feature.

    Example prompt:
    ```
    Block all internet access for all devices right now
    ```

22. **get_port_forwarding**
    Gets port forwarding rules and configuration.

    Example prompt:
    ```
    List all my configured port forwarding rules
    ```

23. **set_port_forwarding_global_state**
    Enables or disables Port Forwarding globally.

    Example prompt:
    ```
    Disable all port forwarding rules temporarily
    ```

24. **list_parental_control_rules**
    Lists all active parental control rules with device names, MAC addresses, type, and schedule.

    Example prompt:
    ```
    Show me all parental control rules and which devices are currently blocked
    ```

25. **block_device**
    Blocks a device from internet access by adding an always-on parental control rule for the given MAC address.

    Example prompt:
    ```
    Block the device with MAC address AA:BB:CC:DD:EE:FF from the internet
    ```

26. **schedule_device_block**
    Blocks a device on a recurring weekly schedule (see [Scheduling a device block](#scheduling-a-device-block)).

    Example prompt:
    ```
    Block AA:BB:CC:DD:EE:FF from the internet on weeknights from 9pm to 7am
    ```

27. **unblock_device**
    Removes an existing parental control block rule for the specified MAC address, restoring internet access.

    Example prompt:
    ```
    Unblock the device with MAC address AA:BB:CC:DD:EE:FF and restore its internet access
    ```

### VPN Management

28. **get_vpn_config**
    Retrieves VPN client and server configuration status.

    Example prompt:
    ```
    Show me the status of all my VPN configurations
    ```

29. **get_vpn_fusion_status**
    Gets VPN Fusion (VPNC) status and configurations.

    Example prompt:
    ```
    What's the current status of my VPN Fusion profiles?
    ```

30. **control_openvpn_client**
    Enables or disables a specific OpenVPN client profile.

    Example prompt:
    ```
    Connect to my OpenVPN client profile #2
    ```

31. **control_openvpn_server**
    Enables or disables a specific OpenVPN server.

    Example prompt:
    ```
    Turn off my OpenVPN server
    ```

32. **control_wireguard_client**
    Enables or disables a specific WireGuard client profile.

    Example prompt:
    ```
    Connect to my WireGuard VPN #1
    ```

33. **control_wireguard_server**
    Enables or disables a specific WireGuard server.

    Example prompt:
    ```
    Enable my WireGuard server to allow remote connections
    ```

34. **control_vpn_fusion_client**
    Enables or disables a VPN Fusion client profile.

    Example prompt:
    ```
    Disconnect from VPN Fusion profile unit 1
    ```

### WiFi Management

35. **set_wifi_settings**
    Configures wireless network settings.

    Example prompt:
    ```
    Change my 5GHz WiFi password to "NewSecurePassword2023!"
    ```

36. **set_wifi_radio_state**
    Enables or disables the radio for a specific WiFi band.

    Example prompt:
    ```
    Turn off my 2.4GHz WiFi radio but leave 5GHz on
    ```

### System Maintenance

37. **reboot_router**
    Initiates a router reboot.

    Example prompt:
    ```
    Reboot my router now
    ```

38. **rebuild_aimesh_network**
    Triggers a rebuild of the AiMesh network.

    Example prompt:
    ```
    My mesh network seems unstable, rebuild the AiMesh network
    ```

39. **restart_dns_service**
    Restarts the DNS service on the router.

    Example prompt:
    ```
    I'm having DNS issues, restart the DNS service
    ```

40. **restart_httpd_service**
    Restarts the router's web server.

    Example prompt:
    ```
    The router admin page is sluggish, restart the HTTPD service
    ```

### LED & Lighting Control

41. **get_led_status**
    Gets router LED status information.

    Example prompt:
    ```
    Are my router LED lights currently on or off?
    ```

42. **set_led_state**
    Turns router LEDs on or off.

    Example prompt:
    ```
    Turn off all the LED lights on my router for the night
    ```

43. **set_aura_lighting**
    Controls ASUS AURA RGB lighting effects.

    Example prompt:
    ```
    Set my router RGB lighting to static red at 80% brightness
    ```

### Advanced Tools

44. **get_devicemap**
    Gets comprehensive device map information (raw data).

    Example prompt:
    ```
    Show me the detailed devicemap data from my router
    ```

45. **get_router_flags**
    Gets internal router flags and states.

    Example prompt:
    ```
    Show me all internal router flags for debugging
    ```

46. **get_vpn_fusion_client_list_raw**
    Gets the raw VPN Fusion client list string.

    Example prompt:
    ```
    Show me the raw VPN Fusion client list configuration string
    ```

### Scheduling a device block

`schedule_device_block` accepts either friendly inputs or a raw schedule string:

- **Friendly:** `days` (e.g. `["Mon", "Wed"]`), `start_time` and `end_time` as
  `"HH:MM"` (24-hour). They're encoded into the ASUS
  `MULTIFILTER_MACFILTER_DAYTIME_V2` format. An overnight window is expressed as
  end earlier than start (e.g. `21:00`–`07:00`); `end_time` may be `24:00` for
  end-of-day.
- **Raw:** pass a `timemap` string directly (overrides the friendly args). Each
  segment is `W` + `1` + weekday (two digits, **Sunday=0 … Saturday=6**) +
  start `HHMM` + end `HHMM`, with segments joined by `<`. For example, Mon & Wed
  09:00–17:00 is `W10109001700<W10309001700`.

With no schedule arguments, the library's default schedule is applied.

## Development & Testing

```bash
uv sync                 # install runtime + dev dependencies
uv run pytest -q        # run the test suite
```

The tests don't connect to a real router — a root `conftest.py` injects dummy
`ROUTER_*` credentials so `server.py` can be imported, and the suite covers the
pure helpers (`tool_helpers.py`) and tool registration. Anything that actually
touches the router requires a real device.

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the tool pattern and conventions,
and [`CLAUDE.md`](CLAUDE.md) for the architecture in depth.

## Troubleshooting

- **`ValidationError ... ROUTER_HOSTNAME` / `ROUTER_PASSWORD` field required` on
  startup** — credentials aren't set. Create `.env` (see
  [Configuration](#configuration)) or pass them via your client's `env` block.
- **Tools return `{"error": ...}` with a connection/timeout message** — wrong
  `ROUTER_HOSTNAME` (use the router's LAN IP, usually your default gateway),
  wrong credentials, or an `ROUTER_USE_SSL` mismatch (try toggling it).
- **The server starts but your client shows no tools** — make sure the client
  launches it with `uv run --directory <absolute-path>` so it runs from the
  project directory; some clients strip inherited environment variables, so rely
  on `.env` (read from that directory) or an explicit `env` block.
- **A feature-specific tool returns an error or empty result** — your router or
  firmware may not support that feature (DSL, AURA, AiMesh, VPN, etc.).

## Security Considerations

- Credentials are read from environment variables / a local `.env` file, which is git-ignored. Keep `.env` out of version control and restrict its file permissions.
- All tools execute commands on your router. Be cautious when using tools that modify settings or reboot the device.
- Some operations may cause temporary network disruptions or service interruptions.

## Contributing

Contributions are welcome — the `asusrouter` library offers many more
capabilities that could be exposed as additional MCP tools. See
[`CONTRIBUTING.md`](CONTRIBUTING.md) for setup, the tool pattern, and conventions.

## Credits

- Built on the [`asusrouter`](https://github.com/Vaskivskyi/asusrouter) library
  by Yevhenii Vaskivskyi.
- This project is a fork of
  [`rgestudillo/mcp-asusrouter`](https://github.com/rgestudillo/mcp-asusrouter).

## License

Released under the [MIT License](LICENSE).
