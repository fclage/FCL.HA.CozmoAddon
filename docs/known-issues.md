# Known issues

Cozmo’s body firmware and the Wi-Fi link have limits this project cannot remove. The notes below are the ones that look like a broken install.

Do not put the lift password, a companion token, or a filled environment file in an issue.

## The robot is stiff, the face is blank, and commands do nothing

The body is still in an SDK session. The head and lift hold their last pose, so the arms resist when you move them by hand. The screen stays black because the engine owns the display. The camera card keeps showing the last frame it received.

This happens when the companion is still sending packets, including after a power-off that did not actually stop the session, and it is more likely while **Color camera** is on. Color frames are larger. Together with the face updates they can fill the robot’s receive buffer. The motors stay engaged until those packets stop.

Recovery:

1. Stop the companion and leave it stopped: `sudo systemctl stop ha-cozmo-companion`. `systemctl is-active ha-cozmo-companion` should say `inactive`.
2. Take Cozmo off the charger and wait about 20 seconds. If the heartbeat was all that held him, the arms go slack and the screen comes back.
3. If he is still stiff with the companion confirmed stopped, the engine itself is hung. The backpack button does nothing in that state. Let the battery run down, then charge him. When the Wi-Fi face appears, leave the companion stopped until that face stays up on its own.
4. Start the companion only after that. Prefer **Color camera** off until you know the link stays up.

Putting him on the charger while the companion is running connects again as soon as the Wi-Fi face appears and can lock him the same way.

## The camera looks frozen

Two different things look alike.

* The picture in Home Assistant is a still. A `picture-entity` card with `camera_view: auto` refreshes about every 10 seconds. The companion also serves a live multipart stream at `http://<host>:8790/v1/camera/stream`.
* The robot has stopped sending frames. `/v1/camera.jpg` then returns no picture once the last frame is a few seconds old. Check the log for `link stale` or `camera off`.

## The picture is dark, blocky, or soft

The body sends one size: 320×240, about 15 frames per second, as a minimized JPEG around quality 50. The protocol lists larger sizes. This firmware does not stream them. A color frame is 160×240 and is scaled up to 320×240, so it is softer across the width and uses more of the link.

The phone app adjusts exposure itself. PyCozmo does not run that loop. Dim frames are brightened in the companion before they are sent, with a cap so a nearly black frame does not become static. The head-light switch adds real light at the camera when the room is dim. The blocks you see are in the robot’s JPEG. Saving the frame again at a higher quality does not put detail back.

## Power off or wake seems to do nothing

**Power off** is only available while the robot is connected. It plays the tired animation when the link is healthy, then shuts the session down so the motors release. A second press releases a session that is still open.

After a real shutdown the access point is gone. Press the backpack button so the `Cozmo_…` network exists, then press **Wake up**. **Wake up**, **Auto**, and **Auto-sleep** stay available while the robot is off, as long as the companion process is running.

## Wi-Fi associates and then drops

Cozmo’s group cipher is TKIP. Adapters that refuse TKIP see the network and do not stay connected. Details and a known-working chipset class are in [wifi.md](wifi.md).

Re-activating the NetworkManager profile while already associated makes Cozmo leave SDK mode and hide the access point. Raise and lower the lift to show the Wi-Fi face again. The companion skips that reactivation when it is already on the right SSID.

## One cube at a time

The connect command uses a single radio slot. Linking a second cube disconnects the one already linked. **Link cubes** links one cube and will not send another connect while that slot is taken.

## Speech

There is no microphone. Phrases and typed text are spoken on the companion host with espeak and played out of the robot. Animations need the PyCozmo asset download (`pycozmo_resources.py download`). Faces work without it.

## What to include in a bug report

```bash
journalctl -u ha-cozmo-companion -n 40 --no-pager
```

Note whether **Camera** and **Color camera** were on, and the `Firmware version` line if the log has one. Leave out the lift password.
