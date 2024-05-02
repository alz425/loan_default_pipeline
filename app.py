# I'm putting all code we've seen before here

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
# from df_after_transform import df_after_transform
from sklearn import set_config
from sklearn.calibration import CalibrationDisplay
from sklearn.compose import (
    ColumnTransformer,
    make_column_selector,
    make_column_transformer,
)
from sklearn.decomposition import PCA
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor, VotingRegressor
from sklearn.feature_selection import (
    RFECV,
    SelectFromModel,
    SelectKBest,
    SequentialFeatureSelector,
    f_classif,
)
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Lasso, LassoCV, LogisticRegression, Ridge, RidgeCV
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    DetCurveDisplay,
    PrecisionRecallDisplay,
    RocCurveDisplay,
    classification_report,
    make_scorer,
)
from sklearn.model_selection import (
    GridSearchCV,
    KFold,
    cross_validate,
    train_test_split,
    cross_val_score,
)
from sklearn.pipeline import Pipeline, make_pipeline
from sklearn.preprocessing import (
    OneHotEncoder,
    OrdinalEncoder,
    PolynomialFeatures,
    StandardScaler,
    MinMaxScaler,
    MaxAbsScaler,
    KBinsDiscretizer,
)
from sklearn.svm import LinearSVC
import streamlit as st
from sklearn.decomposition import TruncatedSVD
from sklearn.metrics import confusion_matrix, mean_squared_error, r2_score
import seaborn as sns
from sklearn.experimental import enable_hist_gradient_boosting
from scipy.sparse import csr_matrix


################################ formatting (not totally sure what all of this does) #############################

set_config(display="diagram")  # display='text' is the default

# Page config
st.set_page_config(
    "Machine Learning to Create Custom Predictions for Loan Defaults",
    "📈",
    initial_sidebar_state="expanded",
    layout="wide",
)

pd.set_option(
    "display.max_colwidth", 1000, "display.max_rows", 50, "display.max_columns", None
)

################################################ sidebar ############################################# 
with st.sidebar:
    if 'current_section' not in st.session_state:
        st.session_state['current_section'] = 'Overview'

    with st.sidebar:
        st.write("# Menu:")

        menu_options = {
            "Overview, Objectives, Process, and Results": "Overview",
            "Custom Machine Learning Model Builder": "Custom Model Builder",
            "Leaderboard": "Leaderboard",
            "Dictionary": "Dictionary"
        }

        # Use buttons with space padding for alignment
        max_length = max(len(option) for option in menu_options.keys())
        for text, section in menu_options.items():
            padded_text = text.ljust(max_length)  # Padding text to make uniform
            if st.button(padded_text):
                st.session_state['current_section'] = section

############################################# load data, scoring, features ################################################

# load data

loans = pd.read_csv("inputs/final_2013_subsample.csv")

# drop some bad columns here, or in the pipeline

# loans = loans.drop(
#     ["member_id", "id", "desc", "earliest_cr_line", "emp_title", "issue_d"], axis=1
# )

# create holdout sample

y = loans.loan_status == "Charged Off"
y.value_counts()
loans = loans.drop("loan_status", axis=1)

X_train, X_test, y_train, y_test = train_test_split(
    loans, y, stratify=y, test_size=0.2, random_state=0
)  # (stratify will make sure that test/train both have equal fractions of outcome)

# define the profit function


def custom_prof_score(y, y_pred, roa=0.02, haircut=0.20):
    """
    Firm profit is this times the average loan size. We can
    ignore that term for the purposes of maximization. 
    """
    TN = sum((y_pred == 0) & (y == 0))  # count loans made and actually paid back
    FN = sum((y_pred == 0) & (y == 1))  # count loans made and actually defaulting
    return TN * roa - FN * haircut


# so that we can use the fcn in sklearn, "make a scorer" out of that function

prof_score = make_scorer(custom_prof_score)

# list of all num vars:
num_pipe_features = X_train.select_dtypes(include="float64").columns

# List of all categorical variables
cat_pipe_features = X_train.select_dtypes(include='object').columns  # all: X_train.select_dtypes(include='object').columns


################################################## custom model code #################################################

