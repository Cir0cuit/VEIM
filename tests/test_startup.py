from main import XCB_LIBRARIES, missing_xcb_libraries


def _load_without(absent):
    def load(soname):
        if soname in absent:
            raise OSError(soname)
    return load


def test_names_the_package_for_a_missing_xcb_library():
    missing = missing_xcb_libraries(
        env={"XDG_SESSION_TYPE": "x11"}, platform="linux",
        load=_load_without({"libxcb-cursor.so.0"}))
    assert missing == [XCB_LIBRARIES["libxcb-cursor.so.0"]]


def test_checks_only_when_qt_would_use_xcb():
    load = _load_without(set(XCB_LIBRARIES))
    assert missing_xcb_libraries({}, "win32", load) == []
    assert missing_xcb_libraries({"XDG_SESSION_TYPE": "wayland"}, "linux", load) == []
    assert missing_xcb_libraries({"QT_QPA_PLATFORM": "offscreen"}, "linux", load) == []
    assert missing_xcb_libraries({"QT_QPA_PLATFORM": "xcb"}, "linux", load)
    assert missing_xcb_libraries({}, "linux", load)


def test_nothing_missing_when_everything_loads():
    assert missing_xcb_libraries({}, "linux", _load_without(set())) == []
