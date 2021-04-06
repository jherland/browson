import textwrap

from browson import render
from node import Node
from style import PythonStyle, JSONStyle


class Test_render_python:
    style = PythonStyle()

    def test_leaf_node(self):
        n = Node.build("foo")
        assert "\n".join(render(n, self.style)) == repr("foo")

    def test_simple_list(self):
        n = Node.build(["foo", 123, True])
        assert "\n".join(render(n, self.style)) == textwrap.dedent(
            """\
            [
                'foo',
                123,
                True,
            ]"""
        )

    def test_simple_dict(self):
        n = Node.build({"foo": 123, "bar": 456, "baz": 789})
        assert "\n".join(render(n, self.style)) == textwrap.dedent(
            """\
            {
                'foo': 123,
                'bar': 456,
                'baz': 789,
            }"""
        )

    def test_nested_dict(self):
        n = Node.build({"foo": {"a": 1, "b": 2}, "bar": {"c": 3, "d": 4}})
        assert "\n".join(render(n, self.style)) == textwrap.dedent(
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


class Test_render_json:
    style = JSONStyle()

    def test_leaf_node(self):
        n = Node.build("foo")
        assert "\n".join(render(n, self.style)) == '"foo"'

    def test_simple_list(self):
        n = Node.build(["foo", 123, True, False, None])
        assert "\n".join(render(n, self.style)) == textwrap.dedent(
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
        n = Node.build({"foo": 123, "bar": 456, "baz": 789})
        assert "\n".join(render(n, self.style)) == textwrap.dedent(
            """\
            {
              "foo": 123,
              "bar": 456,
              "baz": 789
            }"""
        )

    def test_nested_dict(self):
        n = Node.build({"foo": {"a": 1, "b": 2}, "bar": {"c": 3, "d": 4}})
        assert "\n".join(render(n, self.style)) == textwrap.dedent(
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