# Function to create a pipeline based on user-selected model and features
def create_pipeline(model_name, feature_select, feature_create, num_pipe_features, cat_pipe_features, degree = None, param_range = None):
    if model_name == 'Logistic Regression':
        clf = LogisticRegression(class_weight='balanced', penalty='l2')
    elif model_name == 'HistGradientBoostingRegressor':
        if param_range is not None:
            learning_rate_min, learning_rate_max = param_range
            learning_rates = np.linspace(learning_rate_min, learning_rate_max, num=10)  # Adjust num as needed
            clfs = [(str(lr), HistGradientBoostingRegressor(learning_rate=lr)) for lr in learning_rates]
            clf = VotingRegressor(clfs)
        else:
            clf = HistGradientBoostingRegressor()
    elif model_name == 'Lasso':
        if param_range is not None:
            alpha_min, alpha_max, alpha_points = param_range
            alphas = np.linspace(alpha_min, alpha_max, alpha_points)
            clf = LassoCV(alphas=alphas)
        else:
            clf = Lasso(alpha=0.3)
    elif model_name == 'Ridge':
        if param_range is not None:
            alpha_min, alpha_max, alpha_points = param_range
            alphas = np.linspace(alpha_min, alpha_max, alpha_points)
            clf = RidgeCV(alphas=alphas)
        else:
            clf = Ridge()
    elif model_name == 'Linear SVC':
        clf = LinearSVC(class_weight='balanced', penalty='l2')
    # Preprocessing pipelines for numerical and categorical features
    numer_pipe = make_pipeline(SimpleImputer(strategy="mean"), StandardScaler())

    cat_pipe = make_pipeline(OneHotEncoder())
    
    # Preprocessing pipeline for the entire dataset
    # didn't use make_column_transformer; wanted to name steps
    preproc_pipe = make_column_transformer(
    (numer_pipe, num_pipe_features), 
    (cat_pipe, cat_pipe_features), 
    remainder="drop",
    )

# Define the feature selection transformer based on the selected method
    if feature_select == 'passthrough':
        feature_selector = 'passthrough'
    elif feature_select.startswith('PCA'):
        n_components = int(feature_select.split('(')[1].split(')')[0])
        feature_selector = TruncatedSVD(n_components=n_components)
    elif feature_select.startswith('SelectKBest'):
        k = st.number_input("Enter the number of features for SelectKBest", min_value=1, max_value=len(X_train.columns), value=5)
        feature_selector = SelectKBest(k=k)
    elif feature_select.startswith('SelectFromModel'):
        if 'LassoCV' in feature_select:
            model = LassoCV()
        elif 'LinearSVC' in feature_select:
            class_weight = st.selectbox("Select class weight for LinearSVC", ['balanced', None])
            model = LinearSVC(penalty="l1", dual=False, class_weight=class_weight)
        threshold = st.number_input("Enter the threshold for SelectFromModel", min_value=0.0, max_value=1.0, value=0.5)
        feature_selector = SelectFromModel(model, threshold=threshold)
    elif feature_select.startswith('RFECV'):
        model = None
        cv_index = feature_select.find('cv=')
        if cv_index != -1:  # If 'cv=' is found in the string
            cv_value = int(feature_select[cv_index:].split(',')[0].split('=')[1])
        else:
            cv_value = st.number_input("Enter the number of folds for RFECV", min_value=2, max_value=10, value=2)
    
        if 'LogisticRegression' in feature_select:
            class_weight = st.selectbox("Select class weight for LogisticRegression", ['balanced', None])
            model = LogisticRegression(class_weight=class_weight)
    
        feature_selector = RFECV(model, cv=cv_value, scoring=prof_score)
    elif feature_select.startswith('SequentialFeatureSelector'):
        model = None
        if 'LogisticRegression' in feature_select:
            class_weight = st.selectbox("Select class weight for LogisticRegression", ['balanced', None])
            model = LogisticRegression(class_weight=class_weight)
        scoring = prof_score
        n_features_to_select = st.number_input("Enter the number of features to select for SequentialFeatureSelector", min_value=1, max_value=len(X_train.columns), value=5)
        cv = st.number_input("Enter the number of folds for SequentialFeatureSelector", min_value=2, max_value=10, value=2)
        feature_selector = SequentialFeatureSelector(model, scoring=scoring, n_features_to_select=n_features_to_select, cv=cv)
    else:
        st.error("Invalid feature selection method!")
        return None

    # Define the feature creation transformer based on the selected method
    if feature_create == 'passthrough':
        feature_creator = 'passthrough'
    elif feature_create.startswith('PolynomialFeatures'):
        interaction_only = 'interaction_only' in feature_create
        feature_creator = PolynomialFeatures(degree=degree, interaction_only=interaction_only)
    elif feature_create == 'MinMaxScaler':
        feature_creator = MinMaxScaler()
    elif feature_create == 'MaxAbsScaler':
        feature_creator = MaxAbsScaler()
        
    # I used "Pipeline" not "make_pipeline" bc I wanted to name the steps
    pipe = Pipeline([('columntransformer',preproc_pipe),
                 ('feature_create', feature_creator), 
                 ('feature_select', feature_selector), 
                 ('clf', clf)
                ])

    return pipe

