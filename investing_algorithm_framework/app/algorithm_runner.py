import json
import logging
import os
import threading
from datetime import datetime, timezone
from typing import Optional

from investing_algorithm_framework.domain import OperationalException

logger = logging.getLogger("investing_algorithm_framework")

NOT_STARTED = "NOT_STARTED"
RUNNING = "RUNNING"
STOPPING = "STOPPING"
STOPPED = "STOPPED"

CONTROL_FILE_NAME = "algorithm_control.json"


class AlgorithmRunner:
    """
    Thread-safe controller that runs an ``EventLoopService`` in a
    background thread so the trading algorithm can be started and
    stopped on demand (e.g. from the web API) without killing the
    process that hosts it.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._event_loop_service = None
        self._run_kwargs = {}
        self._on_stop = None
        self._status = NOT_STARTED
        self._started_at = None
        self._stopped_at = None
        self._error = None
        self._resource_directory = None
        self._state_handler = None

    def bind_persistence(self, resource_directory, state_handler=None) -> None:
        """
        Wires where the enabled/disabled control flag is persisted.

        This is what makes ``enable()``/``disable()`` meaningful for
        *stateless* deployments (AWS Lambda, Azure Functions): the
        flag file lives inside ``resource_directory``, the same
        directory a configured ``state_handler`` already uploads/
        downloads on every run. Passing the state handler here makes a
        toggle take effect immediately (pushed on the spot) instead of
        waiting for the next natural save.
        """
        with self._lock:
            self._resource_directory = resource_directory
            self._state_handler = state_handler

    def _control_file_path(self) -> Optional[str]:
        if self._resource_directory is None:
            return None
        os.makedirs(self._resource_directory, exist_ok=True)
        return os.path.join(self._resource_directory, CONTROL_FILE_NAME)

    def get_control_state(self) -> dict:
        """Returns the persisted enabled/disabled control state."""
        default = {"enabled": True, "reason": None, "updated_at": None}
        path = self._control_file_path()

        if path is None or not os.path.exists(path):
            return default

        try:
            with open(path, "r") as f:
                return {**default, **json.load(f)}
        except (OSError, ValueError) as e:
            logger.warning(f"Could not read algorithm control file: {e}")
            return default

    def is_enabled(self) -> bool:
        """Enabled by default when no control file has been written yet."""
        return self.get_control_state().get("enabled", True)

    def _persist_enabled(
        self, enabled: bool, reason: Optional[str] = None
    ) -> None:
        path = self._control_file_path()

        if path is None:
            return

        state = {
            "enabled": enabled,
            "reason": reason,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        with open(path, "w") as f:
            json.dump(state, f)

        if self._state_handler is not None:
            try:
                self._state_handler.save(self._resource_directory)
            except Exception as e:
                logger.warning(
                    "Could not push algorithm control state via the "
                    f"configured state handler: {e}"
                )

    def enable(self, reason: Optional[str] = None) -> None:
        """Persists 'enabled', independent of any in-process thread."""
        self._persist_enabled(True, reason=reason)

    def disable(self, reason: Optional[str] = None) -> None:
        """Persists 'disabled', independent of any in-process thread."""
        self._persist_enabled(False, reason=reason)

    def configure(
        self, event_loop_service, on_stop=None, **run_kwargs
    ) -> None:
        """
        Wires the event loop service (and any kwargs for its
        ``start()`` method) that ``start``/``stop`` will control.
        Safe to call again after a ``stop()`` to reconfigure before
        the next ``start()``.

        Args:
            on_stop: Optional; a zero-argument callable invoked (on
                the loop's own background thread) each time the loop
                actually exits, whether from ``stop()`` or an error —
                used to build/persist a ``RunReport`` for the run that
                just finished. Exceptions raised by it are logged, not
                propagated.
        """
        with self._lock:
            self._event_loop_service = event_loop_service
            self._run_kwargs = run_kwargs
            self._on_stop = on_stop

    @property
    def status(self) -> str:
        with self._lock:
            return self._status

    @property
    def is_running(self) -> bool:
        return self.status == RUNNING

    def get_status_report(self) -> dict:
        with self._lock:
            return {
                "status": self._status,
                "started_at": self._started_at.isoformat()
                if self._started_at else None,
                "stopped_at": self._stopped_at.isoformat()
                if self._stopped_at else None,
                "error": self._error,
            }

    def start(self) -> bool:
        """
        Starts (or resumes) the algorithm loop in a background thread.

        Returns:
            bool: True if a new run was started, False if the
                algorithm was already running.

        Raises:
            OperationalException: If the runner has not been
                configured with an event loop service yet (i.e. the
                app has never been run).
        """
        with self._lock:
            if self._event_loop_service is None:
                raise OperationalException(
                    "The algorithm has not been initialized yet. Run "
                    "the app at least once before starting it "
                    "through the API."
                )

            if self._status == RUNNING:
                self.enable()
                return False

            self._event_loop_service.reset_stop()
            self._error = None
            self._started_at = datetime.now(timezone.utc)
            self._stopped_at = None
            self._status = RUNNING
            event_loop_service = self._event_loop_service
            run_kwargs = self._run_kwargs
            on_stop = self._on_stop

        def _run():
            try:
                event_loop_service.start(**run_kwargs)
            except Exception as e:
                logger.error(f"Algorithm loop stopped with an error: {e}")
                with self._lock:
                    self._error = str(e)
            finally:
                with self._lock:
                    self._status = STOPPED
                    self._stopped_at = datetime.now(timezone.utc)
                if on_stop is not None:
                    try:
                        on_stop()
                    except Exception as e:
                        logger.error(
                            f"Failed to build run report after the "
                            f"algorithm loop stopped: {e}"
                        )

        self._thread = threading.Thread(
            name="Algorithm Loop", target=_run, daemon=True
        )
        self._thread.start()
        self.enable()
        return True

    def invoke_now(self, strategy_ids: Optional[list] = None) -> None:
        """
        Forces the algorithm's strategies to run on the loop's very
        next tick, ignoring their configured schedule. The algorithm
        must already be running (see ``start()``) since strategies are
        only ever executed from the loop's own background thread —
        this just queues the request for it to pick up.

        Args:
            strategy_ids: Optional; specific strategy IDs to invoke.
                When None, every registered strategy is invoked.

        Raises:
            OperationalException: If the algorithm is not currently
                running.
        """
        with self._lock:
            if self._status != RUNNING:
                raise OperationalException(
                    "The algorithm is not running. Start it first "
                    "(e.g. POST /api/algorithm/start) before invoking "
                    "a run."
                )
            event_loop_service = self._event_loop_service

        event_loop_service.request_immediate_run(strategy_ids)

    def stop(
        self,
        wait: bool = False,
        timeout: float = 10,
        reason: Optional[str] = None,
        persist: bool = True,
    ) -> bool:
        """
        Signals the running algorithm loop to stop after its current
        iteration completes.

        Args:
            wait: If True, blocks until the background thread has
                actually exited (bounded by ``timeout`` seconds).
            timeout: Max seconds to wait for the thread to exit when
                ``wait`` is True.
            reason: Optional human-readable reason, persisted alongside
                the disabled state (only used when ``persist=True``).
            persist: If True (default), also persists 'disabled' to
                the control file, which a stateless/serverless
                deployment (e.g. AWS Lambda or Azure Functions) checks
                on its next scheduled invocation. Set to False for a
                process-level shutdown (e.g. Ctrl+C / KeyboardInterrupt)
                that should stop this run without disabling future
                runs.

        Returns:
            bool: True if a running in-process loop was signaled to
                stop, False if it was not running (the disabled state
                is still persisted either way, when ``persist=True``).
        """
        if persist:
            self.disable(reason=reason)

        with self._lock:
            if self._status != RUNNING:
                return False
            self._status = STOPPING
            self._event_loop_service.request_stop()
            thread = self._thread

        if wait and thread is not None:
            thread.join(timeout=timeout)

        return True
