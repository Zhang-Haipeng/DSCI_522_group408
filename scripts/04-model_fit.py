# Author: Jack Tan
# Contributer: Jarvis Nederlof, Roc Zhang
# Date: 2020-02-05

"""
This script takes processed data from the 'data' folder in the project repostiory
and creates various models to predict the 'playMin' feature using other features.
Types of model produced includes: baseline, linear regression, XGBoost and LGBM.
Afterwards, the scripts test the models and calculates the MSE and coefficient of
determination on test set. Residual plots are created for all models and a feature
importance plot is created for the GBM model. These figures are then saved accordingly.

Both the file name and the save folder are required as inputs.

Usage: 04-model_fit.py --file_name=<file_name> --save_folder=<save_folder>

Options:
--file_name=<file_name>         File name of the processed features and targets
--save_folder=<save_folder>	Folder to save all figures and csv files produced

Example: python scripts/04-model_fit.py --file_name=player_data_ready.csv --save_folder=results
"""

# Loading the required packages
# Models
from xgboost import XGBRegressor
import lightgbm as lgb
from sklearn.linear_model import LinearRegression
# Plotting
import altair as alt
# Numerical Packages
import numpy as np
import pandas as pd
# SKLearn Packages
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
# Binary Model Save
from pickle import dump
from docopt import docopt
# Other Packages
from termcolor import colored
import sys
import os
# Ignore warnings from packages in models
import warnings
warnings.simplefilter("ignore")

opt = docopt(__doc__)

def main(file_name, save_folder):
	# Load the processed data from csv
	# e.g. 'player_data_ready.csv'

	print(colored("\nWARNING: This script takes about 1 minute to run\n", 'yellow'))

	# Validate the file-path to load file
	path_str = str('../data/' + file_name)
	if os.path.exists(path_str) == False:
		path_str = str('data/' + file_name)
	try:
		data = pd.read_csv(path_str)
		print(colored('Data loaded successfully!', 'green'))
	except:
		print(colored('ERROR: Path to file is not valid!', 'red'))
		raise

	# Validate the save_foler directory exists or make folder
	if os.path.exists(save_folder) == False:
		if os.path.exists(str('../' + save_folder)) == False:
			try:
				os.makedirs(save_folder)
				print(colored('Successfully created folder for save data! Test passed!', 'green'))
			except:
				print(colored('ERROR: Path to save directory is not valid!', 'red'))
				raise

	# Preprocess the Data
	X_train, y_train, X_test, y_test = preprocess(data)

	# Fit the models
	lgb = lgbm_model(X_train, y_train, X_test, y_test)
	xgb = xgboost_model(X_train, y_train, X_test, y_test)
	lm = linear_model(X_train, y_train, X_test, y_test)
	base = baseline_model()

	# Get the predictions and score each model
	results = {}
	resid_df_comb = pd.DataFrame()

	for i, model in enumerate([(lgb, 'LGBM'), (xgb, 'XGboost'), (lm, 'Linear Regression'), (base, 'Base Model (5 Game Ave)')]):
		# Get the predictions
		preds = predictions(model[0], X_test)
		# Get the scoring metrics
		results[model[1]] = scoring(preds, y_test)
		# Calculate the model residuals
		resid_df = calc_residuals(preds, y_test, model[1])
		resid_df['model'] = model[1]
		resid_df_comb = pd.concat((resid_df, resid_df_comb), ignore_index=True)

	fig = alt.Chart(resid_df_comb).mark_circle(size=17, clip=True).encode(
			y = alt.Y('Mean Residual', scale=alt.Scale(domain=(-5, 5)), axis=alt.Axis(title='Residuals')),
			x = alt.X('x', scale=alt.Scale(domain=(0, 45)), axis=alt.Axis(title='Minutes')),
			color = alt.Color('model', legend=None)
			).properties(
				width=400,
				height=90
			).facet(facet='model:N', columns=1, spacing=10
			).properties(
				title='Residual Error Plot'
			).configure_title(
				fontSize=18,
				font='Courier',
				anchor='start')

	# Get the model results into a dataframe
	df = pd.DataFrame(data=results, index=['MSE', 'R^2'])

	# Save the results dataframe
	try:
		save_results(df, save_folder)
		print(colored('Saved results to dataframe! Test Passed!', 'green'))
	except:
		print(colored('Could not save results to dataframe!', 'red'))
		raise

	# Save the plotting figure
	try:
		# plot_figure(fig, save_folder)
		fig.save(str(save_folder)+'/modelling-residual_plot.png', scale_factor=1.0)
		print(colored('Saved residual figure! Test Passed!', 'green'))
	except:
		print(colored('Could not save residual figure!', 'red'))
		raise

	# Save the feature importance from LGBM model
	try:
		feature_importance(lgb, X_test, save_folder)
		print(colored('Saved feature importance figure! Test Passed!', 'green'))
	except:
		print(colored('Could not save feature importance figure!', 'red'))
		raise