################################################### Overview ########################################################

if st.session_state['current_section'] == 'Overview':
    st.title("Overview")
    st.header("Overview, Objectives, Process, and Results")
    st.write("This tab will include an overview of our project proposal, the objectives of our project, the process we went through to build out this dashboard, and the results/takeaways")

################################################### custom model builder ########################################################

elif st.session_state['current_section'] == 'Custom Model Builder':

    # begin : user choices
    st.title("Choose Model, Feature Selection Method, Feature Creation Method, Features, and Display Pipeline")
    # num_pipe_features =  .... st.menu(list of choices or something);
    
    # Checkbox to select numerical features
    selected_num_features = st.multiselect("Select Numerical Features:", num_pipe_features)
    
    # Checkbox to select categorical features
    selected_cat_features = st.multiselect("Select Categorical Features:", cat_pipe_features)
        
    # Dropdown menu to choose the model
    model_name = st.selectbox("Choose Model:", ['Logistic Regression', 'HistGradientBoostingRegressor', 'Lasso', 'Ridge', 'Linear SVC'])
    st.write("Selected Model:", model_name)

    # Select hyperparameter range for Lasso, Ridge, Linear SVC, Logistic Regression, and HistGradient models
    param_range = None
    if model_name in ['Lasso', 'Ridge']:
        alpha_min = st.number_input("Enter the minimum alpha", min_value=0.0001, max_value=100.0, value=0.0001, step=0.0001)
        alpha_max = st.number_input("Enter the maximum alpha", min_value=0.0001, max_value=100.0, value=100.0, step=0.0001)
        alpha_points = st.number_input("Enter the number of alpha points", min_value=1, max_value=100, value=25)
        param_range = (alpha_min, alpha_max, alpha_points)
    elif model_name in ['Linear SVC', 'Logistic Regression']:
        C_min = st.number_input("Enter the minimum value for C", min_value=0.0001, max_value=100.0, value=0.0001, step=0.0001)
        C_max = st.number_input("Enter the maximum value for C", min_value=0.0001, max_value=100.0, value=100.0, step=0.0001)
        param_range = [(C_min, C_max)]  # For Linear SVC and Logistic Regression, param_range is a list of tuples
    elif model_name in ['HistGradientBoostingRegressor']:
        learning_rate_min = st.number_input("Enter the minimum value for learning rate", min_value=0.01, max_value=1.0, value=0.1)
        learning_rate_max = st.number_input("Enter the maximum value for learning rate", min_value=0.01, max_value=1.0, value=0.1)
        param_range = (learning_rate_min, learning_rate_max)


    
    # Dropdown menu to choose the feature selection method
    feature_select_method = st.selectbox("Choose Feature Selection Method:", ['passthrough', 'PCA(5)', 'PCA(10)', 'PCA(15)',
                                                                                 'SelectKBest(f_classif)',
                                                                                 'SelectFromModel(LassoCV())', 'SelectFromModel(LinearSVC(penalty="l1", dual=False))',
                                                                                 
                                                                                 'RFECV(LogisticRegression, scoring=prof_score)',
                                                                                 'SequentialFeatureSelector(LogisticRegression, scoring=prof_score)',])
    
    # Dropdown menu to choose the feature creation method
    feature_create_method = st.selectbox("Choose Feature Creation Method:", ['passthrough', 'PolynomialFeatures', 'MinMaxScaler', 'MaxAbsScaler'])
    
    # If PolynomialFeatures is selected, provide an input field to specify the degree
    if feature_create_method == 'PolynomialFeatures':
        degree = st.number_input("Enter the degree for PolynomialFeatures", min_value=1, max_value=5, value=2)
    else:
        degree = None
    
    # Create the pipeline based on the selected model and features
    pipe = create_pipeline(model_name, feature_select_method, feature_create_method, selected_num_features, selected_cat_features, degree, param_range)
    
    # Dropdown menu to choose the cross-validation strategy
    cv = st.number_input("Enter the number of folds for cross-validation", min_value=2, max_value=10, value=5)
    
    # end: user choices
    ##################################################
    
    # User choice outputs
    
    pipe

    # Fit the pipeline with the training data
    pipe.fit(X_train, y_train)
    
    # Get predictions
    y_pred_train = pipe.predict(X_train)

    if model_name in ["Logistic Regression", "Linear SVC"]:
        # Calculate classification report
        report = classification_report(y_train, y_pred_train, output_dict=True)
        
        # Create a formatted classification report string
        classification_report_str = """
        Classification Report (Train Data):
        
        |        | Precision | Recall | F1-Score | Support |
        |--------|-----------|--------|----------|---------|
        | False  |   {:.2f}   |  {:.2f} |   {:.2f}   |   {:<6}  |
        | True   |   {:.2f}   |  {:.2f} |   {:.2f}   |   {:<6}  |
        |--------|-----------|--------|----------|---------|
        | Accuracy |          |        |   {:.2f}  |         |
        """.format(report["False"]["precision"], report["False"]["recall"], report["False"]["f1-score"], report["False"]["support"],
                   report["True"]["precision"], report["True"]["recall"], report["True"]["f1-score"], report["True"]["support"],
                   report["accuracy"])
        
        # Display classification report
        st.markdown(classification_report_str)
        
        # Calculate confusion matrix
        cm = confusion_matrix(y_train, y_pred_train)
        
        # Display confusion matrix
        st.write("Confusion Matrix (Train Data):")
        confusion_matrix_chart = ConfusionMatrixDisplay(cm).plot()
        st.pyplot(confusion_matrix_chart.figure_)
    else:
        # Calculate metrics for Regression model
        mse_train = mean_squared_error(y_train, y_pred_train)
        rmse_train = np.sqrt(mse_train)
        r2_train = r2_score(y_train, y_pred_train)
    
        # Create a formatted regression report string
        regression_report_str = """
        Regression Report (Train Data):
    
        Mean Squared Error: {:.2f}
        Root Mean Squared Error: {:.2f}
        R-squared: {:.2f}
        """.format(mse_train, rmse_train, r2_train)
    
        # Display regression report
        st.markdown(regression_report_str)
        
        def plot_residuals(y_true, y_pred):
            # Calculate residuals
            residuals = y_true - y_pred
            
            # Create residual plot
            plt.figure(figsize=(8, 6))
            sns.residplot(y_pred, residuals, lowess=True, line_kws={'color': 'red', 'lw': 1})
            
            # Set plot labels and title
            plt.title('Residual Plot')
            plt.xlabel('Predicted Values')
            plt.ylabel('Residuals')
            plt.grid(True)
            
            # Show plot
            st.pyplot()

        #Display residual plot
    
        plot_residuals(y_train, y_pred_train)

    
    # Perform cross-validation with custom scoring and additional metrics
    scoring = {'score': prof_score}
    cv_results = cross_validate(pipe, loans, y, cv=cv, scoring=scoring, return_train_score=True)
    
    st.write("Mean Test Score:", cv_results['test_score'].mean())
    st.write("Standard Deviation Test Score:", cv_results['test_score'].std())
    st.write("Standard Deviation Fit Time:", cv_results['fit_time'].std())
    st.write("Mean Score Time:", cv_results['score_time'].mean())
     # why isn't thisprinting in streamlit

