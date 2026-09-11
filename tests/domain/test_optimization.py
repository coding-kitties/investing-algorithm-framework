import json
import unittest
from dataclasses import FrozenInstanceError

from investing_algorithm_framework.domain.optimization import (
    CandidateProposal, FloatParameter, IntegerParameter,
    OptimizationConfiguration, OptimizationSearchSpace, StrategyOptimizer,
    TrialObservation,
)


class StubOptimizer(StrategyOptimizer):
    supported_search_spaces = frozenset({"finite", "parameters"})

    def initialize(self, search_space, direction):
        pass

    def ask(self, max_candidates):
        return []

    def tell(self, observations):
        pass

    def is_finished(self):
        return False

    def state_dict(self):
        return {}

    def load_state_dict(self, state):
        pass


class TestParameters(unittest.TestCase):
    def test_integer_clamps_and_snaps_without_adding_upper_endpoint(self):
        parameter = IntegerParameter("period", 3, 10, 4)
        for raw, expected in (
            (-100, 3), (3, 3), (4.9, 3), (5.1, 7), (9, 7),
            (10, 7), (100, 7),
        ):
            with self.subTest(raw=raw):
                result = parameter.resolve(raw)
                self.assertIs(type(result), int)
                self.assertEqual(result, expected)

    def test_float_clamps_and_snaps_without_adding_upper_endpoint(self):
        parameter = FloatParameter("threshold", 0.1, 0.8, 0.3)
        for raw, expected in (
            (-100, 0.1), (0.1, 0.1), (0.2, 0.1), (0.3, 0.4),
            (0.7, 0.7), (0.8, 0.7), (100, 0.7),
        ):
            with self.subTest(raw=raw):
                result = parameter.resolve(raw)
                self.assertIs(type(result), float)
                self.assertEqual(result, expected)

    def test_float_grid_includes_decimal_upper_when_on_grid(self):
        parameter = FloatParameter("value", 0, 0.3, 0.1)
        self.assertEqual(parameter.resolve(0.3), 0.3)
        self.assertEqual(parameter.resolve(100), 0.3)

    def test_continuous_float_and_degenerate_ranges(self):
        parameter = FloatParameter("value", -1, 2)
        self.assertEqual(parameter.resolve(-100), -1.0)
        self.assertEqual(parameter.resolve(0.12345), 0.12345)
        self.assertEqual(parameter.resolve(100), 2.0)
        for parameter in (
            IntegerParameter("x", 2, 2),
            IntegerParameter("x", 2, 3, 10),
            FloatParameter("x", 2, 2, 0.1),
            FloatParameter("x", 2, 3, 10),
        ):
            self.assertEqual(parameter.resolve(100), 2)

    def test_grid_handles_negative_bounds_and_even_ties(self):
        integer = IntegerParameter("x", -5, 6, 2)
        self.assertEqual(integer.resolve(-4), -5)
        self.assertEqual(integer.resolve(-2), -1)
        self.assertEqual(integer.resolve(6), 5)
        floating = FloatParameter("x", -0.3, 0.3, 0.1)
        self.assertEqual(floating.resolve(0), 0)
        self.assertEqual(floating.resolve(0.3), 0.3)

    def test_grid_handles_extreme_finite_bounds_and_small_steps(self):
        parameter = FloatParameter("x", -1e308, 1e308, 1e307)
        self.assertEqual(parameter.resolve(1e308), 1e308)
        tiny = FloatParameter("x", 0, 1e-320, 5e-324)
        self.assertLessEqual(tiny.resolve(1e-320), tiny.upper)
        self.assertEqual(IntegerParameter("x", 0, 10**400).resolve(3), 3)

    def test_resolution_rejects_nonfinite_and_nonnumeric_values(self):
        for parameter in (
            IntegerParameter("x", 0, 10),
            FloatParameter("x", 0, 10),
            FloatParameter("x", 0, 10, 0.5),
        ):
            for raw in (float("nan"), float("inf"), -float("inf"),
                        True, None, "2", complex(1, 0), [2]):
                with self.subTest(parameter=parameter, raw=raw):
                    with self.assertRaises(ValueError):
                        parameter.resolve(raw)

    def test_integer_definitions_are_strict(self):
        for values in (
            {"name": ""}, {"name": " "}, {"name": None},
            {"lower": 1.0}, {"upper": 2.0}, {"step": 1.0},
            {"lower": True}, {"upper": False}, {"step": True},
            {"lower": float("nan")}, {"upper": float("inf")},
            {"step": 0}, {"step": -1}, {"lower": 3, "upper": 2},
        ):
            with self.subTest(values=values):
                with self.assertRaises(ValueError):
                    IntegerParameter(**dict(
                        {"name": "x", "lower": 0, "upper": 10}, **values,
                    ))

    def test_float_definitions_validate_all_bounds_and_step(self):
        for name in ("lower", "upper", "step"):
            for value in (float("nan"), float("inf"), -float("inf"),
                          True, None, "2", 10**400):
                with self.subTest(name=name, value=value):
                    with self.assertRaises(ValueError):
                        FloatParameter(**dict(
                            {"name": "x", "lower": 0, "upper": 10},
                            **{name: value},
                        ))
        for values in (
            {"name": ""}, {"name": " "}, {"name": 2},
            {"step": -1}, {"lower": 3, "upper": 2},
        ):
            with self.subTest(values=values):
                with self.assertRaises(ValueError):
                    FloatParameter(**dict(
                        {"name": "x", "lower": 0, "upper": 10}, **values,
                    ))

    def test_parameter_serialization_is_json_and_instances_are_frozen(self):
        for parameter, kind in (
            (IntegerParameter("x", 0, 10), "integer"),
            (FloatParameter("x", 0, 10), "float"),
        ):
            payload = parameter.to_dict()
            self.assertEqual(payload["type"], kind)
            self.assertEqual(payload["name"], "x")
            self.assertEqual(payload["lower"], parameter.lower)
            self.assertEqual(payload["upper"], parameter.upper)
            self.assertEqual(payload["step"], parameter.step)
            self.assertEqual(
                json.loads(json.dumps(payload, allow_nan=False)), payload,
            )
            with self.assertRaises(FrozenInstanceError):
                parameter.lower = 1


