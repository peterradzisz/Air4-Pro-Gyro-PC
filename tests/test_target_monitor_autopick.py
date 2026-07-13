"""
Test target_monitor auto-pick logic (rightmost display).

Run with: python tests/test_target_monitor_autopick.py
Or:       python -m pytest tests/test_target_monitor_autopick.py -v
"""


def _autopick(displays):
    """Mirror of main.py auto-pick logic."""
    return max(displays, key=lambda d: (d['x'], d['y'], d['index']))


def test_single_display():
    displays = [{'index': 0, 'x': 0, 'y': 0, 'name': 'Only', 'w': 1920, 'h': 1080, 'is_primary': True}]
    picked = _autopick(displays)
    assert picked['index'] == 0


def test_two_displays_glasses_right():
    displays = [
        {'index': 0, 'x': 0, 'y': 0, 'name': 'Primary', 'w': 2560, 'h': 1440, 'is_primary': True},
        {'index': 1, 'x': 2560, 'y': 0, 'name': 'Glasses', 'w': 1920, 'h': 1080, 'is_primary': False},
    ]
    picked = _autopick(displays)
    assert picked['index'] == 1


def test_three_displays_glasses_furthest_right():
    displays = [
        {'index': 0, 'x': 0, 'y': 0, 'name': 'Primary', 'w': 2560, 'h': 1440, 'is_primary': True},
        {'index': 1, 'x': 2560, 'y': 0, 'name': 'Second', 'w': 1920, 'h': 1080, 'is_primary': False},
        {'index': 2, 'x': 4480, 'y': 0, 'name': 'Glasses', 'w': 1920, 'h': 1080, 'is_primary': False},
    ]
    picked = _autopick(displays)
    assert picked['index'] == 2


def test_tiebreak_same_x():
    """Vertically stacked displays (same X) — higher Y wins."""
    displays = [
        {'index': 0, 'x': 0, 'y': -1080, 'name': 'Top', 'w': 1920, 'h': 1080, 'is_primary': False},
        {'index': 1, 'x': 0, 'y': 0, 'name': 'Bottom', 'w': 1920, 'h': 1080, 'is_primary': True},
    ]
    picked = _autopick(displays)
    assert picked['index'] == 1


def test_glasses_left_of_primary():
    """Edge case: user has glasses on the LEFT side.
    
    Auto-pick will select Primary (X=0 > X=-1920), which is 'wrong' for this user.
    User must manually override via Ctrl+Alt+S. Documented in README.
    """
    displays = [
        {'index': 0, 'x': -1920, 'y': 0, 'name': 'Glasses', 'w': 1920, 'h': 1080, 'is_primary': False},
        {'index': 1, 'x': 0, 'y': 0, 'name': 'Primary', 'w': 2560, 'h': 1440, 'is_primary': True},
    ]
    picked = _autopick(displays)
    assert picked['index'] == 1  # Documents known limitation


if __name__ == '__main__':
    tests = [
        test_single_display,
        test_two_displays_glasses_right,
        test_three_displays_glasses_furthest_right,
        test_tiebreak_same_x,
        test_glasses_left_of_primary,
    ]
    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            print(f"  PASS: {test.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL: {test.__name__}: {e}")
            failed += 1
    print(f"\n{passed}/{passed + failed} tests passed")
    if failed > 0:
        exit(1)
