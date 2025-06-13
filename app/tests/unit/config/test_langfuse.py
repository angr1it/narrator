"""Smoke tests for Langfuse tracing helpers.

The file defines dummy client classes. Actual tests were removed but the module
is kept to illustrate how to mock Langfuse interactions.
"""


class DummySpan:
    def __init__(self, events):
        self.events = events

    def end(self):
        self.events.append("end")


class DummyClient:
    def __init__(self, events):
        self.events = events

    def span(self, name: str):
        self.events.append(name)
        return DummySpan(self.events)
