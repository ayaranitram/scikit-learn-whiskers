from sklearn.base import BaseEstimator, OutlierMixin
from sklearn.utils.validation import check_X_y, check_is_fitted, check_array
import pandas as pd
import numpy as np

__version__ = '0.1.1'


class WhiskerOutliers(OutlierMixin, BaseEstimator):
    """
    Estimator to identify and mark as outliers the values outside the range
    `threshold` * _iqr_ below and above the first and third quartiles of the fitting data.
    By default, values outside the range of 1.5 IQR from the 1st and 3rd quartile are considered outliers.

    Methods:
        fit_predict(X[, y]) : Perform fit on X and returns labels for X.
        Returns -1 for outliers and 1 for inliers, if distinct is False.
        Returns -1 for outliers below minimum, 1 for outliers above maximum and 0 for inliers, if distinct is True.
    """

    def __init__(self, threshold=1.5, mark_nan=True, add_indicator=False, distinct=True):
        """
        Create an instance of WhiskerOutliers
        :param threshold: float
        :param mark_nan: bool
            return the original array with the outliers changed by numpy.nan
        :param add_indicator: bool
            append a flag indicating where the value was an outlier or not.
        :param distinct: bool
            change behaviour of `add_indicator`:
            False: -1 for outliers and 1 for inliers, as indicated by scikit-learn documentation.
            True: -1 for outliers below minimum, 1 for outliers above maximum and 0 for inliers.
        """
        self.threshold = threshold
        self.mark_nan = mark_nan
        self.add_indicator = add_indicator
        self.distinct = distinct

    def fit(self, X, y=None):
        """
        Fit the instance on X.
        :param X: array-like shape of (n_samples, n_features)
        :param y: ignored
        :return: The fitted WhiskerOutliers instance
        """
        if hasattr(self.threshold, '__getitem__'):
            if len(self.threshold) == 1:
                threshold = [self.threshold[0], self.threshold[0]]
            elif len(self.threshold) > 2:
                raise ValueError("`threshold` must be float or array-like with size 2.")
            threshold_min, threshold_max = threshold[0], threshold[1]
        else:
            threshold_min, threshold_max = self.threshold, self.threshold

        if isinstance(X, pd.Series):
            X = X.values.reshape(-1, 1)
        # validate input
        check_array(X)

        # calculate quantiles
        if isinstance(X, (pd.Series, pd.DataFrame)):
            q1 = X.quantile(0.25)
            q3 = X.quantile(0.75)
        else:  # elif isinstance(X, np.ndarray):
            q1 = np.nanquantile(X, q=0.25, axis=0, method='linear')
            q3 = np.nanquantile(X, q=0.75, axis=0, method='linear')

        # calculate iqr
        iqr = abs(q3 - q1)

        # calculate and retain the minimum and maximum limits of valid data
        self.__dict__['min_'] = q1 - (iqr * threshold_min)
        self.__dict__['max_'] = q3 + (iqr * threshold_max)

        return self

    def transform(self, X, y=None):
        """
        Replace the outlier values by numpy.nan using the limits identified by the `fit` method.
        :param X: array-like shape of (n_samples, n_features)
        :param y: ignored
        :return: The dataset where the outliers have been removed.
        """
        # check if instance has been fitted
        check_is_fitted(self, ['min_', 'max_'])

        if isinstance(X, pd.Series):
            X, meta = X.values.reshape(-1, 1), {'index': X.index, 'dtype': X.dtype, 'name': X.name}
        else:
            meta = None

        # validate input
        check_array(X)

        # set identifiers according to distinct parameter
        if self.distinct:
            outlier_low, inlier, outlier_hi  = -1, 0, 1
        else:
            outlier_low, inlier, outlier_hi = -1, 1, -1

        # procedure when the changing the outliers to NaN is required but add_indicator is not required
        if self.mark_nan and not self.add_indicator:
            if isinstance(X, (pd.Series, pd.DataFrame)):
                return X.mask(X < self.min_, np.nan).mask(X > self.max_, np.nan)
            elif meta is not None:
                return pd.Series(
                    np.where(X > self.max_, np.nan, np.where(X < self.min_, np.nan, X)).flatten(),
                    **meta
                )
            else:  # elif isinstance(X, np.ndarray):
                return np.where(X > self.max_, np.nan, np.where(X < self.min_, np.nan, X))

        # procedure when changing the outlier to NaN is required as well as the add_indicator is required
        elif self.mark_nan and self.add_indicator:
            if isinstance(X, pd.DataFrame):
                return (X.mask(X < self.min_, np.nan).mask(X > self.max_, np.nan)) \
                    .merge((pd.DataFrame(data=inlier, columns=X.columns, index=X.index))
                           .mask(X < self.min_, outlier_low).mask(X > self.max_, outlier_hi),
                           how='inner', left_index=True, right_index=True, suffixes=('', '_outlier')
                           )
            elif isinstance(X, pd.Series):
                return (pd.DataFrame(
                    X.mask(X < self.min_, np.nan).mask(X > self.max_, np.nan))) \
                    .merge((pd.DataFrame(data=inlier, columns=[X.name], index=X.index))
                           .mask(X < self.min_, outlier_low).mask(X > self.max_, outlier_hi),
                           how='inner', left_index=True, right_index=True, suffixes=('', '_outlier')
                           )
            elif meta is not None:
                return pd.DataFrame(
                    data={meta['name']: np.where(X > self.max_, np.nan, np.where(X < self.min_, np.nan, X)).flatten(),
                          str(meta['name']) + '_outlier': np.where(X > self.max_, outlier_hi,
                                                                   np.where(X < self.min_, outlier_low, inlier)
                                                                   ).flatten()},
                    index=meta['index']
                )
            else:  # elif isinstance(X, np.ndarray):
                return np.c_[
                    np.where(X > self.max_, np.nan, np.where(X < self.min_, np.nan, X)),
                    np.where(X > self.max_, outlier_hi, np.where(X < self.min_, outlier_low, inlier))
                ]

        # procedure when changing the outlier to NaN is not required but the add_indicator is required
        elif not self.mark_nan and self.add_indicator:
            if isinstance(X, pd.DataFrame):
                return pd.DataFrame(data=inlier, columns=X.columns, index=X.index)\
                    .mask(X < self.min_, outlier_low).mask(X > self.max_, outlier_hi)
            elif isinstance(X, pd.Series):
                return pd.Series(data=inlier, name=X.name, index=X.index)\
                    .mask(X < self.min_, outlier_low).mask(X > self.max_, outlier_hi)
            elif meta is not None:
                return pd.Series(
                    data=np.where(X > self.max_, outlier_hi, np.where(X < self.min_, outlier_low, inlier)).flatten(),
                    name=meta['name'], index=meta['index']
                )
            else:  # elif isinstance(X, np.ndarray):
                return np.where(X > self.max_, outlier_hi, np.where(X < self.min_, outlier_low, inlier))

        # both parameters are False, return the original X
        else:
            if isinstance(X, (pd.Series, pd.DataFrame)):
                return X
            elif meta is not None:
                return pd.Series(data=X, name=meta['name'], index=meta['index'])
            else:
                return X

    def predict(self, X, y=None):
        """
        alias for `transform`
        """
        return self.transform(X=X, y=y)

    def fit_transform(self, X, y=None):
        """
        Fit to data, then transform it.
        :param X: array-like of shape (n_samples, n_features)
        :param y: ignored
        :return: The transformed dataset.
        """
        self.fit(X)
        return self.transform(X)

    def fit_predict(self, X, y=None):
        """
        alias for `fit_transform`
        """
        return self.fit_transform(X=X, y=y)

    def get_params(self, deep=True):
        """
        Returns a dictionary with the parameters used in the instance.
        :param deep: bool, indicates if deep copy is required.
        :return: dict
        """
        return {'threshold': self.threshold,
                'add_indicator': self.add_indicator}
