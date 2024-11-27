# Introduction to Charms
Kubernetes charms are a powerful feature of the Juju framework, designed to facilitate the deployment and management of applications within Kubernetes environments. A charm encapsulates all the operational logic required to deploy and manage an application or service, making it easier to operate across various Kubernetes clusters, whether on public or private clouds.

The application that the charm will be written for is the FastAPI app with a connection to PostgreSQL and uses starlette-exporter to generate real-time application metrics and to expose them via a /metrics endpoint that is designed to be scraped by Prometheus.Finally, every time a user interacts with the database, the app writes logging information to the log file and also streams it to the stdout.

The app source code is hosted at https://github.com/canonical/api_demo_server
