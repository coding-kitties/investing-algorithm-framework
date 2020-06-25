def get_version(version=None):
    version = get_complete_version(version)
    main = get_main_version(version)
    return main


def get_main_version(version=None):
    """Return main version (X.Y[.Z]) from VERSION."""
    version = get_complete_version(version)
    parts = 2 if version[2] == 0 else 3
    return '.'.join(str(x) for x in version[:parts])


def get_complete_version(version=None):
    """
    Return a tuple of the investing algorithm framework  version. If version
    argument is non-empty,
    check for correctness of the tuple provided.
    """
    if version is None:
        from investing_algorithm_framework import VERSION as version
    else:
        assert len(version) == 5
        assert version[3] in ('alpha', 'beta', 'rc', 'final')

    return version
