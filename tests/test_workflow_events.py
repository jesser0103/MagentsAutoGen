import unittest

from src.workflow.models import (
    WORKFLOW_EVENT_SCHEMA_VERSION,
    WorkflowEventType,
    WorkflowRun,
)


class WorkflowEventTests(unittest.TestCase):
    def test_named_event_round_trips_with_schema_version(self) -> None:
        run = WorkflowRun(user_request="Create a private resource.")
        run.add_event(WorkflowEventType.INPUT_SCREENED, "input_guard", "Request passed.")

        restored_run = WorkflowRun.from_dict(run.to_dict())

        self.assertEqual(restored_run.event_schema_version, WORKFLOW_EVENT_SCHEMA_VERSION)
        self.assertEqual(restored_run.events[0].event_type, "input_screened")
