class MockBus:
    def __init__(self):
        self.events = []

    def publish(self, topic, payload):
        self.events.append((topic, payload))


def test_heartbeat_emits_runtime_event():
    from abi_state import ABIState

    bus = MockBus()
    state = ABIState(
        keyring=None,
        session_manager=None,
        bus=bus,
        policy=None,
    )

    state.heartbeat(
        ae_id="ae-test",
        session_id="sid-1",
        source="emit",
        intent="publish",
        subject="fusion.topic",
        quality="normal",
        meta={"x": 1},
    )

    assert len(bus.events) == 2

    topics = [evt[0] for evt in bus.events]
    assert "abi.runtime.transition" in topics
    assert "ae.runtime" in topics

    # assert len(bus.events) == 1
    #
    # topic, event = bus.events[0]
    # assert topic == "ae.runtime"
    # assert event["type"] == "heartbeat"
    # assert event["ae_id"] == "ae-test"
    # assert event["source"] == "emit"
    # assert event["intent"] == "publish"
    # assert event["subject"] == "fusion.topic"
