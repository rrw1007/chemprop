from typing import List

import numpy as np
from scipy.stats import t, spearmanr
from scipy.special import erfinv

from chemprop.data import MoleculeDataset
from .uncertainty_calibrator import UncertaintyCalibrator
from chemprop.train import evaluate_predictions


class UncertaintyEvaluator:
    """
    A class for evaluating the effectiveness of uncertainty estimates with metrics.
    """

    def __init__(
        self,
        evaluation_method: str,
        calibration_method: str,
        uncertainty_method: str,
        dataset_type: str,
        loss_function: str,
        calibrator: UncertaintyCalibrator,
    ):
        self.evaluation_method = evaluation_method
        self.calibration_method = calibration_method
        self.uncertainty_method = uncertainty_method
        self.dataset_type = dataset_type
        self.loss_function = loss_function
        self.calibrator = calibrator

    def raise_argument_errors(self):
        """
        Raise errors for incompatibilities between dataset type and uncertainty method, or similar.
        """
        if self.dataset_type == "spectra":
            raise NotImplementedError(
                "No uncertainty evaluators implemented for spectra dataset type."
            )

    def evaluate(
        self,
        test_data: MoleculeDataset,
        preds: List[List[float]],
        uncertainties: List[List[float]],
    ):
        """
        Run evaluation of predicted uncertainty values
        """
        pass


class MetricEvaluator(UncertaintyEvaluator):
    """
    A class for evaluating confidence estimates of classification and multiclass datasets using builtin evaluation metrics.
    """

    def __init__(
        self,
        evaluation_method: str,
        calibration_method: str,
        uncertainty_method: str,
        dataset_type: str,
        loss_function: str,
        calibrator: UncertaintyCalibrator,
    ):
        super().__init__(
            evaluation_method=evaluation_method,
            calibration_method=calibration_method,
            uncertainty_method=uncertainty_method,
            dataset_type=dataset_type,
            loss_function=loss_function,
            calibrator=calibrator,
        )

    def raise_argument_errors(self):
        super().raise_argument_errors()

    def evaluate(
        self,
        test_data: MoleculeDataset,
        preds: List[List[float]],
        uncertainties: List[List[float]],
    ):
        return evaluate_predictions(
            preds=uncertainties,
            targets=test_data.targets(),
            num_tasks=np.array(test_data.targets()).shape[1],
            metrics=[self.evaluation_method],
            dataset_type=self.dataset_type,
            gt_targets=test_data.gt_targets,
            lt_targets=test_data.lt_targets,
        )[self.evaluation_method]


class NLLRegressionEvaluator(UncertaintyEvaluator):
    """"""

    def __init__(
        self,
        evaluation_method: str,
        calibration_method: str,
        uncertainty_method: str,
        dataset_type: str,
        loss_function: str,
        calibrator: UncertaintyCalibrator,
    ):
        super().__init__(
            evaluation_method=evaluation_method,
            calibration_method=calibration_method,
            uncertainty_method=uncertainty_method,
            dataset_type=dataset_type,
            loss_function=loss_function,
            calibrator=calibrator,
        )

    def raise_argument_errors(self):
        super().raise_argument_errors()
        if self.dataset_type != "regression":
            raise ValueError(
                "NLL Regression Evaluator is only for regression dataset types."
            )

    def evaluate(
        self,
        test_data: MoleculeDataset,
        preds: List[List[float]],
        uncertainties: List[List[float]],
    ):
        if self.calibrator is None:  # uncalibrated regression uncertainties are variances
            uncertainties = np.array(uncertainties)
            preds = np.array(preds)
            targets = np.array(test_data.targets)
            nll = np.log(2 * np.pi * uncertainties) / 2 \
                + (preds - targets) ** 2 / (2 * uncertainties)
            return np.sum(nll, axis=0).tolist()
        else:
            nll = self.calibrator.nll(
                preds=preds, unc=uncertainties, targets=test_data.targets()
            )  # shape(data, task)
            return np.sum(nll, axis=0).tolist()


