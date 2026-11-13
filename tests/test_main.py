def test_main_preloads_speech(monkeypatch) -> None:
    import companion.__main__ as entry

    monkeypatch.setattr(entry, "load_dotenv", lambda _path: None)
    for name in ("COZMO_SSID", "COZMO_PASSWORD", "COZMO_WIFI_IFACE", "COMPANION_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("COZMO_DRY_RUN", "1")

    preloaded = []
    monkeypatch.setattr("companion.tts.preload", lambda: preloaded.append(1))

    class Robot:
        def __init__(self, settings):
            self.settings = settings
            self.calls = []

        def start(self):
            self.calls.append("start")

        def submit(self, name):
            self.calls.append(name)

        def stop(self):
            self.calls.append("stop")

    created = {}

    def robot_factory(settings):
        created["robot"] = Robot(settings)
        return created["robot"]

    class Server:
        def serve_forever(self):
            return None

        def server_close(self):
            return None

    monkeypatch.setattr(entry, "RobotSession", robot_factory)
    monkeypatch.setattr(entry, "serve", lambda *_args, **_kwargs: Server())
    monkeypatch.setattr(entry.signal, "signal", lambda *_args, **_kwargs: None)

    assert entry.main(["--listen", "127.0.0.1:9"]) == 0
    assert preloaded == [1]
    assert created["robot"].calls == ["start", "connect", "stop"]
