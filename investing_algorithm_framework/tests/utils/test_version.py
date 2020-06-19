from investing_algorithm_framework.utils.version import get_version, get_complete_version, get_main_version


def test():
    assert get_version() is not None
    assert type(get_version()) == str

    version = (1, 0, 0, 'alpha', 0)
    assert get_version(version) == '1.0'
    assert get_main_version(version) == '1.0'
    assert get_complete_version(version) == version