class NLLClassEvaluator(UncertaintyEvaluator):
    """"""

    def __init__(
        self,
        evaluation_method: str,
        calibration_method: str,
        uncertainty_method: str,
        dataset_type: str,
        loss_function: str,
        calibrator: UncertaintyCalibrator,
    ):
        super().__init__(
            evaluation_method=evaluation_method,
            calibration_method=calibration_method,
            uncertainty_method=uncertainty_method,
            dataset_type=dataset_type,
            loss_function=loss_function,
            calibrator=calibrator,
        )

    def raise_argument_errors(self):
        super().raise_argument_errors()
        if self.dataset_type != "classification":
            raise ValueError(
                "NLL Classification Evaluator is only for classification dataset types."
            )

    def evaluate(
        self,
        test_data: MoleculeDataset,
        preds: List[List[float]],
        uncertainties: List[List[float]],
    ):
        targets = np.array(test_data.targets())
        uncertainties = np.array(uncertainties)
        likelihood = uncertainties * targets + (1 - uncertainties) * (1 - targets)
        nll = -1 * np.log(likelihood)
        return np.sum(nll, axis=0).tolist()


class NLLMultiEvaluator(UncertaintyEvaluator):
    """"""

    def __init__(
        self,
        evaluation_method: str,
        calibration_method: str,
        uncertainty_method: str,
        dataset_type: str,
        loss_function: str,
        calibrator: UncertaintyCalibrator,
    ):
        super().__init__(
            evaluation_method=evaluation_method,
            calibration_method=calibration_method,
            uncertainty_method=uncertainty_method,
            dataset_type=dataset_type,
            loss_function=loss_function,
            calibrator=calibrator,
        )

    def raise_argument_errors(self):
        super().raise_argument_errors()
        if self.dataset_type != "multiclass":
            raise ValueError(
                "NLL Multiclass Evaluator is only for multiclass dataset types."
            )

    def evaluate(
        self,
        test_data: MoleculeDataset,
        preds: List[List[float]],
        uncertainties: List[List[float]],
    ):
        targets = np.array(test_data.targets(), dtype="int")  # shape(data, tasks)
        uncertainties = np.array(uncertainties)
        preds = np.array(preds)
        nll = np.zeros_like(targets)
        for i in range(targets.shape[1]):
            task_preds = uncertainties[:, i]
            task_targets = targets[:, i]  # shape(data)
            bin_targets = np.zeros_like(preds[:, 0, :])  # shape(data, classes)
            bin_targets[np.arange(targets.shape[0]), task_targets] = 1
            task_likelihood = np.sum(bin_targets * task_preds, axis=1)
            task_nll = -1 * np.log(task_likelihood)
            nll[:, i] = task_nll
        return np.sum(nll, axis=0).tolist()


