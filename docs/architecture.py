"""Generates one diagram per pipeline.

Deliberately two diagrams rather than one: a combined view has to draw the two
pipelines sharing MongoDB/Secrets Manager and both feeding the same alarms, and
those cross-cutting edges are what force graphviz into long swooping curves.
Split in two, each pipeline is a straight chain, which auto-layout handles well.

Clusters are avoided for the same reason -- graphviz grows a cluster's box to
enclose any edge that arcs above its nodes, which shows up as dead space.
"""

from diagrams import Diagram, Edge
from diagrams.aws.compute import Lambda
from diagrams.aws.integration import SNS, SQS
from diagrams.aws.iot import IotCore, IotSensor
from diagrams.aws.management import Cloudwatch
from diagrams.aws.network import APIGateway
from diagrams.aws.security import SecretsManager
from diagrams.aws.storage import S3
from diagrams.onprem.client import User
from diagrams.onprem.database import MongoDB

DARK = "#1a1a1a"
GREY = "#5c5c5c"

# diagrams sizes a node as 1.9in + 0.4in per extra label line, so a one-line label
# yields a shorter node whose centre sits higher, leaving the edges into it
# visibly slanted. One pinned height for every node keeps them aligned -- it just
# has to clear the tallest case (two lines at the node font size below), or the
# text gets drawn on top of the icon.
NODE_H = "2.9"

graph_attr = {
    "fontsize": "34",
    "fontcolor": DARK,
    "splines": "spline",
    "nodesep": "1.2",
    "ranksep": "1.5",
    "pad": "0.5",
}
node_attr = {"fontsize": "21", "fontcolor": DARK}
edge_attr = {"color": DARK, "penwidth": "2.4", "fontsize": "17", "fontcolor": DARK}


def flow(**kwargs):
    """Main pipeline edge. High weight so the chain stays a straight horizontal line."""
    return Edge(color=DARK, penwidth="2.4", fontcolor=DARK, fontsize="17",
                weight="200", **kwargs)


def loose(**kwargs):
    """Edge whose target is already ranked by another edge, so it can drop out of
    ranking (constraint=false) without leaving that node floating. Zero weight too,
    so it does not tug its endpoints off their row."""
    return Edge(color=DARK, penwidth="2.4", fontcolor=DARK, fontsize="17",
                constraint="false", weight="0", **kwargs)


def branch(**kwargs):
    """Hangs a branch node (a DLQ) off the chain. Constrained, so it gets ranked,
    but low weight: at chain weight it competes with the chain for the Lambda's
    row and both the DLQ and the next chain node end up drawn on a diagonal."""
    return Edge(color=DARK, penwidth="2.4", fontcolor=DARK, fontsize="17",
                weight="1", **kwargs)


def support(**kwargs):
    """Supporting lookup (credentials), not data flow -- toned down so only the
    pipeline itself reads as the pipeline."""
    return Edge(color=GREY, penwidth="1.8", fontcolor=GREY, fontsize="17",
                style="dashed", **kwargs)


def alarm(**kwargs):
    """Cross-cutting observability edge: dotted and grey to read as a side concern."""
    return Edge(color=GREY, penwidth="2.2", fontcolor=GREY, fontsize="17",
                style="dotted", weight="200", **kwargs)


with Diagram(
        "Batch pipeline - accident reports",
        filename="architecture_batch",
        show=False,
        direction="LR",
        graph_attr=graph_attr,
        node_attr=node_attr,
        edge_attr=edge_attr,
):
    # Declared before the chain on purpose: within a rank graphviz keeps roughly
    # the declaration order, so this puts Secrets Manager ABOVE the chain and the
    # DLQ below it. With both on the same side their arrows cross, one going up
    # into the Lambda while the other comes down out of the queue.
    secrets = SecretsManager("Secrets Manager\n(Mongo + PII key)", height=NODE_H)

    client = User("Client\n(uploads Excel)", height=NODE_H)
    api_gw = APIGateway("API Gateway", height=NODE_H)
    lambda1 = Lambda("ValidateAndStore", height=NODE_H)
    s3 = S3("S3\n(raw/processed/failed)", height=NODE_H)
    lambda2 = Lambda("SplitAndEnqueue", height=NODE_H)
    queue = SQS("AccidentReports\nQueue", height=NODE_H)
    lambda3 = Lambda("ValidateAndPersist", height=NODE_H)
    mongo = MongoDB("MongoDB Atlas", height=NODE_H)

    dlq = SQS("AccidentReports\nDLQ", height=NODE_H)
    cloudwatch = Cloudwatch("CloudWatch Alarms\n(DLQ + Lambda errors)", height=NODE_H)
    sns = SNS("SNS Topic\n(email alerts)", height=NODE_H)

    client >> flow(label="POST Excel\n(base64, max 300 rows)") >> api_gw
    api_gw >> flow(label="API Key check") >> lambda1
    lambda1 >> flow(label="store raw") >> s3
    s3 >> flow(label="ObjectCreated\n(uploads/)") >> lambda2
    lambda2 >> flow(label="split rows") >> queue
    queue >> flow(label="1 row / invocation") >> lambda3
    lambda3 >> flow(label="persist\n(encrypted PII)") >> mongo

    lambda2 >> loose(label="move to\nprocessed/failed", style="dashed") >> s3
    secrets >> support(label="credentials") >> lambda3
    lambda3 >> branch(label="invalid row", style="dashed") >> dlq
    queue >> loose(xlabel="redrive (maxReceiveCount 3)", style="dashed") >> dlq

    dlq >> alarm() >> cloudwatch
    cloudwatch >> flow() >> sns


with Diagram(
        "Streaming pipeline - traffic sensor readings",
        filename="architecture_streaming",
        show=False,
        direction="LR",
        graph_attr=graph_attr,
        node_attr=node_attr,
        edge_attr=edge_attr,
):
    # Declared before the chain on purpose: within a rank graphviz keeps roughly
    # the declaration order, so this puts Secrets Manager ABOVE the chain and the
    # DLQ below it. With both on the same side their arrows cross, one going up
    # into the Lambda while the other comes down out of the queue.
    secrets = SecretsManager("Secrets Manager\n(Mongo credentials)", height=NODE_H)

    sensor = IotSensor("Traffic sensor\n(X.509 cert)", height=NODE_H)
    iot_core = IotCore("IoT Core\n(Policy + Topic Rule)", height=NODE_H)
    queue = SQS("SensorReadings\nQueue", height=NODE_H)
    lambda4 = Lambda("PersistSensor\nReading", height=NODE_H)
    mongo = MongoDB("MongoDB Atlas", height=NODE_H)

    dlq = SQS("SensorReadings\nDLQ", height=NODE_H)
    cloudwatch = Cloudwatch("CloudWatch\nAlarms", height=NODE_H)
    sns = SNS("SNS Topic\n(email alerts)", height=NODE_H)

    sensor >> flow(label="MQTT publish\n(mTLS)") >> iot_core
    iot_core >> flow(label="trusted sensor_id\nfrom topic") >> queue
    queue >> flow(label="1 reading / invocation") >> lambda4
    lambda4 >> flow(label="persist") >> mongo

    secrets >> support(label="credentials") >> lambda4
    lambda4 >> branch(label="invalid reading", style="dashed") >> dlq
    queue >> loose(xlabel="redrive (maxReceiveCount 3)", style="dashed") >> dlq

    dlq >> alarm() >> cloudwatch
    cloudwatch >> flow() >> sns
