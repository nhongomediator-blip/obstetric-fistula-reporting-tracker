"""
================================================================================
STEP 11: REGRESSION ANALYSIS (POISSON, THEN NEGATIVE BINOMIAL IF NEEDED)
================================================================================

Tests how poverty, literacy and distance to the nearest health facility
are associated with the number of cases reported by a district, and
calculates a residual for each district-year.

Model (31 district-years with records):

    log(E[reported cases]) = log(expected cases) + b0
                             + b1 x poverty + b2 x literacy
                             + b3 x distance

  - Poisson regression is fitted first because the outcome is a count.
  - The log of expected cases is an offset, so the model describes
    reported cases relative to expected cases and not simply that larger
    districts report more.
  - Overdispersion is checked with the Pearson chi-square divided by the
    residual degrees of freedom (the deviance divided by the residual
    degrees of freedom is printed as well). A value well above 1 means
    the Poisson standard errors are too small, so a Negative Binomial
    model (which estimates the extra variation) is fitted and becomes
    the model that is reported.
  - Exponentiated coefficients are reported as rate ratios with 95%
    confidence intervals.

Residual = reported cases - model-predicted cases.
The predicted cases INCLUDE the offset: predicted cases = expected cases
x exp(b0 + b1 x poverty + b2 x literacy + b3 x distance). A positive
residual means the district reported more cases than the model predicts
from poverty, literacy and distance, and a negative residual means
fewer. The mean residual per district shows how well these three
factors account for its reporting. A large residual of either sign shows
that something else is operating; it does not say what.

Important limits (state them in the write-up):
  - Poverty, literacy and distance take only seven different values
    (one per district), so the 31 district-years are not 31 independent
    pieces of evidence about these three factors. Treat the associations
    as exploratory.
  - Cluster-robust standard errors are not used because seven clusters
    are too few for them to be reliable.

Input:  panel_with_population_births.csv (Step 3)
        facility_access_metrics.csv (Step 5)
        panel_with_poverty_literacy.csv (Step 6)
        manicaland_case_data.xlsx, sheet "Yearly Counts" (Step 7)
Output: regression_results.csv (rate ratios, one row per predictor per
        model; the "model" column says Poisson or Negative Binomial)
        regression_residuals.csv (one row per district-year, using the
        reported model)

Usage:
    python step11_regression_analysis.py
================================================================================
"""

from environment_setup import fix_proj_database
fix_proj_database()

import pandas as pd
import numpy as np
import statsmodels.api as sm
import statsmodels.formula.api as smf

# ------------------------------------------------------------------------------
# SETTINGS
# ------------------------------------------------------------------------------

BASE = r"C:\Users\nhong\OneDrive\Desktop\DISSERTATION FOR SUBMISSION FINALEST\CHAPTER 3 METHODOLOGY"
POPULATION_BIRTHS_FILE = BASE + r"\panel_with_population_births.csv"
FACILITY_ACCESS_FILE = BASE + r"\facility_access_metrics.csv"
POVERTY_LITERACY_FILE = BASE + r"\panel_with_poverty_literacy.csv"
CASE_DATA_FILE = BASE + r"\manicaland_case_data.xlsx"

COEFFICIENTS_OUTPUT_FILE = BASE + r"\regression_results.csv"
RESIDUALS_OUTPUT_FILE = BASE + r"\regression_residuals.csv"

POINT_PREVALENCE = 1.0 / 1000  # per Maheu-Giroux et al. (2015), matching Step 8
FORMULA = "reported_cases ~ poverty_rate + literacy_rate + distance_to_facility_km"
OVERDISPERSION_LIMIT = 1.5  # Pearson chi-square / residual df above this = overdispersed


def build_analysis_dataset():
    """
    Assembles the district-year dataset needed for the regression: real
    reported cases (Step 7), joined with each district-year's prevalence-
    based expected cases, poverty rate, literacy rate, and facility
    distance.

    Only district-years with real reported case data are included,
    consistent with the missing-versus-zero distinction used throughout
    this study.

    Returns:
        pandas.DataFrame: One row per district-year with real data,
            containing all variables needed for the regression.
    """
    population_births = pd.read_csv(POPULATION_BIRTHS_FILE)
    facility_access = pd.read_csv(FACILITY_ACCESS_FILE)
    poverty_literacy = pd.read_csv(POVERTY_LITERACY_FILE)
    yearly_reported = pd.read_excel(CASE_DATA_FILE, sheet_name="Yearly Counts")

    data = yearly_reported.merge(
        population_births[["district", "year", "adult_female_population_18plus"]],
        on=["district", "year"], how="left"
    )
    data["expected_cases"] = data["adult_female_population_18plus"] * POINT_PREVALENCE

    # Facility distance and poverty/literacy are constant per district
    # (not year-varying), so a plain district-level merge is used.
    distance_lookup = facility_access[["district", "distance_to_facility_km"]].drop_duplicates("district")
    data = data.merge(distance_lookup, on="district", how="left")

    covariate_lookup = poverty_literacy[["district", "poverty_rate", "literacy_rate"]].drop_duplicates("district")
    data = data.merge(covariate_lookup, on="district", how="left")

    data["log_expected_cases"] = np.log(data["expected_cases"])
    return data


