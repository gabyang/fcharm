import ops
import ops.testing
import pytest

from charm import FastAPIDemoCharm

# This is aparently a legacy unit testing mechanism, deprecated since version 2.17
@pytest.fixture
def harness():
    harness = ops.testing.Harness(FastAPIDemoCharm)
    harness.begin()
    yield harness
    harness.cleanup()


def test_pebble_layer(
    monkeypatch: pytest.MonkeyPatch, harness: ops.testing.Harness[FastAPIDemoCharm]
):
    monkeypatch.setattr(FastAPIDemoCharm, 'version', '1.0.0')
    # Expected plan after Pebble ready with default config
    expected_plan = {
        'services': {
            'fastapi-service': {
                'override': 'replace',
                'summary': 'fastapi demo',
                'command': 'uvicorn api_demo_server.app:app --host=0.0.0.0 --port=8000',
                'startup': 'enabled',
                # Since the environment is empty, Layer.to_dict() will not
                # include it.
            }
        }
    }

    # Simulate the container coming up and emission of pebble-ready event
    harness.container_pebble_ready('demo-server')
    harness.evaluate_status()

    # Get the plan now we've run PebbleReady
    updated_plan = harness.get_container_pebble_plan('demo-server').to_dict()
    service = harness.model.unit.get_container('demo-server').get_service('fastapi-service')
    # Check that we have the plan we expected:
    assert updated_plan == expected_plan
    # Check the service was started:
    assert service.is_running()
    # Ensure we set a BlockedStatus with appropriate message:
    assert isinstance(harness.model.unit.status, ops.BlockedStatus)
    assert 'Waiting for database' in harness.model.unit.status.message

# Read more here: https://ops.readthedocs.io/en/latest/harness.html#module-ops.testing
