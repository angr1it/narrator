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