class CalibrationAreaEvaluator(UncertaintyEvaluator):
    """"""

    def __init__(
        self,
        evaluation_method: str,
        calibration_method: str,
        uncertainty_method: str,
        dataset_type: str,
        loss_function: str,
        calibrator: UncertaintyCalibrator,
    ):
        super().__init__(
            evaluation_method=evaluation_method,
            calibration_method=calibration_method,
            uncertainty_method=uncertainty_method,
            dataset_type=dataset_type,
            loss_function=loss_function,
            calibrator=calibrator,
        )

    def raise_argument_errors(self):
        super().raise_argument_errors()
        if self.dataset_type != "regression":
            raise NotImplementedError(
                f"Miscalibration area is only implemented for regression dataset types."
            )

    def evaluate(
        self,
        test_data: MoleculeDataset,
        preds: List[List[float]],
        uncertainties: List[List[float]],
    ):
        targets = np.array(test_data.targets())  # shape(data, tasks)
        uncertainties = np.array(uncertainties)
        preds = np.array(preds)
        abs_error = np.abs(preds - targets)  # shape(data, tasks)

        fractions = np.zeros([preds.shape[1], 101])  # shape(tasks, 101)
        fractions[:, 100] = 1

        if self.calibrator is not None:
            # using 101 bin edges, hardcoded
            original_metric = self.calibrator.regression_calibrator_metric
            original_scaling = self.calibrator.scaling
            original_interval = self.calibrator.interval_percentile

            for i in range(1, 100):
                self.calibrator.regression_calibrator_metric = "interval"
                self.calibrator.interval_percentile = i
                self.calibrator.calibrate()
                bin_scaling = self.calibrator.scaling
                bin_unc = (
                    uncertainties
                    / np.expand_dims(original_scaling, axis=0)
                    * np.expand_dims(bin_scaling, axis=0)
                )  # shape(data, tasks)
                bin_fraction = np.sum(bin_unc >= abs_error, axis=0)
                fractions[:, i] = bin_fraction

            self.calibrator.regression_calibrator_metric = original_metric
            self.calibrator.scaling = original_scaling
            self.calibrator.interval_percentile = original_interval

        else:  # uncertainties are uncalibrated variances
            std = np.sqrt(uncertainties)
            for i in range(1, 100):
                bin_scaling = erfinv(i / 100) * np.sqrt(2)
                bin_unc = std * bin_scaling
                bin_fraction = np.mean(bin_unc >= abs_error, axis=0)
                fractions[:, i] = bin_fraction
        # trapezoid rule
        auce = np.sum(
            0.01 * np.abs(fractions - np.expand_dims(np.arange(101) / 100, axis=0)),
            axis=1,
        )
        return auce.tolist()


class ExpectedNormalizedErrorEvaluator(UncertaintyEvaluator):
    """"""

    def __init__(
        self,
        evaluation_method: str,
        calibration_method: str,
        uncertainty_method: str,
        dataset_type: str,
        loss_function: str,
        calibrator: UncertaintyCalibrator,
    ):
        super().__init__(
            evaluation_method=evaluation_method,
            calibration_method=calibration_method,
            uncertainty_method=uncertainty_method,
            dataset_type=dataset_type,
            loss_function=loss_function,
            calibrator=calibrator,
        )

    def raise_argument_errors(self):
        super().raise_argument_errors()
        if self.dataset_type != "regression":
            raise ValueError(
                f"Expected normalized error is only appropriate for regression dataset types."
            )

    def evaluate(
        self,
        test_data: MoleculeDataset,
        preds: List[List[float]],
        uncertainties: List[List[float]],
    ):
        targets = np.array(test_data.targets())  # shape(data, tasks)
        uncertainties = np.array(uncertainties)
        preds = np.array(preds)
        abs_error = np.abs(preds - targets)  # shape(data, tasks)

        sort_record = np.rec.fromarrays([uncertainties, abs_error], names="i, j")
        sort_record.sort(axis=0)
        uncertainties = sort_record["i"]
        abs_error = sort_record["j"]

        # get stdev scaling
        if self.calibrator is not None:
            original_metric = self.calibrator.regression_calibrator_metric
            original_scaling = self.calibrator.scaling

        # 100 bins
        split_unc = np.array_split(
            uncertainties, 100, axis=0
        )  # shape(list100, data, tasks)
        split_error = np.array_split(abs_error, 100, axis=0)

        mean_vars = np.zeros([preds.shape[1], 100])  # shape(tasks, 100)
        rmses = np.zeros_like(mean_vars)

        for i in range(100):
            if self.calibrator is None:  # starts as a variance
                mean_vars[:, i] = np.mean(split_unc[i], axis=0)
                rmses[:, i] = np.sqrt(np.mean(np.square(split_error[i]), axis=0))
            elif self.calibration_method == "tscaling":  # convert back to sample stdev
                bin_unc = split_unc[i] / np.expand_dims(original_scaling, axis=0)
                bin_var = t.var(df=self.calibrator.num_models - 1, scale=bin_unc)
                mean_vars[:, i] = np.mean(bin_var, axis=0)
                rmses[:, i] = np.sqrt(np.mean(np.square(split_error[i]), axis=0))
            else:
                self.calibrator.regression_calibrator_metric = "stdev"
                self.calibrator.calibrate()

                stdev_scaling = self.calibrator.scaling

                self.calibrator.regression_calibrator_metric = original_metric
                self.calibrator.scaling = original_scaling

                bin_unc = split_unc[i]
                bin_unc = (
                    bin_unc
                    / np.expand_dims(original_scaling, axis=0)
                    * np.expand_dims(stdev_scaling, axis=0)
                )  # convert from interval to stdev as needed
                mean_vars[:, i] = np.mean(np.square(bin_unc), axis=0)
                rmses[:, i] = np.sqrt(np.mean(np.square(split_error[i]), axis=0))
        ence = np.mean(np.abs(mean_vars - rmses) / mean_vars, axis=1)
        return ence.tolist()