class baseline_model:
	def predict(self, X):
		predictions = X.loc[:, 'playMin_last5_median']
		return predictions

def preprocess(data):
	"""
	Preprocess the data by dropping certain columns not suitable to train on.
	Split the data into training and testing splits.

	Return a tuple of the training and testing splits.

	Parameters:
	-----------
	data -- (pd DataFrame) The loaded data.
	"""
	# Removing columns that can't be interpretted
	data = data.drop(
		columns=['playDispNm', 'gmDate', 'teamAbbr', 'playPos'])

	# Test that target is in data
	assert 'playMin' in data.columns, 'No targets found!'

	# Splitting data into training and testing
	X, y = data.loc[:, data.columns != 'playMin'], data['playMin']
	X_train, X_test, y_train, y_test = train_test_split(X,
														y,
														random_state=100,
														test_size=0.25)

	assert len(X_train) != len(X_test), 'Improper split of data'
	# print(colored('Successfully split data, test 1 passed!', 'green'))
	return X_train, y_train, X_test, y_test

def lgbm_model(X_train, y_train, X_test, y_test):
	"""
	Initialize and fit the LGBM model.

	Return the fitted model.

	Parameters:
	-----------
	X_train -- (pd DataFrame) The training data
	y_train -- (pd DataFrame) The training target
	X_test -- (pd DataFrame) The testing data
	Y_test -- (pd DataFrame) The testing target
	"""
	print(colored("\nTraining LGBM Model", 'cyan'))
	# LGBM MODEL:
	gbm = lgb.LGBMRegressor(num_leaves=31,
							learning_rate=0.1,
							n_estimators=60)
	gbm.fit(X_train, y_train,
			eval_set=[(X_test, y_test)],
			eval_metric='l2',
			verbose=False)
	assert gbm.best_score_, "LGBM Model didn't fit properly"
	print(colored('Finished Training LGBM Model\n', 'green'))
	return gbm


def xgboost_model(X_train, y_train, X_test, y_test):
	"""
	Initialize and fit the XG Boost model.

	Return the fitted model.

	Parameters:
	-----------
	X_train -- (pd DataFrame) The training data
	y_train -- (pd DataFrame) The training target
	X_test -- (pd DataFrame) The testing data
	Y_test -- (pd DataFrame) The testing target
	"""
	# XGBoost MODEL:
	params = {'n_estimators': 60,
			  'max_depth': 5,
			  'booster': 'gbtree', # gbtree or dart seem best
			  'learning_rate': .1,
			  'gamma': 0,  # default 0 - larger gamma means more conservative model
			  'reg_lambda': 1,  # default 1 - L2 regularization
			  'reg_alpha': 0,  # default 0 - L1 regularization
			  'objective': 'reg:squarederror',
			  'eval_metric': ['rmse'],
			  'verbosity': 0}
	print(colored("Training XGBoost Model", 'cyan'))
	xgb = XGBRegressor(**params).fit(X_train, y_train)
	print(colored('Finished Training XGBoost Model\n', 'green'))
	return xgb

def linear_model(X_train, y_train, X_test, y_test):
	"""
	Initialize and fit the Linear Regression model.

	Return the fitted model.

	Parameters:
	-----------
	X_train -- (pd DataFrame) The training data
	y_train -- (pd DataFrame) The training target
	X_test -- (pd DataFrame) The testing data
	Y_test -- (pd DataFrame) The testing target
	"""
	print(colored("Training Linear Regression Model", 'cyan'))
	# Linear Regression Model
	lr_model = LinearRegression().fit(X=X_train, y=y_train)
	assert len(lr_model.coef_) > 0, 'Linear Regression did not fit properly' 
	print(colored('Finished Training Linear Regression Model\n', 'green'))
	return lr_model

