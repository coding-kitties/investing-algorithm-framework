from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from examples.dashboard_demo import demo


class TestDashboardDemo(TestCase):
    def setUp(self):
        environment = patch.dict(demo.os.environ, {"WSL_DISTRO_NAME": ""})
        environment.start()
        self.addCleanup(environment.stop)

    def test_opens_comparison_after_generating_reports(self):
        with TemporaryDirectory(prefix="dashboard demo ") as directory:
            output = Path(directory).resolve()
            with patch("sys.argv", [
                "demo", "--reports-only", "--output", directory,
            ]), patch.object(
                demo, "build_reports", return_value=output / "comparison.html",
            ) as build, patch.object(
                demo.webbrowser, "open", return_value=True,
            ) as browser, patch.object(demo, "run_backtests") as backtest:
                demo.main()
                build.assert_called_once_with(output)
                browser.assert_called_once_with(
                    (output / "comparison.html").as_uri(), new=2,
                )
                backtest.assert_not_called()

    def test_no_browser_still_generates_reports(self):
        with patch("sys.argv", [
            "demo", "--reports-only", "--no-browser",
        ]), patch.object(demo, "build_reports") as build, patch.object(
            demo, "open_dashboard",
        ) as browser:
            demo.main()
            build.assert_called_once()
            browser.assert_not_called()

    def test_unavailable_browser_logs_manual_open_path(self):
        report_path = Path("/tmp/dashboard demo/comparison.html")
        with patch("sys.argv", [
            "demo", "--reports-only",
        ]), patch.object(
            demo, "build_reports", return_value=report_path,
        ), patch.object(
            demo.webbrowser, "open", return_value=False,
        ), self.assertLogs(demo.__name__, level="WARNING") as logs:
            demo.main()
        self.assertIn(str(report_path), logs.output[0])

    def test_wsl_uses_windows_path_and_quotes_it_for_powershell(self):
        path = Path("/tmp/demo's folder/comparison.html")
        windows_path = (
            "\\\\wsl.localhost\\Ubuntu\\tmp\\demo's folder\\comparison.html"
        )
        with patch.dict(demo.os.environ, {
            "WSL_DISTRO_NAME": "Ubuntu",
        }), patch.object(demo.subprocess, "run", side_effect=[
            demo.subprocess.CompletedProcess(
                [], 0, stdout=windows_path + "\n",
            ),
            demo.subprocess.CompletedProcess([], 0),
        ]) as run, patch.object(demo.webbrowser, "open") as browser:
            self.assertTrue(demo.open_dashboard(path))
            self.assertEqual(run.call_args_list[0].args[0], [
                "wslpath", "-w", str(path.resolve()),
            ])
            self.assertEqual(run.call_args_list[1].args[0], [
                "powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                "$ErrorActionPreference = 'Stop'; Start-Process -FilePath '"
                + windows_path.replace("'", "''") + "'",
            ])
            browser.assert_not_called()

    def test_wsl_launcher_failure_is_not_reported_as_success(self):
        error = demo.subprocess.CalledProcessError(1, ["powershell.exe"])
        with patch.dict(demo.os.environ, {
            "WSL_DISTRO_NAME": "Ubuntu",
        }), patch.object(demo.subprocess, "run", side_effect=[
            demo.subprocess.CompletedProcess([], 0, stdout="report.html"),
            error,
        ]), self.assertRaises(demo.subprocess.CalledProcessError):
            demo.open_dashboard(Path("/tmp/comparison.html"))
