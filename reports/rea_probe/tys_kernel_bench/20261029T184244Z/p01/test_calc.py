from calc import add, subtract, total


def test_add():
    assert add(2, 3) == 5


def test_subtract():
    assert subtract(5, 3) == 2


def test_total():
    assert total([1, 2, 3]) == 6
