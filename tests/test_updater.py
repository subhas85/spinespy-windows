from spinespy_win import updater


def test_is_newer_handles_numeric_ordering():
    assert updater.is_newer("1.10.0", "1.2.0") is True   # 10 > 2 numerically
    assert updater.is_newer("1.2.0", "1.10.0") is False
    assert updater.is_newer("1.2.0", "1.2.0") is False
    assert updater.is_newer("2.0.0", "1.9.9") is True


def test_is_newer_strips_v_prefix():
    assert updater.is_newer("v1.1.0", "1.0.0") is True


def test_parse_release_extracts_setup_asset():
    payload = {
        "tag_name": "v0.2.0",
        "assets": [
            {"name": "notes.txt", "browser_download_url": "http://x/notes.txt"},
            {"name": "SpineSpy-Setup.exe", "browser_download_url": "http://x/Setup.exe"},
        ],
    }
    info = updater.parse_release(payload, current="0.1.0")
    assert info is not None
    assert info.version == "0.2.0"
    assert info.installer_url == "http://x/Setup.exe"


def test_parse_release_none_when_not_newer():
    payload = {"tag_name": "v0.1.0", "assets": []}
    assert updater.parse_release(payload, current="0.1.0") is None
