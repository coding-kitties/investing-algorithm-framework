import importlib
from io import StringIO
from unittest import TestCase
from unittest.mock import patch


progress_module = importlib.import_module(
    "investing_algorithm_framework.domain.utils.custom_tqdm"
)


class TestProgressBackend(TestCase):
    def test_text_progress_in_notebook_does_not_require_widgets(self):
        for disabled in (False, True):
            with self.subTest(disabled=disabled):
                output = StringIO()
                with patch.dict("os.environ", {"IAF_PROGRESS_BACKEND": "text"}), \
                        patch.object(progress_module, "is_jupyter_notebook", return_value=True), \
                        patch.object(progress_module, "tqdm_notebook") as widget:
                    with progress_module.tqdm(
                        total=4, desc="Event progress", file=output,
                        disable=disabled, mininterval=0,
                    ) as progress:
                        progress.update(2)
                        if not disabled:
                            self.assertIn("50%", output.getvalue())
                        progress.update(2)
                    widget.assert_not_called()
                if disabled:
                    self.assertEqual(output.getvalue(), "")
                else:
                    self.assertIn("Event progress", output.getvalue())
                    self.assertIn("100%", output.getvalue())

    def test_auto_preserves_notebook_backend(self):
        with patch.dict("os.environ", {"IAF_PROGRESS_BACKEND": "auto"}), \
                patch.object(progress_module, "is_jupyter_notebook", return_value=True), \
                patch.object(progress_module, "tqdm_notebook") as widget:
            self.assertIs(progress_module.tqdm(total=3), widget.return_value)
            widget.assert_called_once_with(total=3)

    def test_invalid_backend_is_rejected(self):
        with patch.dict("os.environ", {"IAF_PROGRESS_BACKEND": "invalid"}):
            with self.assertRaisesRegex(ValueError, "IAF_PROGRESS_BACKEND"):
                progress_module.tqdm(total=3)