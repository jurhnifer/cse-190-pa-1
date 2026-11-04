import pandas as pd
from starter_3_4.part3.load_data import load_users, load_labels, ATTRIBUTES
from sklearn.linear_model import LogisticRegression
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import f1_score

# has ground truth
# Supervised learning model -> logistic regression (categoric)
# Use multinomial logistic regression; more than 2 choices (not 0 and 1)

# Load data and join the data based on the client id
train_df = pd.merge(load_users("train"), load_labels("train"), on="client_id")
dev_df = pd.merge(load_users("dev"), load_labels("dev"), on="client_id")

# Data cleaning

# Prep for TF-IDF
def combine(searches):
        total_queries = []
        for q in searches:
                total_queries.append(q["query"])

        return " ".join(total_queries)

# Don't need any other attribute under .json (lowk useless), we care more about the searches
# Searches attribute; query only to run TF-IDF to vectorize query texts
train_df["search"] = train_df["searches"].apply(combine)
dev_df["search"] = dev_df["searches"].apply(combine)

# Run TF-IDF on train and dev
tfidf = TfidfVectorizer()
X_train = tfidf.fit_transform(train_df["search"])
X_dev = tfidf.transform(dev_df["search"])

dev_pred_accuracy = {}
models = {}

# Logistic regression for classification; do for each attribute first
for attribute in ATTRIBUTES:
        model = LogisticRegression(class_weight='balanced', max_iter=10000)
        # Train on the training data
        model.fit(X_train, train_df[attribute])
        models[attribute] = model
        # Create predictions on dev data
        dev_prediction = model.predict(X_dev)
        # Use f1_score
        attribute_score = f1_score(dev_df[attribute], dev_prediction, average='macro')
        dev_pred_accuracy[attribute] = attribute_score


# Create output on predictions.csv
# For every user (row), have a prediction for each attribute (column)

# Load the users
test_df = load_users("test")
                        
# Run TFIIDF on test searches/queries; needs to match the clean train data
test_df["search"] = test_df["searches"].apply(combine)
X_test = tfidf.transform(test_df["search"])

# Create a table with just the client_ids
test_table = pd.DataFrame({"client_id": test_df["client_id"]})

# Loop over the ATTRIBUTES
for attribute in ATTRIBUTES:
        model = LogisticRegression(class_weight='balanced', max_iter=10000)
        model.fit(X_train, train_df[attribute])
        # Predict on test data
        test_prediction = model.predict(X_test)
        # Populate column with predictions on the corresponding attribute
        test_table[attribute] = test_prediction


# Create to csv
test_table.to_csv('predictions.csv', index=False)

# Run model on client_id
def get_attribute_table(client_id, searches):
        # Create table
        client_attribute_table = pd.DataFrame({'client_id': [client_id]})
        # Combine searches & run TFIDF
        search = " ".join(searches)
        X_test = tfidf.transform([search])
        # Loop over attributes:
        for attribute in ATTRIBUTES:
                attr_model = models[attribute]
                # Predict on test search
                test_prediction = attr_model.predict(X_test)[0]
                # Get the confidence threshold
                probability = attr_model.predict_proba(X_test)[0].max()
                print(probability)
                print(attribute)             
                # Populate column with predictions on the corresponding attribute
                if probability > 0.75:
                        client_attribute_table[attribute] = test_prediction
                else:
                        client_attribute_table[attribute] = "None"
        return client_attribute_table
        
        