class TestProposalsAndObservations(unittest.TestCase):
    def test_proposal_accepts_exactly_one_mode(self):
        self.assertEqual(CandidateProposal("p", algorithm_id="a").algorithm_id,
                         "a")
        values = {"x": 2.5}
        proposal = CandidateProposal("p", parameters=values)
        values["x"] = 7
        self.assertEqual(proposal.parameters, {"x": 2.5})
        with self.assertRaises(FrozenInstanceError):
            proposal.proposal_id = "other"
        for values in (
            {}, {"algorithm_id": "a", "parameters": {"x": 1}},
            {"algorithm_id": ""}, {"algorithm_id": 2},
            {"parameters": [1, 2]}, {"parameters": {1: 2}},
            {"parameters": {"": 2}}, {"parameters": {"x": True}},
            {"parameters": {"x": "2"}},
        ):
            with self.subTest(values=values):
                with self.assertRaises(ValueError):
                    CandidateProposal("p", **values)
        for proposal_id in ("", " ", 1, None):
            with self.assertRaises(ValueError):
                CandidateProposal(proposal_id, algorithm_id="a")

    def test_nonfinite_proposals_are_rejected_during_resolution(self):
        parameter = FloatParameter("x", 0, 10)
        for value in (float("nan"), float("inf"), -float("inf")):
            proposal = CandidateProposal("p", {"x": value})
            with self.assertRaises(ValueError):
                parameter.resolve(proposal.parameters["x"])

    def test_observation_json_round_trip_for_all_statuses(self):
        for status in ("complete", "invalid", "failed", "pruned"):
            observation = TrialObservation(
                "p", "a" if status == "complete" else None, status,
                score=-0.5 if status == "complete" else None,
                parameters={"x": 2, "y": 0.3},
                error=None if status == "complete" else "not completed",
            )
            payload = json.loads(json.dumps(
                observation.to_dict(), allow_nan=False,
            ))
            self.assertEqual(TrialObservation.from_dict(payload), observation)
            self.assertIs(type(payload["parameters"]["x"]), int)
            with self.assertRaises(FrozenInstanceError):
                observation.status = "invalid"

    def test_observation_requires_finite_complete_score(self):
        for score in (None, True, "1", float("nan"), float("inf"),
                      -float("inf"), 10**400):
            with self.subTest(score=score):
                with self.assertRaises(ValueError):
                    TrialObservation("p", "a", "complete", score=score)
        for status in ("invalid", "failed", "pruned"):
            for score in (0, 1, float("nan")):
                with self.assertRaises(ValueError):
                    TrialObservation("p", None, status, score=score)
        self.assertEqual(
            TrialObservation("p", "a", "complete", score=0).score, 0.0,
        )

    def test_observation_rejects_invalid_fields(self):
        for values in (
            {"proposal_id": ""}, {"algorithm_id": ""},
            {"status": "pending"}, {"status": None}, {"error": 5},
            {"parameters": [2]}, {"parameters": {"x": float("nan")}},
            {"parameters": {"x": True}}, {"parameters": {"": 2}},
        ):
            with self.subTest(values=values):
                with self.assertRaises(ValueError):
                    TrialObservation(**dict(
                        {"proposal_id": "p", "algorithm_id": None,
                         "status": "invalid"}, **values,
                    ))

    def test_observation_copies_mapping_and_serialization_revalidates(self):
        values = {"x": 2}
        observation = TrialObservation(
            "p", None, "invalid", parameters=values,
        )
        values["x"] = 3
        payload = observation.to_dict()
        payload["parameters"]["x"] = 4
        self.assertEqual(observation.parameters, {"x": 2})
        payload["score"] = 1
        with self.assertRaises(ValueError):
            TrialObservation.from_dict(payload)
        self.assertIsNone(TrialObservation("p", None, "failed").parameters)


