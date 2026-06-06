import tempfile
import unittest
from pathlib import Path

from backend.browser import BrowserActions, BrowserSession, ExternalDraftStore
from backend.config.loader import ConfigLoader
from backend.tasks import TaskHistory, TaskQueue, TaskScheduler, TaskStatus


class NoOpenSession(BrowserSession):
    def open_url(self, url: str):
        from backend.browser.session import BrowserResult
        url = self.normalize_url(url)
        result = BrowserResult(True, f"Opened URL: {url}", url=url)
        self.state.remember(result)
        return result


class TestBrowserTasksConfig(unittest.TestCase):
    def test_config_profiles(self):
        loader = ConfigLoader()
        self.assertIn("gtx1050ti", loader.available_profiles())
        self.assertEqual(loader.load("gtx1050ti").hardware.optimization_profile, "gtx1050ti")

    def test_browser_drafts(self):
        with tempfile.TemporaryDirectory() as tmp:
            actions = BrowserActions(NoOpenSession(), ExternalDraftStore(str(Path(tmp) / "drafts.json")))
            result = actions.search("jarvis ai")
            self.assertTrue(result.success)
            self.assertIn("google.com/search", result.url)
            draft = actions.draft_message("email", "test@example.com", "hello")
            self.assertEqual(draft.status, "draft")

    def test_task_queue_and_scheduler(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            history = TaskHistory(str(root / "history.jsonl"))
            queue = TaskQueue(str(root / "tasks.json"), history=history)
            task = queue.add("hello", priority="high")
            queue.complete(task.id, "done")
            self.assertEqual(queue.get(task.id).status, TaskStatus.COMPLETED)
            scheduler = TaskScheduler(str(root / "schedules.json"), queue=queue)
            scheduler.schedule_delay("delayed", 0)
            self.assertEqual(len(scheduler.enqueue_due()), 1)


if __name__ == "__main__":
    unittest.main()