def predictions(model, X_test):
	"""
	Call the predict method on each model.

	Return the model's predictions as an array.

	Parameters:
	-----------
	model -- (model object) the trained model
	X_test -- (pd DataFrame) the testing data
	"""
	try:
		preds = model.predict(X_test)
	except:
		print(colored("Model didn't train properly", 'red'))
		raise
	return preds

def scoring(pred, y_test):
	"""
	Get the mean squared error and the r2 score for each
	model's predictions.

	Return the scoring metrics in a tuple.

	Parameters:
	-----------
	model -- (model object) the trained model
	X_test -- (pd DataFrame) the testing data
	"""
	# Calculating MSE and r2 score for different models
	mse = round(mean_squared_error(y_test, pred), 2)
	r2 = round(r2_score(y_test, pred), 2)
	assert mse > 0, 'Mean squared error should be greater than 0!'
	return mse, r2

def calc_residuals(pred, y_test, model_name):
	"""
	Get the residual error scores for each trained model's predictions.

	Return a dataframe of the model's binned residuals.

	Parameters:
	-----------
	pred -- (list) the model's predictions
	y_test -- (pd DataFrame) the testing targets
	model_name -- (str) the name of the model
	"""
	# Calculating residuals for different models
	assert len(pred) == len(y_test), 'Prediction and test sizes do not match!'
	
	residual = pred - y_test
	if model_name == 'base model':
		df = pd.DataFrame(data={'x': pred, 'y': residual}).groupby(['x']).mean().reset_index()
	else:
		df = pd.DataFrame(data={'x': pred, 'y': residual}).sort_values(by='x')
	preds_df = pd.melt(df,
					   id_vars=['x'],
					   value_vars=['y'],
					   value_name='Mean Residual')

	# Check that the df is not empty
	assert df.empty == False, 'Empty residuals dataframe'

	# Bin the dataframe with a 0.1 bin_size on the actuals
	bins = np.arange(0, np.max(df.loc[:, 'x']), .1)
	preds_binned = preds_df.groupby(pd.cut(preds_df['x'],
									bins,
									labels=False),
									as_index=False).mean()
	return preds_binned

def save_results(df, save_folder):
	"""
	Save the model results metrics into a csv file.

	Parameters:
	-----------
	df -- (pd DataFrame) the models results metrics
	save_folder -- (str) the directory to save the results in
	"""
	assert df.empty == False, 'This should not be true!'
	try:
		df.to_csv(str('../' + save_folder + '/modelling-score_table.csv'))
	except:
		df.to_csv(str(save_folder + '/modelling-score_table.csv'))
	print(colored(f'Saved Model Results in /{save_folder} directory', 'green'))

def feature_importance(gbm, X_test, save_folder):
	"""
	Parameters:
	-----------
	gbm -- (model object) the LGBM model
	X_test -- (pd DataFrame) the testing data
	save_folder -- (str) the directory to save the results in
	"""
	# Feature Importance Plot
	feature_df = pd.DataFrame()
	feature_df['features'] = list(X_test.columns)
	feature_df['importance'] = gbm.feature_importances_
	feature_df.sort_values(by=['importance'], ascending=False, inplace=True)

	# Plot the feature importance
	gbm_features = alt.Chart(feature_df).mark_bar().encode(
		x=alt.X('importance:Q', title='Importance'),
		y=alt.Y('features:N', sort=alt.EncodingSortField(
			field='features', op='count', order='ascending'),
			title='Features'),
	).properties(
		title='Importance of Different Features'
	).configure_title(
			fontSize=18,
			font='Courier',
			anchor='start'
	)
	assert gbm_features != None, 'This should not be true!'
	try:
		gbm_features.save(str('../' + save_folder + '/modelling-gbm_importance.png'), scale_factor=1.0)
	except:
		gbm_features.save(str(save_folder + '/modelling-gbm_importance.png'), scale_factor=1.0)
	print(colored(f'\nSaved Features Importance Plot in /{save_folder} directory', 'green'))

if __name__ == "__main__":
	main(opt["--file_name"], opt["--save_folder"])
