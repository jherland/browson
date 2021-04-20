import textwrap

from browson.node import Node


class TestNode_build:
    def verify_scalar(self, n, expect_kind, expect_value, expect_name=""):
        assert n.name == expect_name
        assert n.kind is expect_kind
        assert n.value == expect_value
        assert n.is_leaf

    def verify_collection(self, n, expect_kind, expect_value, expect_name=""):
        assert n.name == expect_name
        assert n.kind is expect_kind
        assert n.value == expect_value
        assert n.kind in {list, tuple, set, dict}
        assert not n.is_leaf
        assert len(n.children) == len(expect_value)
        if n.kind is dict:
            expect_children = [
                Node(f"{expect_name}.{k}", type(v), v, parent=n, key=k)
                for k, v in expect_value.items()
            ]
        else:
            expect_children = [
                Node(f"{expect_name}[{i}]", type(c), c, parent=n)
                for i, c in enumerate(expect_value)
            ]
        assert n.children == expect_children

    # singletons
    def test_None(self):
        n = Node.build(None)
        self.verify_scalar(n, type(None), None)

    def test_True(self):
        n = Node.build(True)
        self.verify_scalar(n, bool, True)

    def test_False(self):
        n = Node.build(False)
        self.verify_scalar(n, bool, False)

    # numbers
    def test_zero(self):
        n = Node.build(0)
        self.verify_scalar(n, int, 0)

    def test_positive_int(self):
        n = Node.build(1234)
        self.verify_scalar(n, int, 1234)

    def test_negative_int(self):
        n = Node.build(-5678)
        self.verify_scalar(n, int, -5678)

    def test_float_zero(self):
        n = Node.build(0.0)
        self.verify_scalar(n, float, 0.0)

    def test_float_nonzero(self):
        n = Node.build(1.234)
        self.verify_scalar(n, float, 1.234)

    def test_float_negative_inf(self):
        n = Node.build(float("-inf"))
        self.verify_scalar(n, float, float("-inf"))

    def test_float_nan(self):
        n = Node.build(float("nan"))
        # NaN cannot be compared to itself
        assert n.name == ""
        assert n.kind is float
        assert str(n.value) == "nan"
        assert n.is_leaf

    # strings
    def test_empty_string(self):
        n = Node.build("")
        self.verify_scalar(n, str, "")

    def test_short_string(self):
        n = Node.build("foo")
        self.verify_scalar(n, str, "foo")

    # lists
    def test_list_empty(self):
        n = Node.build([])
        self.verify_collection(n, list, [])

    def test_list_single_item(self):
        n = Node.build([123])
        self.verify_collection(n, list, [123])

    def test_list_of_singletons(self):
        n = Node.build([None, True, False])
        self.verify_collection(n, list, [None, True, False])

    def test_list_of_ints(self):
        n = Node.build([123, -456, 789])
        self.verify_collection(n, list, [123, -456, 789])

    # nested lists
    def test_list_of_empty_list(self):
        n = Node.build([[]])
        assert n.name == ""
        assert n.kind is list
        assert n.value == [[]]
        assert not n.is_leaf
        assert len(n.children) == 1

        n2 = n.children[0]
        assert n2.name == "[0]"
        assert n2.kind is list
        assert n2.value == []
        assert not n2.is_leaf
        assert len(n2.children) == 0
        self.verify_collection(n2, list, [], "[0]")

    def test_list_of_list_of_list_of_one_string(self):
        n = Node.build([[["foo"]]])
        assert n.name == ""
        assert n.kind is list
        assert n.value == [[["foo"]]]
        assert not n.is_leaf
        assert len(n.children) == 1

        n2 = n.children[0]
        assert n2.name == "[0]"
        assert n2.kind is list
        assert n2.value == [["foo"]]
        assert not n2.is_leaf
        assert len(n2.children) == 1

        n3 = n2.children[0]
        self.verify_collection(n3, list, ["foo"], "[0][0]")

    # tuples
    def test_tuple_empty(self):
        n = Node.build(())
        self.verify_collection(n, tuple, ())

    def test_tuple_single_item(self):
        n = Node.build(("foo",))
        self.verify_collection(n, tuple, ("foo",))

    def test_tuple_heterogeneous(self):
        n = Node.build((None, "foo", -321))
        self.verify_collection(n, tuple, (None, "foo", -321))

    # sets
    def test_set_empty(self):
        n = Node.build(set())
        self.verify_collection(n, set, set())

    def test_set_single_item(self):
        n = Node.build({"foo"})
        self.verify_collection(n, set, {"foo"})

    def test_set_multiple(self):
        n = Node.build({"foo", 456, "bar", 123})
        self.verify_collection(n, set, {"foo", 456, "bar", 123})

    # dicts
    def test_dict_empty(self):
        n = Node.build({})
        self.verify_collection(n, dict, {})

    def test_dict_single_item(self):
        n = Node.build({"foo": 123})
        self.verify_collection(n, dict, {"foo": 123})

    def test_dict_multiple_items(self):
        n = Node.build({"foo": 123, "bar": 456, "baz": 789})
        self.verify_collection(n, dict, {"foo": 123, "bar": 456, "baz": 789})


