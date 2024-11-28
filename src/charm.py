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
        self.pebble_service_name = "fastapi-service"
        self.container = self.unit.get_container('demo-server')

        # Event handlers
        framework.observe(self.on.demo_server_pebble_ready, self._on_demo_server_pebble_ready)
        framework.observe(self.on.config_changed, self._on_config_changed)

    def _on_demo_server_pebble_ready(self, event: ops.PebbleReadyEvent)  -> None:
        """
        Define and start a workload using the Pebble API.

        Resources for understanding the system:

        Interaction with Pebble: https://juju.is/docs/sdk/pebble
        Status, SDK docs: https://juju.is/docs/sdk/status
        """
        self._update_layer_and_restart
    
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
                f"--port={self.config['server-port']}",
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
    
    def _on_config_changed(self, event: ops.ConfigChangedEvent) -> None:
        port = self.config['server-port']

        # We need to do validation of rules here because Charm does not know which config options are changed.
        if port == 22:
            self.unit.status = ops.BlockedStatus('invalid port number, 22 is reserved for SSH')
            return
        
        logger.debug("New application port is requested: %s", port)
        self._update_layer_and_restart()
    
    def _update_layer_and_restart(self) -> None:
        """
        This method will get the current Pebble layer configuration and compare the new and 
        the existing service definitions, if they differ, it will update the layer and restart the service.

        You'll need to specify the right entrypoint and environment
        configuration for your specific workload. Tip: you can see the
        standard entrypoint of an existing container using docker inspect
        """

        self.unit.status = ops.MaintenanceStatus('Assembling Pebble layers')
        try:
            # Get the current pebble layer config
            services = self.container.get_plan().to_dict().get('services', {})
            if services != self._pebble_layer.to_dict().get('services', {}):
                # Changes were made, add the new layer
                self.container.add_layer('fastapi_demo', self._pebble_layer, combine=True)
                logger.info("Added updated layer 'fastapi_demo' to Pebble plan")
        
                self.container.restart(self.pebble_service_name)
                logger.info(f"Restarted '{self.pebble_service_name}' service")
        
            self.unit.status = ops.ActiveStatus()
        except ops.pebble.APIError:
            self.unit.status = ops.MaintenanceStatus('Waiting for Pebble in workload container')

if __name__ == "__main__":  # pragma: nocover
    ops.main(FastAPIDemoCharm)
