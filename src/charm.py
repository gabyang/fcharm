#!/usr/bin/env python3
from typing import Dict, Optional
from charms.data_platform_libs.v0.data_interfaces import DatabaseCreatedEvent
from charms.data_platform_libs.v0.data_interfaces import DatabaseRequires

import ops
import logging
import requests

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
        self.database = DatabaseRequires(self, relation_name="database", database_name="names_db")

        # Event handlers
        framework.observe(self.on.demo_server_pebble_ready, self._on_demo_server_pebble_ready)
        framework.observe(self.on.config_changed, self._on_config_changed)
        framework.observe(self.database.on.database_created, self._on_database_created)
        framework.observe(self.database.on.endpoints_changed, self._on_database_created)
        framework.observe(self.on.collect_unit_status, self._on_collect_status)

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
                    'environment': self.app_environment,
                }
            },
        }
        return ops.pebble.Layer(pebble_layer)
    
    def _on_config_changed(self, event: ops.ConfigChangedEvent) -> None:
        port = self.config['server-port']

        # We need to do validation of rules here because Charm does not know which config options are changed.
        if port == 22:
            # The collect-status handler will set the status to blocked.
            logger.debug('Invalid port number, 22 is reserved for SSH')
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
        
            self.unit.set_workload_version(self.version)
            self.unit.status = ops.ActiveStatus()
        except ops.pebble.APIError:
            self.unit.status = ops.MaintenanceStatus('Waiting for Pebble in workload container')

    def _on_collect_status(self, event: ops.CollectStatusEvent) -> None:
        port = self.config['server-port']
        
        if port == 22:
            event.add_status(ops.BlockedStatus('Invalid port number, 22 is reserved for SSH'))
        
        if not self.model.get_relation('database'):
            # We need the user to do 'juju integrate'.
            event.add_status(ops.BlockedStatus('Waiting for database relation'))
        
        elif not self.database.fetch_relation_data():
            # We need the charms to finish integrating.
            event.add_status(ops.WaitingStatus('Waiting for database relation'))
        
        try:
            status = self.container.get_service(self.pebble_service_name)
        except (ops.pebble.APIError, ops.ModelError):
            event.add_status(ops.MaintenanceStatus('Waiting for Pebble in workload container'))
        else:
            if not status.is_running():
                event.add_status(ops.MaintenanceStatus('Waiting for the service to start up'))
        
        event.add_status(ops.ActiveStatus())
        
    @property
    def version(self) -> str:
        try:
            if self.container.get_services(self.pebble_service_name):
                return self._request_version()
        except Exception as e:
            logger.warning("unable to get version from API: %s", str(e), exc_info=True)
        return ""

    def _request_version(self) -> str:
        resp = requests.get(f"http://localhost:{self.config['server-port']}/version", timeout=10)
        return resp.json()["version"]
    
    def fetch_postgres_relation_data(self) -> Dict[str, str]:
        """
        This function retrieves relation data from a postgres database using
        the `fetch_relation_data` method of the `database` object. The retrieved data is
        then logged for debugging purposes, and any non-empty data is processed to extract
        endpoint information, username, and password. This processed data is then returned as
        a dictionary. If no data is retrieved, the unit is set to waiting status and
        the program exits with a zero status code.
        """
        relations = self.database.fetch_relation_data()
        logger.debug('Got following database data: %s', relations)
        for data in relations.values():
            if not data:
                continue
            logger.info('New PSQL database endpoint is %s', data['endpoints'])
            host, port = data['endpoints'].split(':')
            db_data = {
                'db_host': host,
                'db_port': port,
                'db_username': data['username'],
                'db_password': data['password'],
            }
            return db_data
        return {}
    
    @property
    def app_environment(self) -> Dict[str, Optional[str]]:
        """
        This property method creates a dictionary containing environment variables
        for the application. It retrieves the database authentication data by calling
        the `fetch_postgres_relation_data` method and uses it to populate the dictionary.
        If any of the values are not present, it will be set to None.
        The method returns this dictionary as output.
        """
        db_data = self.fetch_postgres_relation_data()
        if not db_data:
            return {}
        env = {
            'DEMO_SERVER_DB_HOST': db_data.get('db_host', None),
            'DEMO_SERVER_DB_PORT': db_data.get('db_port', None),
            'DEMO_SERVER_DB_USER': db_data.get('db_username', None),
            'DEMO_SERVER_DB_PASSWORD': db_data.get('db_password', None),
        }
        return env
    
    def _on_database_created(self, event: DatabaseCreatedEvent) -> None:
        """Event is fired when postgres database is created."""
        self._update_layer_and_restart()


if __name__ == "__main__":  # pragma: nocover
    ops.main(FastAPIDemoCharm)
