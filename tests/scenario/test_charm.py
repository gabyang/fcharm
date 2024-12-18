from unittest.mock import Mock

import scenario
from pytest import MonkeyPatch

from charm import FastAPIDemoCharm


def test_get_db_info_action(monkeypatch: MonkeyPatch):
    monkeypatch.setattr('charm.LogProxyConsumer', Mock())
    monkeypatch.setattr('charm.MetricsEndpointProvider', Mock())
    monkeypatch.setattr('charm.GrafanaDashboardProvider', Mock())

    # Use scenario.Context to declare what charm we are testing.
    # Note that Scenario will automatically pick up the metadata from
    # your charmcraft.yaml file, so you typically could just do
    # `ctx = scenario.Context(FastAPIDemoCharm)` here, but the full
    # version is included here as an example.
    ctx = scenario.Context(
        FastAPIDemoCharm,
        meta={
            'name': 'demo-api-charm',
            'containers': {'demo-server': {}},
            'peers': {'fastapi-peer': {'interface': 'fastapi_demo_peers'}},
            'requires': {
                'database': {
                    'interface': 'postgresql_client',
                }
            },
        },
        config={
            'options': {
                'server-port': {
                    'default': 8000,
                }
            }
        },
        actions={
            'get-db-info': {'params': {'show-password': {'default': False, 'type': 'boolean'}}}
        },
    )

    # Declare the input state.
    state_in = scenario.State(
        leader=True,
        relations={
            scenario.Relation(
                endpoint='database',
                interface='postgresql_client',
                remote_app_name='postgresql-k8s',
                local_unit_data={},
                remote_app_data={
                    'endpoints': '127.0.0.1:5432',
                    'username': 'foo',
                    'password': 'bar',
                },
            ),
        },
        containers={
            scenario.Container('demo-server', can_connect=True),
        },
    )

    # Run the action with the defined state and collect the output.
    ctx.run(ctx.on.action('get-db-info', params={'show-password': True}), state_in)

    assert ctx.action_results == {
        'db-host': '127.0.0.1',
        'db-port': '5432',
        'db-username': 'foo',
        'db-password': 'bar',
    }

def test_open_port(monkeypatch: MonkeyPatch):
    monkeypatch.setattr('charm.LogProxyConsumer', Mock())
    monkeypatch.setattr('charm.MetricsEndpointProvider', Mock())
    monkeypatch.setattr('charm.GrafanaDashboardProvider', Mock())

    # Use scenario.Context to declare what charm we are testing.
    ctx = scenario.Context(
        FastAPIDemoCharm,
        meta={
            'name': 'demo-api-charm',
            'containers': {'demo-server': {}},
            'peers': {'fastapi-peer': {'interface': 'fastapi_demo_peers'}},
            'requires': {
                'database': {
                    'interface': 'postgresql_client',
                }
            },
        },
        config={
            'options': {
                'server-port': {
                    'default': 8000,
                }
            }
        },
        actions={
            'get-db-info': {'params': {'show-password': {'default': False, 'type': 'boolean'}}}
        },
    )
    state_in = scenario.State(
        leader=True,
        relations=[
            scenario.Relation(
                endpoint='database',
                interface='postgresql_client',
                remote_app_name='postgresql-k8s',
                local_unit_data={},
                remote_app_data={
                    'endpoints': '127.0.0.1:5432',
                    'username': 'foo',
                    'password': 'bar',
                },
            ),
            scenario.PeerRelation(
                endpoint='fastapi-peer',
                peers_data={'unit_stats': {'started_counter': '0'}},
            ),
        ],
        containers=[
            scenario.Container(name='demo-server', can_connect=True),
        ],
    )
    state1 = ctx.run('config_changed', state_in)
    assert len(state1.opened_ports) == 1
    assert state1.opened_ports[0].port == 8000
    assert state1.opened_ports[0].protocol == 'tcp'