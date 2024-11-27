#!/usr/bin/env python3

import ops
import logging

'''
Log messages can be retrieved using juju debug-log
info: https://discourse.charmhub.io/t/how-to-manage-agent-logs/9151
'''
logger = logging.getLogger(__name__)

class FastAPIDemoCharm(ops.CharmBase):
    """
    Generally speaking: A charm class is a collection of event handling methods. When you want to install, remove, 
    upgrade, configure, etc., an application, Juju sends information to your charm. Ops translates this information 
    into events and your job is to write event handlers
    """

    def __init__(self, framework: ops.Framework) -> None:
        super().__init__(framework)
        framework.observe(self.on.demo_server_pebble_ready, self._on_demo_server_pebble_ready)
        self.pebble_service_name = "fastapi-service"

    def _on_demo_server_pebble_ready(self, event: ops.PebbleReadyEvent)  -> None:
        """
        Define and start a workload using the Pebble API.

        Resources for understanding the system:

        Interaction with Pebble: https://juju.is/docs/sdk/pebble
        Status, SDK docs: https://juju.is/docs/sdk/status
        """
        container = event.workload
        container.add_layer("fastapi_demo", self._pebble_layer, combine=True)
        container.replan()
        self.unit.status = ops.ActiveStatus()
    
    @property
    def _pebble_layer(self) -> ops.pebble.Layer:
        """
        A Pebble layer for the FastAPI demo services.
        Pebble layers: https://canonical-pebble.readthedocs-hosted.com/en/latest/reference/layers
        Configure Pebble leyers: https://juju.is/docs/sdk/interact-with-pebble#heading--configure-a-pebble-layer
        """
        command = ' '.join(
            [
                'uvicorn',
                'api_demo_server.app:app',
                '--host=0.0.0.0',
                '--port=8000',
            ]
        )
        pebble_layer: ops.pebble.LayerDict = {
            'summary': 'FastAPI demo service',
            'description': 'pebble config layer for FastAPI demo server',
            'services': {
                self.pebble_service_name: {
                    'override': 'replace',
                    'summary': 'fastapi demo',
                    'command': command,
                    'startup': 'enabled',
                }
            },
        }
        return ops.pebble.Layer(pebble_layer)

if __name__ == "__main__":  # pragma: nocover
    ops.main(FastAPIDemoCharm)