def fit_poisson_model(data):
    """
    Fits the Poisson regression model: reported cases as a function of
    poverty rate, literacy rate, and facility distance, with log expected
    cases as an offset.

    Args:
        data (pandas.DataFrame): Output of build_analysis_dataset().

    Returns:
        statsmodels regression results object.
    """
    model = smf.glm(
        formula=FORMULA,
        data=data,
        family=sm.families.Poisson(),
        offset=data["log_expected_cases"]
    ).fit()
    return model


def fit_negative_binomial_model(data):
    """
    Fits the Negative Binomial regression (NB2) with the same predictors
    and the same log expected cases offset. It estimates an extra
    dispersion parameter (alpha) that allows the variation in reported
    cases to be larger than the Poisson model assumes, which gives more
    honest standard errors when the data are overdispersed.

    Args:
        data (pandas.DataFrame): Output of build_analysis_dataset().

    Returns:
        statsmodels regression results object.
    """
    model = smf.negativebinomial(FORMULA, data=data, offset=data["log_expected_cases"])
    result = model.fit(disp=False, maxiter=500)
    if not result.mle_retvals.get("converged", True):
        result = model.fit(disp=False, maxiter=5000, method="bfgs")
    if not result.mle_retvals.get("converged", True):
        print("  WARNING: the Negative Binomial model did not fully converge. "
              "Treat its results with caution.")
    return result


def summarise_rate_ratios(model, confidence_level=0.95):
    """
    Converts the model's log-scale coefficients into interpretable Rate
    Ratios with confidence intervals and p-values.

    Args:
        model: Fitted statsmodels result (Poisson GLM or Negative Binomial).
        confidence_level (float): e.g. 0.95.

    Returns:
        pandas.DataFrame: One row per predictor, with Rate Ratio, 95% CI,
            and p-value. The intercept and the dispersion parameter
            (alpha) are not predictors and are left out.
    """
    conf_int = model.conf_int(alpha=1 - confidence_level)
    summary = pd.DataFrame({
        "predictor": model.params.index,
        "coefficient": model.params.values,
        "rate_ratio": np.exp(model.params.values),
        "rate_ratio_95CI_lower": np.exp(conf_int[0].values),
        "rate_ratio_95CI_upper": np.exp(conf_int[1].values),
        "p_value": model.pvalues.values,
    })
    summary["statistically_significant"] = summary["p_value"] < (1 - confidence_level)
    return summary[~summary["predictor"].isin(["Intercept", "alpha"])]


def predicted_cases(model, data):
    """
    Predicted number of reported cases for every district-year,
    INCLUDING the offset:

        predicted cases = expected cases x exp(b0 + b1 x poverty
                          + b2 x literacy + b3 x distance)

    Why this is written out in full: model.predict(data) in statsmodels
    leaves the offset out, which returns the predicted RATE (about 0.1)
    and not the predicted COUNT. Residuals worked out from that rate are
    almost the same as the reported cases themselves and are wrong.

    Args:
        model: Fitted statsmodels result (Poisson GLM or Negative Binomial).
        data (pandas.DataFrame): The analysis dataset (same rows, same
            order, as used to fit the model).

    Returns:
        numpy.ndarray: Predicted cases, one per row of data.
    """
    exog = np.asarray(model.model.exog)
    if len(exog) != len(data):
        raise ValueError("Rows used to fit the model differ from the dataset; "
                         "check for missing values in the covariates.")
    coefficients = np.asarray(model.params)[:exog.shape[1]]  # drops alpha for Negative Binomial
    return np.exp(exog @ coefficients + data["log_expected_cases"].values)