class TestSearchSpace(unittest.TestCase):
    def test_search_space_modes_and_sequence_snapshot(self):
        parameters = [IntegerParameter("x", 0, 10)]
        ids = ["a", "b"]
        generated = OptimizationSearchSpace(parameters=parameters)
        finite = OptimizationSearchSpace(algorithm_ids=ids)
        parameters.clear()
        ids.clear()
        self.assertEqual(generated.mode, "parameters")
        self.assertEqual(len(generated.parameters), 1)
        self.assertEqual(finite.mode, "finite")
        self.assertEqual(finite.algorithm_ids, ("a", "b"))
        with self.assertRaises(FrozenInstanceError):
            finite.algorithm_ids = ("c",)

    def test_search_space_validates_exactly_one_unique_source(self):
        parameter = IntegerParameter("x", 0, 10)
        for values in (
            {},
            {"parameters": [parameter], "algorithm_ids": ["a"]},
            {"parameters": [parameter, FloatParameter("x", 0, 1)]},
            {"parameters": [object()]}, {"parameters": "x"},
            {"parameters": None}, {"algorithm_ids": "a"},
            {"algorithm_ids": None}, {"algorithm_ids": ["a", "a"]},
            {"algorithm_ids": [""]}, {"algorithm_ids": [1]},
        ):
            with self.subTest(values=values):
                with self.assertRaises(ValueError):
                    OptimizationSearchSpace(**values)


