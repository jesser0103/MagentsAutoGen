import unittest

from src.workflow.models import ArtifactLanguage, Plan, PlanStep, RunStatus, WorkflowRun


class WorkflowContractTests(unittest.TestCase):
    def test_plan_with_open_questions_cannot_be_approved(self) -> None:
        plan = Plan(
            summary="Create a storage account",
            steps=(PlanStep(ArtifactLanguage.TERRAFORM, "Create the storage account."),),
            open_questions=("Which Azure region should be used?",),
        )

        self.assertFalse(plan.ready_for_approval)

    def test_run_records_a_valid_approval_boundary(self) -> None:
        run = WorkflowRun(user_request="Create a private storage account")

        run.transition(RunStatus.PLANNING, "workflow", "Planning started")
        run.transition(RunStatus.AWAITING_APPROVAL, "planner", "Plan awaits approval")
        run.transition(RunStatus.CODING, "human", "Plan approved")

        self.assertEqual(run.status, RunStatus.CODING)
        self.assertEqual([event.agent for event in run.events], ["workflow", "planner", "human"])

    def test_run_rejects_invalid_transition(self) -> None:
        run = WorkflowRun(user_request="Write a Python script")

        with self.assertRaisesRegex(ValueError, "submitted to completed"):
            run.transition(RunStatus.COMPLETED, "workflow", "Invalid completion")