################################################### Leaderboard ########################################################

elif st.session_state['current_section'] == 'Leaderboard':
    st.title("Leaderboard")
    st.header("Hopefully this isn't too hard because it will probably be the last thing we do")

################################################### custom model builder ########################################################

elif st.session_state['current_section'] == 'Dictionary':
    st.title("Dictionary")
    st.header("Numerical Features:")
    
    st.subheader("annual_inc")
    st.write('The self-reported annual income provided by the borrower during registration.')

    st.subheader('dti')
    st.write('A ratio calculated using the borrower’s total monthly debt payments on the total debt obligations, excluding mortgage and the requested LC loan, divided by the borrower’s self-reported monthly income.')

    st.subheader('earliest_cr_line')
    st.write('The month the borrowers earliest reported credit line was opened')

    st.subheader('emp_length')
    st.write('Employment length in years. Possible values are between 0 and 10 where 0 means less than one year and 10 means ten or more years. (5962 or 4.4227% missing fields)')

    st.subheader('fico_range_high')
    st.write('The upper boundary range the borrower’s FICO at loan origination belongs to.')

    st.subheader('fico_range_low')
    st.write('The lower boundary range the borrower’s FICO at loan origination belongs to.')

    st.subheader('installment')
    st.write('The monthly payment owed by the borrower if the loan originates.')

    st.subheader('int_rate')
    st.write('Interest Rate on the loan.')

    st.subheader('loan_amnt')
    st.write('')

    st.subheader('mort_acc')
    st.write('')

    st.subheader('')
    st.write('')

    st.subheader('')
    st.write('')

    st.subheader('')
    st.write('')

    st.subheader('')
    st.write('')

    st.subheader('')
    st.write('')

    st.subheader('')
    st.write('')
    
    st.header("Categorical Features:")
    st.header("Model:")


