import nox

# Run everything but 'dist' by default
nox.options.keywords = "not dist"


def _install_this_editable(session, *, extras=None):
    extras = [] if extras is None else extras
    session.install("flit")
    session.run(
        "flit", "install", "-s", "--extras", ",".join(extras), silent=True
    )


@nox.session(python=["3.6", "3.7", "3.8", "3.9"], reuse_venv=True)
def test(session):
    _install_this_editable(session, extras=["test"])
    session.run("pytest", "-x", "--log-level=debug", *session.posargs)


@nox.session(reuse_venv=True)
def format(session):
    _install_this_editable(session, extras=["dev"])
    session.run("black", ".")


@nox.session(reuse_venv=True)
def lint(session):
    _install_this_editable(session, extras=["dev"])
    session.run("flake8")


@nox.session(reuse_venv=True)
def dist(session):
    _install_this_editable(session)
    session.run("flit", "publish", *session.posargs)
    print("*** Don't forget to tag and push!")
