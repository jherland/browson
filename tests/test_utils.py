import pytest

from browson.utils import clamp, LazyList


def test_clamp():
    assert clamp(-3, 0, 100) == 0
    assert clamp(1.23, 0, 100) == 1.23
    assert clamp(-1.23, 0, 100) == 0
    assert clamp(-1, -1, 1) == -1
    assert clamp(1, -1, 1) == 1
    assert clamp(0, -1, 1) == 0
    assert clamp(-2, -1, 1) == -1
    assert clamp(2, -1, 1) == 1


class Test_LazyList:
    def iterator(self, values):
        for value in values:
            yield value

    def test_empty_iterator(self):
        ll = LazyList(self.iterator([]))
        assert len(ll) == 0
        with pytest.raises(IndexError):
            ll[0]
        assert ll == []

    def test_simple_iterator_access_in_sequence(self):
        ll = LazyList(self.iterator([6, 5, 4]))
        assert len(ll) == 0
        assert ll[0] == 6
        assert len(ll) == 1
        assert ll[1] == 5
        assert len(ll) == 2
        assert ll[2] == 4
        assert len(ll) == 3
        assert ll == [6, 5, 4]
        with pytest.raises(IndexError):
            ll[3]
        assert ll == [6, 5, 4]

    def test_simple_iterator_random_access(self):
        ll = LazyList(self.iterator([6, 5, 4, 3, 2, 1]))
        assert len(ll) == 0
        assert ll[2] == 4
        assert ll == [6, 5, 4]
        assert ll[0] == 6
        assert len(ll) == 3
        assert ll[5] == 1
        assert len(ll) == 6
        assert ll == [6, 5, 4, 3, 2, 1]

    def test_can_append_after_iterator_exhausted(self):
        ll = LazyList(self.iterator([6, 5, 4]))
        assert ll[2] == 4
        ll.append(3)
        assert ll[3] == 3
        assert len(ll) == 4

    def test_can_append_before_iterator_exhausted(self):
        ll = LazyList(self.iterator([6, 5, 4]))
        assert ll[0] == 6
        ll.append(3)
        ll.append(2)
        ll.append(1)
        assert ll[3] == 1
        assert len(ll) == 4
        assert ll[4] == 5
        assert ll[5] == 4
        assert len(ll) == 6
        with pytest.raises(IndexError):
            ll[6]
        assert ll == [6, 3, 2, 1, 5, 4]

    def test_can_get_slices(self):
        ll = LazyList(self.iterator([6, 5, 4, 3, 2, 1]))
        assert ll[1:3] == [5, 4]
        assert ll[:4] == [6, 5, 4, 3]
        assert ll[4:] == [2, 1]
        ll = LazyList(self.iterator([6, 5, 4, 3, 2, 1]))
        assert ll[4:7] == [2, 1]

    def test_can_delete_slices(self):
        ll = LazyList(self.iterator([6, 5, 4, 3, 2, 1]))
        assert ll[2] == 4
        del ll[1:]
        assert ll[2] == 2
        del ll[1:2]
        assert ll[2] == 1
        assert len(ll) == 3
        assert ll == [6, 2, 1]

    def test_open_ended_set_slice_empties_iterator(self):
        ll = LazyList(self.iterator([6, 5, 4, 3, 2, 1]))
        assert ll[2] == 4
        ll[1:] = [7, 8, 9]  # wipes generator
        assert ll == [6, 7, 8, 9]
        with pytest.raises(IndexError):
            ll[4]

    def test_can_insert_slices(self):
        ll = LazyList(self.iterator([6, 5, 4, 3, 2, 1]))
        assert ll[2] == 4
        ll[1:3] = [7, 8, 9]
        assert ll == [6, 7, 8, 9]
        assert ll[4] == 3
        ll[5:6] = [10, 11, 12]  # extract int(2) and immediately replace it
        assert ll == [6, 7, 8, 9, 3, 10, 11, 12]
        with pytest.raises(IndexError):
            ll[10]  # extracts int(1) to index 8, but fails to extract any more
        assert ll == [6, 7, 8, 9, 3, 10, 11, 12, 1]
