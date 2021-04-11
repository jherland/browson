import textwrap

from style import DrawableNode, PythonStyle, JSONStyle


def build_node(obj):
    return DrawableNode.build(obj)


def draw_lines(node, style):
    return "\n".join(line for line, _ in node.draw(style))


class Test_render_nodes_python:
    style = PythonStyle()

    def test_leaf_node(self):
        n = build_node("foo")
        assert draw_lines(n, self.style) == repr("foo")

    def test_simple_list(self):
        n = build_node(["foo", 123, True])
        assert draw_lines(n, self.style) == textwrap.dedent(
            """\
            [
                'foo',
                123,
                True,
            ]"""
        )

    def test_simple_dict(self):
        n = build_node({"foo": 123, "bar": 456, "baz": 789})
        assert draw_lines(n, self.style) == textwrap.dedent(
            """\
            {
                'foo': 123,
                'bar': 456,
                'baz': 789,
            }"""
        )

    def test_nested_dict(self):
        n = build_node({"foo": {"a": 1, "b": 2}, "bar": {"c": 3, "d": 4}})
        assert draw_lines(n, self.style) == textwrap.dedent(
            """\
            {
                'foo': {
                    'a': 1,
                    'b': 2,
                },
                'bar': {
                    'c': 3,
                    'd': 4,
                },
            }"""
        )


class Test_render_nodes_json:
    style = JSONStyle()

    def test_leaf_node(self):
        n = build_node("foo")
        assert draw_lines(n, self.style) == '"foo"'

    def test_simple_list(self):
        n = build_node(["foo", 123, True, False, None])
        assert draw_lines(n, self.style) == textwrap.dedent(
            """\
            [
              "foo",
              123,
              true,
              false,
              null
            ]"""
        )

    def test_simple_dict(self):
        n = build_node({"foo": 123, "bar": 456, "baz": 789})
        assert draw_lines(n, self.style) == textwrap.dedent(
            """\
            {
              "foo": 123,
              "bar": 456,
              "baz": 789
            }"""
        )

    def test_nested_dict(self):
        n = build_node({"foo": {"a": 1, "b": 2}, "bar": {"c": 3, "d": 4}})
        assert draw_lines(n, self.style) == textwrap.dedent(
            """\
            {
              "foo": {
                "a": 1,
                "b": 2
              },
              "bar": {
                "c": 3,
                "d": 4
              }
            }"""
        )
