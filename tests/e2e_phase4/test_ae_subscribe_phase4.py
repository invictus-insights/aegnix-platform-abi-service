# tests_ae_sdk_v2/e2e_phase4/test_ae_subscribe_phase4.py

import time
import base64
import threading

from aegnix_ae.client_v2 import AEClient

ABI_URL = "http://127.0.0.1:8080"

# ------------------------------
# REAL KEYS FROM enroll_ae.py
# ------------------------------
#
PHASE4_PUB_PRIV_B64 = "SDzitZgz6q6+SPOo1GgY+kH/zNOXT7KfE02z5RjoT+Y="
PHASE4_PUB_PUB_B64  = "3d8fET5MrTsf91SIGKx+DvvlcqdL6dTqaC6+7wviMcE="

PHASE4_SUB_PRIV_B64 = "TP2NUtVxbTOfwRA+lom8eNvgP0WIlZ8tNojW+hMhOnU="
PHASE4_SUB_PUB_B64 = "UH4bURrWmCOqCveUCFuisf5N1NDwnLwsdZ1EpVmqaTw="


def b64d(x):
    return base64.b64decode(x)


# --------------------------------------------------------------------
# E2E: Subscriber receives a published message
# --------------------------------------------------------------------


def test_ae_subscribe_receive_message():
    received = {"msg": None}

    # Subscriber AE
    sub = AEClient(
        name="phase4_sub",
        abi_url=ABI_URL,
        keypair={
            "priv": b64d(PHASE4_SUB_PRIV_B64),

        },
        publishes=[],
        subscribes=["fusion.topic"],
        transport="http",
    )

    sub.register_with_abi()

    # Register handler
    @sub.on("fusion.topic")
    def handle(msg):
        received["msg"] = msg

    # Start listening in background
    t = threading.Thread(target=sub.listen, daemon=True)
    t.start()

    time.sleep(0.5)

    # Publisher AE
    pub = AEClient(
        name="phase4_pub",
        abi_url=ABI_URL,
        keypair={
            "priv": b64d(PHASE4_PUB_PRIV_B64),

        },
        publishes=["fusion.topic"],
        subscribes=[],
        transport="http",
    )

    pub.register_with_abi()
    pub.emit("fusion.topic", {"hello": "world"})

    # Wait for handler to populate result
    timeout = time.time() + 5
    while received["msg"] is None and time.time() < timeout:
        time.sleep(0.1)

    assert received["msg"] is not None

