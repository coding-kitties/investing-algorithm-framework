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
                patch.object(progress_module.notebook_backend, "IProgress", object()), \
                patch.object(progress_module, "tqdm_notebook") as widget:
            self.assertIs(progress_module.tqdm(total=3), widget.return_value)
            widget.assert_called_once_with(total=3)

    def test_auto_without_widgets_renders_text_with_warning(self):
        output = StringIO()
        with patch.dict("os.environ", {"IAF_PROGRESS_BACKEND": "auto"}), \
                patch.object(progress_module, "is_jupyter_notebook", return_value=True), \
                patch.object(progress_module.notebook_backend, "IProgress", None), \
                patch.object(progress_module, "tqdm_notebook") as widget, \
                self.assertLogs("investing_algorithm_framework", level="WARNING") as logs:
            with progress_module.tqdm(
                total=3, file=output, mininterval=0,
            ) as progress:
                progress.update(3)
        widget.assert_not_called()
        self.assertIn("100%", output.getvalue())
        self.assertIn("3/3", output.getvalue())
        self.assertIn("using text progress", logs.output[0])

    def test_disabled_auto_without_widgets_stays_quiet(self):
        output = StringIO()
        with patch.dict("os.environ", {"IAF_PROGRESS_BACKEND": "auto"}), \
                patch.object(progress_module, "is_jupyter_notebook", return_value=True), \
                patch.object(progress_module.notebook_backend, "IProgress", None), \
                self.assertNoLogs("investing_algorithm_framework", level="WARNING"):
            with progress_module.tqdm(
                total=3, file=output, disable=True,
            ) as progress:
                progress.update(3)
        self.assertEqual(output.getvalue(), "")

    def test_explicit_notebook_without_widgets_raises_clear_error(self):
        with patch.dict("os.environ", {"IAF_PROGRESS_BACKEND": "notebook"}), \
                patch.object(progress_module.notebook_backend, "IProgress", None), \
                patch.object(progress_module, "tqdm_terminal") as terminal:
            with self.assertRaisesRegex(
                ImportError, "IAF_PROGRESS_BACKEND=text",
            ):
                progress_module.tqdm(total=3)
        terminal.assert_not_called()

    def test_invalid_backend_is_rejected(self):
        with patch.dict("os.environ", {"IAF_PROGRESS_BACKEND": "invalid"}):
            with self.assertRaisesRegex(ValueError, "IAF_PROGRESS_BACKEND"):
                progress_module.tqdm(total=3)