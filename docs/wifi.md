# Cozmo Wi-Fi

Cozmo does not join your home network. In SDK mode it is an access point.

| Item | Value |
| --- | --- |
| SSID | `Cozmo_` plus the id printed on the lift |
| Password | Printed on the lift |
| Robot address | `172.31.1.1` |
| Protocol | UDP port `5551` |
| Security | WPA2-PSK. Pairwise ciphers include CCMP and TKIP. The group cipher is TKIP |

The group cipher is the usual reason a modern adapter “sees” the network and then refuses to connect. Many current Linux drivers drop TKIP. You want an adapter whose driver still accepts a TKIP group key.

Adapters based on the Realtek RTL8812BU chipset are a known working class (some TP-Link Archer USB sticks use that chip). On kernels that do not ship that driver you will need the matching out-of-tree module. Confirm the USB id with `lsusb` before installing a driver. Do not install a random Realtek driver for a different chip.

## Dedicated adapter

Use an interface dedicated to Cozmo. Do not use the interface that carries your normal network. The companion creates a NetworkManager profile named `cozmo-ap` with:

- `ipv4.method` auto
- `ipv4.never-default` yes, so this link does not replace your normal default route
- power save disabled
- `802-11-wireless.mtu` 1500. See [MTU and speech](#mtu-and-speech)

If `COZMO_WIFI_IFACE` is empty, the companion tries to pick a Wi-Fi interface that is not the default route. Set the interface name when you have more than one spare radio.

One adapter stays with one robot. A second Cozmo needs a second adapter and a second companion.

## Bring-up check

1. Start the companion with the SSID, password, and interface set.
2. `iw dev <iface> link` shows the `Cozmo_…` SSID.
3. The interface has an address in `172.31.1.0/24`.
4. `ping -I <iface> -c 2 172.31.1.1` gets replies.
5. `GET /v1/status` on the companion reports `robot_connected: true`.

Re-activating the profile while already associated drops the link. Cozmo then leaves SDK mode and hides the access point until you raise and lower the lift again. The companion avoids that when it is already on the right SSID.

## MTU and speech

Cozmo's DHCP server advertises an interface MTU of 576. NetworkManager applies it, but an audio packet with its frame header is about 807 bytes. At MTU 576 Linux splits every audio frame into two IP fragments, and **Cozmo silently drops fragmented datagrams**. You can see it with ping:

```bash
ping -I <iface> -c 5 -s 520 172.31.1.1   # fits in 576: replies
ping -I <iface> -c 5 -s 780 172.31.1.1   # fragmented at 576: no replies
```

The robot never acknowledges the audio frames, so PyCozmo's 62-packet send window fills, keep-alive pings queue behind it, and after about 5 seconds the robot shows `COZMO 01` while the companion logs `link stale` and reconnects. Nothing is heard. Frames from the robot to the host are up to about 1.3 kB, so the robot's own link handles 1500 bytes; only the advertised value is too small.

The companion sets the MTU on the `cozmo-ap` profile every time it joins (on new and existing profiles). On an older companion, or a profile you manage yourself:

```bash
sudo nmcli connection modify cozmo-ap 802-11-wireless.mtu 1500
sudo nmcli device reapply <iface>
ip link show <iface>   # mtu 1500
```

A value set on the profile takes precedence over the DHCP option. `nmcli device reapply` does not drop the association, so the robot stays in SDK mode.

## Home Assistant

The integration only needs to reach the companion HTTP port (default `8790`). It does not need a route to `172.31.1.1`. If the companion runs on another computer, allow that port from Home Assistant and enter that computer’s URL in the config flow.