def calculate_residuals(data, model, check_sum_to_zero=False):
    """
    Calculates the residual for every district-year:
    reported cases minus the model's predicted cases (offset included).

    Args:
        data (pandas.DataFrame): The analysis dataset.
        model: Fitted statsmodels result.
        check_sum_to_zero (bool): For the Poisson model with an intercept,
            the residuals must add up to zero. If they do not, the
            predictions are wrong, and the script stops.

    Returns:
        pandas.DataFrame: The input data with "predicted_cases" and
            "residual" columns added.
    """
    data = data.copy()
    data["predicted_cases"] = predicted_cases(model, data)
    data["residual"] = data["reported_cases"] - data["predicted_cases"]
    if check_sum_to_zero and abs(data["residual"].sum()) > 1e-3:
        raise ValueError(
            f"Residuals should add up to zero for a Poisson model but add up to "
            f"{data['residual'].sum():.3f}. The predicted cases are not including the offset."
        )
    return data


def main():
    """
    Runs the full Step 11 pipeline: assembles the regression dataset,
    fits the Poisson model, checks overdispersion, fits a Negative
    Binomial model if the Poisson model is overdispersed, summarises Rate
    Ratios, calculates residuals per district-year from the reported
    model, and saves both outputs.
    """
    print("Assembling regression dataset from Steps 3, 5, 6, and 7...")
    data = build_analysis_dataset()
    print(f"Assembled {len(data)} district-year observations with real data.")

    print("\nFitting Poisson regression model...")
    poisson = fit_poisson_model(data)
    print(poisson.summary())

    pearson_ratio = poisson.pearson_chi2 / poisson.df_resid
    deviance_ratio = poisson.deviance / poisson.df_resid
    print(f"\nOverdispersion check (Pearson chi-square / residual df): {pearson_ratio:.2f}")
    print(f"Overdispersion check (deviance / residual df):           {deviance_ratio:.2f}")
    overdispersed = pearson_ratio > OVERDISPERSION_LIMIT

    poisson_ratios = summarise_rate_ratios(poisson)
    poisson_ratios.insert(0, "model", "Poisson")

    if overdispersed:
        print("  The value is well above 1: the Poisson standard errors are too small.")
        print("  Fitting a Negative Binomial model, which is the model that will be reported.")
        final_model = fit_negative_binomial_model(data)
        print(final_model.summary())
        alpha = final_model.params["alpha"]
        print(f"\nNegative Binomial dispersion parameter alpha = {alpha:.3f} "
              f"(p = {final_model.pvalues['alpha']:.4f}); alpha above 0 confirms the extra variation.")
        final_ratios = summarise_rate_ratios(final_model)
        final_ratios.insert(0, "model", "Negative Binomial")
        model_name = "Negative Binomial"
    else:
        print("  The value is close to 1: no strong evidence of overdispersion.")
        final_model = poisson
        final_ratios = poisson_ratios
        model_name = "Poisson"

    print(f"\nRate Ratios, {model_name} model (predictor effects on reporting, relative to expected):")
    print(final_ratios.drop(columns="model").to_string(index=False))
    if overdispersed:
        print("\nFor comparison, Poisson Rate Ratios (standard errors too small; do not report as the result):")
        print(poisson_ratios.drop(columns="model").to_string(index=False))

    # Self-check on the Poisson predictions (residuals must add to zero)
    calculate_residuals(data, poisson, check_sum_to_zero=True)
    residuals = calculate_residuals(data, final_model)
    residuals.insert(0, "model", model_name)

    district_residuals = residuals.groupby("district").agg(
        mean_reported=("reported_cases", "mean"),
        mean_predicted=("predicted_cases", "mean"),
        mean_residual=("residual", "mean"),
    ).reset_index().sort_values("mean_residual")
    print(f"\nMean residual per district, {model_name} model (reported minus predicted cases;")
    print("the larger the absolute value, the less the district's reporting is explained by the model):")
    print(district_residuals.round(2).to_string(index=False))

    print("\nNote: poverty, literacy and distance take only 7 different values (one per")
    print("district), so these associations are exploratory and should not be over-read.")

    pd.concat([final_ratios, poisson_ratios]).drop_duplicates(
        subset=["model", "predictor"]).to_csv(COEFFICIENTS_OUTPUT_FILE, index=False)
    residuals.to_csv(RESIDUALS_OUTPUT_FILE, index=False)
    print(f"\nSaved model results to: {COEFFICIENTS_OUTPUT_FILE}")
    print(f"Saved residuals to: {RESIDUALS_OUTPUT_FILE}")


if __name__ == "__main__":
    main()