class SpearmanEvaluator(UncertaintyEvaluator):
    """"""

    def __init__(
        self,
        evaluation_method: str,
        calibration_method: str,
        uncertainty_method: str,
        dataset_type: str,
        loss_function: str,
        calibrator: UncertaintyCalibrator,
    ):
        super().__init__(
            evaluation_method=evaluation_method,
            calibration_method=calibration_method,
            uncertainty_method=uncertainty_method,
            dataset_type=dataset_type,
            loss_function=loss_function,
            calibrator=calibrator,
        )

    def raise_argument_errors(self):
        super().raise_argument_errors()
        if self.dataset_type != "regression":
            raise ValueError(
                f"Spearman rank correlation is only appropriate for regression dataset types."
            )

    def evaluate(
        self,
        test_data: MoleculeDataset,
        preds: List[List[float]],
        uncertainties: List[List[float]],
    ):
        targets = np.array(test_data.targets())  # shape(data, tasks)
        uncertainties = np.array(uncertainties)
        preds = np.array(preds)
        abs_error = np.abs(preds - targets)  # shape(data, tasks)

        num_tasks = targets.shape[1]
        spearman_coeffs = []
        for i in range(num_tasks):
            spmn = spearmanr(uncertainties[:, i], abs_error[:, i]).correlation
            spearman_coeffs.append(spmn)
        return spearman_coeffs


def build_uncertainty_evaluator(
    evaluation_method: str,
    calibration_method: str,
    uncertainty_method: str,
    dataset_type: str,
    loss_function: str,
    calibrator: UncertaintyCalibrator,
):
    """"""
    supported_evaluators = {
        "nll": {
            "regression": NLLRegressionEvaluator,
            "classification": NLLClassEvaluator,
            "multiclass": NLLMultiEvaluator,
            "spectra": None,
        }[dataset_type],
        "miscalibration_area": CalibrationAreaEvaluator,
        "ence": ExpectedNormalizedErrorEvaluator,
        "spearman": SpearmanEvaluator,
    }

    classification_metrics = [
        "auc",
        "prc-auc",
        "accuracy",
        "binary_cross_entropy",
        "f1",
        "mcc",
    ]
    multiclass_metrics = [
        "cross_entropy",
        "accuracy",
        "f1",
        "mcc"
    ]
    if dataset_type == "classification" and evaluation_method in classification_metrics:
        evaluator_class = MetricEvaluator
    elif dataset_type == "multiclass" and evaluation_method in multiclass_metrics:
        evaluator_class = MetricEvaluator
    else:
        evaluator_class = supported_evaluators.get(evaluation_method, None)

    if evaluator_class is None:
        raise NotImplementedError(
            f"Evaluator type {evaluation_method} is not supported. Avalable options are all calibration/multiclass metrics and {list(supported_evaluators.keys())}"
        )
    else:
        evaluator = evaluator_class(
            evaluation_method=evaluation_method,
            calibration_method=calibration_method,
            uncertainty_method=uncertainty_method,
            dataset_type=dataset_type,
            loss_function=loss_function,
            calibrator=calibrator,
        )
        return evaluator