class TestOptimizationConfiguration(unittest.TestCase):
    def make_configuration(self, **overrides):
        values = {
            "search_id": "search-001",
            "optimizer": StubOptimizer(),
            "objective": lambda index: 1.0,
        }
        values.update(overrides)
        return OptimizationConfiguration(**values)

    def test_defaults_and_frozen_configuration(self):
        configuration = self.make_configuration()
        self.assertEqual(configuration.direction, "maximize")
        self.assertEqual(configuration.max_evaluations, 100)
        self.assertEqual(configuration.max_proposals, 1000)
        self.assertEqual(configuration.proposal_batch_size, 16)
        self.assertEqual(configuration.parameters, ())
        self.assertEqual(configuration.constraints, ())
        self.assertIsNone(configuration.strategy_factory)
        with self.assertRaises(FrozenInstanceError):
            configuration.search_id = "another"

    def test_generated_configuration_snapshots_sequences(self):
        parameters = [IntegerParameter("x", 0, 10)]
        constraints = [lambda values: values["x"] > 0]
        configuration = self.make_configuration(
            strategy_factory=lambda values, identifier: None,
            parameters=parameters, constraints=constraints,
            direction="minimize",
        )
        parameters.clear()
        constraints.clear()
        self.assertEqual(len(configuration.parameters), 1)
        self.assertEqual(len(configuration.constraints), 1)
        self.assertEqual(configuration.direction, "minimize")

    def test_search_id_must_be_safe(self):
        for search_id in (
            "", " ", ".", "..", "../search", "search/child", "search\\child",
            "/absolute", "C:drive", "with space", "trailing.", None, 1,
            "null\x00byte", "name\n",
        ):
            with self.subTest(search_id=search_id):
                with self.assertRaises(ValueError):
                    self.make_configuration(search_id=search_id)
        self.assertEqual(
            self.make_configuration(search_id="Search_2.0-a").search_id,
            "Search_2.0-a",
        )

    def test_budget_values_are_positive_integers_excluding_bool(self):
        for name in (
            "max_evaluations", "max_proposals", "proposal_batch_size",
        ):
            for value in (0, -1, True, False, 1.0, "2", None):
                with self.subTest(name=name, value=value):
                    with self.assertRaises(ValueError):
                        self.make_configuration(**{name: value})
            self.assertEqual(
                getattr(self.make_configuration(**{name: 1}), name), 1,
            )

    def test_generated_mode_requires_factory_parameters_and_constraints(self):
        parameter = IntegerParameter("x", 0, 10)
        for values in (
            {"parameters": [parameter]},
            {"strategy_factory": lambda values, identifier: None},
            {"strategy_factory": 2, "parameters": [parameter]},
            {"parameters": [object()]},
            {"parameters": [parameter, parameter]},
            {"constraints": [lambda values: True]},
            {"constraints": [None]},
            {"constraints": None},
            {"constraints": "not a sequence of callables"},
        ):
            with self.subTest(values=values):
                with self.assertRaises(ValueError):
                    self.make_configuration(**values)

    def test_objective_optimizer_direction_and_modes_are_validated(self):
        for values in (
            {"objective": None}, {"objective": 1}, {"optimizer": object()},
            {"direction": "ascending"}, {"direction": None},
        ):
            with self.subTest(values=values):
                with self.assertRaises(ValueError):
                    self.make_configuration(**values)
        for modes in (frozenset(), {"unknown"}, None, "finite"):
            optimizer = StubOptimizer()
            optimizer.supported_search_spaces = modes
            with self.subTest(modes=modes):
                with self.assertRaises(ValueError):
                    self.make_configuration(optimizer=optimizer)

    def test_supported_actual_mode_is_left_for_coordinator(self):
        optimizer = StubOptimizer()
        optimizer.supported_search_spaces = frozenset({"parameters"})
        self.assertIs(self.make_configuration(optimizer=optimizer).optimizer,
                      optimizer)

    def test_optimizer_contract_requires_all_lifecycle_methods(self):
        self.assertEqual(
            StrategyOptimizer.supported_search_spaces, frozenset(),
        )
        self.assertEqual(
            StrategyOptimizer.__abstractmethods__,
            {"initialize", "ask", "tell", "is_finished", "state_dict",
             "load_state_dict"},
        )
        with self.assertRaises(TypeError):
            StrategyOptimizer()