class TestNode_dfwalk:
    def test_leaf_node(self):
        n = Node.build("foo")
        assert list(n.dfwalk()) == [Node("", str, "foo")]

    def test_simple_list(self):
        n = Node.build(["foo", 123, True])
        assert list(n.dfwalk()) == [
            n,
            Node("[0]", str, "foo", parent=n),
            Node("[1]", int, 123, parent=n),
            Node("[2]", bool, True, parent=n),
        ]

    def test_simple_dict(self):
        n = Node.build({"foo": 123, "bar": 456, "baz": 789})
        assert list(n.dfwalk()) == [
            n,
            Node(".foo", int, 123, key="foo", parent=n),
            Node(".bar", int, 456, key="bar", parent=n),
            Node(".baz", int, 789, key="baz", parent=n),
        ]

    def test_nested_dict(self):
        n = Node.build({"foo": {"a": 1, "b": 2}, "bar": [3, 4], "baz": {5, 6}})
        foo = Node(
            ".foo", dict, {"a": 1, "b": 2}, parent=n, key="foo", children=[]
        )
        foo_a = Node(".foo.a", int, 1, parent=foo, key="a")
        foo_b = Node(".foo.b", int, 2, parent=foo, key="b")
        foo.children.extend([foo_a, foo_b])
        bar = Node(".bar", list, [3, 4], parent=n, key="bar", children=[])
        bar_0 = Node(".bar[0]", int, 3, parent=bar)
        bar_1 = Node(".bar[1]", int, 4, parent=bar)
        bar.children.extend([bar_0, bar_1])
        baz = Node(".baz", set, {5, 6}, parent=n, key="baz", children=[])
        baz_0 = Node(".baz[0]", int, 5, parent=baz)
        baz_1 = Node(".baz[1]", int, 6, parent=baz)
        baz.children.extend([baz_0, baz_1])
        assert list(n.dfwalk()) == [
            n,
            foo,
            foo_a,
            foo_b,
            bar,
            bar_0,
            bar_1,
            baz,
            baz_0,
            baz_1,
        ]

    def test_str_visit_heterogeneous_structure(self):
        n = Node.build(
            {
                "dict": {"key": 321, "other_key": None, "last_key": False},
                "list": [1, 2, 3],
                "tuple": (4, 5, 6),
                "set": {7, 8, 9},
                "nested": ([{"key": {"value"}}],),
            }
        )

        def yield_str(node):
            yield str(node)

        assert "\n".join(n.dfwalk(yield_str)) == textwrap.dedent(
            """\
            /dict/5
            .dict/dict/3
            .dict.key/int/*
            .dict.other_key/NoneType/*
            .dict.last_key/bool/*
            .list/list/3
            .list[0]/int/*
            .list[1]/int/*
            .list[2]/int/*
            .tuple/tuple/3
            .tuple[0]/int/*
            .tuple[1]/int/*
            .tuple[2]/int/*
            .set/set/3
            .set[0]/int/*
            .set[1]/int/*
            .set[2]/int/*
            .nested/tuple/1
            .nested[0]/list/1
            .nested[0][0]/dict/1
            .nested[0][0].key/set/1
            .nested[0][0].key[0]/str/*"""
        )


def test_node_ancestors():
    n = Node.build({"foo": {"bar": {"baz": "xyzzy"}}})
    assert list(n.ancestors()) == []
    foo = n.children[0]
    assert list(foo.ancestors()) == [n]
    bar = foo.children[0]
    assert list(bar.ancestors()) == [foo, n]
    baz = bar.children[0]
    assert list(baz.ancestors()) == [bar, foo, n]
