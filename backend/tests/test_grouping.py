from app.grouping.create_groups import _group_sizes


def test_group_sizes_4():
    assert _group_sizes(4) == [4]


def test_group_sizes_8():
    assert _group_sizes(8) == [4, 4]


def test_group_sizes_12():
    assert _group_sizes(12) == [4, 4, 4]


def test_group_sizes_16():
    assert _group_sizes(16) == [4, 4, 4, 4]


def test_group_sizes_20():
    assert _group_sizes(20) == [5, 5, 5, 5]


def test_group_sizes_50():
    assert _group_sizes(50) == [5, 5, 5, 5, 5, 5, 5, 5, 5, 5]